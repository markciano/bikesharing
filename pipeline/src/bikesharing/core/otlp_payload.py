"""Builds a run's OTLP request from its JSON lines, the mapping capture also uses.

Pure: it reads only the shape of a line, never a list of events or systems, so a
new event needs no change here (d009, OTLP request mapping).
"""

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Any, Final

SEVERITY_NUMBER: Final[Mapping[str, int]] = MappingProxyType(
    {"info": 9, "warn": 13, "error": 17}
)
"""OTLP severity number of each level (OpenTelemetry Logs data model)."""

# Fields that become resource or record properties, so they are not attributes.
_NOT_ATTRIBUTES: Final = frozenset({"ts", "level", "component", "version"})
_EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)


def logs_request(lines: Sequence[str]) -> dict[str, Any]:
    """Build the run's ``ExportLogsServiceRequest`` from its JSON lines.

    One resource per distinct ``component`` and ``version`` in order of first
    appearance, one record per line in order, whose body is the line itself.

    Parameters
    ----------
    lines : Sequence[str]
        The run's JSON lines, as written to the log, without their newline.

    Returns
    -------
    dict[str, Any]
        The OTLP/HTTP JSON request; ``{"resourceLogs": []}`` when there are no
        lines.
    """
    resources: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for text in lines:
        fields = json.loads(text)
        key = (fields["component"], fields["version"])
        resources.setdefault(key, []).append(_record(text, fields))
    return {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": component}},
                        {"key": "service.version", "value": {"stringValue": version}},
                    ]
                },
                "scopeLogs": [{"scope": {"name": component}, "logRecords": records}],
            }
            for (component, version), records in resources.items()
        ]
    }


def _record(text: str, fields: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "timeUnixNano": _unix_nano(fields["ts"]),
        "severityText": fields["level"],
        "severityNumber": SEVERITY_NUMBER[fields["level"]],
        "body": {"stringValue": text},
        "attributes": [
            {"key": key, "value": _any_value(value)}
            for key, value in fields.items()
            if key not in _NOT_ATTRIBUTES and value is not None
        ],
    }


def _unix_nano(ts: str) -> str:
    # Integer arithmetic, so the nanoseconds are exact: a float would round them.
    micros = (datetime.fromisoformat(ts) - _EPOCH) // timedelta(microseconds=1)
    return str(micros * 1000)


def _any_value(value: Any) -> dict[str, Any]:
    # bool is an int subclass, so it is tested first.
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    # Compact and unescaped, as JavaScript's JSON.stringify writes it in capture.
    return {"stringValue": json.dumps(value, separators=(",", ":"), ensure_ascii=False)}
