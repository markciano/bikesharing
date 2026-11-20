"""Tests for the run's events, their redaction and the log object's key."""

import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from bikesharing.core import events
from bikesharing.core.batching import Batch
from bikesharing.core.discovery import BronzeObject
from bikesharing.core.events import Event, RunContext, SystemDiscovery
from bikesharing.core.published_file import Violation
from bikesharing.core.verdict import NodeResult

TS = datetime(2026, 11, 19, 8, 30, 15, 123456, tzinfo=UTC)
CONTEXT = RunContext(run_id="0193a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b", version="abc1234")
COMMON_FIELDS = ["ts", "level", "component", "version", "run_id", "event"]
HEARTBEAT_URL = "https://hc-ping.com/5f1c9d1e-2b3a-4c5d-8e7f-001122334455"


def _line(event: Event, secrets: list[str] | None = None) -> dict[str, object]:
    return json.loads(events.to_json_line(event, CONTEXT, secrets or []))


def _bronze(second: int) -> BronzeObject:
    captured_at = datetime(2026, 11, 19, 8, 0, second, tzinfo=UTC)
    return BronzeObject(
        key=f"bicing/station_status/{second}.json",
        system="bicing",
        feed="station_status",
        captured_at=captured_at,
    )


def test_to_json_line_writes_common_fields_first_in_adr_order() -> None:
    event = events.batch_committed(TS, batch=2, rows_inserted=1500, objects=3)

    record = _line(event)

    assert list(record)[:6] == COMMON_FIELDS
    assert list(record)[6:] == ["batch", "rows_inserted", "objects"]


def test_to_json_line_fills_common_fields_from_context() -> None:
    record = _line(events.stage_drained(TS, end_instant=TS))

    assert record["ts"] == "2026-11-19T08:30:15.123Z"
    assert record["level"] == "warn"
    assert record["component"] == "pipeline"
    assert record["version"] == CONTEXT.version
    assert record["run_id"] == CONTEXT.run_id
    assert record["event"] == "stage_drained"


def test_to_json_line_converts_instants_to_utc_with_milliseconds() -> None:
    madrid = timezone(timedelta(hours=1))
    ts = datetime(2026, 11, 19, 9, 30, 15, 0, tzinfo=madrid)

    record = _line(events.file_built(ts, stations=10, data_instant=ts))

    assert record["ts"] == "2026-11-19T08:30:15.000Z"
    assert record["data_instant"] == "2026-11-19T08:30:15.000Z"


def test_to_json_line_rejects_an_instant_without_time_zone() -> None:
    event = events.stage_drained(datetime(2026, 11, 19), end_instant=TS)

    with pytest.raises(ValueError, match="time zone"):
        events.to_json_line(event, CONTEXT, [])


def test_run_started_holds_its_own_fields() -> None:
    record = _line(events.run_started(TS, end_instant=None, excluded_objects=4))

    assert record["level"] == "info"
    assert record["end_instant"] is None
    assert record["excluded_objects"] == 4


def test_objects_discovered_holds_each_systems_counts() -> None:
    event = events.objects_discovered(
        TS,
        systems={
            "ambici": SystemDiscovery(listed=10, pending=2, full_sweep=False),
            "bicing": SystemDiscovery(listed=20, pending=0, full_sweep=True),
        },
    )

    record = _line(event)

    assert record["level"] == "info"
    assert record["ambici"] == {"listed": 10, "pending": 2, "full_sweep": False}
    assert record["bicing"] == {"listed": 20, "pending": 0, "full_sweep": True}


def test_batch_started_holds_its_size_and_capture_range() -> None:
    batch = Batch(number=3, objects=(_bronze(1), _bronze(5), _bronze(9)))

    record = _line(events.batch_started(TS, batch=batch))

    assert record["level"] == "info"
    assert list(record)[6:] == ["batch", "objects", "first_capture", "last_capture"]
    assert record["batch"] == 3
    assert record["objects"] == 3
    assert record["first_capture"] == "2026-11-19T08:00:01.000Z"
    assert record["last_capture"] == "2026-11-19T08:00:09.000Z"


