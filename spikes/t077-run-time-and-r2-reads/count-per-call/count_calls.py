"""Count per call of s019 Probe B: runs the 8 lakehouse calls of a run, one by one, through the proxy.

It runs on the copy's bucket once `cut_log.py` has cut it at a pass's version.
Every call is the pipeline's own function (bikesharing.shell.delta) on the
copy's `Lakehouse`, with the arguments `run.py` gives it, so each opens a fresh
`DeltaTable` as in production. The batch of calls 4-6 replays the copy's last
run (s019 #2, Probe B):

- setup, labelled `setup` and counted apart, reads that run (the latest
  `run_id`, a UUIDv7) from `processed_objects`: its objects and capture range,
  and its `station_stock` rows, from its local dates' partitions;
- call 5 merges those rows again, so it reads the same partitions;
- call 6 records as many objects as that run had, under new keys
  `t077-probe/<n>`, so its MERGE stays insert-only and reads the whole table.

Each table's version before a call starts at the version setup read and moves
to the commit a call writes, as seen by the proxy (a PutObject of
`_delta_log/<version>.json`). Commits since the last checkpoint are
`(version + 1) % 100`, since deltalake 1.6.6 checkpoints at versions 99, 199, ...
(s019 #8).

Inputs:  the copy's bucket, cut; .env with the copy token (as proxy.py).
Outputs: output/count-per-call/pass-<n>-requests.jsonl (one line per request)
         and pass-<n>-calls.csv (one row per call and one for setup); the table,
         with the totals of calls 1-8 and of all rows.

Usage:   uv run python count-per-call/count_calls.py --pass 1|2
"""

import argparse
import csv
import json
import re
import time
from collections import Counter
from datetime import UTC
from pathlib import Path

from arro3.core import Table
from deltalake import DeltaTable, QueryBuilder

from bikesharing.core.settings import LOCAL_TIMEZONE
from bikesharing.shell.delta import (
    ProcessedObject,
    _date,
    _string,
    _values,
    capture_history,
    ensure_tables,
    latest_captures,
    latest_processed,
    merge_station_stock,
    processed_keys,
    record_processed,
)
from bikesharing.shell.run import _VOLUME_WINDOW
from proxy import PROCESSED_OBJECTS_PATH, SPIKE_DIR, STATION_STOCK_PATH, TABLES, CountingProxy

OUTPUT_DIR = SPIKE_DIR / "output" / "count-per-call"
PROBE_PREFIX = "t077-probe/"
COMMIT = re.compile(r"^(.+)/_delta_log/(\d{20})\.json$")
SHORT = {STATION_STOCK_PATH: "stock", PROCESSED_OBJECTS_PATH: "processed"}

# The map's calls, in its order (s019, Lakehouse reads per run), with the tables each opens.
CALLS = [
    (1, "ensure_tables", TABLES),
    (2, "processed_keys", (PROCESSED_OBJECTS_PATH,)),
    (3, "latest_processed", (PROCESSED_OBJECTS_PATH,)),
    (4, "capture_history", (PROCESSED_OBJECTS_PATH,)),
    (5, "merge_station_stock", (STATION_STOCK_PATH,)),
    (6, "record_processed", (PROCESSED_OBJECTS_PATH,)),
    (7, "latest_processed", (PROCESSED_OBJECTS_PATH,)),
    (8, "latest_captures", (STATION_STOCK_PATH,)),
]


def query(table: DeltaTable, sql: str) -> Table:
    """Run `sql` over an open table, registered as `t`, with the pipeline's engine."""
    return Table.from_arrow(QueryBuilder().register("t", table).execute(sql))


def setup(lakehouse) -> dict:
    """Read the copy's last run: versions, objects, capture range and station_stock rows."""
    opts = dict(lakehouse.storage_options)
    po = DeltaTable(lakehouse.table_uri(PROCESSED_OBJECTS_PATH), storage_options=opts)
    ss = DeltaTable(lakehouse.table_uri(STATION_STOCK_PATH), storage_options=opts)
    head = query(po, f"select max(run_id) as run_id, "
                     f"count(*) filter (where starts_with(key, {_string(PROBE_PREFIX)})) as probes from t")
    run_id, probes = _values(head["run_id"])[0], _values(head["probes"])[0]
    if probes:
        raise SystemExit(f"The copy holds {probes} {PROBE_PREFIX} rows from an earlier count: "
                         "cut the log again (cut_log.py) before counting.")
    rows = query(po, f"select * from t where run_id = {_string(run_id)}")
    objects = [
        ProcessedObject(**{name: _values(rows[name])[i] for name in rows.column_names})
        for i in range(rows.num_rows)
    ]
    captures = [obj.captured_at.astimezone(UTC) for obj in objects]
    dates = sorted({c.astimezone(LOCAL_TIMEZONE).date() for c in captures})
    stock = query(ss, f"select * from t where run_id = {_string(run_id)} "
                      f"and local_date in ({', '.join(_date(d) for d in dates)})")
    return {
        "versions": {STATION_STOCK_PATH: ss.version(), PROCESSED_OBJECTS_PATH: po.version()},
        "run_id": run_id,
        "objects": objects,
        "first_capture": min(captures),
        "last_capture": max(captures),
        "stock": stock,
        "local_dates": sorted(set(_values(stock["local_date"]))),
    }


