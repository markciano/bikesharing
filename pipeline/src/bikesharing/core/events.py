"""Builds the run's events as values, serializes them and redacts secrets.

Every event follows one log convention across components: JSON Lines whose
common fields come first, in a fixed order, before the event's own fields
(ADR-0036, One log convention for every component). The core builds each event
from its declared fields only, and the shell writes it to stdout and to the
run's log object (d008, Observability). Before an event is written, the value
of every secret the run holds is replaced in its strings, so that an error
message quoting a URL or a token leaks nothing (d008 D10, Security of the
skeleton).
"""

import json
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from bikesharing.core.batching import Batch
from bikesharing.core.delta_maintenance import CompactionMetrics, RetentionMetrics
from bikesharing.core.published_file import Violation
from bikesharing.core.settings import COMPONENT, System
from bikesharing.core.verdict import NodeResult, Severity

type Level = Literal["info", "warn", "error"]
type FieldValue = (
    str
    | int
    | float
    | bool
    | datetime
    | None
    | Sequence[FieldValue]
    | Mapping[str, FieldValue]
)
# The maintenance tasks ``maintenance_failed`` names (d010, Maintenance events).
type MaintenanceTask = Literal["compaction", "retention", "vacuum", "log_cleanup"]

REDACTED = "***"
_LOG_PREFIX = "logs/pipeline"
_RULE_LEVELS: Mapping[str, Level] = {
    "pass": "info",
    "warn": "warn",
    "fail": "error",
    "error": "error",
}


@dataclass(frozen=True, slots=True)
class RunContext:
    """The common fields that every event of a run shares.

    Attributes
    ----------
    run_id : str
        The run's UUIDv7.
    version : str
        The deployed commit's SHA, or ``unreleased`` for a one-off run.
    """

    run_id: str
    version: str


@dataclass(frozen=True, slots=True)
class Event:
    """One event of a run, before serialization.

    Attributes
    ----------
    ts : datetime
        When it happened, with a time zone.
    level : {"info", "warn", "error"}
        Its log level.
    event : str
        Its name.
    fields : Mapping[str, FieldValue]
        Its own fields, in the order they are written.
    """

    ts: datetime
    level: Level
    event: str
    fields: Mapping[str, FieldValue]


@dataclass(frozen=True, slots=True)
class SystemDiscovery:
    """What discovery found for one system.

    Attributes
    ----------
    listed : int
        The objects listed.
    pending : int
        The objects not yet processed.
    full_sweep : bool
        True when the whole prefix was listed rather than from a start key.
    """

    listed: int
    pending: int
    full_sweep: bool


def run_started(
    ts: datetime, *, end_instant: datetime | None, excluded_objects: int
) -> Event:
    """Build ``run_started``, at info.

    Parameters
    ----------
    ts : datetime
        When the run started.
    end_instant : datetime or None
        The end of the current stage of the first load, or None for no stage.
    excluded_objects : int
        The objects on the exclusion list.

    Returns
    -------
    Event
        The event.
    """
    return Event(
        ts,
        "info",
        "run_started",
        {"end_instant": end_instant, "excluded_objects": excluded_objects},
    )


def objects_discovered(
    ts: datetime, *, systems: Mapping[System, SystemDiscovery]
) -> Event:
    """Build ``objects_discovered``, at info, with one field per system.

    Parameters
    ----------
    ts : datetime
        When discovery ended.
    systems : Mapping[System, SystemDiscovery]
        What discovery found, by system.

    Returns
    -------
    Event
        The event, whose own fields are the system names, each holding
        ``listed``, ``pending`` and ``full_sweep``.
    """
    return Event(
        ts,
        "info",
        "objects_discovered",
        {
            system: {
                "listed": found.listed,
                "pending": found.pending,
                "full_sweep": found.full_sweep,
            }
            for system, found in systems.items()
        },
    )


def stage_drained(ts: datetime, *, end_instant: datetime) -> Event:
    """Build ``stage_drained``, at warn: no object is left before the end instant.

    Parameters
    ----------
    ts : datetime
        When the run found the stage drained.
    end_instant : datetime
        The end of the drained stage.

    Returns
    -------
    Event
        The event.
    """
    return Event(ts, "warn", "stage_drained", {"end_instant": end_instant})


