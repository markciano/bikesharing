"""Parses bronze keys, plans each feed's listing and selects the pending objects.

A run lists each system and feed from shortly before its own latest processed
capture, so that an object written late is still found, and a feed with nothing
processed from its start (d010 D3, Discovery keeps a watermark per system and
feed). Unreadable objects are left out only through a reviewed exclusion list
(d008 #8, Unreadable objects). Keys follow ``contracts/bronze-keys.json``.
"""

import re
from collections.abc import Iterable
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

from bikesharing.core.settings import SYSTEMS, System

_RUN_ID_FORMAT: Final = "%Y%m%dT%H%M%SZ"
_RAW_KEY: Final = re.compile(
    r"raw/(?P<system>[a-z0-9_]+)/(?P<feed>[a-z0-9_]+)/"
    r"(?P<date>\d{4}-\d{2}-\d{2})/(?P<run_id>\d{8}T\d{6}Z)\.json\.gz"
)


class InvalidBronzeKey(ValueError):
    """A listed key that does not follow the bronze key contract."""


@dataclass(frozen=True, slots=True)
class BronzeObject:
    """A bronze object, as its key identifies it.

    Attributes
    ----------
    key : str
        The object's key in the bronze bucket.
    system : System
        The system that published it.
    feed : str
        The GBFS feed it holds.
    captured_at : datetime
        The capture instant, in UTC, truncated to the second.
    """

    key: str
    system: System
    feed: str
    captured_at: datetime


@dataclass(frozen=True, slots=True)
class ListingPlan:
    """How a run lists one system and feed's prefix.

    Attributes
    ----------
    system : System
        The system listed.
    feed : str
        The GBFS feed listed.
    prefix : str
        The prefix listed, ``raw/<system>/<feed>/``.
    start_after : str | None
        The key the listing starts after; None lists the whole prefix.
    full_sweep : bool
        Whether the whole prefix is listed, which only a feed with nothing
        processed does.
    """

    system: System
    feed: str
    prefix: str
    start_after: str | None
    full_sweep: bool


def parse_bronze_key(key: str) -> BronzeObject:
    """Return the bronze object a raw key identifies.

    Parameters
    ----------
    key : str
        A key listed in the bronze bucket.

    Returns
    -------
    BronzeObject
        Its system, feed and capture instant.

    Raises
    ------
    InvalidBronzeKey
        If the key does not follow the contract, its date folder is not the
        UTC date of its timestamp, or its system is not one the pipeline reads.
    """
    match = _RAW_KEY.fullmatch(key)
    if match is None:
        raise InvalidBronzeKey(f"not a raw bronze key: {key!r}")
    system = match["system"]
    if system not in SYSTEMS:
        raise InvalidBronzeKey(f"unknown system {system!r}: {key!r}")
    try:
        captured_at = datetime.strptime(match["run_id"], _RUN_ID_FORMAT).replace(
            tzinfo=UTC
        )
    except ValueError as error:
        raise InvalidBronzeKey(f"invalid timestamp: {key!r}") from error
    if captured_at.date().isoformat() != match["date"]:
        raise InvalidBronzeKey(f"date folder does not match the timestamp: {key!r}")
    return BronzeObject(
        key=key,
        system=cast(System, system),
        feed=match["feed"],
        captured_at=captured_at,
    )


def bronze_key(system: System, feed: str, captured_at: datetime) -> str:
    """Return the raw key of a capture.

    Parameters
    ----------
    system : System
        The system captured.
    feed : str
        The feed captured.
    captured_at : datetime
        The capture instant, timezone-aware; it is truncated to the second.

    Returns
    -------
    str
        The key, ``raw/<system>/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz``.

    Raises
    ------
    ValueError
        If ``captured_at`` is naive.
    """
    utc = _as_utc(captured_at)
    return f"raw/{system}/{feed}/{utc:%Y-%m-%d}/{utc.strftime(_RUN_ID_FORMAT)}.json.gz"


def plan_listing(
    system: System,
    feed: str,
    latest_processed: datetime | None,
    *,
    lookback: timedelta,
) -> ListingPlan:
    """Return how a run lists one system and feed's prefix.

    Parameters
    ----------
    system : System
        The system to list.
    feed : str
        The GBFS feed to list.
    latest_processed : datetime | None
        The capture instant of the feed's latest processed object, or None if
        none is.
    lookback : timedelta
        How far before the latest processed capture the listing starts.

    Returns
    -------
    ListingPlan
        The whole prefix when nothing is processed; otherwise a listing after
        the key of the latest processed capture minus ``lookback``.

    Raises
    ------
    ValueError
        If ``latest_processed`` is naive.
    """
    start_after = (
        None
        if latest_processed is None
        else bronze_key(system, feed, latest_processed - lookback)
    )
    return ListingPlan(
        system=system,
        feed=feed,
        prefix=f"raw/{system}/{feed}/",
        start_after=start_after,
        full_sweep=start_after is None,
    )


def parse_exclusion_list(text: str) -> frozenset[str]:
    """Return the keys of the exclusion list.

    Parameters
    ----------
    text : str
        The list, one ``<key> # <reason>`` per line; blank lines and lines
        starting with ``#`` are ignored.

    Returns
    -------
    frozenset[str]
        The excluded keys.

    Raises
    ------
    ValueError
        If a line has no key or no reason.
    """
    keys: set[str] = set()
    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, marker, reason = line.partition("#")
        if not marker or not key.strip() or not reason.strip():
            raise ValueError(
                f"exclusion list line {number} needs '<key> # <reason>': {line!r}"
            )
        keys.add(key.strip())
    return frozenset(keys)


def pending_objects(
    listed: Iterable[str], processed: AbstractSet[str], excluded: AbstractSet[str]
) -> list[BronzeObject]:
    """Return the listed objects not yet processed nor excluded.

    Parameters
    ----------
    listed : Iterable[str]
        The keys the listing returned.
    processed : AbstractSet[str]
        The keys with a row in ``processed_objects``.
    excluded : AbstractSet[str]
        The keys of the exclusion list.

    Returns
    -------
    list[BronzeObject]
        The pending objects, oldest first, then by key.

    Raises
    ------
    InvalidBronzeKey
        If any listed key does not parse, which fails the run.
    """
    # Every listed key is parsed, processed or not, so that a key breaking the
    # contract fails the run instead of being skipped unnoticed.
    objects = {obj.key: obj for obj in map(parse_bronze_key, listed)}
    done = processed | excluded
    pending = [obj for key, obj in objects.items() if key not in done]
    return sorted(pending, key=lambda obj: (obj.captured_at, obj.key))


def _as_utc(instant: datetime) -> datetime:
    """Return a timezone-aware instant in UTC.

    Parameters
    ----------
    instant : datetime
        The instant.

    Returns
    -------
    datetime
        The same instant, in UTC.

    Raises
    ------
    ValueError
        If ``instant`` is naive, since its timezone would be guessed.
    """
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError(f"naive datetime: {instant!r}")
    return instant.astimezone(UTC)
