"""Decides what compaction, retention and the daily maintenance act on.

Every decision is taken on the table's state as its log gives it, not on what
earlier runs did, so a run that fails or is skipped is caught up by the next
one that runs (ADR-0052, Delta maintenance and access pattern).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo


@dataclass(frozen=True, slots=True)
class Partition:
    """A partition of a table, as its log describes it.

    Attributes
    ----------
    values : tuple[tuple[str, str], ...]
        Its (column, value) pairs, in the table's partition order, as the log
        writes them.
    day : date
        The value of its date column, ``utc_date`` or ``local_date``.
    files : int
        The number of its data files.
    """

    values: tuple[tuple[str, str], ...]
    day: date
    files: int


@dataclass(frozen=True, slots=True)
class CompactionMetrics:
    """What a compaction changed.

    Attributes
    ----------
    partitions : int
        The partitions compacted.
    files_removed : int
        The data files the compaction replaced.
    files_added : int
        The data files it wrote.
    """

    partitions: int
    files_removed: int
    files_added: int


@dataclass(frozen=True, slots=True)
class RetentionMetrics:
    """What retention deleted.

    Attributes
    ----------
    partitions_deleted : int
        The partitions deleted.
    rows_deleted : int
        The rows they held.
    """

    partitions_deleted: int
    rows_deleted: int


def first_open_day(
    latest_capture: datetime, *, lookback: timedelta, timezone: tzinfo
) -> date:
    """Return the earliest day whose partition a later batch can still write to.

    Parameters
    ----------
    latest_capture : datetime
        The latest capture instant of the batch, timezone-aware.
    lookback : timedelta
        How far before the latest processed capture a later batch can reach.
    timezone : tzinfo
        The timezone of the table's date column.

    Returns
    -------
    date
        The date, in ``timezone``, of ``latest_capture`` minus ``lookback``;
        a partition of an earlier day is closed.
    """
    return (latest_capture - lookback).astimezone(timezone).date()


def partitions_to_compact(
    partitions: Iterable[Partition], *, first_open_day: date, threshold: int | None
) -> list[Partition]:
    """Return the partitions due for compaction.

    Parameters
    ----------
    partitions : Iterable[Partition]
        The table's partitions.
    first_open_day : date
        The earliest day still open to writes.
    threshold : int | None
        The data files from which an open partition is compacted; None never
        compacts an open one.

    Returns
    -------
    list[Partition]
        Every closed partition with more than one data file, and every open one
        with at least ``threshold`` files, in the order received.
    """
    due: list[Partition] = []
    for partition in partitions:
        if partition.day < first_open_day:
            is_due = partition.files > 1
        else:
            is_due = threshold is not None and partition.files >= threshold
        if is_due:
            due.append(partition)
    return due


def retention_start(today: date, *, months: int) -> date:
    """Return the first day the retention window keeps.

    Parameters
    ----------
    today : date
        The current local date.
    months : int
        The whole months kept before the month of ``today``.

    Returns
    -------
    date
        The first day of the month of ``today`` minus ``months``.
    """
    year, month_index = divmod(today.year * 12 + today.month - 1 - months, 12)
    return date(year, month_index + 1, 1)


def partitions_to_delete(
    partitions: Iterable[Partition], *, start: date
) -> list[Partition]:
    """Return the partitions outside the retention window.

    Parameters
    ----------
    partitions : Iterable[Partition]
        The table's partitions.
    start : date
        The first day the window keeps.

    Returns
    -------
    list[Partition]
        Every partition whose day is before ``start``, in the order received;
        empty while all are inside the window.
    """
    return [partition for partition in partitions if partition.day < start]


def is_maintenance_run(
    started_at: datetime, *, local_time: time, window: timedelta, timezone: tzinfo
) -> bool:
    """Return whether a run is the one that does the daily maintenance.

    Parameters
    ----------
    started_at : datetime
        The run's start instant, timezone-aware.
    local_time : time
        The local time the maintenance window opens, naive.
    window : timedelta
        The window's length.
    timezone : tzinfo
        The timezone of ``local_time``.

    Returns
    -------
    bool
        Whether ``started_at``, in ``timezone``, falls within
        ``[local_time, local_time + window)`` of its day.
    """
    local = started_at.astimezone(timezone)
    opens_at = datetime.combine(local.date(), local_time, tzinfo=timezone)
    return opens_at <= local < opens_at + window
