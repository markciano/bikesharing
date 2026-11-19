"""The read schema of each system's ``station_status``, passed to dbt as variables.

Each schema declares every field of its system's field dictionary in its
source card, with the JSON type as published: a string as ``VARCHAR``, a
POSIX time as ``BIGINT`` and a count as ``INTEGER``. The staging models cast
and convert. An explicit schema keeps DuckDB from inferring one file by file,
and a row that does not fit it fails its batch (d008 #11, Bronze reading).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from bikesharing.core.settings import System

_VEHICLE_TYPES_AVAILABLE: Final = "STRUCT(vehicle_type_id VARCHAR, count INTEGER)[]"

_STATION_FIELD_TYPES: Final[Mapping[System, Mapping[str, str]]] = MappingProxyType(
    {
        "ambici": MappingProxyType(
            {
                "station_id": "VARCHAR",
                "num_bikes_available": "INTEGER",
                "vehicle_types_available": _VEHICLE_TYPES_AVAILABLE,
                "num_docks_available": "INTEGER",
                "is_installed": "BOOLEAN",
                "is_renting": "BOOLEAN",
                "is_returning": "BOOLEAN",
                "last_reported": "BIGINT",
            }
        ),
        "bicing": MappingProxyType(
            {
                "station_id": "VARCHAR",
                "num_vehicles_available": "INTEGER",
                "vehicle_types_available": _VEHICLE_TYPES_AVAILABLE,
                "num_vehicles_disabled": "INTEGER",
                "num_docks_available": "INTEGER",
                "num_docks_disabled": "INTEGER",
                "vehicle_docks_available": (
                    "STRUCT(vehicle_type_ids VARCHAR[], count INTEGER)[]"
                ),
                "is_installed": "BOOLEAN",
                "is_renting": "BOOLEAN",
                "is_returning": "BOOLEAN",
                "last_reported": "VARCHAR",
            }
        ),
    }
)

# AMBici publishes GBFS 2.3, with POSIX times; Bicing publishes GBFS 3.0, with
# RFC 3339 strings.
_LAST_UPDATED_TYPES: Final[Mapping[System, str]] = MappingProxyType(
    {"ambici": "BIGINT", "bicing": "VARCHAR"}
)


def _stations_struct(fields: Mapping[str, str]) -> str:
    """Return the ``data`` column's type: a struct holding the list of stations.

    Parameters
    ----------
    fields : Mapping[str, str]
        Each station field's name and DuckDB type, in the published order.

    Returns
    -------
    str
        The DuckDB type of ``data``, as ``read_json``'s ``columns`` takes it.
    """
    members = ", ".join(f"{name} {type_}" for name, type_ in fields.items())
    return f"STRUCT(stations STRUCT({members})[])"


STATION_STATUS_COLUMNS: Final[Mapping[System, Mapping[str, str]]] = MappingProxyType(
    {
        system: MappingProxyType(
            {
                "last_updated": _LAST_UPDATED_TYPES[system],
                "ttl": "INTEGER",
                "version": "VARCHAR",
                "data": _stations_struct(fields),
            }
        )
        for system, fields in _STATION_FIELD_TYPES.items()
    }
)
"""Per system, each top-level field of a ``station_status`` object and its DuckDB type."""

STATION_FIELDS: Final[Mapping[System, frozenset[str]]] = MappingProxyType(
    {system: frozenset(fields) for system, fields in _STATION_FIELD_TYPES.items()}
)
"""Per system, the station struct's field names: the declared fields DQR11 compares against."""
