"""Tests of the published file's writing and the page's deployment.

``wrangler`` is a stand-in: a script at the path the shell runs, which records
how it was called and exits as its configuration says, so the tests run the
production subprocess code with no network (d008, Publishing).
"""

import json
import stat
import sys
from pathlib import Path

import pytest

from bikesharing.shell.publishing import (
    FILE_NAME,
    DeployResult,
    deploy_page,
    write_published_file,
)

ACCOUNT_ID = "acct-0123"
API_TOKEN = "cf-secret-token"
TAG = "a1b2c3d"

# The stand-in records its call in ``calls.json`` and reads its behaviour from
# ``behaviour.json``, both in its working directory, which is the web folder.
_STAND_IN = f"""#!{sys.executable}
import json, os, sys, time

with open("calls.json", "w", encoding="utf-8") as calls:
    json.dump({{"argv": sys.argv[1:], "cwd": os.getcwd(), "env": dict(os.environ)}}, calls)
with open("behaviour.json", encoding="utf-8") as behaviour:
    spec = json.load(behaviour)
time.sleep(spec.get("sleep_s", 0))
print(spec["stdout"])
print(spec["stderr"], file=sys.stderr)
sys.exit(spec["exit_code"])
"""


@pytest.fixture
def web_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a web folder whose ``wrangler`` is the stand-in, and a parent
    environment holding variables the deployment must not pass on."""
    folder = tmp_path / "web"
    binary = folder / "node_modules" / ".bin" / "wrangler"
    binary.parent.mkdir(parents=True)
    binary.write_text(_STAND_IN, encoding="utf-8")
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    _behave(folder, exit_code=0, stdout="Deployed", stderr="")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "modal-secret")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "r2-secret")
    return folder


def _behave(
    folder: Path, *, exit_code: int, stdout: str, stderr: str, sleep_s: float = 0
) -> None:
    spec = {"exit_code": exit_code, "stdout": stdout, "stderr": stderr}
    (folder / "behaviour.json").write_text(
        json.dumps({**spec, "sleep_s": sleep_s}), encoding="utf-8"
    )


def _calls(folder: Path) -> dict[str, object]:
    return json.loads((folder / "calls.json").read_text(encoding="utf-8"))


def test_the_file_is_written_as_utf8_json_to_the_assets_directory(
    tmp_path: Path,
) -> None:
    assets_dir = tmp_path / "web" / "public"
    document = {
        "generated_at": "2026-11-19T10:00:00Z",
        "stations": [{"name": "Plaça Catalunya"}],
    }

    path = write_published_file(document, assets_dir)

    assert path == assets_dir / FILE_NAME
    assert FILE_NAME == "latest-station-count.json"
    assert json.loads(path.read_bytes().decode("utf-8")) == document


def test_an_existing_file_is_replaced_by_the_next_one(tmp_path: Path) -> None:
    write_published_file({"stations": [1, 2, 3]}, tmp_path)

    path = write_published_file({"stations": []}, tmp_path)

    assert json.loads(path.read_text(encoding="utf-8")) == {"stations": []}


def test_wrangler_is_called_with_the_config_and_the_tag_from_the_web_folder(
    web_dir: Path,
) -> None:
    result = deploy_page(web_dir, tag=TAG, account_id=ACCOUNT_ID, api_token=API_TOKEN)

    calls = _calls(web_dir)
    assert result.exit_code == 0
    assert calls["argv"] == ["deploy", "--config", "wrangler.jsonc", "--tag", TAG]
    assert Path(str(calls["cwd"])).resolve() == web_dir.resolve()


def test_the_token_reaches_wrangler_through_its_environment_only(web_dir: Path) -> None:
    deploy_page(web_dir, tag=TAG, account_id=ACCOUNT_ID, api_token=API_TOKEN)

    calls = _calls(web_dir)
    env = calls["env"]
    assert isinstance(env, dict)
    # The stand-in's interpreter may add locale variables of its own, so the
    # check is on the parent's secrets, which must not reach the child.
    assert {"PATH", "HOME"} <= set(env)
    assert "MODAL_TOKEN_SECRET" not in env
    assert "R2_SECRET_ACCESS_KEY" not in env
    assert env["CLOUDFLARE_ACCOUNT_ID"] == ACCOUNT_ID
    assert env["CLOUDFLARE_API_TOKEN"] == API_TOKEN
    assert API_TOKEN not in json.dumps(calls["argv"])


# Verifies d008 R31
def test_a_wrangler_that_exits_with_an_error_is_returned_as_a_failed_deployment(
    web_dir: Path,
) -> None:
    _behave(
        web_dir, exit_code=3, stdout="Uploading assets", stderr="Authentication error"
    )

    result = deploy_page(web_dir, tag=TAG, account_id=ACCOUNT_ID, api_token=API_TOKEN)

    assert isinstance(result, DeployResult)
    assert result.exit_code == 3
    assert "Uploading assets" in result.output
    assert "Authentication error" in result.output


# Verifies d008 R31
def test_a_wrangler_that_hangs_is_stopped_and_returned_as_a_failed_deployment(
    web_dir: Path,
) -> None:
    _behave(web_dir, exit_code=0, stdout="never printed", stderr="", sleep_s=30)

    result = deploy_page(
        web_dir, tag=TAG, account_id=ACCOUNT_ID, api_token=API_TOKEN, timeout_s=0.5
    )

    assert result.exit_code == 124
    assert "timed out after 0.5 s" in result.output


# Verifies d008 R31
def test_a_wrangler_that_cannot_start_is_returned_as_a_failed_deployment(
    web_dir: Path,
) -> None:
    (web_dir / "node_modules" / ".bin" / "wrangler").unlink()

    result = deploy_page(web_dir, tag=TAG, account_id=ACCOUNT_ID, api_token=API_TOKEN)

    assert result.exit_code == 127
    assert "FileNotFoundError" in result.output


def test_a_successful_deployment_returns_its_output_and_a_peak_memory(
    web_dir: Path,
) -> None:
    _behave(web_dir, exit_code=0, stdout="Deployed bikesharing-web", stderr="")

    result = deploy_page(web_dir, tag=TAG, account_id=ACCOUNT_ID, api_token=API_TOKEN)

    assert result.exit_code == 0
    assert "Deployed bikesharing-web" in result.output
    assert result.peak_memory_mb > 0
