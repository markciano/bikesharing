#!/usr/bin/env python3
"""
Bicing GBFS observation spike.

Throwaway script: captures the Bicing GBFS 3.0 feeds for a few days, over the
same period as the AMBici spike (ambici-spike.py), to compare both systems.

Decisions (agreed before writing the code):
- Feed URLs are never hard-coded: they are read from the gbfs.json index
  (data.feeds) and refreshed whenever the index is captured.
- Dynamic feed (station_status) every minute; every other feed listed in the
  index, plus the index itself, every 15 minutes.
- No language copy: in GBFS 3.0 the texts are localised inside each feed.
- Raw responses saved untouched, gzip-compressed, partitioned by feed and date:
      raw/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz
- One JSONL request log per day for all feeds, one line per request,
  including failed requests:
      log/requests_<YYYY-MM-DD>.jsonl
- All timestamps in UTC.
- Python standard library only: nothing to install.

Usage:
    python3 bicing_spike.py                    # writes to ./realtime (next to this script)
    python3 bicing_spike.py --out ~/data/spike # custom output folder

Stop with Ctrl+C: the capture in progress finishes, then a summary is shown.
Press Ctrl+C a second time to force-quit immediately.
"""

import argparse
import gzip
import json
import os
import signal
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Configuration
# ---------------------------------------------------------------------------

INDEX_URL = "https://barcelona.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json"
INDEX_FEED = "gbfs"  # name used for the index in paths and in the log

# Change every minute: captured on every tick.
DYNAMIC_FEEDS = [
    "station_status",
]

# Every other feed listed in the index is "static" and captured every
# STATIC_EVERY_TICKS ticks, together with the index itself: lets us notice
# if feeds are added or removed.

TICK_SECONDS = 60            # same ticks as the AMBici spike; ttl is 0, so it says nothing
STATIC_EVERY_TICKS = 15      # static feeds every 15 minutes
PROGRESS_EVERY_TICKS = 15    # progress line every 15 minutes
REQUEST_TIMEOUT_SECONDS = 20  # must stay well below TICK_SECONDS
USER_AGENT = "bicing-gbfs-observation-spike/1.0 (personal learning project)"

DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "realtime"


# ---------------------------------------------------------------------------
# Time helpers (always UTC)
# ---------------------------------------------------------------------------

def utc_now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"  # millisecond precision


def compact(dt):
    return dt.strftime("%Y%m%dT%H%M%SZ")


def floor_to_tick(dt, tick_seconds):
    epoch = int(dt.timestamp())
    return datetime.fromtimestamp(epoch - epoch % tick_seconds, tz=timezone.utc)


# ---------------------------------------------------------------------------
# 2. Feed catalog (URLs read from the index)
# ---------------------------------------------------------------------------

class FeedCatalog:
    """Feed name -> URL, as listed in data.feeds of the gbfs.json index."""

    def __init__(self):
        self.urls = {}

    def update(self, index_body):
        """Replace the catalog from an index body. Keeps the old one if unreadable."""
        try:
            feeds = json.loads(index_body)["data"]["feeds"]
            urls = {feed["name"]: feed["url"] for feed in feeds}
        except Exception:
            return
        if urls:
            self.urls = urls

    def static_feeds(self):
        return [name for name in self.urls if name not in DYNAMIC_FEEDS]


# ---------------------------------------------------------------------------
# 3. Capture one feed
# ---------------------------------------------------------------------------

def http_get(url):
    """
    Returns (http_status, body_bytes, elapsed_ms, error_text).
    Never raises: every failure is turned into an error_text for the log.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read()
            return response.status, body, elapsed_ms(started), None
    except urllib.error.HTTPError as exc:
        return exc.code, None, elapsed_ms(started), f"HTTPError: {exc.reason}"
    except urllib.error.URLError as exc:
        return None, None, elapsed_ms(started), f"URLError: {exc.reason}"
    except (socket.timeout, TimeoutError):
        return None, None, elapsed_ms(started), "timeout"
    except Exception as exc:  # anything else must not stop a 48h capture
        return None, None, elapsed_ms(started), f"{type(exc).__name__}: {exc}"


def elapsed_ms(started):
    return int((time.monotonic() - started) * 1000)


def server_last_updated(body):
    """
    Reads GBFS 'last_updated' only to record it in the log. In GBFS 3.0 it is an
    RFC 3339 string; it is logged normalised to UTC, like the other timestamps.
    The raw body is saved untouched regardless of whether this works.
    """
    try:
        value = json.loads(body).get("last_updated")
        if value is None:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return iso(parsed.astimezone(timezone.utc))
    except Exception:
        return None


def write_gzip_atomically(path, body):
    """Write to a temporary file, then rename: a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with gzip.open(tmp, "wb") as fh:
        fh.write(body)
    os.replace(tmp, path)
    return path.stat().st_size


