"""Break the pipeline's runs in d008's cost window (DI15) into phases, from their log objects.

Reads logs/pipeline/date=2026-11-21..23/*.jsonl from bikesharing-lakehouse with the
validation's read-only token (.env: LAKEHOUSE_READ_R2_*), keeps runs whose
run_started falls in [2026-11-21T03:00Z, 2026-11-23T03:00Z), and derives each
phase from the timestamps of consecutive events:

  discovery   run_started        -> objects_discovered
  to batch    objects_discovered -> first batch_started
  batches     each batch_started -> its batch_committed (split into dbt nodes and the rest)
  gold file   last batch end     -> file_built
  page        file_built         -> page_deployed
  tail        page_deployed      -> run_finished

Prints only aggregates (mean, median, p95 per phase, in seconds), the mean of
each phase over the first and last 12 h of the window, and the slowest dbt nodes.
Never prints a credential or a log line.
"""

import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import obstore
from obstore.store import S3Store

ENV = Path(__file__).resolve().parents[3] / ".env"
ACCOUNT_ID = "b88ece5b9aad94b83f1710afa6d24070"
START = datetime(2026, 11, 21, 3, tzinfo=UTC)
END = datetime(2026, 11, 23, 3, tzinfo=UTC)
DAYS = ["2026-11-21", "2026-11-22", "2026-11-23"]
PHASES = ["discovery", "to batch", "batches", "  dbt nodes", "  rest of batch",
          "gold file", "page", "tail", "total"]


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


def p95(xs):
    xs = sorted(xs)
    return xs[max(0, round(0.95 * len(xs)) - 1)]


def first(events, name):
    return next((e for e in events if e["event"] == name), None)


def gap(a, b):
    return (ts(b["ts"]) - ts(a["ts"])).total_seconds() if a and b else None


def phases(events):
    """Seconds per phase of one run; None where a phase did not happen."""
    events = sorted(events, key=lambda e: e["ts"])
    started, discovered = first(events, "run_started"), first(events, "objects_discovered")
    built, deployed = first(events, "file_built"), first(events, "page_deployed")
    finished = first(events, "run_finished")
    out = {"discovery": gap(started, discovered), "total": finished.get("duration_s")}
    batch_s = dbt_s = 0.0
    batch_start = last_end = None
    first_batch = None
    # node_finished events between a batch's start and end belong to that batch.
    for e in events:
        if e["event"] == "batch_started":
            batch_start = e
            first_batch = first_batch or e
        elif e["event"] == "node_finished" and batch_start:
            dbt_s += e.get("duration_s") or 0
        elif e["event"] in ("batch_committed", "batch_failed") and batch_start:
            batch_s += gap(batch_start, e)
            last_end, batch_start = e, None
    out["to batch"] = gap(discovered, first_batch)
    out["batches"] = batch_s if first_batch else None
    out["  dbt nodes"] = dbt_s if first_batch else None
    out["  rest of batch"] = batch_s - dbt_s if first_batch else None
    out["gold file"] = gap(last_end or discovered, built)
    out["page"] = gap(built, deployed)
    out["tail"] = gap(deployed, finished)
    return out


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

runs, nodes, batches_per_run = [], defaultdict(list), []
for day in DAYS:
    keys = [m["path"] for b in obstore.list(store, prefix=f"logs/pipeline/date={day}/") for m in b]
    print(f"{day}: {len(keys)} log objects", flush=True)
    for key in keys:
        text = bytes(obstore.get(store, key).bytes()).decode()
        events = [json.loads(line) for line in text.splitlines() if line.strip()]
        started, finished = first(events, "run_started"), first(events, "run_finished")
        if not started or not finished or not START <= ts(started["ts"]) < END:
            continue
        runs.append((ts(started["ts"]), phases(events)))
        batches_per_run.append(sum(e["event"] == "batch_started" for e in events))
        for e in events:
            if e["event"] == "node_finished":
                nodes[e.get("node")].append(e.get("duration_s") or 0)

print(f"\nRuns: {len(runs)}; batches per run: mean {statistics.mean(batches_per_run):.2f}, "
      f"max {max(batches_per_run)}")
half = START.replace(hour=15)  # first 12 h end at 15:00 UTC on 2026-11-21
late = END.replace(day=22, hour=15)  # last 12 h start at 15:00 UTC on 2026-11-22
print(f"\n{'phase':<16}{'n':>5}{'mean':>9}{'median':>9}{'p95':>9}{'first12h':>10}{'last12h':>9}")
for p in PHASES:
    xs = [r[p] for _, r in runs if r[p] is not None]
    early = [r[p] for t, r in runs if t < half and r[p] is not None]
    later = [r[p] for t, r in runs if t >= late and r[p] is not None]
    if not xs:
        print(f"{p:<16}    0")
        continue
    print(f"{p:<16}{len(xs):>5}{statistics.mean(xs):>9.1f}{statistics.median(xs):>9.1f}"
          f"{p95(xs):>9.1f}{statistics.mean(early) if early else 0:>10.1f}"
          f"{statistics.mean(later) if later else 0:>9.1f}")
print("\nSlowest dbt nodes by mean s per run:")
for name, xs in sorted(nodes.items(), key=lambda kv: -sum(kv[1]))[:8]:
    print(f"  {name}: mean {statistics.mean(xs):.2f}, total {sum(xs) / len(runs):.2f} per run")
print(f"\nElapsed: {time.monotonic() - t0:.0f} s")
