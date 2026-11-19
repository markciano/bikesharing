"""Tests of the batching: end instant, batches, time budget and stage end."""

from datetime import UTC, datetime, timedelta

import pytest

from bikesharing.core.batching import (
    Batch,
    may_start_batch,
    plan_batches,
    stage_drained,
    within_end_instant,
)
from bikesharing.core.discovery import BronzeObject, bronze_key
from bikesharing.core.settings import System

START = datetime(2026, 10, 14, 10, 0, tzinfo=UTC)
BUDGET = timedelta(seconds=30)


def _object(minute: int, system: System = "bicing") -> BronzeObject:
    captured_at = START + timedelta(minutes=minute)
    return BronzeObject(
        key=bronze_key(system, "station_status", captured_at),
        system=system,
        feed="station_status",
        captured_at=captured_at,
    )


# Verifies d008 R13
def test_plan_batches_splits_objects_into_batches_of_at_most_the_bound() -> None:
    objects = [_object(minute) for minute in range(5)]

    batches = plan_batches(objects, max_objects=2)

    assert batches == [
        Batch(number=1, objects=tuple(objects[0:2])),
        Batch(number=2, objects=tuple(objects[2:4])),
        Batch(number=3, objects=tuple(objects[4:5])),
    ]


def test_plan_batches_keeps_the_input_order_across_systems() -> None:
    objects = [_object(0, "ambici"), _object(0, "bicing"), _object(1, "ambici")]

    batches = plan_batches(objects, max_objects=2)

    assert [obj for batch in batches for obj in batch.objects] == objects


def test_plan_batches_returns_no_batch_without_objects() -> None:
    assert plan_batches([], max_objects=2) == []


def test_plan_batches_raises_on_bound_below_one() -> None:
    with pytest.raises(ValueError):
        plan_batches([_object(0)], max_objects=0)


def test_batch_reports_its_first_and_last_capture() -> None:
    batch = Batch(number=1, objects=(_object(0), _object(1), _object(2)))

    assert (batch.first_capture, batch.last_capture) == (
        START,
        START + timedelta(minutes=2),
    )


# Verifies d008 R12
@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        (timedelta(0), True),
        (timedelta(seconds=29), True),
        (timedelta(seconds=30), False),
        (timedelta(seconds=31), False),
    ],
    ids=["at start", "just within", "budget spent", "past budget"],
)
def test_may_start_batch_only_while_the_budget_is_not_spent(
    elapsed: timedelta, expected: bool
) -> None:
    assert (
        may_start_batch(run_started=START, now=START + elapsed, budget=BUDGET)
        is expected
    )


# Verifies d008 R18
def test_within_end_instant_keeps_objects_captured_before_it_oldest_first() -> None:
    end_instant = START + timedelta(minutes=2)
    objects = [_object(1), _object(0), _object(2), _object(3)]

    assert within_end_instant(objects, end_instant) == [_object(0), _object(1)]


def test_within_end_instant_keeps_every_object_without_end_instant() -> None:
    objects = [_object(0), _object(1)]

    assert within_end_instant(objects, None) == objects


# Verifies d008 R19
def test_stage_drained_with_end_instant_and_no_object_before_it() -> None:
    assert stage_drained([_object(5)], START + timedelta(minutes=5)) is True


@pytest.mark.parametrize(
    ("objects", "end_instant"),
    [
        ([_object(4)], START + timedelta(minutes=5)),
        ([], None),
        ([_object(0)], None),
    ],
    ids=[
        "object before end instant",
        "no end instant, nothing pending",
        "no end instant",
    ],
)
def test_stage_not_drained_with_object_before_end_instant_or_without_one(
    objects: list[BronzeObject], end_instant: datetime | None
) -> None:
    assert stage_drained(objects, end_instant) is False