def test_node_finished_holds_dbts_node_fields() -> None:
    result = NodeResult(
        unique_id="test.bikesharing.DQR3",
        name="DQR3",
        resource_type="test",
        status="warn",
        severity="warn",
        failures=7,
        rows=None,
        duration_s=0.42,
    )

    record = _line(events.node_finished(TS, result=result))

    assert record["level"] == "info"
    assert list(record)[6:] == ["node", "status", "duration_s", "rows", "num_failures"]
    assert record["node"] == "test.bikesharing.DQR3"
    assert record["status"] == "warn"
    assert record["duration_s"] == 0.42
    assert record["rows"] is None
    assert record["num_failures"] == 7


@pytest.mark.parametrize(
    ("status", "level"),
    [("pass", "info"), ("warn", "warn"), ("fail", "error"), ("error", "error")],
)
def test_rule_checked_takes_its_level_from_its_status(status: str, level: str) -> None:
    event = events.rule_checked(
        TS,
        rule="DQR5",
        severity="error",
        status=status,  # type: ignore[arg-type]
        failures=0,
    )

    record = _line(event)

    assert record["level"] == level
    assert record["rule"] == "DQR5"
    assert record["severity"] == "error"
    assert record["status"] == status
    assert record["failures"] == 0


def test_volume_not_evaluated_holds_its_own_fields() -> None:
    event = events.volume_not_evaluated(
        TS, system="ambici", captured_at=TS, captures_in_window=12
    )

    record = _line(event)

    assert record["level"] == "info"
    assert record["system"] == "ambici"
    assert record["captured_at"] == "2026-11-19T08:30:15.123Z"
    assert record["captures_in_window"] == 12


def test_schema_drift_field_is_a_warning() -> None:
    event = events.schema_drift_field(
        TS, system="bicing", field="vehicle_types", change="added"
    )

    record = _line(event)

    assert record["level"] == "warn"
    assert record["system"] == "bicing"
    assert record["field"] == "vehicle_types"
    assert record["change"] == "added"


def test_batch_failed_is_an_error_with_its_reason() -> None:
    event = events.batch_failed(
        TS, batch=1, reason="exception", error_type="IOException", error="disk full"
    )

    record = _line(event)

    assert record["level"] == "error"
    assert list(record)[6:] == ["batch", "reason", "error_type", "error"]
    assert record["reason"] == "exception"
    assert record["error_type"] == "IOException"
    assert record["error"] == "disk full"


def test_file_invalid_holds_each_violation_with_its_path() -> None:
    violations = [
        Violation(path="/stations/0/station_id", message="1 is not of type 'string'"),
        Violation(path="", message="'data_instant' is a required property"),
    ]

    record = _line(events.file_invalid(TS, violations=violations))

    assert record["level"] == "error"
    assert record["violations"] == [
        {"path": "/stations/0/station_id", "message": "1 is not of type 'string'"},
        {"path": "", "message": "'data_instant' is a required property"},
    ]


def test_page_deployed_holds_its_tag_and_peak_memory() -> None:
    record = _line(events.page_deployed(TS, tag="v42", deploy_peak_memory_mb=180.5))

    assert record["level"] == "info"
    assert record["tag"] == "v42"
    assert record["deploy_peak_memory_mb"] == 180.5


def test_page_deploy_failed_is_an_error_with_its_output() -> None:
    record = _line(events.page_deploy_failed(TS, exit_code=1, output="boom"))

    assert record["level"] == "error"
    assert record["exit_code"] == 1
    assert record["output"] == "boom"


def test_heartbeat_failed_is_a_warning_without_the_url() -> None:
    event = events.heartbeat_failed(
        TS, signal="fail", attempts=3, error_type="URLError"
    )

    record = _line(event)

    assert record["level"] == "warn"
    assert list(record)[6:] == ["signal", "attempts", "error_type"]
    assert record["signal"] == "fail"
    assert record["attempts"] == 3
    assert record["error_type"] == "URLError"


def test_log_upload_failed_is_a_warning() -> None:
    record = _line(events.log_upload_failed(TS, error_type="ClientError"))

    assert record["level"] == "warn"
    assert record["error_type"] == "ClientError"


@pytest.mark.parametrize(
    ("outcome", "level"), [("succeeded", "info"), ("failed", "error")]
)
def test_run_finished_takes_its_level_from_its_outcome(
    outcome: str, level: str
) -> None:
    event = events.run_finished(
        TS,
        outcome=outcome,  # type: ignore[arg-type]
        batches=2,
        rows_inserted=3000,
        duration_s=95.5,
        peak_memory_mb=812.3,
        error_type=None,
        error=None,
    )

    record = _line(event)

    assert record["level"] == level
    assert list(record)[6:] == [
        "outcome",
        "batches",
        "rows_inserted",
        "duration_s",
        "peak_memory_mb",
        "error_type",
        "error",
    ]
    assert record["outcome"] == outcome
    assert record["error_type"] is None
    assert record["error"] is None


