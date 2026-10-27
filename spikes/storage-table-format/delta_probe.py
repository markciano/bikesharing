# Probe A of s010: checks that deltalake writes, MERGEs and keeps concurrent commits safe on R2,
# and measures what C needs (operations per commit through the proxy, bytes per row, log overhead).
#
# Subcommands:
#   gate  (step 2) the D4 hard-cut checks: write, merge, concurrent; requests go directly to R2.
#   full  (step 4) the counted run, through the proxy (r2_proxy.py): write (60 commits), merge (10),
#         concurrent, optimize, vacuum, on a table with delta.checkpointInterval = 10 (#27). After each
#         check, a measure window reads the table's log to record versions, bytes and checkpoints.
#   extra (step 4) after full, on its table: Polars and DuckDB reads, token scope, bucket lock (#22).
# Input:  station_status objects of both providers from the local capture copy
#         (spikes/cloudflare-capture-spike/data/V4/raw/<provider>/station_status/<day>/<UTC time>.json.gz).
# Target: s3://<R2_TEST_BUCKET>/<run_id>/station_status on R2, or a temporary local table with --local.
# Output: one JSON line per check in output/probe-<run_id>.jsonl (output/local/ with --local),
#         and a summary table on the console. extra appends to full's file.
#
# Usage: uv run python delta_probe.py gate|full [--local] [--day YYYY-MM-DD] [--start HH:MM] [--minutes N]
#        uv run python delta_probe.py extra --run-id ID [--skip CHECK ...] [--only CHECK [--no-proxy]]

import argparse
import gzip
import json
import math
import os
import statistics
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

import boto3
import duckdb
import polars as pl
from botocore.config import Config
from botocore.exceptions import ClientError
from deltalake import DeltaTable, QueryBuilder, write_deltalake
from deltalake.exceptions import CommitFailedError
from dotenv import load_dotenv

HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "cloudflare-capture-spike" / "data" / "V4" / "raw"
OUTPUT_DIR = HERE / "output"
PROVIDERS = ("ambici", "bicing")
KEY = ["source", "station_id", "last_reported"]

# Captured minutes per check; the window holds them in this order (decision log #32).
CONCURRENT_MINUTES = 4  # 2 for the MERGE pair, then 2 for the append pair
MODES = {
    "gate": {"write": 10, "merge": 3, "proxied": False, "measure": False, "config": None},
    "full": {"write": 60, "merge": 10, "proxied": True, "measure": True,
             "config": {"delta.checkpointInterval": "10"}},
}
for _mode in MODES.values():
    _mode["minutes"] = _mode["write"] + _mode["merge"] + CONCURRENT_MINUTES

EXTRA_CHECKS = ("polars", "duckdb", "token", "lock")
# The delta extension's log reads (delta-kernel) take no proxy or CA setting (F6): its check runs uncounted.
NO_PROXY_CLIENTS = {"duckdb"}

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


def now() -> str:
    return datetime.now(UTC).isoformat()


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


# --- Connections ------------------------------------------------------------


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


def proxy_settings() -> tuple[str, Path]:
    # Called before the first request of a counted run: no request may bypass the proxy.
    load_dotenv(HERE / ".env")
    url, ca = os.environ.get("PROXY_URL", ""), os.environ.get("PROXY_CA_CERT", "")
    if not url or not ca:
        sys.exit("PROXY_URL and PROXY_CA_CERT must be set: every request of full and extra goes through the proxy")
    ca_path = Path(ca).expanduser()
    if not ca_path.is_file():
        sys.exit(f"PROXY_CA_CERT not found: {ca_path} (run mitmdump once to create it)")
    return url, ca_path


def proxied_options(proxy: tuple[str, Path]) -> dict[str, str]:
    # object_store client options, used by deltalake and Polars; the CA is PEM content, not a path.
    url, ca_path = proxy
    return {"proxy_url": url, "proxy_ca_certificate": ca_path.read_text()}


