"""Writes the published file and deploys the page with ``wrangler``.

The page's Worker serves the file as a static asset, so publishing is a
deployment: the file goes to the Worker's assets directory and ``wrangler``
uploads it. ``wrangler`` runs as a subprocess that holds the Cloudflare token
in its environment only, and a failed deployment is returned, never raised, so
the run can log it and fail after its batches are committed (d008, Publishing).
"""

import json
import os
import resource
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from bikesharing.core.events import peak_memory_mb

FILE_NAME: Final = "latest-station-count.json"
# The run's batches stop opening at 7 min of its 10-minute timeout, so a
# deployment bounded at 2 min leaves the run time to log, upload and ping
# (d008 D6, Provisional run bounds).
DEPLOY_TIMEOUT_S: Final = 120.0
_WRANGLER: Final = Path("node_modules") / ".bin" / "wrangler"
_CONFIG: Final = "wrangler.jsonc"
# Shell conventions: GNU timeout's exit code, and the shell's "command not found".
_TIMED_OUT: Final = 124
_NOT_STARTED: Final = 127


@dataclass(frozen=True, slots=True)
class DeployResult:
    """The outcome of one ``wrangler deploy``.

    Attributes
    ----------
    exit_code : int
        ``wrangler``'s exit code; 0 is a successful deployment.
    output : str
        Its standard output and standard error, interleaved.
    peak_memory_mb : float
        The largest peak memory, in decimal MB, of any child process of this
        one up to the deployment's end (``RUSAGE_CHILDREN``), which in a run
        is ``wrangler``'s own peak.
    """

    exit_code: int
    output: str
    peak_memory_mb: float


def write_published_file(document: Mapping[str, object], assets_dir: Path) -> Path:
    """Write the published file to the Worker's assets directory.

    Parameters
    ----------
    document : Mapping[str, object]
        The file's content, already validated against its schema.
    assets_dir : Path
        The Worker's assets directory; it is created if missing.

    Returns
    -------
    Path
        The written file, ``assets_dir / FILE_NAME``. It replaces the previous
        one.
    """
    assets_dir.mkdir(parents=True, exist_ok=True)
    path = assets_dir / FILE_NAME
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def deploy_page(
    web_dir: Path,
    *,
    tag: str,
    account_id: str,
    api_token: str,
    timeout_s: float = DEPLOY_TIMEOUT_S,
) -> DeployResult:
    """Deploy the page by running ``wrangler deploy`` in the web folder.

    Parameters
    ----------
    web_dir : Path
        The page's component, holding ``wrangler.jsonc`` and the locked
        ``wrangler`` in ``node_modules``.
    tag : str
        The version tag the deployment carries, the run's code version.
    account_id : str
        The Cloudflare account, passed in ``CLOUDFLARE_ACCOUNT_ID``.
    api_token : str
        The Cloudflare token. It is a secret: it goes in ``CLOUDFLARE_API_TOKEN``
        only, never in the arguments, which other processes can read.
    timeout_s : float, default DEPLOY_TIMEOUT_S
        How long ``wrangler`` may run before it is killed.

    Returns
    -------
    DeployResult
        The exit code, output and peak memory. A failed deployment is
        returned, never raised: a non-zero exit as it is, a ``wrangler``
        killed at its timeout as exit code 124 with the output it wrote, and a
        ``wrangler`` that cannot start as exit code 127 with the error's type
        and message.
    """
    folder = web_dir.resolve()
    # Only what wrangler needs: the parent's environment holds the run's other
    # secrets (R2 keys, heartbeat URL), which this child must not receive.
    env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ["HOME"],
        "CLOUDFLARE_ACCOUNT_ID": account_id,
        "CLOUDFLARE_API_TOKEN": api_token,
    }
    try:
        completed = subprocess.run(
            [str(folder / _WRANGLER), "deploy", "--config", _CONFIG, "--tag", tag],
            cwd=folder,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as error:
        # subprocess.run kills the child at its timeout; the output read so
        # far comes as bytes whatever the text mode.
        partial = error.output
        written = (
            partial.decode("utf-8", errors="replace")
            if isinstance(partial, bytes)
            else partial or ""
        )
        return _result(
            _TIMED_OUT, f"wrangler timed out after {timeout_s:g} s\n{written}"
        )
    except OSError as error:
        return _result(
            _NOT_STARTED, f"wrangler could not start: {type(error).__name__}: {error}"
        )
    return _result(completed.returncode, completed.stdout)


def _result(exit_code: int, output: str) -> DeployResult:
    """Return a deployment's outcome, with the peak memory of this process's children."""
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return DeployResult(
        exit_code=exit_code,
        output=output,
        peak_memory_mb=peak_memory_mb(children.ru_maxrss),
    )
