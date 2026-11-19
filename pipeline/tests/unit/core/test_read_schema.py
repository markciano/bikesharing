"""Tests of the read schema of each system's ``station_status``.

The expected values are each system's field dictionary in its source card,
with the JSON type as published (d008, Bronze reading).
"""

import pytest

from bikesharing.core.read_schema import STATION_FIELDS, STATION_STATUS_COLUMNS
from bikesharing.core.settings import System

AMBICI_DATA = (
    "STRUCT(stations STRUCT("
    "station_id VARCHAR, "
    "num_bikes_available INTEGER, "
    "vehicle_types_available STRUCT(vehicle_type_id VARCHAR, count INTEGER)[], "
    "num_docks_available INTEGER, "
    "is_installed BOOLEAN, "
    "is_renting BOOLEAN, "
    "is_returning BOOLEAN, "
    "last_reported BIGINT"
    ")[])"
)

BICING_DATA = (
    "STRUCT(stations STRUCT("
    "station_id VARCHAR, "
    "num_vehicles_available INTEGER, "
    "vehicle_types_available STRUCT(vehicle_type_id VARCHAR, count INTEGER)[], "
    "num_vehicles_disabled INTEGER, "
    "num_docks_available INTEGER, "
    "num_docks_disabled INTEGER, "
    "vehicle_docks_available STRUCT(vehicle_type_ids VARCHAR[], count INTEGER)[], "
    "is_installed BOOLEAN, "
    "is_renting BOOLEAN, "
    "is_returning BOOLEAN, "
    "last_reported VARCHAR"
    ")[])"
)


def test_station_status_columns_cover_both_systems() -> None:
    assert set(STATION_STATUS_COLUMNS) == {"ambici", "bicing"}


@pytest.mark.parametrize(
    ("system", "expected"),
    [
        (
            "ambici",
            {
                "last_updated": "BIGINT",
                "ttl": "INTEGER",
                "version": "VARCHAR",
                "data": AMBICI_DATA,
            },
        ),
        (
            "bicing",
            {
                "last_updated": "VARCHAR",
                "ttl": "INTEGER",
                "version": "VARCHAR",
                "data": BICING_DATA,
            },
        ),
    ],
)
def test_station_status_columns_declare_source_card_fields_with_published_types(
    system: System, expected: dict[str, str]
) -> None:
    assert dict(STATION_STATUS_COLUMNS[system]) == expected


@pytest.mark.parametrize(
    ("system", "expected"),
    [
        (
            "ambici",
            {
                "station_id",
                "num_bikes_available",
                "vehicle_types_available",
                "num_docks_available",
                "is_installed",
                "is_renting",
                "is_returning",
                "last_reported",
            },
        ),
        (
            "bicing",
            {
                "station_id",
                "num_vehicles_available",
                "vehicle_types_available",
                "num_vehicles_disabled",
                "num_docks_available",
                "num_docks_disabled",
                "vehicle_docks_available",
                "is_installed",
                "is_renting",
                "is_returning",
                "last_reported",
            },
        ),
    ],
)
def test_station_fields_list_the_station_struct_fields_of_each_system(
    system: System, expected: set[str]
) -> None:
    assert STATION_FIELDS[system] == expected