def s3_client(proxy: tuple[str, Path] | None):
    # boto3 reaches the proxy through its own Config and trusts its CA through `verify`, in this process only.
    config = Config(
        region_name="auto",
        s3={"addressing_style": "path"},
        # boto3 >= 1.36 adds CRC32 checksums by default, which R2 is reported to reject.
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
        proxies={"http": proxy[0], "https": proxy[0]} if proxy else None,
    )
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_TEST_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_TEST_SECRET_ACCESS_KEY"],
        config=config,
        verify=str(proxy[1]) if proxy else None,
    )


# --- Table ------------------------------------------------------------------


class Table:
    def __init__(self, uri: str, storage_options: dict[str, str] | None, config=None, read_via_delta=False):
        self.uri = uri
        self.options = storage_options
        self.config = config  # table properties set when the first commit creates the table
        # full reads through deltalake, whose proxy setting is confirmed; gate keeps Polars' reader.
        self.read_via_delta = read_via_delta

    def open(self) -> DeltaTable:
        return DeltaTable(self.uri, storage_options=self.options)

    def read(self) -> pl.DataFrame:
        if self.read_via_delta:
            reader = QueryBuilder().register("t", self.open()).execute("SELECT * FROM t")
            return pl.DataFrame(reader.read_all())
        return pl.read_delta(self.uri, storage_options=self.options)

    def version(self) -> int:
        return self.open().version()


class LogStore:
    # Lists and reads the table's _delta_log for the measure windows: a local folder or the R2 prefix.
    def __init__(self, table: Table, s3=None, bucket: str | None = None, prefix: str | None = None):
        self.local = None if s3 else Path(table.uri) / "_delta_log"
        self.s3, self.bucket, self.prefix = s3, bucket, f"{prefix}/_delta_log/" if prefix else None

    def sizes(self) -> dict[str, int]:
        if self.local:
            return {p.name: p.stat().st_size for p in self.local.iterdir() if p.is_file()}
        pages = self.s3.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=self.prefix)
        return {o["Key"].removeprefix(self.prefix): o["Size"] for page in pages for o in page.get("Contents", [])}

    def read(self, name: str) -> bytes:
        if self.local:
            return (self.local / name).read_bytes()
        return self.s3.get_object(Bucket=self.bucket, Key=self.prefix + name)["Body"].read()


def append(target: str | DeltaTable, rows: pl.DataFrame, options, mode: str = "append", configuration=None) -> None:
    write_deltalake(
        target, rows, mode=mode, partition_by=["capture_date"], storage_options=options, configuration=configuration
    )


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


def add_actions(dt: DeltaTable) -> pl.DataFrame:
    return pl.DataFrame(dt.get_add_actions(flatten=True))


def partition_files(dt: DeltaTable, rows: pl.DataFrame) -> int:
    # Files in the MERGE's target partition, from the handle's snapshot (#27).
    days = {str(d) for d in rows["capture_date"].unique()}
    adds = add_actions(dt)
    return adds.filter(pl.col("partition.capture_date").cast(pl.String).is_in(days)).height


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


@contextmanager
def window(state: dict, op: str, **fields):
    # One operation's time window: analyse_ops.py assigns the requests inside it to this operation.
    # Windows never overlap; requests in a check outside every window are its verification reads.
    rec = {"op": op, "start": now(), **fields}
    t0 = time.perf_counter()
    yield rec
    rec["latency_ms"] = ms(t0)
    rec["end"] = now()
    state["ops"].append(rec)


# --- Checks -----------------------------------------------------------------
# Each check returns (version, commit latencies in ms, details) or raises CheckFailed.
# `state` carries the serial model of the table, the keys seen so far and the operation windows.


