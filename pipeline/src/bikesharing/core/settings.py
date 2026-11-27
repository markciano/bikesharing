"""The run's constants, reviewed and traced by the code version.

A change to any of them is a reviewed change deployed as a new code version
(d008, Environments and configuration).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Final, Literal
from zoneinfo import ZoneInfo

type System = Literal["ambici", "bicing"]
"""A bike sharing system the pipeline reads."""

type TableName = Literal["station_stock", "processed_objects"]
"""A Delta table of the lakehouse."""

type SystemFeed = tuple[System, str]
"""A system and one of its feeds, the key of each discovery watermark."""

COMPONENT: Final = "pipeline"
UNRELEASED_VERSION: Final = "unreleased"
SYSTEMS: Final[tuple[System, ...]] = ("ambici", "bicing")
FEED: Final = "station_status"
LOCAL_TIMEZONE: Final = ZoneInfo("Europe/Madrid")

# The owner's Cloudflare account ID: it identifies the account, and grants no
# access on its own.
CLOUDFLARE_ACCOUNT_ID: Final[str] = "b88ece5b9aad94b83f1710afa6d24070"
BRONZE_BUCKET: Final = "bikesharing-bronze"
LAKEHOUSE_BUCKET: Final = "bikesharing-lakehouse"
LOG_PREFIX: Final = "logs/pipeline"

# Each table's settings. TABLE_PATHS' keys are the pipeline's tables.
TABLE_PATHS: Final[Mapping[TableName, str]] = {
    "station_stock": "silver/station_stock",
    "processed_objects": "control/processed_objects",
}
# Commits between two checkpoints, the number that minimizes R2 requests per run.
CHECKPOINT_INTERVAL: Final[Mapping[TableName, int]] = {
    "station_stock": 8,
    "processed_objects": 8,
}
# A table left out never compacts its active partitions.
COMPACTION_THRESHOLD: Final[Mapping[TableName, int]] = {"processed_objects": 10}
# A table left out keeps all its rows.
RETENTION_MONTHS: Final[Mapping[TableName, int]] = {"station_stock": 12}
# Tombstones outlive vacuum's wait, so that the daily vacuum has several days to
# delete each removed file before a checkpoint drops its tombstone.
TOMBSTONE_RETENTION: Final = timedelta(days=10)
# The table history kept (ADR-0021, Retention per layer).
VACUUM_RETENTION: Final = timedelta(days=7)
# The local time of day of the daily maintenance.
MAINTENANCE_LOCAL_TIME: Final = time(4, 0)

# The first load drained in stages, each ending at an instant (d008 D8, First load
# in chronological stages). None, the last stage, processes every object.
END_INSTANT: Final[datetime | None] = None
MAX_OBJECTS_PER_BATCH: Final = 360
LISTING_LOOKBACK: Final = timedelta(hours=1)
DUCKDB_MEMORY_FRACTION: Final = 0.6


@dataclass(frozen=True)
class RunSettings:
    """The run's cadence, time budget, timeout and container memory.

    Attributes
    ----------
    cadence : timedelta
        Time between the starts of two runs.
    time_budget : timedelta
        Time after which a run stops taking new batches.
    timeout : timedelta
        Time after which the platform stops the run.
    container_memory_mib : int
        The container's memory, in MiB (Modal measures it so).
    """

    cadence: timedelta
    time_budget: timedelta
    timeout: timedelta
    container_memory_mib: int


_RUN_SETTINGS_KEYS: Final = (
    "cadence_min",
    "time_budget_s",
    "timeout_s",
    "container_memory_mib",
)


def parse_run_settings(data: Mapping[str, object]) -> RunSettings:
    """Parse the decoded ``run_settings.json`` and check it.

    Parameters
    ----------
    data : Mapping[str, object]
        The decoded file: ``cadence_min``, ``time_budget_s``, ``timeout_s`` and
        ``container_memory_mib``.

    Returns
    -------
    RunSettings
        The settings, with the durations as ``timedelta``.

    Raises
    ------
    ValueError
        When a key is missing or unknown, a value is not a positive integer,
        ``cadence_min`` does not divide 60, or the time budget is not below the
        timeout and the timeout below the cadence (d008 D6, Provisional run
        bounds).
    """
    missing = [key for key in _RUN_SETTINGS_KEYS if key not in data]
    if missing:
        raise ValueError(f"missing run setting: {', '.join(missing)}")
    unknown = [key for key in data if key not in _RUN_SETTINGS_KEYS]
    if unknown:
        raise ValueError(f"unknown run setting: {', '.join(unknown)}")
    for key in _RUN_SETTINGS_KEYS:
        value = data[key]
        # bool is an int subclass, and JSON true must not pass as 1.
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{key} must be a positive integer, got {value!r}")

    cadence_min = int(data["cadence_min"])  # type: ignore[call-overload]
    if 60 % cadence_min:
        raise ValueError(f"cadence_min must divide 60, got {cadence_min}")
    settings = RunSettings(
        cadence=timedelta(minutes=cadence_min),
        time_budget=timedelta(seconds=int(data["time_budget_s"])),  # type: ignore[call-overload]
        timeout=timedelta(seconds=int(data["timeout_s"])),  # type: ignore[call-overload]
        container_memory_mib=int(data["container_memory_mib"]),  # type: ignore[call-overload]
    )
    if settings.time_budget >= settings.timeout:
        raise ValueError("time_budget_s must be below timeout_s")
    if settings.timeout >= settings.cadence:
        raise ValueError("timeout_s must be below the cadence")
    return settings


def schedule_cron(settings: RunSettings) -> str:
    """Give the run's cron expression.

    Parameters
    ----------
    settings : RunSettings
        The run settings.

    Returns
    -------
    str
        ``*/<cadence in minutes> * * * *``.
    """
    return f"*/{int(settings.cadence.total_seconds() // 60)} * * * *"