def capture(out_dir, url, feed, tick, purpose, target_path):
    """
    Fetch one feed and save it if the request succeeded.
    Returns (log record, body); body is None when the request failed.
    """
    requested_at = utc_now()
    status, body, ms, error = (None, None, 0, "feed not listed in the index")
    if url is not None:
        status, body, ms, error = http_get(url)

    record = {
        "tick_utc": iso(tick),
        "requested_at_utc": iso(requested_at),
        "purpose": purpose,
        "feed": feed,
        "url": url,
        "http_status": status,
        "elapsed_ms": ms,
        "bytes_raw": None,
        "bytes_gz": None,
        "server_last_updated": None,
        "file": None,
        "error": error,
    }

    if body is not None and error is None:
        try:
            record["bytes_raw"] = len(body)
            record["bytes_gz"] = write_gzip_atomically(target_path, body)
            record["server_last_updated"] = server_last_updated(body)
            record["file"] = str(target_path.relative_to(out_dir))
        except Exception as exc:
            record["error"] = f"save failed: {type(exc).__name__}: {exc}"

    return record, body


# ---------------------------------------------------------------------------
# 4. Request log (JSONL, one file per UTC day, all feeds together)
# ---------------------------------------------------------------------------

def append_log(out_dir, record):
    day = record["requested_at_utc"][:10]
    log_path = out_dir / "log" / f"requests_{day}.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        fh.flush()


# ---------------------------------------------------------------------------
# Run statistics
# ---------------------------------------------------------------------------

class Stats:
    def __init__(self):
        self.started = utc_now()
        self.ok = 0
        self.errors = 0
        self.missed_ticks = 0
        self.ticks = 0

    def count(self, record):
        if record["error"] is None:
            self.ok += 1
        else:
            self.errors += 1


def folder_size_mb(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return total / (1024 * 1024)


def print_progress(out_dir, stats):
    running = utc_now() - stats.started
    hours = running.total_seconds() / 3600
    size = folder_size_mb(out_dir)
    per_day = size / hours * 24 if hours > 0 else 0
    print(
        f"[{iso(utc_now())}] ticks={stats.ticks} ok={stats.ok} errors={stats.errors} "
        f"missed_ticks={stats.missed_ticks} disk={size:.1f} MB "
        f"(~{per_day:.0f} MB/day at this rate)",
        flush=True,
    )


# ---------------------------------------------------------------------------
# 8. Clean shutdown on Ctrl+C
# ---------------------------------------------------------------------------

class StopFlag:
    def __init__(self):
        self.requested = False

    def handle(self, _signum, _frame):
        if self.requested:
            print("\nSecond Ctrl+C: exiting immediately.", flush=True)
            sys.exit(130)
        self.requested = True
        print("\nStop requested: finishing the current capture...", flush=True)


def sleep_until(target, stop):
    """Sleep in short steps so Ctrl+C is noticed quickly."""
    while not stop.requested:
        remaining = (target - utc_now()).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 1.0))


# ---------------------------------------------------------------------------
# 5. Main loop
# ---------------------------------------------------------------------------

def capture_feed(out_dir, catalog, feed, tick, purpose, stats):
    """Capture one feed from the catalog, log it, and return the body."""
    target = out_dir / "raw" / feed / tick.strftime("%Y-%m-%d") / f"{compact(tick)}.json.gz"
    record, body = capture(out_dir, catalog.urls.get(feed), feed, tick, purpose, target)
    append_log(out_dir, record)
    stats.count(record)
    if record["error"] is not None:
        print(f"[{iso(utc_now())}] {feed}: {record['error']}", flush=True)
    return record, body


