# Probe B of s010: measures capture's and the Bicing history's volumes from the owner's local copies,
# with no request to R2, and writes the volumes file the cost model (C) reads.
#
# Capture: raw/ objects, bytes and records per provider, feed and day (records are the entries of the
# payload's main list, 1 for feeds without one); for station_status, also distinct (station_id,
# last_reported) records. logs/ objects, bytes and writes per day. state/ keeps only its latest version
# locally, so its writes per day are derived from logs/: capture's V4.js writes <source>_index.json once
# per successful index fetch, which is a `gbfs` log line with no error. The first and last captured days
# are dropped as incomplete, in raw/, logs/ and state/ alike.
# History: per .7z archive, streamed with macOS's tar (libarchive reads 7z), never extracted to disk:
# .7z and uncompressed bytes, raw rows counted with a CSV parser (quoted newlines reported), distinct
# (station_id, last_reported) rows, snapshots (last_updated) per UTC day and rows at one snapshot per day.
#
# Input:  ../cloudflare-capture-spike/data/V4/ and ../bicing-spike/historical-data/raw/*.7z
# Output: output/volumes.json and a summary on the console
#
# Usage: uv run python measure_volume.py                      (full run)
#        uv run python measure_volume.py --archive FILE [...]  (those archives alone; no volumes file)
#        uv run python measure_volume.py --synthetic          (self-check on a hand-made sample in output/local/)

import argparse
import csv
import gzip
import json
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).parent
CAPTURE_DIR = HERE.parent / "cloudflare-capture-spike" / "data" / "V4"
HISTORY_DIR = HERE.parent / "bicing-spike" / "historical-data" / "raw"
OUTPUT = HERE / "output"

# The main list of each feed's payload; a feed not named here counts one record per object.
MAIN_LIST = {
    "station_status": "stations",
    "station_information": "stations",
    "free_bike_status": "bikes",
    "vehicle_types": "vehicle_types",
    "system_pricing_plans": "plans",
    "system_regions": "regions",
    "system_hours": "rental_hours",
    "gbfs_versions": "versions",
}
DEDUP_FEED = "station_status"

ARCHIVE_NAME = re.compile(r"^(\d{4})_(\d{2})_.+_(ESTACIONS|INFORMACIO)\.7z$")


# --- Capture ---------------------------------------------------------------


def day_folders(root: Path) -> list[str]:
    """Every UTC day that has a folder under raw/<provider>/<feed>/ or logs/."""
    days = {p.name for p in root.glob("raw/*/*/*") if p.is_dir()}
    days |= {p.name for p in (root / "logs").iterdir() if p.is_dir()}
    return sorted(days)


def payload_records(payload: dict, feed: str) -> list | None:
    """The main list of a GBFS payload, or None if the feed has none."""
    key = MAIN_LIST.get(feed)
    if key is None:
        return None
    data = payload["data"]
    # GBFS 2.x may nest data per language.
    if key not in data and "en" in data:
        data = data["en"]
    return data[key]


def measure_raw_day(folder: Path, feed: str) -> dict:
    files = sorted(folder.glob("*.json.gz"))
    out = {"objects": len(files), "bytes": 0, "records": 0, "unreadable": 0}
    keys = set()
    for f in files:
        out["bytes"] += f.stat().st_size
        try:
            payload = json.loads(gzip.decompress(f.read_bytes()))
            records = payload_records(payload, feed)
        except (OSError, ValueError, KeyError):
            out["unreadable"] += 1
            continue
        if records is None:
            out["records"] += 1
            continue
        out["records"] += len(records)
        if feed == DEDUP_FEED:
            keys.update((str(r.get("station_id")), str(r.get("last_reported"))) for r in records)
    if feed == DEDUP_FEED:
        out["distinct_records"] = len(keys)
    return out


def measure_logs_day(folder: Path) -> tuple[dict, dict]:
    """logs/ objects, bytes and writes of one day, and the state/ writes derived from them."""
    files = sorted(folder.glob("*.jsonl"))
    logs = {"objects": len(files), "bytes": sum(f.stat().st_size for f in files), "writes": len(files)}
    state = {"writes": 0, "bytes_written": 0, "static_passes": 0}
    for f in files:
        index_lines = [line for line in map(json.loads, f.read_text().splitlines()) if line["feed"] == "gbfs"]
        if index_lines:
            state["static_passes"] += 1
        for line in index_lines:
            if line["error"] is None:
                state["writes"] += 1
                state["bytes_written"] += line["bytes"] or 0
    return logs, state


def measure_capture(root: Path) -> dict:
    days = day_folders(root)
    complete, dropped = days[1:-1], [days[0], days[-1]]

    raw: dict = defaultdict(dict)
    for feed_dir in sorted(p for p in root.glob("raw/*/*") if p.is_dir()):
        provider, feed = feed_dir.parent.name, feed_dir.name
        raw[provider][feed] = {
            day: measure_raw_day(feed_dir / day, feed) for day in complete if (feed_dir / day).is_dir()
        }

    logs, state_per_day = {}, {}
    for day in complete:
        logs[day], state_per_day[day] = measure_logs_day(root / "logs" / day)
    state_files = sorted((root / "state").glob("*"))
    state = {
        "objects": len(state_files),
        "bytes": sum(f.stat().st_size for f in state_files),
        "per_day": state_per_day,
    }
    return {"days": complete, "dropped_days": dropped, "raw": dict(raw), "logs": logs, "state": state}


