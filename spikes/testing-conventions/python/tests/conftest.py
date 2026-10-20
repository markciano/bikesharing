"""Shared fixtures for the Python PoC tests (spike s008, P1).

Function-scoped on purpose (python.md): each test gets a fresh object.
"""

from collections.abc import Callable
from datetime import datetime, timezone

import pytest


@pytest.fixture
def now() -> datetime:
    """Fixed UTC time: code under test never reads the clock."""
    return datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def make_payload() -> Callable[[list[dict]], dict]:
    """Build a GBFS station_status payload from a list of station dicts."""

    def _make(stations: list[dict]) -> dict:
        return {
            "last_updated": 1792324800,
            "ttl": 60,
            "version": "2.3",
            "data": {"stations": stations},
        }

    return _make


@pytest.fixture
def make_station() -> Callable[..., dict]:
    """Build one GBFS station dict; only `last_reported` varies per test."""

    def _make(station_id: str = "1", last_reported: int = 1792324790) -> dict:
        return {
            "station_id": station_id,
            "num_bikes_available": 5,
            "num_docks_available": 15,
            "is_installed": True,
            "is_renting": True,
            "is_returning": True,
            "last_reported": last_reported,
        }

    return _make
