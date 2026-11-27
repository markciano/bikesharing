"""Tests of the maintenance decisions: compaction, retention and the daily run."""

from datetime import UTC, date, datetime, time, timedelta, tzinfo
from zoneinfo import ZoneInfo

import pytest

from bikesharing.core.delta_maintenance import (
    Partition,
    first_open_day,
    is_maintenance_run,
    partitions_to_compact,
    partitions_to_delete,
    retention_start,
)

MADRID = ZoneInfo("Europe/Madrid")
LOOKBACK = timedelta(minutes=15)
FIRST_OPEN_DAY = date(2026, 11, 27)
MAINTENANCE_TIME = time(4, 0)
WINDOW = timedelta(minutes=15)


def _partition(day: date, files: int = 1) -> Partition:
    return Partition(values=(("local_date", day.isoformat()),), day=day, files=files)


# Verifies d010 R12
@pytest.mark.parametrize(
    ("today", "start"),
    [
        (date(2026, 11, 30), date(2025, 11, 1)),
        (date(2026, 12, 1), date(2025, 12, 1)),
        (date(2026, 12, 31), date(2025, 12, 1)),
        (date(2027, 1, 1), date(2026, 1, 1)),
        (date(2028, 2, 29), date(2027, 2, 1)),
    ],
    ids=["month-end", "month-start", "year-end", "year-start", "leap-day"],
)
def test_retention_start_is_first_day_of_month_twelve_months_before(
    today: date, start: date
) -> None:
    assert retention_start(today, months=12) == start


# Verifies d010 R12
def test_retention_start_crosses_the_year_when_months_exceed_the_current_one() -> None:
    assert retention_start(date(2027, 1, 15), months=1) == date(2026, 12, 1)


# Verifies d010 R12
@pytest.mark.parametrize(
    ("today", "leaving"),
    [
        (date(2026, 12, 1), date(2025, 11, 30)),
        (date(2027, 1, 1), date(2025, 12, 31)),
    ],
    ids=["month-edge", "year-edge"],
)
def test_partitions_to_delete_takes_every_day_before_the_window(
    today: date, leaving: date
) -> None:
    oldest = _partition(date(2025, 10, 1))
    last_outside = _partition(leaving)
    first_inside = _partition(leaving + timedelta(days=1))

    deleted = partitions_to_delete(
        [oldest, last_outside, first_inside],
        start=retention_start(today, months=12),
    )

    assert deleted == [oldest, last_outside]


# Verifies d010 R13
def test_partitions_to_delete_keeps_the_first_day_of_the_window_and_later_ones() -> (
    None
):
    start = date(2025, 12, 1)
    inside = [
        _partition(start),
        _partition(date(2025, 12, 2)),
        _partition(date(2026, 12, 1)),
    ]

    assert partitions_to_delete(inside, start=start) == []


@pytest.mark.parametrize(
    ("files", "compacted"),
    [(1, False), (2, True), (30, True)],
    ids=["one-file", "two-files", "many-files"],
)
def test_partitions_to_compact_takes_a_closed_partition_with_more_than_one_file(
    files: int, compacted: bool
) -> None:
    closed = _partition(FIRST_OPEN_DAY - timedelta(days=1), files)

    due = partitions_to_compact([closed], first_open_day=FIRST_OPEN_DAY, threshold=10)

    assert due == ([closed] if compacted else [])


@pytest.mark.parametrize(
    ("day", "files", "compacted"),
    [
        (FIRST_OPEN_DAY, 9, False),
        (FIRST_OPEN_DAY, 10, True),
        (FIRST_OPEN_DAY + timedelta(days=1), 11, True),
    ],
    ids=["below-threshold", "at-threshold", "later-day-over-threshold"],
)
def test_partitions_to_compact_takes_an_open_partition_from_the_threshold(
    day: date, files: int, compacted: bool
) -> None:
    open_partition = _partition(day, files)

    due = partitions_to_compact(
        [open_partition], first_open_day=FIRST_OPEN_DAY, threshold=10
    )

    assert due == ([open_partition] if compacted else [])


def test_partitions_to_compact_leaves_open_partitions_when_there_is_no_threshold() -> (
    None
):
    closed = _partition(FIRST_OPEN_DAY - timedelta(days=1), files=2)
    open_partition = _partition(FIRST_OPEN_DAY, files=100)

    due = partitions_to_compact(
        [closed, open_partition], first_open_day=FIRST_OPEN_DAY, threshold=None
    )

    assert due == [closed]


@pytest.mark.parametrize(
    ("latest_capture", "timezone", "day"),
    [
        (datetime(2026, 11, 27, 0, 10, tzinfo=UTC), UTC, date(2026, 11, 26)),
        (datetime(2026, 11, 27, 0, 15, tzinfo=UTC), UTC, date(2026, 11, 27)),
        (datetime(2026, 11, 26, 23, 10, tzinfo=UTC), MADRID, date(2026, 11, 26)),
        (datetime(2026, 11, 26, 23, 15, tzinfo=UTC), MADRID, date(2026, 11, 27)),
    ],
    ids=[
        "utc-within-lookback",
        "utc-lookback-over",
        "madrid-within-lookback",
        "madrid-lookback-over",
    ],
)
def test_first_open_day_is_the_local_date_of_the_capture_minus_the_lookback(
    latest_capture: datetime, timezone: tzinfo, day: date
) -> None:
    assert first_open_day(latest_capture, lookback=LOOKBACK, timezone=timezone) == day


# 04:00 in Madrid is 03:00 UTC in winter and 02:00 UTC in summer.
@pytest.mark.parametrize(
    ("started_at", "is_maintenance"),
    [
        (datetime(2026, 11, 27, 2, 59, 59, tzinfo=UTC), False),
        (datetime(2026, 11, 27, 3, 0, tzinfo=UTC), True),
        (datetime(2026, 11, 27, 3, 14, 59, 999999, tzinfo=UTC), True),
        (datetime(2026, 11, 27, 3, 15, tzinfo=UTC), False),
        (datetime(2026, 7, 27, 2, 0, tzinfo=UTC), True),
        (datetime(2026, 7, 27, 3, 0, tzinfo=UTC), False),
    ],
    ids=[
        "before-window",
        "window-start",
        "just-before-end",
        "window-end",
        "summer-window-start",
        "summer-an-hour-late",
    ],
)
def test_is_maintenance_run_holds_only_within_the_local_window(
    started_at: datetime, is_maintenance: bool
) -> None:
    result = is_maintenance_run(
        started_at, local_time=MAINTENANCE_TIME, window=WINDOW, timezone=MADRID
    )

    assert result is is_maintenance
