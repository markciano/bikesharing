# Probe A of s010: checks that deltalake writes, MERGEs and keeps concurrent commits safe on R2.
#
# Subcommand `gate` (step 2) runs the D4 hard-cut checks: write, merge, concurrent.
# Input:  station_status objects of both providers from the local capture copy
#         (spikes/cloudflare-capture-spike/data/V4/raw/<provider>/station_status/<day>/<UTC time>.json.gz).
# Target: s3://<R2_TEST_BUCKET>/<run_id>/station_status on R2, or a temporary local table with --local.
# Output: one JSON line per check in output/probe-<run_id>.jsonl (output/local/ with --local),
#         and a summary table on the console.
#
# Usage: uv run python delta_probe.py gate [--local] [--day YYYY-MM-DD] [--start HH:MM] [--minutes N]

import argparse
import gzip
import json
import os
import statistics
import sys
import tempfile
import time
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
from deltalake import DeltaTable, write_deltalake
from deltalake.exceptions import CommitFailedError
from dotenv import load_dotenv

HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "cloudflare-capture-spike" / "data" / "V4" / "raw"
OUTPUT_DIR = HERE / "output"
PROVIDERS = ("ambici", "bicing")
KEY = ["source", "station_id", "last_reported"]

# Captured minutes per check; the window holds them in this order (decision log #32).
WRITE_COMMITS = 10
MERGE_COMMITS = 3
CONCURRENT_MINUTES = 4  # 2 for the MERGE pair, then 2 for the append pair
GATE_MINUTES = WRITE_COMMITS + MERGE_COMMITS + CONCURRENT_MINUTES

SCHEMA = {
    "source": pl.String,
    "station_id": pl.String,
    "last_reported": pl.Datetime("us", "UTC"),
    "captured_at": pl.Datetime("us", "UTC"),
    "bikes_available": pl.Int64,
    "docks_available": pl.Int64,
    "capture_date": pl.Date,
}


class CheckFailed(Exception):
    pass


# --- Sample -----------------------------------------------------------------


def first_full_day(data_dir: Path) -> str:
    # The first captured day is incomplete (§2 B), so the default is the second day both providers have.
    days = sorted(
        set.intersection(*(
            {p.name for p in (data_dir / provider / "station_status").iterdir() if p.is_dir()}
            for provider in PROVIDERS
        ))
    )
    if len(days) < 2:
        sys.exit(f"No full day of station_status in {data_dir}")
    return days[1]


def window_keys(data_dir: Path, provider: str, day: str, start: str, minutes: int) -> list[Path]:
    # Object keys are <UTC time>.json.gz, e.g. 20261015T000047Z.json.gz; one object per captured minute.
    folder = data_dir / provider / "station_status" / day
    start_key = day.replace("-", "") + "T" + start.replace(":", "")
    keys = sorted(p for p in folder.glob("*.json.gz") if p.name >= start_key)[:minutes]
    if len(keys) < minutes:
        sys.exit(f"{folder}: {len(keys)} objects from {start}, {minutes} needed")
    return keys


def parse_last_reported(value) -> datetime:
    # GBFS 2.x gives POSIX seconds (AMBici, 2.3); GBFS 3.0 gives RFC 3339 (Bicing).
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC)
    return datetime.fromisoformat(value).astimezone(UTC)