def check_write(table: Table, minutes: list[pl.DataFrame], state: dict):
    latencies, written = [], 0
    for i, minute in enumerate(minutes):
        rows = new_keys_only(minute, state["seen"])
        with window(state, "append", handle_version=None) as w:
            if i == 0:
                append(table.uri, rows, table.options, mode="error", configuration=table.config)  # creates the table
                w["version_after"] = 0
            else:
                dt = table.open()  # fresh handle per commit (#27)
                w["handle_version"] = dt.version()
                append(dt, rows, table.options)
                w["version_after"] = dt.version()
        latencies.append(w["latency_ms"])
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
        with window(state, "merge") as w:
            dt = table.open()
            w["handle_version"] = dt.version()
            if state["measure"]:
                w["partition_files"] = partition_files(dt, minute)
            result = merge(dt, minute)
            w["version_after"] = dt.version()
        latencies.append(w["latency_ms"])
        stats.append({k: result[k] for k in ("num_target_rows_updated", "num_target_rows_inserted")})
        state["model"] = upsert(state["model"], minute)
        state["seen"].update(minute.select(KEY).iter_rows())
    df = table.read()
    dups, distinct = duplicate_keys(df), df.select(KEY).n_unique()
    if dups or df.height != distinct:
        raise CheckFailed(f"{dups} duplicate keys; rows {df.height} for {distinct} distinct keys")
    return table.version(), latencies, {"commits": len(minutes), "rows": df.height, "merges": stats}


def stale_pair(table: Table, state: dict, op: str, first, second):
    # Fault injection: two handles opened at the same version; one commits, then the other on its stale snapshot.
    with window(state, "load") as load_a:
        dt_a = table.open()
    with window(state, "load") as load_b:
        dt_b = table.open()
    base = dt_a.version()
    if dt_b.version() != base:
        raise CheckFailed("handles not opened at the same version")
    with window(state, op, handle_version=base) as commit_a:
        first(dt_a)
        commit_a["version_after"] = dt_a.version()
    with window(state, op, handle_version=base) as commit_b:
        try:
            second(dt_b)
            outcome = "retried"
        except CommitFailedError as e:
            outcome = f"conflict: {e}"
        commit_b["version_after"] = dt_b.version()
    latencies = [load_a["latency_ms"] + commit_a["latency_ms"], load_b["latency_ms"] + commit_b["latency_ms"]]
    return base, outcome, latencies, {"start": load_a["start"], "end": commit_b["end"]}


