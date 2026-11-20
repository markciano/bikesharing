"""Integration tests of a run end to end, over the bronze fixtures and local Delta tables.

Bronze is a ``LocalStore`` over a copy of the fixtures, the lakehouse a local
folder, and the log store another; ``wrangler`` is a stand-in script and the
heartbeat's check a local HTTP stub, so a run executes the production code with
no network beyond the loopback (d008, Tests and CI).
"""

import gzip
import json
import shutil
import stat
import sys
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from arro3.core import Table
from bikesharing.shell.run import (
    PublishTarget,
    RunConfig,
    one_off_config,
    run,
    scheduled_config,
)
from deltalake import DeltaTable, QueryBuilder
from obstore.store import LocalStore

from bikesharing.shell.delta import (
    PROCESSED_OBJECTS_PATH,
    STATION_STOCK_PATH,
    local_lakehouse,
    processed_keys,
)

REPO = Path(__file__).resolve().parents[3]
DBT_PROJECT = REPO / "pipeline" / "dbt"
SCHEMA = json.loads(
    (REPO / "contracts" / "latest-station-count.schema.json").read_text()
)
NOW = datetime(2026, 10, 22, 8, 0, tzinfo=UTC)
VERSION = "0123456789abcdef0123456789abcdef01234567"
SECRET = "cf-secret-token"

AMBICI = [
    f"raw/ambici/station_status/2026-10-19/20261019T08{minute}45Z.json.gz"
    for minute in ("57", "58", "59")
]
BICING = [
    f"raw/bicing/station_status/2026-10-22/20261022T074{minute}19Z.json.gz"
    for minute in ("2", "3", "4", "5")
]
# With batches of 4, oldest first: AMBICI's three and BICING's first, then the rest.
BATCH_1 = [*AMBICI, BICING[0]]
BATCH_2 = BICING[1:]

# The stand-in records its call in ``calls.json`` and exits with the code in
# ``exit_code``, both in its working directory, which is the web folder.
_WRANGLER = f"""#!{sys.executable}
import json, sys

with open("calls.json", "w", encoding="utf-8") as calls:
    json.dump(sys.argv[1:], calls)
with open("exit_code", encoding="utf-8") as code:
    sys.exit(int(code.read()))
"""


@pytest.fixture
def config(tmp_path: Path, bronze_folder: Path, delta_path: Path) -> RunConfig:
    """A run over the fixtures that publishes nothing and pings no check."""
    exclusion_list = tmp_path / "excluded_objects.txt"
    exclusion_list.write_text("# No object is excluded.\n", encoding="utf-8")
    logs = tmp_path / "logs"
    logs.mkdir()
    return RunConfig(
        version=VERSION,
        bronze=LocalStore(bronze_folder),
        lakehouse=local_lakehouse(delta_path),
        log_store=LocalStore(logs),
        publish=None,
        heartbeat_url=None,
        secrets=frozenset({SECRET}),
        file_schema=SCHEMA,
        dbt_project_dir=DBT_PROJECT,
        exclusion_list=exclusion_list,
        work_dir=tmp_path / "work",
        container_memory_mib=512,
        end_instant=None,
        max_objects=4,
        time_budget=timedelta(hours=1),
        lookback=timedelta(hours=1),
        clock=lambda: NOW,
    )


def _web_dir(tmp_path: Path, exit_code: int) -> Path:
    """Return a web folder whose ``wrangler`` is the stand-in."""
    folder = tmp_path / "web"
    binary = folder / "node_modules" / ".bin" / "wrangler"
    binary.parent.mkdir(parents=True)
    binary.write_text(_WRANGLER, encoding="utf-8")
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    (folder / "exit_code").write_text(str(exit_code), encoding="utf-8")
    return folder


def _publishing(config: RunConfig, tmp_path: Path, exit_code: int = 0) -> RunConfig:
    target = PublishTarget(
        web_dir=_web_dir(tmp_path, exit_code), account_id="acct", api_token=SECRET
    )
    return replace(config, publish=target)


