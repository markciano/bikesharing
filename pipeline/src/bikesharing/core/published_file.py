"""Builds the published file from gold's rows and validates it against its schema.

The file ``latest-station-count.json`` is the contract between the pipeline
and the page, declared as a JSON Schema in ``contracts/``. The run deploys a
file only if it passes that schema, and logs each violation with its path in
the file otherwise (d008, Publishing).
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from jsonschema import Draft202012Validator


@dataclass(frozen=True, slots=True)
class Violation:
    """A rule of the schema that the file breaks.

    Attributes
    ----------
    path : str
        Where in the file, as a JSON Pointer (RFC 6901); ``""`` is the whole
        file.
    message : str
        What the schema rejects there, as ``jsonschema`` words it.
    """

    path: str
    message: str


def build_published_file(stations: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Build the published document from the rows of ``latest_station_count``.

    Parameters
    ----------
    stations : Sequence[Mapping[str, object]]
        One row per station, with gold's columns: ``system`` and
        ``station_id`` (str), ``num_vehicles_available`` and
        ``num_docks_available`` (int or None), ``is_renting`` and
        ``is_returning`` (bool), ``last_reported`` and ``captured_at``
        (datetime with a time zone).

    Returns
    -------
    dict[str, object]
        ``data_instant``, the latest ``captured_at``, and ``stations``, the
        rows sorted by system and ``station_id``; every instant is written in
        RFC 3339, in UTC with ``Z``.

    Raises
    ------
    ValueError
        If there are no rows, or a ``captured_at`` is not a datetime with a
        time zone, or any instant has no time zone.
    """
    if not stations:
        raise ValueError("the published file needs at least one station")
    data_instant = max(_aware(row["captured_at"]) for row in stations)
    ordered = sorted(
        stations, key=lambda row: (str(row["system"]), str(row["station_id"]))
    )
    return {
        "data_instant": _rfc3339(data_instant),
        "stations": [_serialized(row) for row in ordered],
    }


def validate_published_file(
    document: object, schema: Mapping[str, object]
) -> list[Violation]:
    """Validate the published document against its JSON Schema (DQR14).

    Parameters
    ----------
    document : object
        The document to publish.
    schema : Mapping[str, object]
        The contents of ``contracts/latest-station-count.schema.json``.

    Returns
    -------
    list[Violation]
        Every violation, with its path in the document; empty when the
        document passes.
    """
    validator = Draft202012Validator(schema)
    return [
        Violation(path=_json_pointer(error.absolute_path), message=error.message)
        for error in validator.iter_errors(document)
    ]


def _serialized(row: Mapping[str, object]) -> dict[str, object]:
    return {
        name: _rfc3339(_aware(value)) if isinstance(value, datetime) else value
        for name, value in row.items()
    }


def _aware(value: object) -> datetime:
    # An instant with no time zone cannot be placed in UTC without a guess,
    # and the file states every instant in UTC.
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"expected a datetime with a time zone, not {value!r}")
    return value


def _rfc3339(instant: datetime) -> str:
    return instant.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _json_pointer(path: Iterable[str | int]) -> str:
    return "".join(
        "/" + str(part).replace("~", "~0").replace("/", "~1") for part in path
    )