def check_concurrent(table: Table, minutes: list[pl.DataFrame], state: dict):
    details, latencies = {}, []

    # Two MERGEs on the same partition, with overlapping new keys: the insert race (#32).
    m1, m2 = minutes[0], minutes[1]
    base, outcome, lat, span = stale_pair(table, state, "merge", lambda dt: merge(dt, m1), lambda dt: merge(dt, m2))
    latencies += lat
    if outcome != "retried":
        # The rejected MERGE wrote nothing; it is retried on a fresh handle, as a pipeline run would.
        with window(state, "merge") as w:
            dt = table.open()
            w["handle_version"] = dt.version()
            merge(dt, m2)
            w["version_after"] = dt.version()
        latencies.append(w["latency_ms"])
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
    if state["measure"]:
        details["merge_pair"].update(span)

    # Two appends; the second minute is deduplicated against the first too (#32).
    a1 = new_keys_only(minutes[2], state["seen"])
    a2 = new_keys_only(minutes[3], state["seen"])
    base, outcome, lat, span = stale_pair(
        table, state, "append", lambda dt: append(dt, a1, table.options), lambda dt: append(dt, a2, table.options)
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
    if state["measure"]:
        details["append_pair"].update(span)
        details["rows"] = df.height
    return version, latencies, details


def check_optimize(table: Table, _minutes, state: dict):
    files_before = add_actions(table.open()).height
    with window(state, "optimize") as w:
        dt = table.open()
        w["handle_version"] = dt.version()
        metrics = dt.optimize.compact()
    df = table.read()
    files_after = add_actions(table.open()).height
    details = {"files_before": files_before, "files_after": files_after, "rows": df.height, "metrics": metrics}
    if files_after >= files_before or not same_rows(df, state["model"]):
        raise CheckFailed(f"optimize: {details}")
    return table.version(), [w["latency_ms"]], details


def check_vacuum(table: Table, _minutes, state: dict):
    # A dry run with the default 7-day retention finds nothing to delete; zero retention lets the probe
    # see files deleted (step 4 Scope). Each run opens a fresh handle, as a pipeline run would.
    with window(state, "vacuum_dry_run") as dry:
        dt = table.open()
        dry["handle_version"] = dt.version()
        candidates = dt.vacuum(dry_run=True)
    with window(state, "vacuum") as run:
        dt = table.open()
        run["handle_version"] = dt.version()
        deleted = dt.vacuum(retention_hours=0, dry_run=False, enforce_retention_duration=False)
    df = table.read()
    details = {"dry_run_files": len(candidates), "deleted_files": len(deleted), "rows": df.height}
    if candidates or not deleted or not same_rows(df, state["model"]):
        raise CheckFailed(f"vacuum: {details}")
    return table.version(), [dry["latency_ms"], run["latency_ms"]], details


# --- Measure (full) ---------------------------------------------------------


def epoch_ms(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp() * 1000


def json_commits_loaded(handle_version: int, checkpoints: list[int]) -> int:
    # A fresh handle at version h loads the last checkpoint c <= h, then the JSON commits c+1..h.
    previous = [c for c in checkpoints if c <= handle_version]
    return handle_version - previous[-1] if previous else handle_version + 1


def measure(table: Table, store: LogStore, state: dict, ops: list[dict]) -> dict:
    # Reads the log after a check: each new version is assigned to the operation whose window holds its
    # commit timestamp, and the operations and the check get the bytes, files and checkpoints C needs.
    start = now()
    sizes = store.sizes()
    checkpoints = sorted(int(n[:20]) for n in sizes if n.endswith(".checkpoint.parquet"))
    new = []
    for name in sorted(n for n in sizes if len(n) == 25 and n.endswith(".json") and n[:20].isdigit()):
        v = int(name[:20])
        if v in state["versions"]:
            continue
        actions = [json.loads(line) for line in store.read(name).splitlines() if line.strip()]
        adds = [a["add"] for a in actions if "add" in a]
        removes = [a["remove"] for a in actions if "remove" in a]
        info = next(a["commitInfo"] for a in actions if "commitInfo" in a)
        state["versions"][v] = {
            "timestamp": info.get("timestamp"),
            "operation": info.get("operation"),
            "json_bytes": sizes[name],
            "checkpoint_bytes": sizes.get(f"{v:020}.checkpoint.parquet"),
            "files_added": len(adds),
            "bytes_added": sum(a.get("size", 0) for a in adds),
            "rows_added": sum(json.loads(a["stats"]).get("numRecords", 0) for a in adds if a.get("stats")),
            "files_removed": len(removes),
            "bytes_removed": sum(r.get("size") or 0 for r in removes),
        }
        new.append(v)

    # A version goes to the first operation whose window holds its timestamp (ms, truncated) and that
    # reached it: append and MERGE handles know their version after the commit, which keeps a stale
    # writer's version out of the window of the commit before it.
    owner = {}
    for v in new:
        ts = state["versions"][v]["timestamp"]
        for i, op in enumerate(ops):
            if (math.floor(epoch_ms(op["start"])) <= ts <= math.ceil(epoch_ms(op["end"]))
                    and v <= op.get("version_after", v)):
                owner[v] = i
                break
    for i, op in enumerate(ops):
        vs = [v for v in new if owner.get(v) == i]
        info = [state["versions"][v] for v in vs]
        op.update({
            "versions": vs,
            "json_bytes": sum(i["json_bytes"] for i in info),
            "checkpoint": any(i["checkpoint_bytes"] for i in info),
            "checkpoint_bytes": sum(i["checkpoint_bytes"] or 0 for i in info),
            **{k: sum(i[k] for i in info)
               for k in ("files_added", "bytes_added", "rows_added", "files_removed", "bytes_removed")},
        })
        if op.get("handle_version") is not None:
            op["json_commits_loaded"] = json_commits_loaded(op["handle_version"], checkpoints)

    info = [state["versions"][v] for v in new]
    adds = add_actions(table.open())
    return {
        "start": start,
        "end": now(),
        "versions": new,
        "unassigned_versions": [v for v in new if v not in owner],
        "parquet_bytes_per_row": round(adds["size_bytes"].sum() / max(adds["num_records"].sum(), 1), 2),
        "data_files": adds.height,
        "log_bytes_per_commit": round(statistics.mean(i["json_bytes"] for i in info), 1) if info else None,
        "checkpoints": sum(1 for i in info if i["checkpoint_bytes"]),
        "checkpoint_bytes": sum(i["checkpoint_bytes"] or 0 for i in info),
        # Bytes of the files written by commits that also removed files: MERGE rewrites and compaction.
        "bytes_rewritten": sum(i["bytes_added"] for i in info if i["files_removed"]),
        "bytes_removed": sum(i["bytes_removed"] for i in info),
    }


# --- Run --------------------------------------------------------------------


def print_summary(summary: list, log_path: Path) -> None:
    print(f"\n{'check':<12}{'result':<8}{'version':>8}{'commits':>9}{'median ms':>11}{'max ms':>9}")
    for name, result, version, latencies in summary:
        med = f"{statistics.median(latencies):.0f}" if latencies else "-"
        top = f"{max(latencies):.0f}" if latencies else "-"
        shown = result if result == "ok" else "FAIL"
        print(f"{name:<12}{shown:<8}{str(version):>8}{len(latencies):>9}{med:>11}{top:>9}")
        if result != "ok":
            print(f"  {result}")
    print(f"\nlog: {log_path.relative_to(HERE)}")


def run_checks(args) -> int:
    mode = MODES[args.command]
    full = args.command == "full"
    proxy = None
    if mode["proxied"] and not args.local:
        proxy = proxy_settings()  # aborts before any request if the proxy is not set
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    day = args.day or first_full_day(args.data_dir)
    if args.minutes < mode["minutes"]:
        sys.exit(f"--minutes must be at least {mode['minutes']}")
    minutes = load_minutes(args.data_dir, day, args.start, args.minutes)

    tmp = None
    if args.local:
        tmp = tempfile.TemporaryDirectory()
        table = Table(str(Path(tmp.name) / run_id / "station_status"), None, mode["config"], read_via_delta=full)
        store = LogStore(table)
        log_path = OUTPUT_DIR / "local" / f"probe-{run_id}.jsonl"
    else:
        options = r2_storage_options()
        if proxy:
            options |= proxied_options(proxy)
        bucket = os.environ["R2_TEST_BUCKET"]
        table = Table(f"s3://{bucket}/{run_id}/station_status", options, mode["config"], read_via_delta=full)
        store = LogStore(table, s3_client(proxy), bucket, f"{run_id}/station_status") if full else None
        log_path = OUTPUT_DIR / f"probe-{run_id}.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    w, m = mode["write"], mode["write"] + mode["merge"]
    checks = [
        ("write", check_write, minutes[:w]),
        ("merge", check_merge, minutes[w:m]),
        ("concurrent", check_concurrent, minutes[m:m + CONCURRENT_MINUTES]),
    ]
    if full:
        checks += [("optimize", check_optimize, None), ("vacuum", check_vacuum, None)]
    state = {"model": pl.DataFrame(schema=SCHEMA), "seen": set(), "ops": [], "versions": {}, "measure": full}
    print(f"run_id {run_id} · table {table.uri} · day {day} from {args.start}, {args.minutes} minutes")

    summary, failed = [], False
    with log_path.open("a") as log:
        for name, check, data in checks:
            state["ops"] = []
            start = now()
            try:
                version, latencies, details = check(table, data, state)
                result = "ok"
            except Exception as e:  # any error is the check's result; the run stops
                version, latencies, details, result = None, [], {}, f"{type(e).__name__}: {e}"
                failed = True
            line = {
                "run_id": run_id,
                "check": name,
                "start": start,
                "end": now(),
                "result": result,
                "version": version,
                "commit_latency_ms": latencies,
                "local": args.local,
                "details": details,
            }
            if full:
                line = {"phase": "full", **line, "ops": state["ops"]}
                if not failed:
                    try:
                        line["measure"] = measure(table, store, state, state["ops"])
                    except Exception as e:  # C needs the measures: a failed measure stops the run
                        line["result"] = result = f"measure failed: {type(e).__name__}: {e}"
                        failed = True
            log.write(json.dumps(line, default=str) + "\n")
            summary.append((name, result, version, latencies))
            if failed:
                break

    print_summary(summary, log_path)
    if full:
        print(f"run_id {run_id}")
    if tmp:
        tmp.cleanup()
    return 1 if failed else 0


# --- Extra ------------------------------------------------------------------


def attempt(call) -> dict:
    # One S3 call whose permission is under test: allowed, or denied with its status and error code.
    try:
        response = call()
        return {"allowed": True, "status": response["ResponseMetadata"]["HTTPStatusCode"]}
    except ClientError as e:
        return {"allowed": False, "status": e.response["ResponseMetadata"]["HTTPStatusCode"],
                "code": e.response["Error"]["Code"]}


def denied(result: dict) -> bool:
    return not result["allowed"] and result["status"] in (401, 403)


def extra_polars(ctx: dict) -> dict:
    rows = pl.read_delta(ctx["uri"], storage_options=ctx["options"]).height
    if rows != ctx["expected_rows"]:
        raise CheckFailed(f"Polars read {rows} rows, {ctx['expected_rows']} expected")
    return {"rows": rows}


def extra_duckdb(ctx: dict) -> dict:
    con = duckdb.connect()
    con.execute("INSTALL delta")
    con.execute("LOAD delta")
    secret = {k: os.environ[v].replace("'", "''") for k, v in (
        ("KEY_ID", "R2_TEST_ACCESS_KEY_ID"), ("SECRET", "R2_TEST_SECRET_ACCESS_KEY"), ("ACCOUNT_ID", "R2_ACCOUNT_ID"))}
    con.execute("CREATE SECRET s010 (TYPE r2, " + ", ".join(f"{k} '{v}'" for k, v in secret.items()) + ")")
    r2_uri = ctx["uri"].replace("s3://", "r2://", 1)
    rows = con.execute(f"SELECT count(*) FROM delta_scan('{r2_uri}')").fetchone()[0]
    if rows != ctx["expected_rows"]:
        raise CheckFailed(f"DuckDB read {rows} rows, {ctx['expected_rows']} expected")
    return {"rows": rows}


def extra_token(ctx: dict) -> dict:
    # The test token must not list, read or write the production bucket (D7). The read uses a key that
    # exists there (the local copy mirrors the bucket), so a 404 would mean the read was not denied.
    s3, prod = ctx["s3"], os.environ["R2_PROD_BUCKET"]
    sample = next((DATA_DIR / "ambici" / "station_status" / first_full_day(DATA_DIR)).glob("*.json.gz"))
    details = {
        "list": attempt(lambda: s3.list_objects_v2(Bucket=prod, MaxKeys=1)),
        "read": attempt(lambda: s3.get_object(Bucket=prod, Key=str(sample.relative_to(DATA_DIR.parent)))),
        "write": attempt(lambda: s3.put_object(Bucket=prod, Key="s010-token-check/canary.txt", Body=b"s010")),
    }
    if not all(denied(r) for r in details.values()):
        raise CheckFailed(f"token reaches {prod}: {details}")
    return details


def extra_lock(ctx: dict) -> dict:
    # Under the locked prefix, a new object is written; an overwrite and a delete must then fail (D7).
    s3, bucket = ctx["s3"], os.environ["R2_TEST_BUCKET"]
    key = f"{os.environ['R2_LOCKED_PREFIX']}{ctx['run_id']}/lock-check.txt"
    details = {
        "key": key,
        "create": attempt(lambda: s3.put_object(Bucket=bucket, Key=key, Body=b"original")),
        "overwrite": attempt(lambda: s3.put_object(Bucket=bucket, Key=key, Body=b"overwrite")),
        "delete": attempt(lambda: s3.delete_object(Bucket=bucket, Key=key)),
    }
    details["unchanged"] = s3.get_object(Bucket=bucket, Key=key)["Body"].read() == b"original"
    if not (details["create"]["allowed"] and not details["overwrite"]["allowed"]
            and not details["delete"]["allowed"] and details["unchanged"]):
        raise CheckFailed(f"lock: {details}")
    return details


EXTRA = {"polars": extra_polars, "duckdb": extra_duckdb, "token": extra_token, "lock": extra_lock}


def run_extra(args, parser) -> int:
    if args.no_proxy and not args.only:
        parser.error("--no-proxy needs --only: only one check of a client that cannot use the proxy runs uncounted")
    names = [args.only] if args.only else [c for c in EXTRA_CHECKS if c not in (args.skip or [])]
    proxy = None if args.no_proxy else proxy_settings()  # aborts before any request if the proxy is not set
    if proxy and NO_PROXY_CLIENTS & set(names):
        sys.exit(f"{', '.join(sorted(NO_PROXY_CLIENTS & set(names)))} cannot use the proxy (F6): "
                 "add --skip duckdb, and run --only duckdb --no-proxy on another day")
    log_path = OUTPUT_DIR / f"probe-{args.run_id}.jsonl"
    if not log_path.is_file():
        sys.exit(f"No log of run {args.run_id}: {log_path.relative_to(HERE)}")
    full_lines = [json.loads(line) for line in log_path.read_text().splitlines()]
    full_lines = [line for line in full_lines if line.get("phase") == "full" and "rows" in line["details"]]
    if not full_lines:
        sys.exit(f"Run {args.run_id} has no full check with a row count")

    options = r2_storage_options()
    if proxy:
        options |= proxied_options(proxy)
    ctx = {
        "run_id": args.run_id,
        "uri": f"s3://{os.environ['R2_TEST_BUCKET']}/{args.run_id}/station_status",
        "options": options,
        "expected_rows": full_lines[-1]["details"]["rows"],
        "s3": s3_client(proxy),
    }
    print(f"run_id {args.run_id} · extra checks {', '.join(names)} · proxy {'on' if proxy else 'off (uncounted)'}")

    summary, failed = [], False
    with log_path.open("a") as log:
        for name in names:
            start = now()
            try:
                details, result = EXTRA[name](ctx), "ok"
            except Exception as e:
                details, result, failed = {}, f"{type(e).__name__}: {e}", True
            line = {"phase": "extra", "run_id": args.run_id, "check": name, "start": start, "end": now(),
                    "result": result, "proxied": proxy is not None, "details": details}
            log.write(json.dumps(line, default=str) + "\n")
            summary.append((name, result, None, []))
    print_summary(summary, log_path)
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="s010 probe A: Delta Lake on R2")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("gate", "D4 hard-cut checks: write, merge, concurrent"),
                            ("full", "counted run through the proxy: gate's checks, optimize, vacuum")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--local", action="store_true", help="run against a temporary local table, not R2")
        p.add_argument("--data-dir", type=Path, default=DATA_DIR)
        p.add_argument("--day", help="UTC day YYYY-MM-DD (default: first full captured day)")
        p.add_argument("--start", default="00:00", help="UTC start HH:MM (default: 00:00)")
        p.add_argument("--minutes", type=int, default=MODES[name]["minutes"],
                       help=f"captured minutes (default: {MODES[name]['minutes']})")
    extra = sub.add_parser("extra", help="after full: Polars and DuckDB reads, token scope, bucket lock")
    extra.add_argument("--run-id", required=True, help="run_id printed by full")
    extra.add_argument("--skip", action="append", choices=EXTRA_CHECKS, help="leave a check out (repeatable)")
    extra.add_argument("--only", choices=EXTRA_CHECKS, help="run one check alone")
    extra.add_argument("--no-proxy", action="store_true", help="with --only: run the check uncounted, without the proxy")
    args = parser.parse_args()
    if args.command == "extra":
        return run_extra(args, parser)
    if args.day:
        date.fromisoformat(args.day)
    return run_checks(args)


if __name__ == "__main__":
    sys.exit(main())
