"""Phase times of the pipeline's runs in d008's cost window by local day and hour.

Same input as run_phases.py: logs/pipeline/date=2026-11-21..23/*.jsonl from
bikesharing-lakehouse, read with the validation's read-only token (.env:
LAKEHOUSE_READ_R2_*), runs started in [2026-11-21T03:00Z, 2026-11-23T03:00Z).

For each run it derives three phases from consecutive event timestamps:
  disc   run_started        -> objects_discovered
  batch  batch time minus dbt nodes (download, read, Delta writes, dbt start-up)
  gold   last batch end     -> file_built
and prints their mean per hour of the local day (Europe/Madrid), one row per
local date and hour. A saw-tooth that drops at local midnight points at the
day partition; a steady rise across midnight points at a table that never
resets. Prints only aggregates; never a credential or a log line.
"""

import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import obstore
from obstore.store import S3Store

ENV = Path(__file__).resolve().parents[3] / ".env"
ACCOUNT_ID = "b88ece5b9aad94b83f1710afa6d24070"
START = datetime(2026, 11, 21, 3, tzinfo=UTC)
END = datetime(2026, 11, 23, 3, tzinfo=UTC)
DAYS = ["2026-11-21", "2026-11-22", "2026-11-23"]
LOCAL = ZoneInfo("Europe/Madrid")


def load_env(path):
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().removeprefix("export ")
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def first(events, name):
    return next((e for e in events if e["event"] == name), None)


def gap(a, b):
    return (ts(b["ts"]) - ts(a["ts"])).total_seconds() if a and b else None


def phases(events):
    """Seconds of discovery, batch work without dbt nodes, and the gold file."""
    events = sorted(events, key=lambda e: e["ts"])
    started, discovered = first(events, "run_started"), first(events, "objects_discovered")
    built = first(events, "file_built")
    batch_s = dbt_s = 0.0
    batch_start = last_end = None
    for e in events:
        if e["event"] == "batch_started":
            batch_start = e
        elif e["event"] == "node_finished" and batch_start:
            dbt_s += e.get("duration_s") or 0
        elif e["event"] in ("batch_committed", "batch_failed") and batch_start:
            batch_s += gap(batch_start, e)
            last_end, batch_start = e, None
    return gap(started, discovered), batch_s - dbt_s, gap(last_end or discovered, built)


t0 = time.monotonic()
env = load_env(ENV)
for k in ("LAKEHOUSE_READ_R2_ACCESS_KEY_ID", "LAKEHOUSE_READ_R2_SECRET_ACCESS_KEY"):
    if not env.get(k):
        sys.exit(f"Missing {k} in .env")
store = S3Store(
    "bikesharing-lakehouse",
    endpoint=f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com",
    region="auto",
    access_key_id=env["LAKEHOUSE_READ_R2_ACCESS_KEY_ID"],
    secret_access_key=env["LAKEHOUSE_READ_R2_SECRET_ACCESS_KEY"],
)

groups = defaultdict(list)  # (local date, local hour) -> [(disc, batch, gold)]
for day in DAYS:
    keys = [m["path"] for b in obstore.list(store, prefix=f"logs/pipeline/date={day}/") for m in b]
    print(f"{day}: {len(keys)} log objects", flush=True)
    for key in keys:
        text = bytes(obstore.get(store, key).bytes()).decode()
        events = [json.loads(line) for line in text.splitlines() if line.strip()]
        started = first(events, "run_started")
        if not started or not first(events, "run_finished"):
            continue
        t = ts(started["ts"])
        if not START <= t < END:
            continue
        local = t.astimezone(LOCAL)
        groups[(local.date().isoformat(), local.hour)].append(phases(events))


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else float("nan")


print(f"\n{'local date':<12}{'hour':>5}{'runs':>5}{'disc':>8}{'batch':>8}{'gold':>8}")
for (d, h), rows in sorted(groups.items()):
    print(f"{d:<12}{h:>5}{len(rows):>5}{mean(r[0] for r in rows):>8.1f}"
          f"{mean(r[1] for r in rows):>8.1f}{mean(r[2] for r in rows):>8.1f}")
print(f"\nElapsed: {time.monotonic() - t0:.0f} s")
