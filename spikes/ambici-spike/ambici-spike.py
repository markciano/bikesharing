#!/usr/bin/env python3
"""
AMBici GBFS observation spike.

Throwaway script: captures the AMBici GBFS feeds for a few days.

Decisions (agreed before writing the code):
- All 9 feeds (+ the gbfs.json index) in English.
- Dynamic feeds every minute, static feeds every 15 minutes.
- One-off copy of every feed in Catalan and Spanish, for comparison.
- Raw responses saved untouched, gzip-compressed, partitioned by feed and date:
      raw/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz
- One JSONL request log per day for all feeds, one line per request,
  including failed requests:
      log/requests_<YYYY-MM-DD>.jsonl
- All timestamps in UTC.
- Python standard library only: nothing to install.

Usage:
    python3 ambici-spike.py                    # writes to ./ambici-spike
    python3 ambici-spike.py --out ~/data/spike # custom output folder

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

BASE_URL = "https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_bs"
LANGUAGE = "en"
COMPARISON_LANGUAGES = ["ca", "es"]

# Change every minute: captured on every tick.
DYNAMIC_FEEDS = [
    "station_status",
    "free_bike_status",
]

# Change rarely: captured every STATIC_EVERY_TICKS ticks.
# "gbfs" is the index itself: lets us notice if feeds are added or removed.
STATIC_FEEDS = [
    "gbfs",
    "system_information",
    "vehicle_types",
    "station_information",
    "system_hours",
    "system_regions",
    "system_pricing_plans",
    "geofencing_zones",
]

TICK_SECONDS = 60            # the feeds declare ttl=60: no point polling faster
STATIC_EVERY_TICKS = 15      # static feeds every 15 minutes
PROGRESS_EVERY_TICKS = 15    # progress line every 15 minutes
REQUEST_TIMEOUT_SECONDS = 20  # must stay well below TICK_SECONDS
USER_AGENT = "ambici-gbfs-observation-spike/1.0 (personal learning project)"


def feed_url(base_url, language, feed):
    """The index lives at the root; every other feed lives under the language."""
    if feed == "gbfs":
        return f"{base_url}/gbfs.json"
    return f"{base_url}/{language}/{feed}.json"


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
    Reads GBFS 'last_updated' only to record it in the log.
    The raw body is saved untouched regardless of whether this works.
    """
    try:
        value = json.loads(body).get("last_updated")
        return int(value) if value is not None else None
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


def capture(out_dir, base_url, feed, language, tick, purpose, target_path):
    """Fetch one feed, save it if the request succeeded, and return the log record."""
    requested_at = utc_now()
    url = feed_url(base_url, language, feed)
    status, body, ms, error = http_get(url)

    record = {
        "tick_utc": iso(tick),
        "requested_at_utc": iso(requested_at),
        "purpose": purpose,
        "feed": feed,
        "language": language,
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

    return record


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
# 2. One-off copy in the comparison languages
# ---------------------------------------------------------------------------

def capture_languages(out_dir, base_url, stats):
    tick = utc_now()
    for language in COMPARISON_LANGUAGES:
        for feed in DYNAMIC_FEEDS + STATIC_FEEDS:
            if feed == "gbfs":
                continue  # the index is language-independent
            target = out_dir / "languages" / language / f"{feed}_{compact(tick)}.json.gz"
            record = capture(out_dir, base_url, feed, language, tick, "language_copy", target)
            append_log(out_dir, record)
            stats.count(record)
    print(f"Language copies done ({', '.join(COMPARISON_LANGUAGES)}).", flush=True)


# ---------------------------------------------------------------------------
# 5. Main loop
# ---------------------------------------------------------------------------

def capture_tick(out_dir, base_url, tick, feeds, stats):
    for feed in feeds:
        target = (
            out_dir / "raw" / feed / tick.strftime("%Y-%m-%d") / f"{compact(tick)}.json.gz"
        )
        record = capture(out_dir, base_url, feed, LANGUAGE, tick, "observation", target)
        append_log(out_dir, record)
        stats.count(record)
        if record["error"] is not None:
            print(f"[{iso(utc_now())}] {feed}: {record['error']}", flush=True)


def run(out_dir, base_url, max_ticks):
    out_dir.mkdir(parents=True, exist_ok=True)
    stop = StopFlag()
    signal.signal(signal.SIGINT, stop.handle)
    stats = Stats()

    print(f"Output folder: {out_dir.resolve()}", flush=True)
    print(f"Feeds: {len(DYNAMIC_FEEDS)} dynamic every {TICK_SECONDS}s, "
          f"{len(STATIC_FEEDS)} static every {STATIC_EVERY_TICKS} ticks. "
          f"Ctrl+C to stop.", flush=True)

    capture_languages(out_dir, base_url, stats)

    first = True
    next_tick = floor_to_tick(utc_now(), TICK_SECONDS) + timedelta(seconds=TICK_SECONDS)

    while not stop.requested:
        sleep_until(next_tick, stop)
        if stop.requested:
            break

        tick = next_tick
        tick_number = int(tick.timestamp()) // TICK_SECONDS
        feeds = list(DYNAMIC_FEEDS)
        if first or tick_number % STATIC_EVERY_TICKS == 0:
            feeds += STATIC_FEEDS
        first = False

        capture_tick(out_dir, base_url, tick, feeds, stats)
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
    parser = argparse.ArgumentParser(description="AMBici GBFS observation spike")
    parser.add_argument("--out", default="ambici-spike", help="output folder")
    parser.add_argument("--base-url", default=BASE_URL, help=argparse.SUPPRESS)
    parser.add_argument("--max-ticks", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--tick-seconds", type=int, default=None, help=argparse.SUPPRESS)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.tick_seconds:  # testing only
        TICK_SECONDS = args.tick_seconds
    run(Path(args.out).expanduser(), args.base_url, args.max_ticks)