def batch_started(ts: datetime, *, batch: Batch) -> Event:
    """Build ``batch_started``, at info.

    Parameters
    ----------
    ts : datetime
        When the batch started.
    batch : Batch
        The batch.

    Returns
    -------
    Event
        The event, with the batch's number, its object count and its capture
        range.
    """
    return Event(
        ts,
        "info",
        "batch_started",
        {
            "batch": batch.number,
            "objects": len(batch.objects),
            "first_capture": batch.first_capture,
            "last_capture": batch.last_capture,
        },
    )


def node_finished(ts: datetime, *, result: NodeResult) -> Event:
    """Build ``node_finished``, at info, from one node of ``dbt build``.

    Parameters
    ----------
    ts : datetime
        When the node's result was read.
    result : NodeResult
        The node's outcome.

    Returns
    -------
    Event
        The event, with dbt's unique ID of the node as ``node``.
    """
    return Event(
        ts,
        "info",
        "node_finished",
        {
            "node": result.unique_id,
            "status": result.status,
            "duration_s": result.duration_s,
            "rows": result.rows,
            "num_failures": result.failures,
        },
    )


def rule_checked(
    ts: datetime,
    *,
    rule: str,
    severity: Severity,
    status: Literal["pass", "warn", "fail", "error"],
    failures: int,
) -> Event:
    """Build ``rule_checked``, at a level set by its status.

    Parameters
    ----------
    ts : datetime
        When the rule was checked.
    rule : str
        The rule's DQR ID.
    severity : {"error", "warn"}
        The rule's configured severity, written as ``rule_severity``: Loki
        reads a ``severity`` attribute as the log level, which this field is
        not (d009 DI10, Field mapping).
    status : {"pass", "warn", "fail", "error"}
        The check's outcome.
    failures : int
        The failing rows.

    Returns
    -------
    Event
        The event, at info for ``pass``, warn for ``warn``, and error for
        ``fail`` and ``error``.
    """
    return Event(
        ts,
        _RULE_LEVELS[status],
        "rule_checked",
        {
            "rule": rule,
            "rule_severity": severity,
            "status": status,
            "failures": failures,
        },
    )


def volume_not_evaluated(
    ts: datetime, *, system: System, captured_at: datetime, captures_in_window: int
) -> Event:
    """Build ``volume_not_evaluated``, at info: too few captures for the median.

    Parameters
    ----------
    ts : datetime
        When the check ran.
    system : System
        The system of the capture.
    captured_at : datetime
        The capture not evaluated.
    captures_in_window : int
        The captures in its rolling window.

    Returns
    -------
    Event
        The event.
    """
    return Event(
        ts,
        "info",
        "volume_not_evaluated",
        {
            "system": system,
            "captured_at": captured_at,
            "captures_in_window": captures_in_window,
        },
    )


def schema_drift_field(
    ts: datetime, *, system: System, field: str, change: Literal["added", "dropped"]
) -> Event:
    """Build ``schema_drift_field``, at warn.

    Parameters
    ----------
    ts : datetime
        When the drift was found.
    system : System
        The system whose feed changed.
    field : str
        The field added or dropped.
    change : {"added", "dropped"}
        How it changed.

    Returns
    -------
    Event
        The event.
    """
    return Event(
        ts,
        "warn",
        "schema_drift_field",
        {"system": system, "field": field, "change": change},
    )


def batch_committed(
    ts: datetime, *, batch: int, rows_inserted: int, objects: int
) -> Event:
    """Build ``batch_committed``, at info.

    Parameters
    ----------
    ts : datetime
        When the batch committed.
    batch : int
        The batch's number.
    rows_inserted : int
        The rows the batch inserted.
    objects : int
        The bronze objects it processed.

    Returns
    -------
    Event
        The event.
    """
    return Event(
        ts,
        "info",
        "batch_committed",
        {"batch": batch, "rows_inserted": rows_inserted, "objects": objects},
    )


