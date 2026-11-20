"""Platform module: the Modal app of the pipeline, with its image, functions and secrets.

This is the only file that imports Modal's SDK, and it does not import the engine; it
calls the shell's ``run`` and nothing else (ADR-0046, Functional core and imperative
shell for the pipeline, rules 1 and 4). The deploy script runs it with the ``platform``
dependency group, which the checks never install.

The image holds the runtime dependencies, Node with the page's ``wrangler``, and the
files the run reads. It is built at deploy time from the repository's pins, so
production runs what CI tested (d008, Runtime and dependencies).
"""

import os
from pathlib import Path

import modal

from bikesharing.shell.run import one_off_config, run, scheduled_config

# The container's hard limit and its reservation, in MiB, which Modal measures in
# binary units. `run` takes it to size DuckDB's memory limit (d008, Run operation on
# Modal).
MEMORY_MIB = 4096

APP_NAME = "bikesharing-pipeline"
CRON = "*/15 * * * *"
TIMEOUT_S = 600

# Where the repository's files sit in the image, as `run` reads them.
REMOTE_ROOT = Path("/repo")

# The `uv` that installs the locked dependencies in the image, pinned like any other
# tool of a build that ends up holding secrets. It is the version `uv.lock` was
# resolved with, and its patch moves with the lockfile.
UV_VERSION = "0.13.5"

# One Modal Secret per credential, so each function attaches only its own (d008,
# Environments and configuration). The keys are the environment variables that
# `scheduled_config` and `one_off_config` read.
BRONZE_READ_SECRET = (
    "bikesharing-pipeline-bronze-read",
    ["BRONZE_R2_ACCESS_KEY_ID", "BRONZE_R2_SECRET_ACCESS_KEY"],
)
LAKEHOUSE_WRITE_SECRET = (
    "bikesharing-pipeline-lakehouse-write",
    ["LAKEHOUSE_R2_ACCESS_KEY_ID", "LAKEHOUSE_R2_SECRET_ACCESS_KEY"],
)
DEPLOY_SECRET = ("bikesharing-pipeline-deploy", ["CLOUDFLARE_API_TOKEN"])
HEARTBEAT_SECRET = ("bikesharing-pipeline-heartbeat", ["HEARTBEAT_URL"])

# Files of a local checkout that must not reach the image: dbt's and Wrangler's
# working folders, installed packages and local credentials.
LOCAL_ONLY = [
    "**/node_modules",
    "**/target",
    "**/logs",
    "**/__pycache__",
    "**/.wrangler",
    "**/.dev.vars",
    "**/.env*",
]

PIPELINE_DIR = Path(__file__).resolve().parent
REPO_DIR = PIPELINE_DIR.parent


def _secret(spec: tuple[str, list[str]]) -> modal.Secret:
    """Reference a Modal Secret by name, requiring the keys the pipeline reads.

    Parameters
    ----------
    spec : tuple[str, list[str]]
        The Secret's name and the environment variables it must hold.

    Returns
    -------
    modal.Secret
        The reference; deploying fails with a message naming the missing key when the
        Secret lacks one of them.
    """
    name, keys = spec
    return modal.Secret.from_name(name, required_keys=keys)


def _node_install_command(version: str) -> str:
    """Build the shell command that installs Node from nodejs.org's official tarball.

    Parameters
    ----------
    version : str
        The exact Node version, as ``web/.nvmrc`` pins it, without a leading ``v``.

    Returns
    -------
    str
        A command that downloads the Linux x64 tarball and the release's
        ``SHASUMS256.txt``, installs the tarball only if its SHA-256 matches, and
        removes both files.
    """
    release = f"https://nodejs.org/dist/v{version}"
    tarball = f"node-v{version}-linux-x64.tar.gz"
    return " && ".join(
        [
            'cd "$(mktemp -d)"',
            f"curl --fail --silent --show-error --location --remote-name {release}/{tarball}",
            f"curl --fail --silent --show-error --location --remote-name {release}/SHASUMS256.txt",
            f'grep " {tarball}$" SHASUMS256.txt | sha256sum --check --strict -',
            f"tar --extract --gzip --file {tarball} --directory /usr/local --strip-components=1 --no-same-owner",
            f"rm {tarball} SHASUMS256.txt",
            "node --version",
        ]
    )


