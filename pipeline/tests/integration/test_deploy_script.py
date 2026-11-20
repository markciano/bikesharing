"""Tests of the deploy script's refusals and of the calls it makes.

The script runs for real in a temporary Git repository, with a bare repository as its
``origin``. ``uv`` is a stand-in first on the ``PATH``: a script that records how it
was called and exits as the test says, so the tests run the production script with no
network and no Modal account, and can check that a refused deployment never reaches it
(d008, Deploy script).
"""

import json
import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "deploy.sh"

# The stand-in appends one line per call to the file ``UV_CALLS`` names, outside the
# repository so that the record is not an untracked file. A call that carries
# ``deploy`` exits with ``UV_DEPLOY_EXIT``, and a call that carries ``smoke_test.py``
# with ``UV_SMOKE_EXIT``.
_UV_STAND_IN = f"""#!{sys.executable}
import json, os, sys

with open(os.environ["UV_CALLS"], "a", encoding="utf-8") as calls:
    calls.write(
        json.dumps(
            {{
                "argv": sys.argv[1:],
                "cwd": os.getcwd(),
                "code_version": os.environ.get("CODE_VERSION"),
            }}
        )
        + "\\n"
    )
if "deploy" in sys.argv:
    sys.exit(int(os.environ.get("UV_DEPLOY_EXIT", "0")))
if "scripts/smoke_test.py" in sys.argv:
    sys.exit(int(os.environ.get("UV_SMOKE_EXIT", "0")))
"""


@dataclass(frozen=True)
class DeployRepo:
    """A working repository with its bare origin and the stand-in's record."""

    root: Path
    origin: Path
    calls: Path
    env: dict[str, str]

    def git(self, *args: str, cwd: Path | None = None) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd or self.root,
            env=self.env,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def commit(self, name: str, *, cwd: Path | None = None) -> None:
        folder = cwd or self.root
        (folder / name).write_text(name, encoding="utf-8")
        self.git("add", name, cwd=folder)
        self.git("commit", "--message", name, cwd=folder)

    def head(self) -> str:
        return self.git("rev-parse", "HEAD")

    def deploy(self, **extra_env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(self.root / "pipeline" / "scripts" / "deploy.sh")],
            cwd=self.root,
            env={**self.env, **extra_env},
            check=False,
            capture_output=True,
            text=True,
        )

    def uv_calls(self) -> list[dict[str, object]]:
        if not self.calls.exists():
            return []
        lines = self.calls.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines]


@pytest.fixture
def repo(tmp_path: Path) -> DeployRepo:
    """Return a clean repository whose HEAD is its ``origin/main``."""
    stand_in = tmp_path / "bin" / "uv"
    stand_in.parent.mkdir()
    stand_in.write_text(_UV_STAND_IN, encoding="utf-8")
    stand_in.chmod(stand_in.stat().st_mode | stat.S_IXUSR)
    env = {
        **os.environ,
        "PATH": f"{stand_in.parent}{os.pathsep}{os.environ['PATH']}",
        "HOME": str(tmp_path / "home"),
        # The developer's own Git configuration (signing, hooks) must not reach the
        # tests.
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "UV_CALLS": str(tmp_path / "uv_calls.jsonl"),
        # A stale value in the caller's shell must not become the code version.
        "CODE_VERSION": "stale",
    }
    deploy_repo = DeployRepo(
        root=tmp_path / "work",
        origin=tmp_path / "origin.git",
        calls=tmp_path / "uv_calls.jsonl",
        env=env,
    )
    deploy_repo.origin.mkdir()
    deploy_repo.git("init", "--bare", "--initial-branch=main", cwd=deploy_repo.origin)
    deploy_repo.root.mkdir()
    deploy_repo.git("init", "--initial-branch=main")
    deploy_repo.git("remote", "add", "origin", str(deploy_repo.origin))
    scripts = deploy_repo.root / "pipeline" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy(SCRIPT, scripts / "deploy.sh")
    (deploy_repo.root / "pipeline" / "modal_app.py").write_text("", encoding="utf-8")
    deploy_repo.git("add", ".")
    deploy_repo.git("commit", "--message", "initial")
    deploy_repo.git("push", "--set-upstream", "origin", "main")
    return deploy_repo


# Verifies d008 R10
def test_a_tracked_file_with_an_uncommitted_change_is_refused_before_any_call(
    repo: DeployRepo,
) -> None:
    (repo.root / "pipeline" / "modal_app.py").write_text("edited", encoding="utf-8")

    result = repo.deploy()

    assert result.returncode != 0
    assert "uncommitted changes" in result.stderr
    assert "pipeline/modal_app.py" in result.stderr
    assert repo.uv_calls() == []