def batch_failed(
    ts: datetime,
    *,
    batch: int,
    reason: Literal["nodes_failed", "not_insert_only", "exception"],
    error_type: str | None,
    error: str | None,
) -> Event:
    """Build ``batch_failed``, at error.

    Parameters
    ----------
    ts : datetime
        When the batch failed.
    batch : int
        The batch's number.
    reason : {"nodes_failed", "not_insert_only", "exception"}
        Why it failed.
    error_type : str or None
        The exception's type name, for ``exception``.
    error : str or None
        The exception's message, for ``exception``; redacted on writing.

    Returns
    -------
    Event
        The event.
    """
    return Event(
        ts,
        "error",
        "batch_failed",
        {"batch": batch, "reason": reason, "error_type": error_type, "error": error},
    )


def table_compacted(
    ts: datetime, *, table: str, metrics: CompactionMetrics, duration_s: float
) -> Event:
    """Build ``table_compacted``, at info.

    Parameters
    ----------
    ts : datetime
        When the compaction ended.
    table : str
        The table compacted.
    metrics : CompactionMetrics
        What the compaction changed.
    duration_s : float
        How long it took, in seconds.

    Returns
    -------
    Event
        The event.
    """
    return Event(
        ts,
        "info",
        "table_compacted",
        {
            "table": table,
            "partitions": metrics.partitions,
            "files_removed": metrics.files_removed,
            "files_added": metrics.files_added,
            "duration_s": duration_s,
        },
    )


def retention_applied(
    ts: datetime, *, table: str, metrics: RetentionMetrics, duration_s: float
) -> Event:
    """Build ``retention_applied``, at info.

    Parameters
    ----------
    ts : datetime
        When the retention ended.
    table : str
        The table retention ran on.
    metrics : RetentionMetrics
        What it deleted, zero when nothing was outside the window.
    duration_s : float
        How long it took, in seconds.

    Returns
    -------
    Event
        The event.
    """
    return Event(
        ts,
        "info",
        "retention_applied",
        {
            "table": table,
            "partitions_deleted": metrics.partitions_deleted,
            "rows_deleted": metrics.rows_deleted,
            "duration_s": duration_s,
        },
    )


def table_vacuumed(
    ts: datetime, *, table: str, files_deleted: int, duration_s: float
) -> Event:
    """Build ``table_vacuumed``, at info.

    Parameters
    ----------
    ts : datetime
        When the vacuum ended.
    table : str
        The table vacuumed.
    files_deleted : int
        The files it deleted.
    duration_s : float
        How long it took, in seconds.

    Returns
    -------
    Event
        The event.
    """
    return Event(
        ts,
        "info",
        "table_vacuumed",
        {"table": table, "files_deleted": files_deleted, "duration_s": duration_s},
    )


def log_cleaned(ts: datetime, *, table: str, duration_s: float) -> Event:
    """Build ``log_cleaned``, at info.

    Parameters
    ----------
    ts : datetime
        When the log cleanup ended.
    table : str
        The table whose log was cleaned.
    duration_s : float
        How long it took, in seconds.

    Returns
    -------
    Event
        The event.
    """
    return Event(ts, "info", "log_cleaned", {"table": table, "duration_s": duration_s})


def maintenance_failed(
    ts: datetime,
    *,
    table: str,
    task: MaintenanceTask,
    error_type: str,
    error: str,
) -> Event:
    """Build ``maintenance_failed``, at warn.

    Parameters
    ----------
    ts : datetime
        When the task failed.
    table : str
        The table it was working on.
    task : {"compaction", "retention", "vacuum", "log_cleanup"}
        The task that failed.
    error_type : str
        The exception's type name.
    error : str
        The exception's message; redacted on writing.

    Returns
    -------
    Event
        The event.
    """
    return Event(
        ts,
        "warn",
        "maintenance_failed",
        {"table": table, "task": task, "error_type": error_type, "error": error},
    )


def file_built(ts: datetime, *, stations: int, data_instant: datetime) -> Event:
    """Build ``file_built``, at info.

    Parameters
    ----------
    ts : datetime
        When the file was built.
    stations : int
        The stations in the file.
    data_instant : datetime
        The file's latest capture instant.

    Returns
    -------
    Event
        The event.
    """
    return Event(
        ts, "info", "file_built", {"stations": stations, "data_instant": data_instant}
    )


