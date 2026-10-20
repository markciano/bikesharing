"""Station status parsing and staleness (spike s008, P1).

Input: a GBFS `station_status` payload (dict).
Output: `Station` records and the subset that has not reported recently.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class Station:
    station_id: str
    num_bikes_available: int
    num_docks_available: int
    last_reported: datetime  # UTC


def parse_stations(payload: dict) -> list[Station]:
    return [
        Station(
            station_id=s["station_id"],
            num_bikes_available=s["num_bikes_available"],
            num_docks_available=s["num_docks_available"],
            last_reported=datetime.fromtimestamp(s["last_reported"], tz=timezone.utc),
        )
        for s in payload["data"]["stations"]
    ]


def find_stale(stations: list[Station], now: datetime, max_age: timedelta) -> list[Station]:
    # `now` is a parameter so the result never depends on the clock.
    return [s for s in stations if now - s.last_reported >= max_age]