# Verifies d008 R10
def test_a_staged_change_is_refused_before_any_call(repo: DeployRepo) -> None:
    (repo.root / "staged.txt").write_text("staged", encoding="utf-8")
    repo.git("add", "staged.txt")

    result = repo.deploy()

    assert result.returncode != 0
    assert "uncommitted changes" in result.stderr
    assert "staged.txt" in result.stderr
    assert repo.uv_calls() == []


# Verifies d008 R10
def test_an_untracked_file_is_refused_before_any_call(repo: DeployRepo) -> None:
    (repo.root / "pipeline" / "notes.txt").write_text("untracked", encoding="utf-8")

    result = repo.deploy()

    assert result.returncode != 0
    assert "untracked files" in result.stderr
    assert "pipeline/notes.txt" in result.stderr
    assert repo.uv_calls() == []


# Verifies d008 R10
def test_a_local_commit_that_origin_main_does_not_hold_is_refused_before_any_call(
    repo: DeployRepo,
) -> None:
    repo.commit("local.txt")

    result = repo.deploy()

    assert result.returncode != 0
    assert "not origin/main" in result.stderr
    assert repo.head() in result.stderr
    assert repo.uv_calls() == []


# Verifies d008 R10
def test_a_head_behind_origin_main_is_refused_before_any_call(
    repo: DeployRepo, tmp_path: Path
) -> None:
    other = tmp_path / "other"
    repo.git("clone", str(repo.origin), str(other), cwd=tmp_path)
    repo.commit("upstream.txt", cwd=other)
    repo.git("push", "origin", "main", cwd=other)

    result = repo.deploy()

    assert result.returncode != 0
    assert "not origin/main" in result.stderr
    assert repo.uv_calls() == []


# Verifies d008 R10
def test_a_clone_whose_fetch_leaves_the_origin_main_ref_stale_still_sees_the_new_tip(
    repo: DeployRepo, tmp_path: Path
) -> None:
    # A single-branch checkout, such as CI's, may fetch no refspec that covers main.
    repo.git(
        "config", "remote.origin.fetch", "+refs/heads/other:refs/remotes/origin/other"
    )
    other = tmp_path / "other"
    repo.git("clone", str(repo.origin), str(other), cwd=tmp_path)
    repo.commit("upstream.txt", cwd=other)
    repo.git("push", "origin", "main", cwd=other)

    result = repo.deploy()

    assert result.returncode != 0
    assert "not origin/main" in result.stderr
    assert repo.uv_calls() == []


# Verifies d008 R9
def test_a_clean_head_at_origin_main_is_deployed_tagged_with_its_full_sha(
    repo: DeployRepo,
) -> None:
    sha = repo.head()

    result = repo.deploy()

    assert result.returncode == 0, result.stderr
    deploy_call = repo.uv_calls()[0]
    assert deploy_call["argv"] == [
        "run",
        "--locked",
        "--group",
        "platform",
        "modal",
        "deploy",
        "--tag",
        sha,
        "modal_app.py",
    ]
    assert len(sha) == 40
    assert Path(str(deploy_call["cwd"])).resolve() == (repo.root / "pipeline").resolve()


# Verifies d008 R9
def test_the_image_gets_the_sha_as_its_code_version_whatever_the_callers_environment_holds(
    repo: DeployRepo,
) -> None:
    sha = repo.head()

    repo.deploy()

    assert repo.uv_calls()[0]["code_version"] == sha


def test_the_deployed_function_is_invoked_once_after_the_deployment(
    repo: DeployRepo,
) -> None:
    result = repo.deploy()

    assert result.returncode == 0, result.stderr
    calls = repo.uv_calls()
    assert [call["argv"] for call in calls[1:]] == [
        ["run", "--locked", "--group", "platform", "python", "scripts/smoke_test.py"]
    ]
    assert Path(str(calls[1]["cwd"])).resolve() == (repo.root / "pipeline").resolve()


def test_a_failed_deployment_fails_the_script_without_invoking_the_function(
    repo: DeployRepo,
) -> None:
    result = repo.deploy(UV_DEPLOY_EXIT="3")

    assert result.returncode != 0
    assert len(repo.uv_calls()) == 1


def test_a_failed_smoke_test_fails_the_script(repo: DeployRepo) -> None:
    result = repo.deploy(UV_SMOKE_EXIT="1")

    assert result.returncode != 0
    assert len(repo.uv_calls()) == 2