def capture_index(out_dir, catalog, tick, purpose, stats):
    """Capture the index and refresh the catalog from it."""
    now = utc_now()
    target = out_dir / "raw" / INDEX_FEED / tick.strftime("%Y-%m-%d") / f"{compact(now)}.json.gz"
    record, body = capture(out_dir, INDEX_URL, INDEX_FEED, tick, purpose, target)
    append_log(out_dir, record)
    stats.count(record)
    if record["error"] is not None:
        print(f"[{iso(utc_now())}] {INDEX_FEED}: {record['error']}", flush=True)
    if body is not None:
        catalog.update(body)


def capture_tick(out_dir, catalog, tick, static_due, stats):
    index_refreshed = False
    had_catalog = bool(catalog.urls)

    # The index comes first, so every URL used in this tick is current. It is also
    # retried every tick while the catalog is still empty (index down at start-up).
    if static_due or not had_catalog:
        capture_index(out_dir, catalog, tick, "observation", stats)
        index_refreshed = True

    feeds = list(DYNAMIC_FEEDS)
    if static_due or (not had_catalog and catalog.urls):
        feeds += catalog.static_feeds()

    failed = False
    for feed in feeds:
        record, _body = capture_feed(out_dir, catalog, feed, tick, "observation", stats)
        failed = failed or (feed in DYNAMIC_FEEDS and record["error"] is not None)

    # A dynamic feed failed: its URL may have changed. Re-read the index now,
    # so the next tick uses the new URL (the failed request is not retried).
    if failed and not index_refreshed:
        capture_index(out_dir, catalog, tick, "index_refresh", stats)


def run(out_dir, max_ticks):
    out_dir.mkdir(parents=True, exist_ok=True)
    stop = StopFlag()
    signal.signal(signal.SIGINT, stop.handle)
    stats = Stats()
    catalog = FeedCatalog()

    print(f"Output folder: {out_dir.resolve()}", flush=True)
    print(f"Index: {INDEX_URL}", flush=True)
    print(f"Dynamic feeds ({len(DYNAMIC_FEEDS)}) every {TICK_SECONDS}s; the other feeds listed "
          f"in the index every {STATIC_EVERY_TICKS} ticks. Ctrl+C to stop.", flush=True)

    first = True
    next_tick = floor_to_tick(utc_now(), TICK_SECONDS) + timedelta(seconds=TICK_SECONDS)

    while not stop.requested:
        sleep_until(next_tick, stop)
        if stop.requested:
            break

        tick = next_tick
        tick_number = int(tick.timestamp()) // TICK_SECONDS
        static_due = first or tick_number % STATIC_EVERY_TICKS == 0
        first = False

        capture_tick(out_dir, catalog, tick, static_due, stats)
        stats.ticks += 1

        if stats.ticks % PROGRESS_EVERY_TICKS == 0:
            print_progress(out_dir, stats)

        if max_ticks is not None and stats.ticks >= max_ticks:
            break

        # Next tick. If the Mac slept or a capture overran, skip ahead and
        # count the missed ticks: the gaps will also be visible in the log.
        next_tick = tick + timedelta(seconds=TICK_SECONDS)
        now_floor = floor_to_tick(utc_now(), TICK_SECONDS)
        if now_floor >= next_tick:
            missed = int((now_floor - next_tick).total_seconds()) // TICK_SECONDS + 1
            stats.missed_ticks += missed
            print(f"[{iso(utc_now())}] WARNING: {missed} tick(s) missed "
                  f"(computer asleep or capture too slow).", flush=True)
            next_tick = now_floor + timedelta(seconds=TICK_SECONDS)

    print("\n--- Summary ---", flush=True)
    print_progress(out_dir, stats)
    print(f"Started {iso(stats.started)}, ended {iso(utc_now())}.", flush=True)


def parse_args():
    parser = argparse.ArgumentParser(description="Bicing GBFS observation spike")
    parser.add_argument("--out", default=str(DEFAULT_OUT_DIR),
                        help="output folder (default: 'realtime' next to this script)")
    parser.add_argument("--max-ticks", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--tick-seconds", type=int, default=None, help=argparse.SUPPRESS)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.tick_seconds:  # testing only
        TICK_SECONDS = args.tick_seconds
    run(Path(args.out).expanduser(), args.max_ticks)
