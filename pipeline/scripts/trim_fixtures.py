"""Write the pipeline's bronze fixtures and their manifest from a local sample.

The sample is a folder of bronze ``station_status`` objects at their bronze
keys as relative paths. Each fixture is one sampled object, kept at its key,
trimmed to a few stations and gzip-compressed; a variety no sampled object
carries is a copy of a sampled object with one change, marked as derived in
the manifest (ADR-0037, Trimmed source samples are committed as test
fixtures). The script checks in the sample that each variety holds, so a new
sample that lacks one fails instead of writing a wrong fixture.

Run from the project root::

    uv run --directory pipeline python scripts/trim_fixtures.py <sample folder>
"""

import argparse
import gzip
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "bronze"
MANIFEST = "manifest.json"
FEED = "station_status"
ADDED_FIELD = "added_field"
BICING_ATTRIBUTION = (
    "Bicing GBFS feed (system_id bike_barcelona), Barcelona. The feed has no "
    "licence fields (CC0 by the GBFS 3.0 default); attributed as good practice."
)
BICING_OPTIONAL_FIELDS = ("num_vehicles_disabled", "num_docks_disabled")

type Station = dict[str, Any]
type Change = Callable[[list[Station]], None]


@dataclass(frozen=True)
class Fixture:
    """One fixture: the sampled object it comes from and what it shows.

    Attributes
    ----------
    key : str
        The bronze key the object is read from and the fixture written at.
    stations : tuple[str, ...]
        The station IDs kept, each of which the sampled object must hold.
    variety : str
        What the fixture shows, as the manifest states it.
    absent : tuple[str, ...]
        Station IDs the sampled object must not hold.
    out_of_service : tuple[str, ...]
        Kept station IDs that must be out of service in the sampled object.
    derived : str | None
        The change made to the sampled object, or None for a captured one.
    change : Change | None
        The function that makes that change on the kept stations.
    """

    key: str
    stations: tuple[str, ...]
    variety: str
    absent: tuple[str, ...] = ()
    out_of_service: tuple[str, ...] = ()
    derived: str | None = None
    change: Change | None = field(default=None, compare=False)


def _add_field(stations: list[Station]) -> None:
    stations[0][ADDED_FIELD] = 1


def _drop_bicing_optional_fields(stations: list[Station]) -> None:
    for name in BICING_OPTIONAL_FIELDS:
        del stations[0][name]


FIXTURES: tuple[Fixture, ...] = (
    Fixture(
        key="raw/ambici/station_status/2026-10-19/20261019T085745Z.json.gz",
        stations=("189004148", "444880309", "563557729"),
        variety="the capture before station 563557729 is removed",
    ),
    Fixture(
        key="raw/ambici/station_status/2026-10-19/20261019T085845Z.json.gz",
        stations=("189004148", "444880309"),
        absent=("563557729",),
        variety="the capture after station 563557729 is removed",
    ),
    Fixture(
        key="raw/ambici/station_status/2026-10-19/20261019T085945Z.json.gz",
        stations=("189004148", "444880309"),
        variety="a station with a field outside the read schema",
        derived=f"`{ADDED_FIELD}` added to the first station",
        change=_add_field,
    ),
    Fixture(
        key="raw/bicing/station_status/2026-10-22/20261022T074219Z.json.gz",
        stations=("1", "245", "396"),
        out_of_service=("245",),
        variety="a station out of service (245), and the capture before station 396 is removed",
    ),
    Fixture(
        key="raw/bicing/station_status/2026-10-22/20261022T074319Z.json.gz",
        stations=("1", "245"),
        absent=("396",),
        out_of_service=("245",),
        variety="the capture after station 396 is removed",
    ),
    Fixture(
        key="raw/bicing/station_status/2026-10-22/20261022T074419Z.json.gz",
        stations=("1", "245"),
        variety="a station without GBFS's optional fields",
        derived=f"{', '.join(BICING_OPTIONAL_FIELDS)} removed from the first station",
        change=_drop_bicing_optional_fields,
    ),
    Fixture(
        key="raw/bicing/station_status/2026-10-22/20261022T074519Z.json.gz",
        stations=("1", "245"),
        variety="a station with a field outside the read schema",
        derived=f"`{ADDED_FIELD}` added to the first station",
        change=_add_field,
    ),
)


def _captured_at(key: str) -> str:
    """Return the capture instant of a bronze key, as RFC 3339 in UTC.

    Parameters
    ----------
    key : str
        A bronze key, whose file name is the instant as ``YYYYMMDDTHHMMSSZ``.

    Returns
    -------
    str
        The instant, e.g. ``2026-10-19T08:57:45Z``.
    """
    stamp = key.rsplit("/", 1)[1].split(".", 1)[0]
    return f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]}T{stamp[9:11]}:{stamp[11:13]}:{stamp[13:15]}Z"


def _trim(sample: Path, fixture: Fixture) -> dict[str, Any]:
    """Return the fixture's object: the sampled one, trimmed and changed.

    Parameters
    ----------
    sample : Path
        The sample folder.
    fixture : Fixture
        The fixture to build.

    Returns
    -------
    dict[str, Any]
        The object, with only the kept stations, in their published order.

    Raises
    ------
    ValueError
        If the sampled object does not show the fixture's variety.
    """
    obj: dict[str, Any] = json.loads(
        gzip.decompress((sample / fixture.key).read_bytes())
    )
    by_id = {s["station_id"]: s for s in obj["data"]["stations"]}
    missing = set(fixture.stations) - set(by_id)
    present = set(fixture.absent) & set(by_id)
    serving = {sid for sid in fixture.out_of_service if by_id[sid]["is_renting"]}
    if missing or present or serving:
        raise ValueError(
            f"{fixture.key}: missing {sorted(missing)}, present {sorted(present)}, "
            f"in service {sorted(serving)}"
        )
    kept = [s for s in obj["data"]["stations"] if s["station_id"] in fixture.stations]
    if fixture.change is not None:
        fixture.change(kept)
    obj["data"]["stations"] = kept
    return obj


def _manifest_entry(fixture: Fixture) -> dict[str, str]:
    """Return the fixture's provenance, as the manifest lists it.

    Parameters
    ----------
    fixture : Fixture
        The fixture.

    Returns
    -------
    dict[str, str]
        Its key, source, feed, capture instant, variety, change if derived,
        and attribution for Bicing.
    """
    source = fixture.key.split("/")[1]
    entry = {
        "key": fixture.key,
        "source": source,
        "feed": FEED,
        "captured_at": _captured_at(fixture.key),
        "variety": fixture.variety,
    }
    if fixture.derived is not None:
        entry["derived"] = fixture.derived
    if source == "bicing":
        entry["attribution"] = BICING_ATTRIBUTION
    return entry


def main() -> None:
    """Write every fixture and the manifest to the fixtures folder."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "sample", type=Path, help="folder of bronze objects at their keys"
    )
    sample: Path = parser.parse_args().sample
    for fixture in FIXTURES:
        target = FIXTURES_DIR / fixture.key
        target.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(_trim(sample, fixture), ensure_ascii=False).encode()
        # mtime 0 keeps the gzip bytes the same on every run, so Git sees no change.
        target.write_bytes(gzip.compress(body, mtime=0))
    manifest = [_manifest_entry(fixture) for fixture in FIXTURES]
    (FIXTURES_DIR / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
