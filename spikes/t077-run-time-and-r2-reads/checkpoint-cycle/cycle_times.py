"""Place each run in its checkpoint cycle and compare discovery's time around each checkpoint.

Inputs:  data/logs/**/*.jsonl (the runs' log objects, one per run),
         data/delta-log.txt (production's log dates, RFC 3339 with offset).
Outputs: output/checkpoint-cycle/runs.csv, one row per run;
         output/checkpoint-cycle/checkpoints.csv, one row per checkpoint of
         processed_objects, also printed.

Offline: it makes no request. All times are converted to UTC.
"""

import csv
import io
import json
import re
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

SPIKE_DIR = Path(__file__).resolve().parents[1]
LOGS = SPIKE_DIR / "data" / "logs"
DELTA_LOG_DATES = SPIKE_DIR / "data" / "delta-log.txt"
OUTPUT = SPIKE_DIR / "output" / "checkpoint-cycle"

WINDOW_START = datetime(2026, 11, 22, tzinfo=UTC)
NEIGHBOURS = 4  # runs compared on each side of a checkpoint
THRESHOLD_PCT = 20  # Q1's criterion
PROCESSED = "control/processed_objects"
STOCK = "silver/station_stock"

COMMIT = re.compile(r"^(\d{20})\.json$")
CHECKPOINT = re.compile(r"^(\d{20})\.checkpoint\.parquet$")


def read_delta_log():
    """Per table, {version: LastModified} of its commits and of its checkpoints."""
    tables = {t: {"commits": {}, "checkpoints": {}} for t in (PROCESSED, STOCK)}
    for line in DELTA_LOG_DATES.read_text(encoding="utf-8").splitlines():
        stamp, path = line.split(";", 1)
        table, name = path.split("/_delta_log/", 1)
        # rclone prints the local offset; fromisoformat keeps it, astimezone converts.
        when = datetime.fromisoformat(stamp).astimezone(UTC)
        for kind, pattern in (("commits", COMMIT), ("checkpoints", CHECKPOINT)):
            if match := pattern.match(name):
                tables[table][kind][int(match.group(1))] = when
    return tables


def read_runs():
    """The window's runs, by start; discovery_s is None without objects_discovered."""
    runs, not_started = [], []
    for path in sorted(LOGS.rglob("*.jsonl")):
        events = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                event = json.loads(line)
                events.setdefault(event["event"], event)  # first of each name
        name = path.relative_to(LOGS).as_posix()
        if "run_started" not in events:
            not_started.append(name)
            continue
        started = datetime.fromisoformat(events["run_started"]["ts"])
        if started < WINDOW_START:
            continue
        discovered = events.get("objects_discovered")
        discovery_s = None
        if discovered:
            discovery_s = (datetime.fromisoformat(discovered["ts"]) - started).total_seconds()
        runs.append({"started": started, "discovery_s": discovery_s, "log": name})
    return sorted(runs, key=lambda r: r["started"]), not_started


def latest_at(versions, instant):
    return max((v for v, when in versions.items() if when <= instant), default=None)


def utc(instant, timespec="milliseconds"):
    return instant.isoformat(timespec=timespec).replace("+00:00", "Z")


def to_csv(rows):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def run_rows(runs, table):
    rows = []
    for run in runs:
        version = latest_at(table["commits"], run["started"])
        checkpoint = latest_at(table["checkpoints"], run["started"])
        known = version is not None and checkpoint is not None
        rows.append({
            "run_started": utc(run["started"]),
            "discovery_s": "" if run["discovery_s"] is None else f"{run['discovery_s']:.3f}",
            "version_at_start": "" if version is None else version,
            "last_checkpoint": "" if checkpoint is None else checkpoint,
            "commits_since_checkpoint": version - checkpoint if known else "",
            "log": run["log"],
        })
    return rows


def checkpoint_rows(runs, table):
    timed = [r for r in runs if r["discovery_s"] is not None]
    rows = []
    for version, when in sorted(table["checkpoints"].items()):
        if when < WINDOW_START:
            continue
        # A run in progress when the checkpoint is written counts as "before":
        # its discovery, which comes first in a run, read the log without it.
        before = [r["discovery_s"] for r in timed if r["started"] < when][-NEIGHBOURS:]
        after = [r["discovery_s"] for r in timed if r["started"] >= when][:NEIGHBOURS]
        complete = len(before) == NEIGHBOURS and len(after) == NEIGHBOURS
        mean_before = statistics.mean(before) if before else None
        mean_after = statistics.mean(after) if after else None
        drop = (mean_before - mean_after) / mean_before * 100 if complete else None
        rows.append({
            "version": version,
            "checkpoint_utc": utc(when, "seconds"),
            "runs_before": len(before),
            "runs_after": len(after),
            "mean_before_s": "" if mean_before is None else f"{mean_before:.3f}",
            "mean_after_s": "" if mean_after is None else f"{mean_after:.3f}",
            "drop_pct": "" if drop is None else f"{drop:.1f}",
            "drop_ge_20": "" if drop is None else ("yes" if drop >= THRESHOLD_PCT else "no"),
        })
    return rows


def main():
    t0 = time.monotonic()
    tables = read_delta_log()
    runs, not_started = read_runs()
    per_run = run_rows(runs, tables[PROCESSED])
    per_checkpoint = checkpoint_rows(runs, tables[PROCESSED])

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "runs.csv").write_text(to_csv(per_run), encoding="utf-8")
    (OUTPUT / "checkpoints.csv").write_text(to_csv(per_checkpoint), encoding="utf-8")
    print(to_csv(per_checkpoint), end="")

    print(f"\nRuns in the window: {len(runs)}, from {utc(runs[0]['started'])} "
          f"to {utc(runs[-1]['started'])}")
    undiscovered = [r for r in runs if r["discovery_s"] is None]
    print(f"Runs with no objects_discovered: {len(undiscovered)}")
    for run in undiscovered:
        print(f"  {utc(run['started'])} {run['log']}")
    print(f"Log objects with no run_started: {len(not_started)}")
    for name in not_started:
        print(f"  {name}")
    stock = [f"{v} at {utc(when, 'seconds')}"
             for v, when in sorted(tables[STOCK]["checkpoints"].items())
             if when >= WINDOW_START]
    print(f"station_stock checkpoints in the window: {', '.join(stock) or 'none'}")
    print(f"Elapsed: {time.monotonic() - t0:.1f} s")


if __name__ == "__main__":
    main()