def load_object(provider: str, path: Path) -> pl.DataFrame:
    captured_at = datetime.strptime(path.name.removesuffix(".json.gz"), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    with gzip.open(path) as f:
        stations = json.load(f)["data"]["stations"]
    rows = [
        {
            "source": provider,
            "station_id": str(s["station_id"]),
            "last_reported": parse_last_reported(s["last_reported"]),
            "captured_at": captured_at,
            # GBFS 3.0 renamed num_bikes_available to num_vehicles_available.
            "bikes_available": s.get("num_bikes_available", s.get("num_vehicles_available")),
            "docks_available": s["num_docks_available"],
            "capture_date": captured_at.date(),
        }
        for s in stations
    ]
    return pl.DataFrame(rows, schema=SCHEMA)


def load_minutes(data_dir: Path, day: str, start: str, minutes: int) -> list[pl.DataFrame]:
    # One DataFrame per captured minute, with the rows of both providers.
    per_provider = {p: window_keys(data_dir, p, day, start, minutes) for p in PROVIDERS}
    return [
        pl.concat([load_object(p, per_provider[p][i]) for p in PROVIDERS])
        for i in range(minutes)
    ]


def new_keys_only(rows: pl.DataFrame, seen: set) -> pl.DataFrame:
    # Silver's dedup basis (#32): an append writes only keys not yet seen in the window; `seen` is updated.
    keys = list(rows.select(KEY).iter_rows())
    mask = [k not in seen for k in keys]
    seen.update(keys)
    return rows.filter(pl.Series(mask))


# --- Table ------------------------------------------------------------------


def r2_storage_options() -> dict[str, str]:
    load_dotenv(HERE / ".env")
    names = ["R2_ACCOUNT_ID", "R2_TEST_BUCKET", "R2_TEST_ACCESS_KEY_ID", "R2_TEST_SECRET_ACCESS_KEY"]
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(f"Missing in .env: {', '.join(missing)}")
    return {
        "AWS_ENDPOINT_URL": f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        "AWS_REGION": "auto",
        "AWS_ACCESS_KEY_ID": os.environ["R2_TEST_ACCESS_KEY_ID"],
        "AWS_SECRET_ACCESS_KEY": os.environ["R2_TEST_SECRET_ACCESS_KEY"],
        # Commits are put-if-absent (If-None-Match: *), which R2 enforces: no external lock (#18).
        "aws_conditional_put": "etag",
    }


class Table:
    def __init__(self, uri: str, storage_options: dict[str, str] | None):
        self.uri = uri
        self.options = storage_options

    def open(self) -> DeltaTable:
        return DeltaTable(self.uri, storage_options=self.options)

    def read(self) -> pl.DataFrame:
        return pl.read_delta(self.uri, storage_options=self.options)

    def version(self) -> int:
        return self.open().version()


def append(target: str | DeltaTable, rows: pl.DataFrame, options, mode: str = "append") -> None:
    write_deltalake(target, rows, mode=mode, partition_by=["capture_date"], storage_options=options)


def merge(dt: DeltaTable, rows: pl.DataFrame) -> dict:
    # Upsert on the key; the partition value in the predicate keeps conflict detection to that partition.
    days = ", ".join(f"'{d}'" for d in rows["capture_date"].unique().sort())
    predicate = f"t.capture_date IN ({days}) AND " + " AND ".join(f"t.{c} = s.{c}" for c in KEY)
    return (
        dt.merge(rows, predicate, source_alias="s", target_alias="t")
        .when_matched_update_all()
        .when_not_matched_insert_all()
        .execute()
    )


def upsert(model: pl.DataFrame, rows: pl.DataFrame) -> pl.DataFrame:
    # In-memory serial MERGE, the reference the table is compared with.
    return pl.concat([model.join(rows, on=KEY, how="anti"), rows])


def same_rows(actual: pl.DataFrame, expected: pl.DataFrame) -> bool:
    actual = actual.select(expected.columns).cast(expected.schema).sort(KEY + ["captured_at"])
    return actual.equals(expected.sort(KEY + ["captured_at"]))


def duplicate_keys(df: pl.DataFrame) -> int:
    return df.height - df.select(KEY).n_unique()


def ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)


# --- Checks -----------------------------------------------------------------
# Each check returns (version, commit latencies in ms, details) or raises CheckFailed.
# `state` carries the serial model of the table and the keys seen so far.