def file_invalid(ts: datetime, *, violations: Sequence[Violation]) -> Event:
    """Build ``file_invalid``, at error.

    Parameters
    ----------
    ts : datetime
        When the file was validated.
    violations : Sequence[Violation]
        Every violation of the file's schema.

    Returns
    -------
    Event
        The event, with each violation's ``path`` and ``message``.
    """
    return Event(
        ts,
        "error",
        "file_invalid",
        {"violations": [{"path": v.path, "message": v.message} for v in violations]},
    )


def page_deployed(ts: datetime, *, tag: str, deploy_peak_memory_mb: float) -> Event:
    """Build ``page_deployed``, at info.

    Parameters
    ----------
    ts : datetime
        When the deploy ended.
    tag : str
        The deployed version's tag.
    deploy_peak_memory_mb : float
        The deploy's peak memory, in decimal MB.

    Returns
    -------
    Event
        The event.
    """
    return Event(
        ts,
        "info",
        "page_deployed",
        {"tag": tag, "deploy_peak_memory_mb": deploy_peak_memory_mb},
    )


def page_deploy_failed(ts: datetime, *, exit_code: int, output: str) -> Event:
    """Build ``page_deploy_failed``, at error.

    Parameters
    ----------
    ts : datetime
        When the deploy ended.
    exit_code : int
        The deploy's exit code.
    output : str
        The deploy's output; redacted on writing.

    Returns
    -------
    Event
        The event.
    """
    return Event(
        ts, "error", "page_deploy_failed", {"exit_code": exit_code, "output": output}
    )


def heartbeat_failed(
    ts: datetime,
    *,
    signal: Literal["start", "success", "fail"],
    attempts: int,
    error_type: str,
) -> Event:
    """Build ``heartbeat_failed``, at warn; it never carries the heartbeat's URL.

    Parameters
    ----------
    ts : datetime
        When the last attempt failed.
    signal : {"start", "success", "fail"}
        The signal not delivered.
    attempts : int
        The attempts made.
    error_type : str
        The last exception's type name.

    Returns
    -------
    Event
        The event.
    """
    return Event(
        ts,
        "warn",
        "heartbeat_failed",
        {"signal": signal, "attempts": attempts, "error_type": error_type},
    )


def log_upload_failed(ts: datetime, *, error_type: str) -> Event:
    """Build ``log_upload_failed``, at warn.

    The R2 log object cannot hold it, so it goes to stdout and is kept for the
    copy sent to Grafana.

    Parameters
    ----------
    ts : datetime
        When the upload failed.
    error_type : str
        The exception's type name.

    Returns
    -------
    Event
        The event.
    """
    return Event(ts, "warn", "log_upload_failed", {"error_type": error_type})


def otlp_send_failed(ts: datetime, *, error_type: str) -> Event:
    """Build ``otlp_send_failed``, at warn; it goes to stdout only.

    It is emitted after the copy was sent, so the copy cannot hold it.

    Parameters
    ----------
    ts : datetime
        When the send failed.
    error_type : str
        The exception's type name.

    Returns
    -------
    Event
        The event.
    """
    return Event(ts, "warn", "otlp_send_failed", {"error_type": error_type})


def run_finished(
    ts: datetime,
    *,
    outcome: Literal["succeeded", "failed"],
    batches: int,
    rows_inserted: int,
    duration_s: float,
    peak_memory_mb: float,
    error_type: str | None,
    error: str | None,
) -> Event:
    """Build ``run_finished``, at info when the run succeeded and error otherwise.

    Parameters
    ----------
    ts : datetime
        When the run finished.
    outcome : {"succeeded", "failed"}
        The run's outcome.
    batches : int
        The batches committed.
    rows_inserted : int
        The rows inserted over the run.
    duration_s : float
        The run's wall-clock time, in seconds.
    peak_memory_mb : float
        The process's peak memory, in decimal MB.
    error_type : str or None
        The type name of an exception raised outside a batch, which failed the
        run; None otherwise.
    error : str or None
        That exception's message; redacted on writing.

    Returns
    -------
    Event
        The event.
    """
    return Event(
        ts,
        "info" if outcome == "succeeded" else "error",
        "run_finished",
        {
            "outcome": outcome,
            "batches": batches,
            "rows_inserted": rows_inserted,
            "duration_s": duration_s,
            "peak_memory_mb": peak_memory_mb,
            "error_type": error_type,
            "error": error,
        },
    )


