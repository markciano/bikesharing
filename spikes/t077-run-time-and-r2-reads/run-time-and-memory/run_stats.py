"""Summarise the pipeline's runs in d008's cost window (DI15) from their log objects.

Reads logs/pipeline/date=2026-11-21..23/*.jsonl from bikesharing-lakehouse with the
validation's read-only token (.env: LAKEHOUSE_READ_R2_*), keeps runs whose
run_started falls in [2026-11-21T03:00Z, 2026-11-23T03:00Z), and prints only
aggregates: count, outcomes, duration_s and peak_memory_mb (max, p95, median),
split by full sweep or incremental listing. Never prints a credential.
"""

import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import obstore
from obstore.store import S3Store

ENV = Path(__file__).resolve().parents[3] / ".env"
ACCOUNT_ID = "b88ece5b9aad94b83f1710afa6d24070"
START = datetime(2026, 11, 21, 3, tzinfo=UTC)
END = datetime(2026, 11, 23, 3, tzinfo=UTC)
DAYS = ["2026-11-21", "2026-11-22", "2026-11-23"]


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


def summary(name, xs):
    if not xs:
        return f"  {name}: none"
    return (f"  {name}: n={len(xs)} max={max(xs):.1f} p95={p95(xs):.1f} "
            f"median={statistics.median(xs):.1f} min={min(xs):.1f}")


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

runs = []
for day in DAYS:
    keys = [m["path"] for batch in obstore.list(store, prefix=f"logs/pipeline/date={day}/")
            for m in batch]
    print(f"{day}: {len(keys)} log objects", flush=True)
    for key in keys:
        lines = bytes(obstore.get(store, key).bytes()).decode().splitlines()
        events = [json.loads(line) for line in lines if line.strip()]
        started = next((e for e in events if e["event"] == "run_started"), None)
        finished = next((e for e in events if e["event"] == "run_finished"), None)
        discovered = next((e for e in events if e["event"] == "objects_discovered"), None)
        if not started or not finished or not START <= ts(started["ts"]) < END:
            continue
        # A run is a full sweep when any system's listing was one.
        full = any(v.get("full_sweep") for v in (discovered or {}).values()
                   if isinstance(v, dict))
        runs.append({"outcome": finished.get("outcome"), "full": full,
                     "d": finished.get("duration_s"), "m": finished.get("peak_memory_mb"),
                     "start": started["ts"], "version": started.get("version")})

print(f"\nRuns in window: {len(runs)} (expected 192)")
print("Outcomes:", {o: sum(r["outcome"] == o for r in runs) for o in {r["outcome"] for r in runs}})
print("Versions:", sorted({r["version"] for r in runs}))
for label, sel in (("all", runs), ("full sweep", [r for r in runs if r["full"]]),
                   ("incremental", [r for r in runs if not r["full"]])):
    print(f"{label}:")
    print(summary("duration_s", [r["d"] for r in sel if r["d"] is not None]))
    print(summary("peak_memory_mb", [r["m"] for r in sel if r["m"] is not None]))
slow = sorted(runs, key=lambda r: r["d"] or 0, reverse=True)[:5]
print("Slowest:", [(r["start"], r["d"], r["m"], "full" if r["full"] else "incr") for r in slow])
print(f"\nElapsed: {time.monotonic() - t0:.0f} s")