# --- History ---------------------------------------------------------------


class ByteCounter:
    """Passes byte lines through, decoded, and counts their bytes."""

    def __init__(self, lines: Iterable[bytes]):
        self.lines = lines
        self.bytes = 0

    def __iter__(self) -> Iterator[str]:
        for line in self.lines:
            self.bytes += len(line)
            yield line.decode("utf-8")


def measure_csv(lines: Iterable[bytes]) -> dict:
    """Counts one CSV stream: raw rows, quoted newlines, distinct keys and snapshots per UTC day."""
    counter = ByteCounter(lines)
    # The CSV parser joins quoted fields that span lines, so rows are records, not lines.
    reader = csv.reader(counter)
    header = next(reader)
    station, reported, updated = (header.index(c) for c in ("station_id", "last_reported", "last_updated"))

    rows = quoted_newlines = bad_snapshot = 0
    keys = set()
    snapshots: dict[str, Counter] = defaultdict(Counter)  # UTC day -> rows per last_updated
    for row in reader:
        rows += 1
        quoted_newlines += sum(field.count("\n") for field in row)
        keys.add((row[station], row[reported]))
        try:
            ts = int(row[updated])
        except ValueError:
            bad_snapshot += 1
            continue
        day = datetime.fromtimestamp(ts, UTC).date().isoformat()
        snapshots[day][ts] += 1

    days = sorted(snapshots)
    return {
        "uncompressed_bytes": counter.bytes,
        "raw_rows": rows,
        "quoted_newlines": quoted_newlines,
        "distinct_rows": len(keys),
        "rows_without_snapshot": bad_snapshot,
        "snapshots_per_day": {d: len(snapshots[d]) for d in days},
        # The day's first snapshot stands for one snapshot per day (#21).
        "rows_one_snapshot_per_day": {d: snapshots[d][min(snapshots[d])] for d in days},
    }


def stream_archive(path: Path) -> Iterator[bytes]:
    """Lines of the archive's single CSV, streamed by tar to stdout."""
    proc = subprocess.Popen(["tar", "-xOf", str(path)], stdout=subprocess.PIPE)
    yield from proc.stdout
    if proc.wait() != 0:
        sys.exit(f"{path.name}: tar exited with {proc.returncode}")


def measure_archive(path: Path) -> dict:
    match = ARCHIVE_NAME.match(path.name)
    if match is None:
        sys.exit(f"{path.name}: not a BicingNou ESTACIONS or INFORMACIO archive")
    year, month, kind = match.groups()
    return {
        "archive": path.name,
        "type": kind,
        "month": f"{year}-{month}",
        "archive_bytes": path.stat().st_size,
        **measure_csv(stream_archive(path)),
    }


# --- Summary ---------------------------------------------------------------


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def print_capture(capture: dict):
    print(f"capture: {len(capture['days'])} complete days {capture['days'][0]}..{capture['days'][-1]}"
          f" (dropped {', '.join(capture['dropped_days'])}); means per day")
    print(f"  {'provider/feed':34} {'objects':>8} {'MB':>8} {'records':>11} {'distinct':>11}")
    for provider, feeds in capture["raw"].items():
        for feed, days in feeds.items():
            d = days.values()
            distinct = f"{mean(x['distinct_records'] for x in d):11.0f}" if feed == DEDUP_FEED else ""
            unreadable = sum(x["unreadable"] for x in d)
            note = f"  ({unreadable} unreadable)" if unreadable else ""
            print(f"  {provider + '/' + feed:34} {mean(x['objects'] for x in d):8.1f}"
                  f" {mean(x['bytes'] for x in d) / 1e6:8.2f} {mean(x['records'] for x in d):11.0f}"
                  f" {distinct}{note}")
    logs = capture["logs"].values()
    state = capture["state"]["per_day"].values()
    print(f"  {'logs/':34} {mean(x['objects'] for x in logs):8.1f} {mean(x['bytes'] for x in logs) / 1e6:8.2f}"
          f"   writes {mean(x['writes'] for x in logs):.1f}")
    print(f"  {'state/ (derived)':34} {'':8} {mean(x['bytes_written'] for x in state) / 1e6:8.2f}"
          f"   writes {mean(x['writes'] for x in state):.1f}, static passes {mean(x['static_passes'] for x in state):.1f}")


def print_history(history: list[dict]):
    print(f"history: {len(history)} archives")
    print(f"  {'archive':42} {'7z MB':>7} {'csv bytes':>12} {'raw rows':>10} {'q.nl':>5}"
          f" {'distinct':>10} {'snap/day':>8} {'rows@1snap/day':>14}")
    for a in history:
        print(f"  {a['archive']:42} {a['archive_bytes'] / 1e6:7.1f} {a['uncompressed_bytes']:12,}"
              f" {a['raw_rows']:10,} {a['quoted_newlines']:5} {a['distinct_rows']:10,}"
              f" {mean(a['snapshots_per_day'].values()):8.1f} {mean(a['rows_one_snapshot_per_day'].values()):14.1f}")