def to_json_line(event: Event, context: RunContext, secrets: Collection[str]) -> str:
    """Serialize an event as one JSON line, with every secret redacted.

    Parameters
    ----------
    event : Event
        The event.
    context : RunContext
        The run's common fields.
    secrets : Collection[str]
        The value of every secret the run holds.

    Returns
    -------
    str
        A JSON object, without a trailing newline: ``ts``, ``level``,
        ``component``, ``version``, ``run_id`` and ``event`` first, then the
        event's own fields in their order. Every instant is written in RFC 3339
        with milliseconds, in UTC with ``Z``, and every occurrence of a secret
        in any string, a mapping's keys included, is replaced with ``***``.

    Raises
    ------
    ValueError
        If an instant has no time zone.
    """
    record: dict[str, FieldValue] = {
        "ts": event.ts,
        "level": event.level,
        "component": COMPONENT,
        "version": context.version,
        "run_id": context.run_id,
        "event": event.event,
        **event.fields,
    }
    return json.dumps(_encoded(record, _ordered_secrets(secrets)), ensure_ascii=False)


def redact(text: str, secrets: Collection[str]) -> str:
    """Replace every occurrence of each secret's value in a text with ``***``.

    Parameters
    ----------
    text : str
        The text, such as an exception's message.
    secrets : Collection[str]
        The value of every secret the run holds; empty values are ignored.

    Returns
    -------
    str
        The text with each secret replaced.
    """
    return _redacted(text, _ordered_secrets(secrets))


def peak_memory_mb(ru_maxrss_kib: int) -> float:
    """Convert Linux's ``ru_maxrss``, in KiB, to decimal MB.

    Parameters
    ----------
    ru_maxrss_kib : int
        The peak resident set size, in KiB, as Linux reports it.

    Returns
    -------
    float
        The same size in decimal MB.
    """
    return ru_maxrss_kib * 1024 / 1_000_000


def log_object_key(run_id: str, started_at: datetime) -> str:
    """Return the key of the run's log object.

    Parameters
    ----------
    run_id : str
        The run's ID.
    started_at : datetime
        When the run started, with a time zone.

    Returns
    -------
    str
        ``logs/pipeline/date=YYYY-MM-DD/<run_id>.jsonl``, dated by the run's
        start in UTC.

    Raises
    ------
    ValueError
        If ``started_at`` has no time zone.
    """
    day = _utc(started_at).date().isoformat()
    return f"{_LOG_PREFIX}/date={day}/{run_id}.jsonl"


def _ordered_secrets(secrets: Collection[str]) -> list[str]:
    # Longest first, so that a secret containing another is replaced whole
    # rather than leaving its remainder visible around the shorter one.
    return sorted({s for s in secrets if s}, key=len, reverse=True)


def _redacted(text: str, secrets: Sequence[str]) -> str:
    for secret in secrets:
        text = text.replace(secret, REDACTED)
    return text


def _encoded(value: FieldValue, secrets: Sequence[str]) -> object:
    if isinstance(value, datetime):
        return _rfc3339_ms(value)
    if isinstance(value, str):
        return _redacted(value, secrets)
    if isinstance(value, Mapping):
        return {
            _redacted(key, secrets): _encoded(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, Sequence):
        return [_encoded(item, secrets) for item in value]
    return value


def _utc(instant: datetime) -> datetime:
    # An instant with no time zone cannot be placed in UTC without a guess,
    # and every stored timestamp is in UTC.
    if instant.utcoffset() is None:
        raise ValueError(f"expected a datetime with a time zone, not {instant!r}")
    return instant.astimezone(UTC)


def _rfc3339_ms(instant: datetime) -> str:
    return _utc(instant).isoformat(timespec="milliseconds").replace("+00:00", "Z")