def _build_image() -> modal.Image:
    """Build the pipeline's image from the repository's pins and locked files.

    Layers go from the least to the most often changed, so that a code change
    rebuilds only the last ones. ``npm ci`` needs the page's manifest and lockfile in
    the image before it runs, so those two are copied; everything after the
    dependencies is copied too, which keeps a build self-contained.

    Returns
    -------
    modal.Image
        An image with Python at ``.python-version``'s patch, the locked runtime
        dependencies with no ``dev`` or ``platform`` group, Node at ``web/.nvmrc``'s
        version, ``web/``'s locked ``wrangler``, the files `run` reads under
        ``/repo``, the package, and ``CODE_VERSION`` from the deploying shell's
        environment, empty when it is unset (d008, Environments and configuration).
    """
    python_patch = (PIPELINE_DIR / ".python-version").read_text().strip()
    node_version = (REPO_DIR / "web" / ".nvmrc").read_text().strip().removeprefix("v")
    web_dir = REPO_DIR / "web"
    remote_web = REMOTE_ROOT / "web"
    schema = "contracts/latest-station-count.schema.json"

    return (
        modal.Image.from_registry(f"python:{python_patch}-slim-bookworm")
        .apt_install("ca-certificates", "curl")
        .run_commands(_node_install_command(node_version))
        # `--locked` fails the build when `uv.lock` does not match `pyproject.toml`,
        # which `frozen=True`'s `--frozen` would not; the two flags exclude each
        # other. The system Python is the pinned patch, so uv may neither prefer nor
        # download another one.
        .uv_sync(
            str(PIPELINE_DIR),
            frozen=False,
            uv_version=UV_VERSION,
            extra_options="--locked --no-dev --python-preference=only-system --no-python-downloads",
        )
        .add_local_file(
            web_dir / "package.json", str(remote_web / "package.json"), copy=True
        )
        .add_local_file(
            web_dir / "package-lock.json",
            str(remote_web / "package-lock.json"),
            copy=True,
        )
        .run_commands(f"cd {remote_web} && npm ci")
        .add_local_dir(
            PIPELINE_DIR / "dbt",
            str(REMOTE_ROOT / "pipeline" / "dbt"),
            copy=True,
            ignore=LOCAL_ONLY,
        )
        .add_local_dir(
            PIPELINE_DIR / "config", str(REMOTE_ROOT / "pipeline" / "config"), copy=True
        )
        .add_local_dir(web_dir, str(remote_web), copy=True, ignore=LOCAL_ONLY)
        .add_local_file(REPO_DIR / schema, str(REMOTE_ROOT / schema), copy=True)
        .env({"CODE_VERSION": os.environ.get("CODE_VERSION", "")})
        .add_local_python_source("bikesharing")
    )


# The container imports this module again to find its function, without the
# repository's pins, which sit outside the image; it never builds the image, so a
# stand-in is enough there.
image = _build_image() if modal.is_local() else modal.Image.debian_slim()

app = modal.App(APP_NAME)


def _raise_if_failed(outcome: str) -> None:
    """Make Modal record the call as failed when the run failed.

    Parameters
    ----------
    outcome : str
        The result of ``run``, ``"succeeded"`` or ``"failed"``.

    Raises
    ------
    RuntimeError
        If the run failed, so that the deploy script's smoke test sees a failed call.
    """
    if outcome == "failed":
        raise RuntimeError("The pipeline run failed; its events are in the run's logs.")


@app.function(
    image=image,
    schedule=modal.Cron(CRON),
    secrets=[
        _secret(BRONZE_READ_SECRET),
        _secret(LAKEHOUSE_WRITE_SECRET),
        _secret(DEPLOY_SECRET),
        _secret(HEARTBEAT_SECRET),
    ],
    cpu=1.0,
    memory=(MEMORY_MIB, MEMORY_MIB),
    timeout=TIMEOUT_S,
    max_containers=1,
)
def scheduled_run() -> None:
    """Run the pipeline on its schedule, with every credential of production.

    Raises
    ------
    ValueError
        If the image holds no code version.
    RuntimeError
        If the run failed.
    """
    config = scheduled_config(
        os.environ, root=REMOTE_ROOT, container_memory_mib=MEMORY_MIB
    )
    _raise_if_failed(run(config))


@app.function(
    image=image,
    secrets=[_secret(BRONZE_READ_SECRET)],
    cpu=1.0,
    memory=(MEMORY_MIB, MEMORY_MIB),
    timeout=TIMEOUT_S,
)
def one_off_run() -> None:
    """Run the pipeline once, over bronze's read-only credentials.

    It keeps its tables on the container's disk, publishes nothing and sends no
    heartbeat, so a run from a branch can neither write to production nor deploy the
    page.

    Raises
    ------
    RuntimeError
        If the run failed.
    """
    config = one_off_config(
        os.environ, root=REMOTE_ROOT, container_memory_mib=MEMORY_MIB
    )
    _raise_if_failed(run(config))
