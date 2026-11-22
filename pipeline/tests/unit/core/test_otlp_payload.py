"""Unit tests for the OTLP request built from a run's JSON lines.

They mirror capture's tests of the same mapping (``capture/test/unit/otlp.test.js``),
so that both components map a line alike (d009, OTLP request mapping).
"""

import json
from typing import Any

from bikesharing.core.otlp_payload import SEVERITY_NUMBER, logs_request

VERSION = "7f3c2a9e1b4d4c6a8e2f5d9b0a1c3e47"
RUN_ID = "20261018T120003Z"


def line(fields: dict[str, Any] | None = None, **common: Any) -> str:
    """A JSON line as the pipeline writes it: the common fields, then the event's own."""
    return json.dumps(
        {
            "ts": "2026-01-01T00:00:00.871Z",
            "level": "info",
            "component": "pipeline",
            "version": VERSION,
            "run_id": RUN_ID,
            "event": "run_started",
            **common,
            **(fields or {}),
        }
    )


def records(request: dict[str, Any]) -> list[dict[str, Any]]:
    """The records of the request's first resource."""
    return request["resourceLogs"][0]["scopeLogs"][0]["logRecords"]


def attrs(record: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """The attributes of a record as ``(key, value)`` pairs, in order."""
    return [(a["key"], a["value"]) for a in record["attributes"]]


def test_severity_number_gives_each_level_its_opentelemetry_number() -> None:
    assert dict(SEVERITY_NUMBER) == {"info": 9, "warn": 13, "error": 17}


def test_logs_request_builds_one_resource_per_component_and_version_in_order() -> None:
    lines = [
        line(version="v2"),
        line(version="v1"),
        line(version="v2"),
        line(component="capture", version="v1"),
    ]

    resources = logs_request(lines)["resourceLogs"]

    assert [r["resource"]["attributes"] for r in resources] == [
        [
            {"key": "service.name", "value": {"stringValue": "pipeline"}},
            {"key": "service.version", "value": {"stringValue": "v2"}},
        ],
        [
            {"key": "service.name", "value": {"stringValue": "pipeline"}},
            {"key": "service.version", "value": {"stringValue": "v1"}},
        ],
        [
            {"key": "service.name", "value": {"stringValue": "capture"}},
            {"key": "service.version", "value": {"stringValue": "v1"}},
        ],
    ]
    assert [[s["scope"]["name"] for s in r["scopeLogs"]] for r in resources] == [
        ["pipeline"],
        ["pipeline"],
        ["capture"],
    ]
    assert [len(r["scopeLogs"][0]["logRecords"]) for r in resources] == [2, 1, 1]


def test_logs_request_builds_one_record_per_line_with_nanosecond_time_as_string() -> (
    None
):
    lines = [
        line({"system": "bicing"}),
        line({"system": "ambici"}, ts="2026-01-01T00:00:01.002Z"),
    ]

    built = records(logs_request(lines))

    assert [r["timeUnixNano"] for r in built] == [
        "1767225600871000000",
        "1767225601002000000",
    ]
    assert [dict(attrs(r))["system"] for r in built] == [
        {"stringValue": "bicing"},
        {"stringValue": "ambici"},
    ]


def test_logs_request_gives_each_record_its_level_and_severity_number() -> None:
    lines = [line(level=level) for level in ("info", "warn", "error")]

    built = records(logs_request(lines))

    assert [(r["severityText"], r["severityNumber"]) for r in built] == [
        ("info", 9),
        ("warn", 13),
        ("error", 17),
    ]


def test_logs_request_maps_every_other_field_to_a_typed_attribute_in_order() -> None:
    fields = {
        "system": "bicing",
        "status": 200,
        "latency_ms": 412,
        "recompressed": False,
        "ratio": 0.5,
        "unknown_feeds": ["a", "b"],
        "headers": {"server": "nginx"},
    }

    [record] = records(logs_request([line(fields)]))

    assert attrs(record) == [
        ("run_id", {"stringValue": RUN_ID}),
        ("event", {"stringValue": "run_started"}),
        ("system", {"stringValue": "bicing"}),
        ("status", {"intValue": "200"}),
        ("latency_ms", {"intValue": "412"}),
        ("recompressed", {"boolValue": False}),
        ("ratio", {"doubleValue": 0.5}),
        # Compact, as JavaScript's JSON.stringify writes it in capture.
        ("unknown_feeds", {"stringValue": '["a","b"]'}),
        ("headers", {"stringValue": '{"server":"nginx"}'}),
    ]


def test_logs_request_leaves_out_a_null_field() -> None:
    [record] = records(
        logs_request([line({"system": "bicing", "feed": None, "status": None})])
    )

    assert [key for key, _ in attrs(record)] == ["run_id", "event", "system"]


# Verifies d009 R2
def test_logs_request_builds_a_record_for_an_event_and_system_never_seen() -> None:
    fields = {"system": "zzz-bikes", "brand_new_field": 7}

    [record] = records(logs_request([line(fields, event="never_seen_event")]))

    assert attrs(record) == [
        ("run_id", {"stringValue": RUN_ID}),
        ("event", {"stringValue": "never_seen_event"}),
        ("system", {"stringValue": "zzz-bikes"}),
        ("brand_new_field", {"intValue": "7"}),
    ]


# Verifies d009 R6
def test_logs_request_sets_each_body_to_its_line_as_written() -> None:
    # Spaces and key order that json.dumps would not produce, and a redacted secret.
    odd = (
        '{"ts": "2026-01-01T00:00:00.871Z", "level":"error","component":"pipeline",'
        f'"version":"{VERSION}","run_id":"{RUN_ID}","event":"heartbeat_failed",'
        '"error":"OSError: failed to reach [redacted]"}'
    )
    lines = [line({"system": "bicing"}), odd]

    built = records(logs_request(lines))

    assert [r["body"] for r in built] == [{"stringValue": text} for text in lines]


def test_logs_request_builds_no_resources_when_there_are_no_lines() -> None:
    assert logs_request([]) == {"resourceLogs": []}
