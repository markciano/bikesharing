"""Integration tests: file fixture to records, and the P4 consumer test of the collector contract."""

import gzip
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from poc.keys import parse_key
from poc.payload import decompress_payload
from poc.status import find_stale, parse_stations

TESTS = Path(__file__).resolve().parents[1]
CONTRACT = TESTS.parents[1] / "contract"
VECTORS = json.loads((CONTRACT / "collector-contract.json").read_text())


def test_file_fixture_becomes_records_with_the_stale_one_flagged(now):
    payload = json.loads((TESTS / "fixtures" / "station_status.json").read_text())

    stale = find_stale(parse_stations(payload), now, max_age=timedelta(minutes=10))

    assert [s.station_id for s in stale] == ["11"]


@pytest.mark.parametrize("case", VECTORS["valid"], ids=lambda c: c["name"])
def test_parse_key_accepts_every_valid_contract_vector(case):
    source, feed, captured_at = parse_key(case["key"])

    assert (source, feed) == (case["source"], case["feed"])
    assert captured_at == datetime.fromisoformat(case["captured_at"])


@pytest.mark.parametrize("case", VECTORS["invalid"], ids=lambda c: c["reason"])
def test_parse_key_rejects_every_invalid_contract_vector(case):
    with pytest.raises(ValueError):
        parse_key(case["key"])


def test_contract_fixture_gzipped_in_memory_is_read_back_unchanged():
    original = (CONTRACT / "fixtures" / "station_status.json").read_bytes()

    assert decompress_payload(gzip.compress(original)) == original