# --- Synthetic self-check ----------------------------------------------------

# station_id, last_reported, name, last_updated; epochs 1000 and 1060 fall on 1970-01-01, 86410 on
# 1970-01-02. Row 2 has a quoted newline; rows 3 and 5 repeat the key (1, 100).
SAMPLE_CSV = (
    b'"station_id","last_reported","name","last_updated"\n'
    b'1,100,"A",1000\n'
    b'2,100,"B\nsecond line",1000\n'
    b'1,100,"A",1060\n'
    b'2,160,"B",1060\n'
    b'1,100,"A",86410\n'
    b'3,200,"C",86410\n'
)
SAMPLE_EXPECTED = {
    "uncompressed_bytes": len(SAMPLE_CSV),
    "raw_rows": 6,
    "quoted_newlines": 1,
    "distinct_rows": 4,
    "rows_without_snapshot": 0,
    "snapshots_per_day": {"1970-01-01": 2, "1970-01-02": 1},
    "rows_one_snapshot_per_day": {"1970-01-01": 2, "1970-01-02": 2},
}


def write_gz(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(payload).encode()))


def build_sample_capture(root: Path):
    """Three days; only the middle one is complete and counted."""
    shutil.rmtree(root, ignore_errors=True)
    for day in ("2026-10-14", "2026-10-15", "2026-10-16"):
        status = root / "raw" / "bicing" / "station_status" / day
        write_gz(status / "a.json.gz", {"data": {"stations": [{"station_id": 1, "last_reported": "t1"},
                                                              {"station_id": 2, "last_reported": "t1"}]}})
        # Station 1 has not reported again: its key repeats.
        write_gz(status / "b.json.gz", {"data": {"stations": [{"station_id": 1, "last_reported": "t1"},
                                                              {"station_id": 2, "last_reported": "t2"}]}})
        write_gz(root / "raw" / "bicing" / "system_information" / day / "a.json.gz", {"data": {"name": "x"}})
        logs = root / "logs" / day
        logs.mkdir(parents=True)
        # A static pass: one index fetch succeeds and is written, one fails.
        (logs / "a.jsonl").write_text(
            '{"feed":"gbfs","bytes":10,"error":null}\n'
            '{"feed":"gbfs","bytes":null,"error":"Error: index returned 503"}\n'
            '{"feed":"station_status","bytes":20,"error":null}\n'
        )
        (logs / "b.jsonl").write_text('{"feed":"station_status","bytes":20,"error":null}\n')
    (root / "state").mkdir()
    (root / "state" / "bicing_index.json").write_text("{}")


def synthetic() -> int:
    errors = []
    got = measure_csv(iter(SAMPLE_CSV.splitlines(keepends=True)))
    for key, expected in SAMPLE_EXPECTED.items():
        if got[key] != expected:
            errors.append(f"csv {key}: {got[key]} != {expected}")

    root = OUTPUT / "local" / "synthetic-volume"
    build_sample_capture(root)
    capture = measure_capture(root)
    status = capture["raw"]["bicing"]["station_status"]
    checks = {
        "complete days": (capture["days"], ["2026-10-15"]),
        "station_status records": (status["2026-10-15"]["records"], 4),
        "station_status distinct": (status["2026-10-15"]["distinct_records"], 3),
        "station_status objects": (status["2026-10-15"]["objects"], 2),
        "system_information records": (capture["raw"]["bicing"]["system_information"]["2026-10-15"]["records"], 1),
        "logs writes": (capture["logs"]["2026-10-15"]["writes"], 2),
        "state writes": (capture["state"]["per_day"]["2026-10-15"]["writes"], 1),
        "state static passes": (capture["state"]["per_day"]["2026-10-15"]["static_passes"], 1),
    }
    errors += [f"{name}: {got} != {expected}" for name, (got, expected) in checks.items() if got != expected]

    print("synthetic self-check: " + ("ok" if not errors else "FAIL\n  " + "\n  ".join(errors)))
    return 1 if errors else 0


# --- Main ------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="s010 probe B: measured volume")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--archive", nargs="+", metavar="FILE",
                       help=f"history archives in {HISTORY_DIR.relative_to(HERE.parent.parent)} to measure alone")
    group.add_argument("--synthetic", action="store_true", help="self-check on a hand-made sample")
    args = parser.parse_args()

    if args.synthetic:
        return synthetic()
    if args.archive:
        print_history([measure_archive(HISTORY_DIR / name) for name in args.archive])
        return 0

    capture = measure_capture(CAPTURE_DIR)
    print_capture(capture)
    history = [measure_archive(p) for p in sorted(HISTORY_DIR.glob("*.7z"))]
    print_history(history)
    volumes = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "capture": capture,
               "history": history}
    (OUTPUT / "volumes.json").write_text(json.dumps(volumes, indent=2) + "\n")
    print(f"wrote {(OUTPUT / 'volumes.json').relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
