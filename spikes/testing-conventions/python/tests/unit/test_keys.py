"""Unit tests for poc.keys: bronze-side parser of the ADR-0012 key."""

from datetime import datetime, timezone

import pytest

from poc.keys import parse_key


def test_parse_key_returns_source_feed_and_utc_timestamp():
    key = "raw/bicing/station_status/2026-10-18/20261018T120000Z.json.gz"

    source, feed, captured_at = parse_key(key)

    assert (source, feed) == ("bicing", "station_status")
    assert captured_at == datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)


def test_parse_key_timestamp_is_timezone_aware_utc():
    key = "raw/ambici/station_status/2026-10-19/20261019T001500Z.json.gz"

    _, _, captured_at = parse_key(key)

    assert captured_at.utcoffset() == timezone.utc.utcoffset(None)


@pytest.mark.parametrize(
    "key",
    [
        "raw/bicing/station_status/2026-10-18/20261018T120000Z.json",
        "raw/bicing/station_status/2026-10-18/20261018T120000.json.gz",
        "raw/bicing/station_status/2026-10-19/20261018T120000Z.json.gz",
        "raw/bicing/2026-10-18/20261018T120000Z.json.gz",
        "bronze/bicing/station_status/2026-10-18/20261018T120000Z.json.gz",
    ],
    ids=["extension", "no-z", "date-mismatch", "missing-segment", "wrong-prefix"],
)
def test_parse_key_rejects_key_that_breaks_the_contract(key):
    with pytest.raises(ValueError):
        parse_key(key)