def _runs(tmp_path: Path) -> list[list[dict[str, Any]]]:
    """Return each run's events, from its log object, oldest run first."""
    objects = sorted((tmp_path / "logs").rglob("*.jsonl"), key=lambda path: path.name)
    return [
        [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        for path in objects
    ]


def _events(tmp_path: Path) -> list[dict[str, Any]]:
    """Return the events of the latest run."""
    return _runs(tmp_path)[-1]


def _named(events: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [event for event in events if event["event"] == name]


def _count(delta_path: Path, path: str, sql: str) -> int:
    table = DeltaTable(str(delta_path.resolve() / path))
    result = Table.from_arrow(QueryBuilder().register("t", table).execute(sql))
    value = result["n"][0].as_py()
    return int(value) if value is not None else 0


def _stock_rows(delta_path: Path) -> int:
    return _count(delta_path, STATION_STOCK_PATH, "select count(*) as n from t")


def _processed_stations(delta_path: Path) -> int:
    return _count(
        delta_path, PROCESSED_OBJECTS_PATH, "select sum(station_count) as n from t"
    )


def _processed(delta_path: Path) -> set[str]:
    return set(processed_keys(local_lakehouse(delta_path)))


def _rewrite(object_file: Path, change: Callable[[list[dict[str, Any]]], None]) -> None:
    """Rewrite a bronze object, changing its list of stations in place."""
    body = json.loads(gzip.decompress(object_file.read_bytes()))
    change(body["data"]["stations"])
    object_file.write_bytes(gzip.compress(json.dumps(body).encode()))


@dataclass
class _Check:
    """The heartbeat check's stand-in: records each request's path and body."""

    port: int
    requests: list[tuple[str, str]] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/ping/check-id"


@pytest.fixture
def check() -> Iterator[_Check]:
    state = _Check(port=0)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            state.requests.append((self.path, body))
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            """Keep the test output free of the server's access log."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    state.port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield state
    server.shutdown()
    server.server_close()


# Verifies d008 R8
def test_two_batches_commit_in_one_process_and_log_each_rule(
    config: RunConfig, tmp_path: Path, delta_path: Path
) -> None:
    outcome = run(config)

    events = _events(tmp_path)
    assert outcome == "succeeded"
    assert _processed(delta_path) == set(AMBICI + BICING)
    assert _stock_rows(delta_path) == _processed_stations(delta_path) > 0
    assert [e["objects"] for e in _named(events, "batch_committed")] == [4, 3]
    assert {(e["rule"], e["severity"]) for e in _named(events, "rule_checked")} == {
        ("DQR1", "error"),
        ("DQR2", "error"),
        ("DQR11", "warn"),
        ("DQR12", "warn"),
        ("DQR13", "error"),
        ("DQR14", "error"),
    }
    assert _named(events, "file_built")
    finished = _named(events, "run_finished")[0]
    assert finished["outcome"] == "succeeded"
    assert finished["batches"] == 2
    assert finished["rows_inserted"] == _stock_rows(delta_path)
    assert finished["error_type"] is None


def test_events_share_the_runs_common_fields_from_start_to_finish(
    config: RunConfig, tmp_path: Path
) -> None:
    run(config)

    events = _events(tmp_path)
    assert events[0]["event"] == "run_started"
    assert events[-1]["event"] == "run_finished"
    assert {e["version"] for e in events} == {VERSION}
    assert len({e["run_id"] for e in events}) == 1
    assert {e["component"] for e in events} == {"pipeline"}


def test_the_run_removes_its_work_folder(config: RunConfig) -> None:
    run(config)

    assert list(config.work_dir.iterdir()) == []


# Verifies d008 R20
def test_a_batch_that_fails_a_rule_commits_nothing_and_stops_the_run(
    config: RunConfig, tmp_path: Path, bronze_folder: Path, delta_path: Path
) -> None:
    _rewrite(bronze_folder / BATCH_2[1], lambda stations: stations.append(stations[0]))

    outcome = run(config)

    events = _events(tmp_path)
    assert outcome == "failed"
    assert _processed(delta_path) == set(BATCH_1)
    assert _stock_rows(delta_path) == _processed_stations(delta_path)
    failed = _named(events, "batch_failed")
    assert [(e["batch"], e["reason"]) for e in failed] == [(2, "nodes_failed")]
    checked = {(e["rule"], e["status"]) for e in _named(events, "rule_checked")}
    assert ("DQR1", "fail") in checked
    assert not _named(events, "file_built")


# Verifies d008 R21
def test_a_batch_with_a_row_breaking_a_contract_commits_nothing_and_stops_the_run(
    config: RunConfig, tmp_path: Path, bronze_folder: Path, delta_path: Path
) -> None:
    def drop_station_id(stations: list[dict[str, Any]]) -> None:
        stations[0]["station_id"] = None

    _rewrite(bronze_folder / AMBICI[0], drop_station_id)

    outcome = run(config)

    events = _events(tmp_path)
    assert outcome == "failed"
    assert _processed(delta_path) == set()
    assert _stock_rows(delta_path) == 0
    assert [e["batch"] for e in _named(events, "batch_started")] == [1]
    assert [e["reason"] for e in _named(events, "batch_failed")] == ["nodes_failed"]
    stock = [
        e
        for e in _named(events, "node_finished")
        if e["node"].endswith(".station_stock")
    ]
    assert [e["status"] for e in stock] == ["error"]


# Verifies d008 R22
def test_a_batch_with_an_unreadable_object_commits_nothing_and_stops_the_run(
    config: RunConfig, tmp_path: Path, bronze_folder: Path, delta_path: Path
) -> None:
    (bronze_folder / AMBICI[1]).write_bytes(b"not a gzip object")

    outcome = run(config)

    events = _events(tmp_path)
    assert outcome == "failed"
    assert _processed(delta_path) == set()
    assert _stock_rows(delta_path) == 0
    assert [e["batch"] for e in _named(events, "batch_failed")] == [1]
    assert not _named(events, "file_built")


def test_a_run_stopped_between_its_two_commits_is_completed_with_no_new_row(
    config: RunConfig,
    tmp_path: Path,
    delta_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def stop(*_: object) -> None:
        raise RuntimeError("stopped before recording the batch")

    with monkeypatch.context() as patch:
        patch.setattr("bikesharing.shell.run.record_processed", stop)
        stopped = run(config)
    stock_after_stop = _stock_rows(delta_path)

    completed = run(config)

    events = _events(tmp_path)
    assert stopped == "failed"
    assert _named(_runs(tmp_path)[0], "batch_failed")[0]["reason"] == "exception"
    assert stock_after_stop > 0
    assert completed == "succeeded"
    assert _processed(delta_path) == set(AMBICI + BICING)
    assert _stock_rows(delta_path) == _processed_stations(delta_path)
    assert _named(events, "batch_committed")[0]["rows_inserted"] == 0


def test_an_excluded_object_is_never_processed(
    config: RunConfig, tmp_path: Path, delta_path: Path
) -> None:
    config.exclusion_list.write_text(
        f"{BICING[-1]} # unreadable in production\n", encoding="utf-8"
    )

    outcome = run(config)

    events = _events(tmp_path)
    assert outcome == "succeeded"
    assert _processed(delta_path) == set(AMBICI + BICING[:-1])
    assert _named(events, "run_started")[0]["excluded_objects"] == 1
    assert _named(events, "objects_discovered")[0]["bicing"] == {
        "listed": 4,
        "pending": 3,
        "full_sweep": True,
    }


def test_an_exception_outside_a_batch_fails_the_run_with_its_error(
    config: RunConfig, tmp_path: Path, bronze_folder: Path
) -> None:
    (bronze_folder / "raw" / "bicing" / "station_status" / "stray.json.gz").touch()

    outcome = run(config)

    finished = _named(_events(tmp_path), "run_finished")[0]
    assert outcome == "failed"
    assert finished["outcome"] == "failed"
    assert finished["error_type"] == "InvalidBronzeKey"
    assert "stray.json.gz" in finished["error"]


def test_a_drained_stage_with_nothing_processed_builds_no_file(
    config: RunConfig, tmp_path: Path, delta_path: Path
) -> None:
    end_instant = datetime(2026, 10, 1, tzinfo=UTC)

    outcome = run(replace(config, end_instant=end_instant))

    events = _events(tmp_path)
    assert outcome == "succeeded"
    assert (
        _named(events, "stage_drained")[0]["end_instant"] == "2026-10-01T00:00:00.000Z"
    )
    assert not _named(events, "batch_started")
    assert not _named(events, "file_built")
    assert _processed(delta_path) == set()


# Verifies d008 R6
def test_the_file_keeps_the_earlier_count_of_a_system_with_no_new_capture(
    config: RunConfig, tmp_path: Path, bronze_folder: Path
) -> None:
    publishing = _publishing(config, tmp_path)
    run(publishing)
    later = "raw/bicing/station_status/2026-10-22/20261022T080019Z.json.gz"
    shutil.copyfile(bronze_folder / BICING[-1], bronze_folder / later)

    outcome = run(publishing)

    assert publishing.publish is not None
    document = json.loads(
        (
            publishing.publish.web_dir / "public" / "latest-station-count.json"
        ).read_text()
    )
    captured = {(s["system"], s["captured_at"]) for s in document["stations"]}
    assert outcome == "succeeded"
    assert captured == {
        ("ambici", "2026-10-19T08:59:45Z"),
        ("bicing", "2026-10-22T08:00:19Z"),
    }
    assert document["data_instant"] == "2026-10-22T08:00:19Z"
    built = _named(_events(tmp_path), "file_built")[0]
    assert built["stations"] == len(document["stations"])


def test_a_published_file_is_deployed_tagged_with_the_code_version(
    config: RunConfig, tmp_path: Path
) -> None:
    publishing = _publishing(config, tmp_path)

    outcome = run(publishing)

    assert publishing.publish is not None
    calls = json.loads((publishing.publish.web_dir / "calls.json").read_text())
    assert outcome == "succeeded"
    assert calls == ["deploy", "--config", "wrangler.jsonc", "--tag", VERSION]
    assert _named(_events(tmp_path), "page_deployed")[0]["tag"] == VERSION


# Verifies d008 R31
def test_a_failed_deployment_keeps_the_commits_and_fails_the_run(
    config: RunConfig, tmp_path: Path, delta_path: Path
) -> None:
    outcome = run(_publishing(config, tmp_path, exit_code=1))

    events = _events(tmp_path)
    assert outcome == "failed"
    assert _processed(delta_path) == set(AMBICI + BICING)
    assert [e["exit_code"] for e in _named(events, "page_deploy_failed")] == [1]
    assert _named(events, "run_finished")[0]["outcome"] == "failed"


# Verifies d008 R14
def test_a_run_that_succeeds_pings_start_then_success(
    config: RunConfig, check: _Check
) -> None:
    outcome = run(replace(config, heartbeat_url=check.url))

    assert outcome == "succeeded"
    assert [path for path, _ in check.requests] == [
        "/ping/check-id/start",
        "/ping/check-id",
    ]


# Verifies d008 R15
def test_a_run_that_fails_pings_fail_with_run_finished_and_the_failing_event(
    config: RunConfig, check: _Check, bronze_folder: Path
) -> None:
    (bronze_folder / AMBICI[1]).write_bytes(b"not a gzip object")

    outcome = run(replace(config, heartbeat_url=check.url))

    assert outcome == "failed"
    assert [path for path, _ in check.requests] == [
        "/ping/check-id/start",
        "/ping/check-id/fail",
    ]
    body = [json.loads(line) for line in check.requests[1][1].splitlines()]
    assert body[0]["event"] == "run_finished"
    assert "batch_failed" in {line["event"] for line in body[1:]}
    assert {line["level"] for line in body} == {"error"}


def _environment() -> dict[str, str]:
    return {
        "CODE_VERSION": VERSION,
        "BRONZE_R2_ACCESS_KEY_ID": "bronze-id",
        "BRONZE_R2_SECRET_ACCESS_KEY": "bronze-secret",
        "LAKEHOUSE_R2_ACCESS_KEY_ID": "lakehouse-id",
        "LAKEHOUSE_R2_SECRET_ACCESS_KEY": "lakehouse-secret",
        "CLOUDFLARE_API_TOKEN": "cloudflare-token",
        "HEARTBEAT_URL": "https://hc-ping.com/check-id",
    }


@pytest.mark.parametrize("version", [None, ""])
def test_the_scheduled_config_refuses_a_missing_code_version(
    version: str | None,
) -> None:
    env = _environment()
    if version is None:
        del env["CODE_VERSION"]
    else:
        env["CODE_VERSION"] = version

    with pytest.raises(ValueError, match="CODE_VERSION"):
        scheduled_config(env, root=REPO, container_memory_mib=4096)


def test_the_scheduled_config_writes_to_r2_publishes_and_pings() -> None:
    config = scheduled_config(_environment(), root=REPO, container_memory_mib=4096)

    assert config.version == VERSION
    assert config.lakehouse.uri == "s3://bikesharing-lakehouse"
    assert config.log_store is not None
    assert config.publish is not None
    assert config.publish.web_dir == REPO / "web"
    assert config.publish.api_token == "cloudflare-token"
    assert config.heartbeat_url == "https://hc-ping.com/check-id"
    assert config.file_schema == SCHEMA
    assert (
        config.exclusion_list == REPO / "pipeline" / "config" / "excluded_objects.txt"
    )
    assert config.dbt_project_dir == DBT_PROJECT
    assert config.container_memory_mib == 4096
    assert set(_environment().values()) - {VERSION} <= config.secrets


# Verifies d008 R26
def test_the_one_off_config_holds_only_bronze_and_writes_locally() -> None:
    env = {
        "BRONZE_R2_ACCESS_KEY_ID": "bronze-id",
        "BRONZE_R2_SECRET_ACCESS_KEY": "bronze-secret",
    }

    config = one_off_config(env, root=REPO, container_memory_mib=4096)

    assert config.version == "unreleased"
    assert config.lakehouse.uri.startswith(str(config.work_dir.resolve()))
    assert config.lakehouse.storage_options == {}
    assert config.log_store is None
    assert config.publish is None
    assert config.heartbeat_url is None
    assert config.secrets == frozenset({"bronze-id", "bronze-secret"})
    assert config.file_schema == SCHEMA