def check_write(table: Table, minutes: list[pl.DataFrame], state: dict):
    latencies, written = [], 0
    for i, minute in enumerate(minutes):
        rows = new_keys_only(minute, state["seen"])
        t0 = time.perf_counter()
        if i == 0:
            append(table.uri, rows, table.options, mode="error")  # creates the table
        else:
            append(table.open(), rows, table.options)  # fresh handle per commit (#27)
        latencies.append(ms(t0))
        written += rows.height
        state["model"] = pl.concat([state["model"], rows])
    dt = table.open()
    versions, count = len(dt.history()), table.read().height
    if versions != len(minutes) or count != written:
        raise CheckFailed(f"versions {versions} for {len(minutes)} commits, rows {count} for {written} written")
    return dt.version(), latencies, {"commits": len(minutes), "rows": count}


def check_merge(table: Table, minutes: list[pl.DataFrame], state: dict):
    latencies, stats = [], []
    for minute in minutes:
        t0 = time.perf_counter()
        result = merge(table.open(), minute)
        latencies.append(ms(t0))
        stats.append({k: result[k] for k in ("num_target_rows_updated", "num_target_rows_inserted")})
        state["model"] = upsert(state["model"], minute)
        state["seen"].update(minute.select(KEY).iter_rows())
    df = table.read()
    dups, distinct = duplicate_keys(df), df.select(KEY).n_unique()
    if dups or df.height != distinct:
        raise CheckFailed(f"{dups} duplicate keys; rows {df.height} for {distinct} distinct keys")
    return table.version(), latencies, {"commits": len(minutes), "rows": df.height, "merges": stats}


def stale_pair(table: Table, first, second):
    # Fault injection: two handles opened at the same version; one commits, then the other on its stale snapshot.
    t0 = time.perf_counter()
    dt_a = table.open()
    open_a = ms(t0)
    t0 = time.perf_counter()
    dt_b = table.open()
    open_b = ms(t0)
    base = dt_a.version()
    if dt_b.version() != base:
        raise CheckFailed("handles not opened at the same version")
    t0 = time.perf_counter()
    first(dt_a)
    lat_a = open_a + ms(t0)
    t0 = time.perf_counter()
    try:
        second(dt_b)
        outcome = "retried"
    except CommitFailedError as e:
        outcome = f"conflict: {e}"
    lat_b = open_b + ms(t0)
    return base, outcome, [lat_a, lat_b]


def check_concurrent(table: Table, minutes: list[pl.DataFrame], state: dict):
    details, latencies = {}, []

    # Two MERGEs on the same partition, with overlapping new keys: the insert race (#32).
    m1, m2 = minutes[0], minutes[1]
    base, outcome, lat = stale_pair(table, lambda dt: merge(dt, m1), lambda dt: merge(dt, m2))
    latencies += lat
    if outcome != "retried":
        # The rejected MERGE wrote nothing; it is retried on a fresh handle, as a pipeline run would.
        t0 = time.perf_counter()
        merge(table.open(), m2)
        latencies.append(ms(t0))
    state["model"] = upsert(upsert(state["model"], m1), m2)
    state["seen"].update(pl.concat([m1, m2]).select(KEY).iter_rows())
    df = table.read()
    details["merge_pair"] = {
        "base_version": base,
        "outcome": outcome,
        "version": table.version(),
        "duplicate_keys": duplicate_keys(df),
        "matches_serial": same_rows(df, state["model"]),
    }
    if details["merge_pair"]["duplicate_keys"] or not details["merge_pair"]["matches_serial"]:
        raise CheckFailed(f"merge pair: {details['merge_pair']}")

    # Two appends; the second minute is deduplicated against the first too (#32).
    a1 = new_keys_only(minutes[2], state["seen"])
    a2 = new_keys_only(minutes[3], state["seen"])
    base, outcome, lat = stale_pair(
        table, lambda dt: append(dt, a1, table.options), lambda dt: append(dt, a2, table.options)
    )
    latencies += lat
    state["model"] = pl.concat([state["model"], a1, a2])
    df = table.read()
    version = table.version()
    details["append_pair"] = {
        "base_version": base,
        "outcome": outcome,
        "version": version,
        "duplicate_keys": duplicate_keys(df),
        "matches_serial": same_rows(df, state["model"]),
    }
    # Compatible appends must both land, on consecutive versions.
    if (
        outcome != "retried"
        or version != base + 2
        or details["append_pair"]["duplicate_keys"]
        or not details["append_pair"]["matches_serial"]
    ):
        raise CheckFailed(f"append pair: {details['append_pair']}")
    return version, latencies, details


