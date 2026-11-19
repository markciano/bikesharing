"""Tests of the discovery: bronze keys, the listing plan and the pending objects."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from bikesharing.core.discovery import (
    BronzeObject,
    InvalidBronzeKey,
    ListingPlan,
    bronze_key,
    parse_bronze_key,
    parse_exclusion_list,
    pending_objects,
    plan_listing,
)

CONTRACT = Path(__file__).parents[4] / "contracts" / "bronze-keys.json"
VECTORS: dict[str, Any] = json.loads(CONTRACT.read_text())
RAW_VALID = [case for case in VECTORS["valid"] if case["kind"] == "raw"]
RAW_INVALID = [case for case in VECTORS["invalid"] if case["key"].startswith("raw/")]

MADRID = ZoneInfo("Europe/Madrid")
LOOKBACK = timedelta(hours=1)


def _instant(text: str) -> datetime:
    return datetime.fromisoformat(text)


def _key(stamp: str, system: str = "bicing") -> str:
    """Return a station_status key for a ``YYYYMMDDTHHMMSSZ`` stamp."""
    date = f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]}"
    return f"raw/{system}/station_status/{date}/{stamp}.json.gz"


# Contract consumer: contracts/bronze-keys.json, raw keys.


@pytest.mark.parametrize("case", RAW_VALID, ids=lambda case: case["name"])
def test_parse_bronze_key_reads_source_feed_and_instant_from_valid_key(
    case: dict[str, str],
) -> None:
    parsed = parse_bronze_key(case["key"])

    assert parsed == BronzeObject(
        key=case["key"],
        system=case["source"],  # type: ignore[arg-type]
        feed=case["feed"],
        captured_at=_instant(case["captured_at"]).replace(microsecond=0),
    )


@pytest.mark.parametrize("case", RAW_VALID, ids=lambda case: case["name"])
def test_bronze_key_builds_contract_key_from_capture_instant(
    case: dict[str, str],
) -> None:
    key = bronze_key(
        case["source"],  # type: ignore[arg-type]
        case["feed"],
        _instant(case["captured_at"]),
    )

    assert key == case["key"]


@pytest.mark.parametrize("case", RAW_INVALID, ids=lambda case: case["reason"])
def test_parse_bronze_key_raises_on_key_breaking_contract(
    case: dict[str, str],
) -> None:
    with pytest.raises(InvalidBronzeKey):
        parse_bronze_key(case["key"])


@pytest.mark.parametrize(
    "key",
    [
        "raw/citybike/station_status/2026-10-18/20261018T120000Z.json.gz",
        "logs/date=2026-10-18/20261018T120003Z.jsonl",
    ],
    ids=["unknown system", "log key"],
)
def test_parse_bronze_key_raises_on_key_outside_systems_raw_objects(key: str) -> None:
    with pytest.raises(InvalidBronzeKey):
        parse_bronze_key(key)


# Listing plan (d008 #7, Discovery of pending objects).


def test_plan_listing_sweeps_whole_prefix_when_nothing_is_processed() -> None:
    plan = plan_listing(
        "ambici",
        None,
        now=datetime(2026, 10, 18, 12, 0, tzinfo=UTC),
        lookback=LOOKBACK,
        timezone=MADRID,
    )

    assert plan == ListingPlan(
        system="ambici",
        prefix="raw/ambici/station_status/",
        start_after=None,
        full_sweep=True,
    )


def test_plan_listing_lists_after_latest_minus_lookback_on_same_local_date() -> None:
    plan = plan_listing(
        "bicing",
        datetime(2026, 10, 18, 11, 30, 5, tzinfo=UTC),
        now=datetime(2026, 10, 18, 11, 40, tzinfo=UTC),
        lookback=LOOKBACK,
        timezone=MADRID,
    )

    assert plan == ListingPlan(
        system="bicing",
        prefix="raw/bicing/station_status/",
        start_after=_key("20261018T103005Z"),
        full_sweep=False,
    )


def test_plan_listing_sweeps_whole_prefix_on_first_run_after_local_midnight() -> None:
    # 21:59Z and 22:01Z fall on either side of midnight in Madrid (UTC+2),
    # though both are on the same UTC date.
    plan = plan_listing(
        "bicing",
        datetime(2026, 10, 18, 21, 59, tzinfo=UTC),
        now=datetime(2026, 10, 18, 22, 1, tzinfo=UTC),
        lookback=LOOKBACK,
        timezone=MADRID,
    )

    assert plan.full_sweep is True
    assert plan.start_after is None


def test_plan_listing_lists_incrementally_after_utc_midnight_within_local_day() -> None:
    # 23:30Z and 00:10Z are on different UTC dates but the same day in Madrid.
    plan = plan_listing(
        "bicing",
        datetime(2026, 10, 18, 23, 30, tzinfo=UTC),
        now=datetime(2026, 10, 19, 0, 10, tzinfo=UTC),
        lookback=LOOKBACK,
        timezone=MADRID,
    )

    assert plan.full_sweep is False
    assert plan.start_after == _key("20261018T223000Z")


def test_plan_listing_raises_on_naive_instant() -> None:
    with pytest.raises(ValueError):
        plan_listing(
            "bicing",
            datetime(2026, 10, 18, 11, 30),
            now=datetime(2026, 10, 18, 11, 40, tzinfo=UTC),
            lookback=LOOKBACK,
            timezone=MADRID,
        )


# Exclusion list (d008 #8, Unreadable objects).


def test_parse_exclusion_list_returns_keys_skipping_blank_and_comment_lines() -> None:
    text = (
        "# Unreadable bronze objects, one per line.\n"
        "\n"
        f"{_key('20261018T120000Z')} # truncated gzip\n"
        f"  {_key('20261018T120100Z', 'ambici')}   #   not JSON  \n"
    )

    assert parse_exclusion_list(text) == frozenset(
        {_key("20261018T120000Z"), _key("20261018T120100Z", "ambici")}
    )


@pytest.mark.parametrize(
    "line",
    [
        _key("20261018T120000Z"),
        f"{_key('20261018T120000Z')} #",
        f"{_key('20261018T120000Z')} #  ",
    ],
    ids=["no marker", "empty reason", "blank reason"],
)
def test_parse_exclusion_list_raises_on_line_without_reason(line: str) -> None:
    with pytest.raises(ValueError):
        parse_exclusion_list(line + "\n")


# Pending objects (d008 #7 and #8).


def test_pending_objects_drops_processed_and_excluded_keys() -> None:
    processed, excluded, pending = (
        _key("20261018T120000Z"),
        _key("20261018T120100Z"),
        _key("20261018T120200Z"),
    )

    result = pending_objects(
        [processed, excluded, pending], frozenset({processed}), frozenset({excluded})
    )

    assert [obj.key for obj in result] == [pending]


def test_pending_objects_orders_oldest_first_then_by_key() -> None:
    later = _key("20261018T120100Z", "ambici")
    same_instant_bicing = _key("20261018T120000Z", "bicing")
    same_instant_ambici = _key("20261018T120000Z", "ambici")

    result = pending_objects(
        [later, same_instant_bicing, same_instant_ambici], frozenset(), frozenset()
    )

    assert [obj.key for obj in result] == [
        same_instant_ambici,
        same_instant_bicing,
        later,
    ]


def test_pending_objects_raises_on_listed_key_that_does_not_parse() -> None:
    with pytest.raises(InvalidBronzeKey):
        pending_objects(
            ["raw/bicing/station_status/2026-10-18/20261018T120000Z.json"],
            frozenset(),
            frozenset(),
        )
