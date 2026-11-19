"""Applies the end instant, splits the pending objects into batches and gates each batch.

A run drains its backlog oldest first in bounded batches, and opens no batch
once its time budget is spent, so it ends before its timeout (d008 D6,
Provisional run bounds). While the first load runs in stages, only objects
captured before the end instant are processed, and a run that finds none
reports that the stage has drained (d008 D8, First load in chronological
stages).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from bikesharing.core.discovery import BronzeObject


@dataclass(frozen=True, slots=True)
class Batch:
    """A batch of bronze objects processed together.

    Attributes
    ----------
    number : int
        The batch's number within the run, from 1.
    objects : tuple[BronzeObject, ...]
        Its objects, oldest first.
    """

    number: int
    objects: tuple[BronzeObject, ...]

    @property
    def first_capture(self) -> datetime:
        """datetime: The capture instant of the batch's oldest object."""
        return min(obj.captured_at for obj in self.objects)

    @property
    def last_capture(self) -> datetime:
        """datetime: The capture instant of the batch's newest object."""
        return max(obj.captured_at for obj in self.objects)


def within_end_instant(
    objects: Sequence[BronzeObject], end_instant: datetime | None
) -> list[BronzeObject]:
    """Return the objects captured before the end instant, oldest first.

    Parameters
    ----------
    objects : Sequence[BronzeObject]
        The pending objects.
    end_instant : datetime | None
        The end of the current stage, exclusive, or None for no stage.

    Returns
    -------
    list[BronzeObject]
        The objects captured before ``end_instant``, or all of them when it is
        None, ordered by capture instant, then by key.
    """
    # The end instant is the end of a local day, so the interval is half-open:
    # a capture at the next midnight belongs to the next stage.
    kept = [
        obj for obj in objects if end_instant is None or obj.captured_at < end_instant
    ]
    return sorted(kept, key=lambda obj: (obj.captured_at, obj.key))


def plan_batches(objects: Sequence[BronzeObject], max_objects: int) -> list[Batch]:
    """Split the objects into batches of at most ``max_objects``, in their order.

    Parameters
    ----------
    objects : Sequence[BronzeObject]
        The objects to process, oldest first.
    max_objects : int
        The batch bound.

    Returns
    -------
    list[Batch]
        The batches, numbered from 1; none when there are no objects.

    Raises
    ------
    ValueError
        If ``max_objects`` is below 1.
    """
    if max_objects < 1:
        raise ValueError(f"max_objects must be at least 1, not {max_objects}")
    return [
        Batch(number=number, objects=tuple(objects[start : start + max_objects]))
        for number, start in enumerate(range(0, len(objects), max_objects), start=1)
    ]


def may_start_batch(*, run_started: datetime, now: datetime, budget: timedelta) -> bool:
    """Return whether another batch may start within the run's time budget.

    Parameters
    ----------
    run_started : datetime
        When the run started.
    now : datetime
        The current instant.
    budget : timedelta
        The run's time budget.

    Returns
    -------
    bool
        True while less than ``budget`` has passed since ``run_started``.
    """
    return now - run_started < budget


def stage_drained(
    objects: Sequence[BronzeObject], end_instant: datetime | None
) -> bool:
    """Return whether the current stage of the first load has drained.

    Parameters
    ----------
    objects : Sequence[BronzeObject]
        The pending objects.
    end_instant : datetime | None
        The end of the current stage, exclusive, or None for no stage.

    Returns
    -------
    bool
        True when an end instant is set and no object is captured before it.
    """
    return end_instant is not None and not within_end_instant(objects, end_instant)