# --- Run --------------------------------------------------------------------


def run_gate(args) -> int:
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    day = args.day or first_full_day(args.data_dir)
    if args.minutes < GATE_MINUTES:
        sys.exit(f"--minutes must be at least {GATE_MINUTES}")
    minutes = load_minutes(args.data_dir, day, args.start, args.minutes)

    tmp = None
    if args.local:
        tmp = tempfile.TemporaryDirectory()
        table = Table(str(Path(tmp.name) / run_id / "station_status"), None)
        log_path = OUTPUT_DIR / "local" / f"probe-{run_id}.jsonl"
    else:
        options = r2_storage_options()
        table = Table(f"s3://{os.environ['R2_TEST_BUCKET']}/{run_id}/station_status", options)
        log_path = OUTPUT_DIR / f"probe-{run_id}.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    w, m = WRITE_COMMITS, WRITE_COMMITS + MERGE_COMMITS
    checks = [
        ("write", check_write, minutes[:w]),
        ("merge", check_merge, minutes[w:m]),
        ("concurrent", check_concurrent, minutes[m:m + CONCURRENT_MINUTES]),
    ]
    state = {"model": pl.DataFrame(schema=SCHEMA), "seen": set()}
    print(f"run_id {run_id} · table {table.uri} · day {day} from {args.start}, {args.minutes} minutes")

    summary, failed = [], False
    with log_path.open("a") as log:
        for name, check, data in checks:
            start = datetime.now(UTC)
            try:
                version, latencies, details = check(table, data, state)
                result = "ok"
            except Exception as e:  # any error is the check's result; the run stops
                version, latencies, details, result = None, [], {}, f"{type(e).__name__}: {e}"
                failed = True
            line = {
                "run_id": run_id,
                "check": name,
                "start": start.isoformat(),
                "end": datetime.now(UTC).isoformat(),
                "result": result,
                "version": version,
                "commit_latency_ms": latencies,
                "local": args.local,
                "details": details,
            }
            log.write(json.dumps(line, default=str) + "\n")
            summary.append((name, result, version, latencies))
            if failed:
                break

    print(f"\n{'check':<12}{'result':<8}{'version':>8}{'commits':>9}{'median ms':>11}{'max ms':>9}")
    for name, result, version, latencies in summary:
        med = f"{statistics.median(latencies):.0f}" if latencies else "-"
        top = f"{max(latencies):.0f}" if latencies else "-"
        shown = result if result == "ok" else "FAIL"
        print(f"{name:<12}{shown:<8}{str(version):>8}{len(latencies):>9}{med:>11}{top:>9}")
        if result != "ok":
            print(f"  {result}")
    print(f"\nlog: {log_path.relative_to(HERE)}")
    if tmp:
        tmp.cleanup()
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    gate = sub.add_parser("gate", help="D4 hard-cut checks: write, merge, concurrent")
    gate.add_argument("--local", action="store_true", help="run against a temporary local table, not R2")
    gate.add_argument("--data-dir", type=Path, default=DATA_DIR)
    gate.add_argument("--day", help="UTC day YYYY-MM-DD (default: first full captured day)")
    gate.add_argument("--start", default="00:00", help="UTC start HH:MM (default: 00:00)")
    gate.add_argument("--minutes", type=int, default=GATE_MINUTES, help=f"captured minutes (default: {GATE_MINUTES})")
    args = parser.parse_args()
    if args.day:
        date.fromisoformat(args.day)
    return run_gate(args)


if __name__ == "__main__":
    sys.exit(main())
