"""Bronze-side parser of the collector key (spike s008, P1 + P4 consumer).

Input: an object key `raw/<source>/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz` (ADR-0012).
Output: `(source, feed, captured_at)` with `captured_at` in UTC; `ValueError` if the key breaks the contract.
"""

import re
from datetime import datetime, timezone

_KEY = re.compile(
    r"raw/(?P<source>[^/]+)/(?P<feed>[^/]+)/(?P<date>\d{4}-\d{2}-\d{2})/(?P<stamp>\d{8}T\d{6}Z)\.json\.gz"
)


def parse_key(key: str) -> tuple[str, str, datetime]:
    match = _KEY.fullmatch(key)
    if match is None:
        raise ValueError(f"key does not follow the collector contract: {key}")
    captured_at = datetime.strptime(match["stamp"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    if captured_at.date().isoformat() != match["date"]:
        raise ValueError(f"date folder does not match the timestamp: {key}")
    return match["source"], match["feed"], captured_at