def test_run_finished_holds_an_exception_raised_outside_a_batch() -> None:
    event = events.run_finished(
        TS,
        outcome="failed",
        batches=0,
        rows_inserted=0,
        duration_s=1.5,
        peak_memory_mb=120.0,
        error_type="GenericError",
        error=f"listing failed for {HEARTBEAT_URL}",
    )

    record = _line(event, [HEARTBEAT_URL])

    assert record["level"] == "error"
    assert record["error_type"] == "GenericError"
    assert record["error"] == "listing failed for ***"


# Verifies d008 R24
def test_redact_replaces_the_heartbeat_url_in_an_error_message() -> None:
    message = f"<urlopen error timed out> for {HEARTBEAT_URL}/fail"

    redacted = events.redact(message, [HEARTBEAT_URL, "token-123"])

    assert HEARTBEAT_URL not in redacted
    assert redacted == "<urlopen error timed out> for ***/fail"


# Verifies d008 R24
def test_redact_replaces_every_occurrence_of_each_secret() -> None:
    message = "key=AKIA1 secret=s3cr3t again AKIA1"

    redacted = events.redact(message, ["AKIA1", "s3cr3t"])

    assert redacted == "key=*** secret=*** again ***"


# Verifies d008 R24
def test_redact_hides_a_secret_that_contains_another_whole() -> None:
    redacted = events.redact(f"ping {HEARTBEAT_URL}", ["hc-ping.com", HEARTBEAT_URL])

    assert redacted == "ping ***"


def test_redact_ignores_an_empty_secret() -> None:
    assert events.redact("nothing to hide", ["", "x-token"]) == "nothing to hide"


# Verifies d008 R24
def test_to_json_line_redacts_secrets_in_every_string_value() -> None:
    event = events.batch_failed(
        TS,
        batch=1,
        reason="exception",
        error_type="HTTPError",
        error=f"403 from https://acct.r2.dev?X-Amz-Credential=AKIA1 and {HEARTBEAT_URL}",
    )

    line = events.to_json_line(event, CONTEXT, [HEARTBEAT_URL, "AKIA1"])

    assert HEARTBEAT_URL not in line
    assert "AKIA1" not in line
    assert json.loads(line)["error"] == (
        "403 from https://acct.r2.dev?X-Amz-Credential=*** and ***"
    )


# Verifies d008 R24
def test_to_json_line_redacts_secrets_in_nested_values() -> None:
    violations = [Violation(path="/stations/0", message="leaked s3cr3t here")]

    line = events.to_json_line(
        events.file_invalid(TS, violations=violations), CONTEXT, ["s3cr3t"]
    )

    assert "s3cr3t" not in line
    assert json.loads(line)["violations"][0]["message"] == "leaked *** here"


# Verifies d008 R24
def test_to_json_line_redacts_secrets_in_mapping_keys() -> None:
    event = Event(TS, "info", "probe", {"by_target": {HEARTBEAT_URL: 1}})

    line = events.to_json_line(event, CONTEXT, [HEARTBEAT_URL])

    assert HEARTBEAT_URL not in line
    assert json.loads(line)["by_target"] == {"***": 1}


def test_peak_memory_mb_converts_kib_to_decimal_mb() -> None:
    assert events.peak_memory_mb(1_000_000) == pytest.approx(1024.0)


def test_log_object_key_is_dated_by_the_runs_utc_start() -> None:
    # 00:30 in Madrid on the 20th is still the 19th in UTC.
    started_at = datetime(2026, 11, 20, 0, 30, tzinfo=timezone(timedelta(hours=1)))

    key = events.log_object_key(CONTEXT.run_id, started_at)

    assert key == f"logs/pipeline/date=2026-11-19/{CONTEXT.run_id}.jsonl"


def test_log_object_key_rejects_a_start_without_time_zone() -> None:
    with pytest.raises(ValueError, match="time zone"):
        events.log_object_key(CONTEXT.run_id, datetime(2026, 11, 19, 8))
