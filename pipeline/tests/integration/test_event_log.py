"""Tests of the event log: each event to a stream as it happens and kept for the log object.

The log writes to any text stream, so the tests pass their own and run the
production code with no network (d008, Observability).
"""

import io
import json
from datetime import UTC, datetime

from bikesharing.core import events
from bikesharing.core.events import RunContext
from bikesharing.shell.event_log import EventLog

CONTEXT = RunContext(run_id="0194f3a2-7c1e-7a55-9d3b-2f6c8e1a4b70", version="a1b2c3d")
TS = datetime(2026, 10, 22, 7, 42, 19, 123000, tzinfo=UTC)


class _RecordingStream(io.StringIO):
    """A stream that remembers what it held at each flush."""

    def __init__(self) -> None:
        super().__init__()
        self.flushed: list[str] = []

    def flush(self) -> None:
        self.flushed.append(self.getvalue())
        super().flush()


def test_emit_writes_the_line_and_flushes_before_the_next_event() -> None:
    stream = _RecordingStream()
    log = EventLog(CONTEXT, [], stream)

    line = log.emit(events.batch_committed(TS, batch=1, rows_inserted=10, objects=2))

    assert stream.flushed == [line + "\n"]
    log.emit(events.stage_drained(TS, end_instant=TS))
    assert stream.flushed[0] == line + "\n"
    assert len(stream.flushed) == 2


def test_emit_returns_the_json_line_with_the_common_fields_first() -> None:
    log = EventLog(CONTEXT, [], io.StringIO())

    line = log.emit(events.batch_committed(TS, batch=1, rows_inserted=10, objects=2))

    parsed = json.loads(line)
    assert list(parsed)[:6] == [
        "ts",
        "level",
        "component",
        "version",
        "run_id",
        "event",
    ]
    assert parsed["event"] == "batch_committed"
    assert parsed["run_id"] == CONTEXT.run_id
    assert parsed["rows_inserted"] == 10


def test_body_holds_every_event_in_order_as_json_lines() -> None:
    log = EventLog(CONTEXT, [], io.StringIO())
    log.emit(events.run_started(TS, end_instant=None, excluded_objects=0))
    log.emit(events.batch_committed(TS, batch=1, rows_inserted=10, objects=2))
    log.emit(
        events.run_finished(
            TS,
            outcome="succeeded",
            batches=1,
            rows_inserted=10,
            duration_s=1.5,
            peak_memory_mb=200.0,
        )
    )

    body = log.body()

    assert body.endswith("\n")
    assert [json.loads(line)["event"] for line in body.splitlines()] == [
        "run_started",
        "batch_committed",
        "run_finished",
    ]


def test_body_equals_what_the_stream_received() -> None:
    stream = io.StringIO()
    log = EventLog(CONTEXT, [], stream)
    log.emit(events.run_started(TS, end_instant=None, excluded_objects=0))
    log.emit(events.stage_drained(TS, end_instant=TS))

    assert log.body() == stream.getvalue()


def test_body_is_empty_before_any_event() -> None:
    assert EventLog(CONTEXT, [], io.StringIO()).body() == ""


# Verifies d008 R24
def test_emit_redacts_a_secret_in_the_stream_and_in_the_body() -> None:
    stream = io.StringIO()
    log = EventLog(CONTEXT, ["s3cr3t-token"], stream)

    log.emit(
        events.batch_failed(
            TS,
            batch=1,
            reason="exception",
            error_type="HTTPError",
            error="403 for https://hc-ping.example/s3cr3t-token",
        )
    )

    assert "s3cr3t-token" not in stream.getvalue()
    assert "s3cr3t-token" not in log.body()
    assert "***" in log.body()