def calls(lakehouse, run: dict) -> dict:
    """The 8 calls, each with the arguments run.py gives it; streams are read in full,
    as the run writes them to Parquet, so their reads fall inside the call."""
    first = run["first_capture"]
    probe = [
        ProcessedObject(**{**{f: getattr(obj, f) for f in ProcessedObject.__slots__},
                           "key": f"{PROBE_PREFIX}{n}"})
        for n, obj in enumerate(run["objects"], start=1)
    ]
    return {
        1: lambda: ensure_tables(lakehouse),
        2: lambda: processed_keys(lakehouse),
        3: lambda: latest_processed(lakehouse),
        4: lambda: Table.from_arrow(capture_history(lakehouse, since=first - _VOLUME_WINDOW, until=first)),
        5: lambda: merge_station_stock(lakehouse, run["stock"], first_capture=first,
                                       last_capture=run["last_capture"], local_dates=run["local_dates"]),
        6: lambda: record_processed(lakehouse, probe),
        # As in run._publish: only the systems with a processed capture.
        7: lambda: run.update(latest={s: c for s, c in latest_processed(lakehouse).items() if c is not None}),
        8: lambda: Table.from_arrow(latest_captures(lakehouse, run["latest"])),
    }


def counts(lines: list[dict]) -> Counter:
    c = Counter()
    for line in lines:
        c["GetObject"] += line["operation"] == "GetObject"
        c["B_other"] += line["class"] == "B" and line["operation"] != "GetObject"
        c["A"] += line["class"] == "A"
        c["failed"] += line["status"] is None or line["status"] >= 500
    return c


def committed(lines: list[dict]) -> dict[str, int]:
    """Return the version each table's commit in these requests wrote."""
    written = {}
    for line in lines:
        m = COMMIT.match(line["key"])
        if m and line["operation"] == "PutObject" and line["status"] == 200:
            written[m[1]] = int(m[2])
    return written


def row(label: str, name: str, tables, versions: dict, lines: list[dict], seconds: float) -> dict:
    c = counts(lines)
    out = {"row": label, "call": name, "GetObject": c["GetObject"], "B_other": c["B_other"],
           "A": c["A"], "failed": c["failed"], "seconds": round(seconds, 2)}
    for table in TABLES:
        v = versions[table] if table in tables else None
        out[f"{SHORT[table]}_version"] = "" if v is None else v
        out[f"{SHORT[table]}_since"] = "" if v is None else (v + 1) % 100
    return out


def print_table(rows: list[dict]) -> None:
    print(f"{'row':<6}{'call':<22}{'GetObject':>10}{'B other':>9}{'A':>5}{'failed':>8}{'s':>8}"
          f"{'stock v':>9}{'since':>6}{'proc. v':>9}{'since':>6}")
    for r in rows:
        print(f"{r['row']:<6}{r['call']:<22}{r['GetObject']:>10,}{r['B_other']:>9,}{r['A']:>5,}"
              f"{r['failed']:>8,}{r['seconds']:>8.2f}{r['stock_version']!s:>9}{r['stock_since']!s:>6}"
              f"{r['processed_version']!s:>9}{r['processed_since']!s:>6}")
    for title, part in (("1-8", rows[1:]), ("all", rows)):
        t = sum((Counter({k: r[k] for k in ("GetObject", "B_other", "A", "failed", "seconds")})
                 for r in part), Counter())
        print(f"{title:<6}{'total':<22}{t['GetObject']:>10,}{t['B_other']:>9,}{t['A']:>5,}"
              f"{t['failed']:>8,}{t['seconds']:>8.2f}   Class B {t['GetObject'] + t['B_other']:,}")


def main(pass_no: int) -> None:
    t0 = time.monotonic()
    log_path: Path = OUTPUT_DIR / f"pass-{pass_no}-requests.jsonl"
    csv_path: Path = OUTPUT_DIR / f"pass-{pass_no}-calls.csv"
    timings = {}
    with CountingProxy(log_path) as proxy:
        lakehouse = proxy.lakehouse
        start = time.monotonic()
        with proxy.label("setup"):
            run = setup(lakehouse)
        timings["setup"] = time.monotonic() - start
        print(f"setup: run {run['run_id']}, {len(run['objects'])} objects from "
              f"{run['first_capture']:%Y-%m-%dT%H:%M:%S}Z to {run['last_capture']:%Y-%m-%dT%H:%M:%S}Z, "
              f"{run['stock'].num_rows:,} station_stock rows on {', '.join(map(str, run['local_dates']))}; "
              f"versions {run['versions']} ({timings['setup']:.1f} s)")
        steps = calls(lakehouse, run)
        for n, name, _ in CALLS:
            start = time.monotonic()
            with proxy.label(str(n)):
                steps[n]()
            timings[str(n)] = time.monotonic() - start
            print(f"call {n} {name}: {timings[str(n)]:.1f} s")

    lines = [json.loads(line) for line in log_path.read_text().splitlines()]
    by_label: dict[str, list[dict]] = {}
    for line in lines:
        by_label.setdefault(line["label"], []).append(line)
    versions = dict(run["versions"])
    rows = [row("setup", "setup", TABLES, versions, by_label.get("setup", []), timings["setup"])]
    for n, name, tables in CALLS:
        part = by_label.get(str(n), [])
        rows.append(row(str(n), name, tables, versions, part, timings[str(n)]))
        versions.update(committed(part))

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(lines):,} requests in {log_path.relative_to(SPIKE_DIR)}; rows in {csv_path.relative_to(SPIKE_DIR)}")
    print_table(rows)
    print(f"Elapsed: {time.monotonic() - t0:.1f} s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pass", dest="pass_no", type=int, choices=(1, 2), required=True,
                        help="the pass the copy was cut for (cut_log.py); it names the outputs")
    main(parser.parse_args().pass_no)
