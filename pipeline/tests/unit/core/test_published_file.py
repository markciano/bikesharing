"""Tests of the published file: built from gold's rows and validated (DQR14)."""

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

import pytest
from bikesharing.core.published_file import (
    build_published_file,
    validate_published_file,
)

SCHEMA = json.loads(
    (
        Path(__file__).parents[4] / "contracts" / "latest-station-count.schema.json"
    ).read_text()
)
NOON = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def _stations(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], build_published_file(rows)["stations"])


def _row(
    system: str = "bicing",
    station_id: str = "1",
    captured_at: datetime = NOON,
    **overrides: object,
) -> dict[str, object]:
    return {
        "system": system,
        "station_id": station_id,
        "num_vehicles_available": 7,
        "num_docks_available": 13,
        "is_renting": True,
        "is_returning": True,
        "last_reported": captured_at - timedelta(seconds=30),
        "captured_at": captured_at,
        **overrides,
    }


def _document(**station_overrides: object) -> dict[str, Any]:
    station: dict[str, object] = {
        "system": "bicing",
        "station_id": "1",
        "num_vehicles_available": 7,
        "num_docks_available": 13,
        "is_renting": True,
        "is_returning": True,
        "last_reported": "2026-10-18T11:59:30Z",
        "captured_at": "2026-10-18T12:00:00Z",
    }
    station.update(station_overrides)
    return {"data_instant": "2026-10-18T12:00:00Z", "stations": [station]}


def test_build_published_file_sorts_stations_by_system_and_station_id() -> None:
    rows = [
        _row("bicing", "2"),
        _row("ambici", "9"),
        _row("bicing", "10"),
        _row("ambici", "1"),
    ]

    assert [(s["system"], s["station_id"]) for s in _stations(rows)] == [
        ("ambici", "1"),
        ("ambici", "9"),
        ("bicing", "10"),
        ("bicing", "2"),
    ]


def test_build_published_file_sets_data_instant_to_the_latest_capture() -> None:
    rows = [
        _row("ambici", "1", captured_at=NOON - timedelta(minutes=10)),
        _row("bicing", "1", captured_at=NOON),
        _row("bicing", "2", captured_at=NOON - timedelta(minutes=5)),
    ]

    assert build_published_file(rows)["data_instant"] == "2026-10-18T12:00:00Z"


def test_build_published_file_writes_instants_in_rfc_3339_utc_with_z() -> None:
    madrid_summer = timezone(timedelta(hours=2))
    row = _row(
        captured_at=datetime(2026, 10, 18, 14, 0, tzinfo=madrid_summer),
        last_reported=datetime(2026, 10, 18, 11, 59, 30, 500000, tzinfo=UTC),
    )

    station = _stations([row])[0]

    assert (station["captured_at"], station["last_reported"]) == (
        "2026-10-18T12:00:00Z",
        "2026-10-18T11:59:30.500000Z",
    )


def test_build_published_file_keeps_the_row_fields_and_null_measures() -> None:
    row = _row(num_vehicles_available=None)

    station = _stations([row])[0]

    assert station == {
        "system": "bicing",
        "station_id": "1",
        "num_vehicles_available": None,
        "num_docks_available": 13,
        "is_renting": True,
        "is_returning": True,
        "last_reported": "2026-10-18T11:59:30Z",
        "captured_at": "2026-10-18T12:00:00Z",
    }


def test_build_published_file_raises_on_no_rows() -> None:
    with pytest.raises(ValueError):
        build_published_file([])


def test_build_published_file_raises_on_an_instant_without_time_zone() -> None:
    with pytest.raises(ValueError):
        build_published_file([_row(captured_at=datetime(2026, 10, 18, 12, 0))])


# Verifies d008 R7
def test_build_published_file_from_gold_rows_passes_the_schema() -> None:
    rows = [_row("ambici", "1"), _row("bicing", "1", num_docks_available=None)]

    assert validate_published_file(build_published_file(rows), SCHEMA) == []


# Verifies d008 R7
@pytest.mark.parametrize(
    ("document", "path"),
    [
        (_document(is_renting="true"), "/stations/0/is_renting"),
        (_document(num_docks_available=-1), "/stations/0/num_docks_available"),
        (_document(name="Plaça de Catalunya"), "/stations/0"),
        ({"stations": _document()["stations"]}, ""),
        ([], ""),
    ],
    ids=[
        "wrong type",
        "below minimum",
        "field outside D2's list",
        "missing field",
        "not an object",
    ],
)
def test_validate_published_file_reports_a_violation_with_its_json_pointer(
    document: object, path: str
) -> None:
    violations = validate_published_file(document, SCHEMA)

    assert [v.path for v in violations] == [path]
    assert violations[0].message


def test_validate_published_file_reports_every_violation() -> None:
    document = _document(is_renting="true", captured_at="2026-10-18 12:00:00")

    violations = validate_published_file(document, SCHEMA)

    assert {v.path for v in violations} == {
        "/stations/0/is_renting",
        "/stations/0/captured_at",
    }


def test_validate_published_file_returns_no_violation_for_a_valid_file() -> None:
    assert validate_published_file(_document(), SCHEMA) == []
