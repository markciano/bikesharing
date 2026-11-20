"""The run's constants, reviewed and traced by the code version.

A change to any of them is a reviewed change deployed as a new code version
(d008, Environments and configuration).
"""

from datetime import datetime, timedelta
from typing import Final, Literal
from zoneinfo import ZoneInfo

type System = Literal["ambici", "bicing"]
"""A bike sharing system the pipeline reads."""

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
STATION_STOCK_PATH: Final = "silver/station_stock"
PROCESSED_OBJECTS_PATH: Final = "control/processed_objects"
LOG_PREFIX: Final = "logs/pipeline"

# The first load drains in stages; the second one ends with the first week of
# bronze captures, the local days 2026-10-14 to 2026-10-20 (d008 D8, First load in
# chronological stages). None processes every object.
END_INSTANT: Final[datetime | None] = datetime(2026, 10, 21, tzinfo=LOCAL_TIMEZONE)
MAX_OBJECTS_PER_BATCH: Final = 360
TIME_BUDGET: Final = timedelta(minutes=7)
LISTING_LOOKBACK: Final = timedelta(hours=1)
DUCKDB_MEMORY_FRACTION: Final = 0.6
