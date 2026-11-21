"""Independent validation of silver/station_stock against bronze (d008, Step 29).

Throwaway, read-only. It re-derives what the table should hold from the raw
bronze objects with its own small implementation, never the pipeline's code, so
that a bug shared by the pipeline and a copy of it cannot pass unseen. Run it
with the pipeline's locked environment, as many times as wanted during the
drain:

    uv run --directory pipeline python ../spikes/d008-s29-validation/station-stock-matches-bronze/validate_station_stock.py

Each run pins the table's current Delta version, validates only what is new
since the last run without a failure (``--full`` validates everything), prints a
report and saves it under ``out/``.

Checks: (1) counts per day against bronze, (2) field by field on a sample of
captures, (3) ranges and nulls, (4) local calendar keys and the DST day.
"""

import argparse
import gzip
import json
import os
import random
import re
import sys
import threading
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import obstore
from arro3.core import Table
from deltalake import DeltaTable, QueryBuilder
from obstore.store import LocalStore, ObjectStore, S3Store

ACCOUNT_ID = "b88ece5b9aad94b83f1710afa6d24070"
BRONZE_BUCKET = "bikesharing-bronze"
LAKEHOUSE_BUCKET = "bikesharing-lakehouse"
STOCK_PATH = "silver/station_stock"
SYSTEMS = ("ambici", "bicing")
MADRID = ZoneInfo("Europe/Madrid")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
STATE_FILE = HERE / "state.json"
OUT_DIR = HERE / "out"
EXCLUDED_FILE = REPO / "pipeline" / "config" / "excluded_objects.txt"
FIXTURES = REPO / "pipeline" / "tests" / "fixtures" / "bronze"

KEY_RE = re.compile(
    r"raw/(?P<system>[a-z0-9_]+)/station_status/(?P<date>\d{4}-\d{2}-\d{2})/"
    r"(?P<run_id>\d{8}T\d{6}Z)\.json\.gz"
)
SHA_RE = re.compile(r"[0-9a-f]{40}")

# The night Europe/Madrid leaves summer time: 25 local hours (ADR-0041).
DST_LOCAL_DATE = date(2026, 10, 25)
DST_START_UTC = datetime(2026, 10, 24, 22, 0, tzinfo=UTC)
DST_END_UTC = datetime(2026, 10, 25, 23, 0, tzinfo=UTC)

FIELDS = (
    "num_vehicles_available",
    "num_docks_available",
    "num_vehicles_disabled",
    "num_docks_disabled",
    "is_installed",
    "is_renting",
    "is_returning",
    "last_reported",
    "last_updated",
)
TIME_BUCKETS = (
    ("night", range(0, 6)),
    ("morning peak", range(7, 10)),
    ("evening peak", range(17, 20)),
)
MAX_DIFFS_PER_CAPTURE = 5
MAX_DIFFS_SHOWN = 20

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


# --- pure helpers: what the table should hold ---------------------------------


def ensure_utc(value: datetime) -> datetime:
    """Return an aware datetime in UTC, taking a naive one as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_instant(value: Any) -> datetime | None:
    """Parse a GBFS instant: POSIX seconds (2.x) or RFC 3339 text (3.0)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def parse_key(key: str) -> tuple[str, datetime] | None:
    """Return the system and capture instant a bronze key names, or None."""
    match = KEY_RE.fullmatch(key)
    if match is None:
        return None
    captured_at = datetime.strptime(match["run_id"], "%Y%m%dT%H%M%SZ").replace(
        tzinfo=UTC
    )
    if captured_at.date().isoformat() != match["date"]:
        return None
    return match["system"], captured_at


def bronze_key(system: str, captured_at: datetime) -> str:
    """Return the key of a capture's ``station_status`` object."""
    return (
        f"raw/{system}/station_status/{captured_at:%Y-%m-%d}/"
        f"{captured_at:%Y%m%dT%H%M%SZ}.json.gz"
    )


def expected_rows(system: str, doc: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the rows a bronze object should produce, by station ID.

    The rules are written from the data contract, not copied from the pipeline:
    TR5 (AMBici's ``num_bikes_available`` is ``num_vehicles_available``), TR6 and
    TR7 (flags and ``last_reported`` as published), TR8 (disabled counts as
    published by Bicing, null for AMBici) and TR9 (null vehicles at a Bicing
    station that neither rents nor returns).
    """
    last_updated = parse_instant(doc.get("last_updated"))
    rows: dict[str, dict[str, Any]] = {}
    for station in doc["data"]["stations"]:
        if system == "bicing":
            out_of_service = not station["is_renting"] and not station["is_returning"]
            vehicles = None if out_of_service else station.get("num_vehicles_available")
            disabled_vehicles = station.get("num_vehicles_disabled")
            disabled_docks = station.get("num_docks_disabled")
        else:
            vehicles = station.get("num_bikes_available")
            disabled_vehicles = None
            disabled_docks = None
        rows[str(station["station_id"])] = {
            "num_vehicles_available": vehicles,
            "num_docks_available": station.get("num_docks_available"),
            "num_vehicles_disabled": disabled_vehicles,
            "num_docks_disabled": disabled_docks,
            "is_installed": station.get("is_installed"),
            "is_renting": station.get("is_renting"),
            "is_returning": station.get("is_returning"),
            "last_reported": parse_instant(station.get("last_reported")),
            "last_updated": last_updated,
        }
    return rows


def local_keys(captured_at: datetime) -> tuple[date, int]:
    """Return the local date and the minute of the local day of an instant."""
    local = captured_at.astimezone(MADRID)
    return local.date(), 60 * local.hour + local.minute


def time_bucket(captured_at: datetime) -> str:
    """Return the part of the local day an instant falls in."""
    hour = captured_at.astimezone(MADRID).hour
    for name, hours in TIME_BUCKETS:
        if hour in hours:
            return name
    return "other"


def draw(captures: Iterable[datetime], count: int, rng: random.Random) -> list[datetime]:
    """Draw up to ``count`` captures, rotating through the parts of the day."""
    by_bucket: dict[str, list[datetime]] = defaultdict(list)
    for captured_at in sorted(captures):
        by_bucket[time_bucket(captured_at)].append(captured_at)
    order = [
        name
        for name in ("night", "morning peak", "evening peak", "other")
        if by_bucket[name]
    ]
    picked: list[datetime] = []
    while len(picked) < count and any(by_bucket[name] for name in order):
        for name in order:
            if by_bucket[name] and len(picked) < count:
                picked.append(by_bucket[name].pop(rng.randrange(len(by_bucket[name]))))
    return picked


# --- connections --------------------------------------------------------------


def load_env(path: Path) -> dict[str, str]:
    """Read ``KEY=value`` lines of a ``.env`` file; never prints a value."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().removeprefix("export ")
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def require(env: Mapping[str, str], name: str) -> str:
    """Return a credential or stop naming the missing variable."""
    value = env.get(name, "")
    if not value:
        sys.exit(f"Missing {name}: set it in .env at the repository root.")
    return value


class Requests:
    """Counts the script's own requests to the bronze bucket."""

    def __init__(self) -> None:
        self.lists = 0
        self.gets = 0
        self._lock = threading.Lock()

    def add(self, *, lists: int = 0, gets: int = 0) -> None:
        with self._lock:
            self.lists += lists
            self.gets += gets


def list_day(
    store: ObjectStore, system: str, day: date, requests: Requests
) -> list[str]:
    """List the keys of one system's UTC day; each page is one request."""
    keys: list[str] = []
    for page in obstore.list(store, prefix=f"raw/{system}/station_status/{day}/"):
        requests.add(lists=1)
        keys.extend(meta["path"] for meta in page)
    return keys


def read_object(
    store: ObjectStore, key: str, requests: Requests
) -> tuple[dict[str, Any] | None, str | None]:
    """Download and parse an object: (document, None) or (None, reason)."""
    requests.add(gets=1)
    try:
        raw = bytes(obstore.get(store, key).bytes())
    except FileNotFoundError:
        return None, "missing"
    try:
        return json.loads(gzip.decompress(raw)), None
    except (OSError, ValueError, EOFError) as error:
        return None, f"unreadable ({type(error).__name__})"


def read_objects(
    store: ObjectStore, keys: Sequence[str], requests: Requests
) -> dict[str, tuple[dict[str, Any] | None, str | None]]:
    """Download objects concurrently, as the pipeline does."""
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda key: read_object(store, key, requests), keys))
    return dict(zip(keys, results, strict=True))


def excluded_keys() -> set[str]:
    """Return the keys the pipeline excludes on purpose."""
    keys: set[str] = set()
    if EXCLUDED_FILE.exists():
        for line in EXCLUDED_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                keys.add(line.split("#", 1)[0].strip())
    return keys


# --- table access -------------------------------------------------------------


def values(column: Any) -> list[Any]:
    """Return a column's values as Python objects."""
    return [column[i].as_py() for i in range(len(column))]


def query(table: DeltaTable, sql: str) -> list[dict[str, Any]]:
    """Run SQL over the pinned table, registered as ``t``; return its rows."""
    result = Table.from_arrow(QueryBuilder().register("t", table).execute(sql))
    columns = {name: values(result[name]) for name in result.column_names}
    return [dict(zip(columns, row, strict=True)) for row in zip(*columns.values())]


def ts(value: datetime) -> str:
    """Return a SQL timestamp literal in UTC."""
    return f"TIMESTAMP '{ensure_utc(value).isoformat()}'"


def window_sql(
    previous: Mapping[str, datetime | None],
    current: Mapping[str, datetime | None],
    systems: Sequence[str] = SYSTEMS,
) -> str:
    """Return the predicate of each system's window: (previous, current]."""
    parts = []
    for system in systems:
        upper = current.get(system)
        if upper is None:
            continue
        part = f"system = '{system}' and captured_at <= {ts(upper)}"
        lower = previous.get(system)
        if lower is not None:
            part += f" and captured_at > {ts(lower)}"
        parts.append(f"({part})")
    return " or ".join(parts) or "false"


# --- report -------------------------------------------------------------------


def cell(value: Any) -> tuple[str, bool]:
    """Return a table cell's text and whether it aligns to the right."""
    if isinstance(value, bool):
        return str(value), False
    if isinstance(value, int):
        return f"{value:,}", True
    return str(value), False


def fmt_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    """Format a small table with aligned columns."""
    cells = [[cell(v) for v in row] for row in rows]
    widths = [
        max(len(headers[i]), *(len(row[i][0]) for row in cells)) if cells else len(h)
        for i, h in enumerate(headers)
    ]
    lines = [" " + "  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True))]
    for row in cells:
        lines.append(
            " "
            + "  ".join(
                text.rjust(w) if right else text.ljust(w)
                for (text, right), w in zip(row, widths, strict=True)
            ).rstrip()
        )
    return lines


@dataclass
class Result:
    number: int
    name: str
    status: str
    detail: str


class Report:
    """Collects the report's lines, printing each as it is added."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def add(self, *lines: str) -> None:
        for line in lines:
            print(line, flush=True)
            self.lines.append(line)


# --- the checks ---------------------------------------------------------------


@dataclass
class Context:
    stock: DeltaTable
    bronze: ObjectStore
    requests: Requests
    previous: dict[str, datetime | None]
    current: dict[str, datetime | None]
    window: str
    captures: dict[str, dict[datetime, int]]  # system -> capture -> stations
    args: argparse.Namespace
    rng: random.Random
    report: Report
    state: dict[str, Any]


def check_counts(ctx: Context) -> Result:
    """Check 1: per day and system, bronze's objects and stations against the table."""
    ctx.report.add("", "[1] COUNTS PER DAY (UTC days of the window)")
    excluded = excluded_keys()
    rows: list[list[Any]] = []
    details: list[str] = []
    failures = 0
    pairs = 0
    for system in SYSTEMS:
        captures = ctx.captures[system]
        if not captures:
            continue
        days = sorted({captured_at.date() for captured_at in captures})
        chosen = set(days) if ctx.args.all_days else {days[0], days[-1]}
        dst_utc_day = DST_END_UTC.date()
        if days[0] <= dst_utc_day <= days[-1]:
            chosen.add(dst_utc_day)
        for day in sorted(chosen):
            pairs += 1
            # Reading a day's objects takes a while: show which one is running.
            print(f"   … reading {system} {day}", file=sys.stderr, flush=True)
            lower, upper = ctx.previous.get(system), ctx.current[system]
            keys = {
                key: parsed[1]
                for key in list_day(ctx.bronze, system, day, ctx.requests)
                if key not in excluded and (parsed := parse_key(key))
                if parsed[1] <= upper and (lower is None or parsed[1] > lower)
            }
            docs = read_objects(ctx.bronze, sorted(keys), ctx.requests)
            unreadable = {k: r[1] for k, r in docs.items() if r[0] is None}
            bronze_stations = sum(
                len(doc["data"]["stations"]) for doc, _ in docs.values() if doc
            )
            table_captures = {c for c in captures if c.date() == day}
            table_rows = sum(captures[c] for c in table_captures)
            bronze_captures = set(keys.values())
            only_bronze = sorted(bronze_captures - table_captures)
            only_table = sorted(table_captures - bronze_captures)
            ok = (
                not unreadable
                and not only_bronze
                and not only_table
                and bronze_stations == table_rows
            )
            failures += 0 if ok else 1
            rows.append(
                [
                    str(day),
                    system,
                    len(keys),
                    len(table_captures),
                    bronze_stations,
                    table_rows,
                    table_rows - bronze_stations,
                    PASS if ok else FAIL,
                ]
            )
            for label, items in (
                ("in bronze, not in table", only_bronze),
                ("in table, not in bronze", only_table),
            ):
                if items:
                    shown = ", ".join(f"{c:%H:%M:%SZ}" for c in items[:5])
                    details.append(
                        f"   ↳ {day} {system}: {len(items)} capture(s) {label}: {shown}"
                    )
            for key, reason in list(unreadable.items())[:5]:
                details.append(f"   ↳ {key}: {reason}")
    if not rows:
        ctx.report.add(" no captures in the window")
        return Result(1, "counts per day", SKIP, "no captures in the window")
    ctx.report.add(
        *fmt_table(
            [
                "date",
                "system",
                "bronze_objects",
                "table_captures",
                "bronze_stations",
                "table_rows",
                "diff",
                "result",
            ],
            rows,
        ),
        *details,
    )
    return Result(
        1,
        "counts per day",
        FAIL if failures else PASS,
        f"{pairs - failures}/{pairs} day-system pairs match",
    )


def pick_sample(ctx: Context) -> list[tuple[str, datetime, str]]:
    """Pick the captures of check 2: a random draw per system, plus edge cases."""
    sample: list[tuple[str, datetime, str]] = []
    seen: set[tuple[str, datetime]] = set()

    def add(system: str, captured_at: datetime, kind: str) -> None:
        if (system, captured_at) not in seen:
            seen.add((system, captured_at))
            sample.append((system, captured_at, kind))

    for system in SYSTEMS:
        for captured_at in draw(ctx.captures[system], ctx.args.sample, ctx.rng):
            add(system, captured_at, "random")
    edge_queries = {
        ("bicing", "out of service", 2): "not is_renting and not is_returning",
        ("bicing", "zero vehicles", 1): "num_vehicles_available = 0",
        ("ambici", "zero vehicles", 1): "num_vehicles_available = 0",
    }
    for (system, kind, count), condition in edge_queries.items():
        if ctx.current.get(system) is None:
            continue
        found = query(
            ctx.stock,
            f"select captured_at from t where system = '{system}' and {condition} "
            f"and ({window_sql(ctx.previous, ctx.current, (system,))}) "
            "group by captured_at limit 200",
        )
        pool = sorted(ensure_utc(r["captured_at"]) for r in found)
        for captured_at in ctx.rng.sample(pool, min(count, len(pool))):
            add(system, captured_at, kind)
    for system in SYSTEMS:
        if ctx.captures[system]:
            smallest = min(ctx.captures[system], key=lambda c: (ctx.captures[system][c], c))
            add(system, smallest, "fewest stations")
    return sample


def check_fields(ctx: Context) -> Result:
    """Check 2: a sample of captures compared station by station, field by field."""
    ctx.report.add("", "[2] FIELD BY FIELD")
    sample = pick_sample(ctx)
    if not sample:
        ctx.report.add(" no captures in the window")
        return Result(2, "field by field", SKIP, "no captures in the window")
    predicate = " or ".join(
        f"(system = '{system}' and captured_at = {ts(captured_at)})"
        for system, captured_at, _ in sample
    )
    columns = ", ".join(("system", "station_id", "captured_at", *FIELDS))
    stock_rows: dict[tuple[str, datetime], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in query(ctx.stock, f"select {columns} from t where {predicate}"):
        stock_rows[(row["system"], ensure_utc(row["captured_at"]))][
            str(row["station_id"])
        ] = row
    docs = read_objects(
        ctx.bronze, [bronze_key(s, c) for s, c, _ in sample], ctx.requests
    )
    table_rows: list[list[Any]] = []
    details: list[str] = []
    failed_captures = 0
    total_diffs = 0
    shown = 0
    for system, captured_at, kind in sample:
        doc, reason = docs[bronze_key(system, captured_at)]
        diffs: list[str] = []
        stations = compared = 0
        if doc is None:
            diffs.append(f"bronze object {reason}")
        else:
            expected = expected_rows(system, doc)
            actual = stock_rows.get((system, captured_at), {})
            stations = len(expected)
            for station_id, want in expected.items():
                got = actual.get(station_id)
                if got is None:
                    diffs.append(f"station {station_id}: in bronze, not in table")
                    continue
                for name in FIELDS:
                    compared += 1
                    have = got[name]
                    if isinstance(have, datetime):
                        have = ensure_utc(have)
                    if have != want[name]:
                        diffs.append(
                            f"station {station_id} · {name} · "
                            f"bronze={want[name]!r} table={have!r}"
                        )
            for station_id in sorted(set(actual) - set(expected)):
                diffs.append(f"station {station_id}: in table, not in bronze")
        total_diffs += len(diffs)
        failed_captures += 1 if diffs else 0
        table_rows.append(
            [
                system,
                f"{captured_at:%Y-%m-%dT%H:%M:%SZ}",
                kind,
                stations,
                compared,
                len(diffs),
                FAIL if diffs else PASS,
            ]
        )
        for diff in diffs[:MAX_DIFFS_PER_CAPTURE]:
            if shown < MAX_DIFFS_SHOWN:
                details.append(f"   ↳ {system} {captured_at:%Y-%m-%dT%H:%M:%SZ} {diff}")
                shown += 1
    ctx.report.add(
        *fmt_table(
            ["system", "captured_at", "kind", "stations", "fields_compared",
             "differences", "result"],
            table_rows,
        ),
        *details,
    )
    if total_diffs > shown:
        ctx.report.add(f"   ({total_diffs - shown} more differences not shown)")
    return Result(
        2,
        "field by field",
        FAIL if failed_captures else PASS,
        f"{len(sample) - failed_captures}/{len(sample)} captures match"
        + (f", {total_diffs} differences" if total_diffs else ""),
    )


def check_ranges(ctx: Context) -> Result:
    """Check 3: nulls and ranges over every row of the window."""
    ctx.report.add("", "[3] RANGES AND NULLS (every row of the window)")
    row = query(
        ctx.stock,
        f"""select
            count(*) as n,
            sum(case when system = 'bicing' and num_vehicles_available is null
                and (is_renting or is_returning) then 1 else 0 end) as tr9_null,
            sum(case when system = 'bicing' and num_vehicles_available is not null
                and not is_renting and not is_returning then 1 else 0 end) as tr9_value,
            sum(case when system = 'ambici' and num_vehicles_available is null
                then 1 else 0 end) as ambici_null,
            sum(case when system = 'ambici' and (num_vehicles_disabled is not null
                or num_docks_disabled is not null) then 1 else 0 end) as ambici_disabled,
            sum(case when num_vehicles_available < 0 or num_docks_available < 0
                or num_vehicles_disabled < 0 or num_docks_disabled < 0
                then 1 else 0 end) as negatives,
            sum(case when system is null or station_id is null or captured_at is null
                or local_date is null or local_minute is null or is_installed is null
                or is_renting is null or is_returning is null or last_reported is null
                or last_updated is null or run_id is null or code_version is null
                then 1 else 0 end) as null_required,
            sum(case when system not in ('ambici', 'bicing') then 1 else 0 end)
                as unknown_system,
            sum(case when local_minute < 0 or local_minute > 1439 then 1 else 0 end)
                as bad_minute
        from t where {ctx.window}""",
    )[0]
    versions = query(
        ctx.stock,
        f"select code_version, count(*) as n from t where {ctx.window} "
        "group by code_version order by n desc",
    )
    bad_versions = [
        v for v in versions if not v["code_version"] or not SHA_RE.fullmatch(v["code_version"])
    ]
    rules = [
        ("bicing: num_vehicles_available null only at an out-of-service station (TR9)",
         (row["tr9_null"] or 0) + (row["tr9_value"] or 0)),
        ("ambici: num_vehicles_available never null", row["ambici_null"] or 0),
        ("ambici: disabled counts always null (TR8)", row["ambici_disabled"] or 0),
        ("no negative measure", row["negatives"] or 0),
        ("key, flag, instant and lineage columns never null", row["null_required"] or 0),
        ("system is ambici or bicing", row["unknown_system"] or 0),
        ("local_minute between 0 and 1439", row["bad_minute"] or 0),
        ("code_version is a full 40-hex SHA (R9)", sum(v["n"] for v in bad_versions)),
    ]
    ctx.report.add(
        f" rows checked: {row['n']:,}",
        *fmt_table(
            ["rule", "violations", "result"],
            [[name, count, PASS if count == 0 else FAIL] for name, count in rules],
        ),
        " code_version values in the window (compare with `git log`):",
        *fmt_table(
            ["code_version", "rows"], [[v["code_version"], v["n"]] for v in versions[:10]]
        ),
    )
    total = sum(count for _, count in rules)
    return Result(
        3,
        "ranges and nulls",
        FAIL if total else PASS,
        f"{total} violations in {row['n']:,} rows",
    )


def check_local_keys(ctx: Context) -> Result:
    """Check 4: local calendar keys of every capture, and the DST day."""
    ctx.report.add("", "[4] LOCAL KEYS AND DST")
    rows = query(
        ctx.stock,
        "select distinct system, captured_at, local_date, local_minute from t "
        f"where {ctx.window}",
    )
    by_capture: dict[tuple[str, datetime], set[tuple[date, int]]] = defaultdict(set)
    for row in rows:
        by_capture[(row["system"], ensure_utc(row["captured_at"]))].add(
            (row["local_date"], row["local_minute"])
        )
    wrong = [
        (key, found)
        for key, found in by_capture.items()
        if found != {local_keys(key[1])}
    ]
    ctx.report.add(
        f" local_date and local_minute of {len(by_capture):,} captures against Europe/Madrid: "
        f"{FAIL if wrong else PASS}"
    )
    for (system, captured_at), found in wrong[:5]:
        ctx.report.add(
            f"   ↳ {system} {captured_at:%Y-%m-%dT%H:%M:%SZ}: table={sorted(found)} "
            f"expected={local_keys(captured_at)}"
        )
    dst_failed = False
    reached = all(
        ctx.current[s] is not None and ctx.current[s] >= DST_END_UTC
        for s in SYSTEMS
        if ctx.current.get(s) is not None
    ) and any(ctx.current.get(s) is not None for s in SYSTEMS)
    if ctx.state.get("dst_checked") and not ctx.args.full:
        ctx.report.add(f" {DST_LOCAL_DATE}: SKIP, already checked in an earlier run")
        dst_note = "DST day checked earlier"
    elif not reached:
        latest = ", ".join(
            f"{s} {ctx.current[s]:%Y-%m-%dT%H:%MZ}"
            for s in SYSTEMS
            if ctx.current.get(s)
        )
        ctx.report.add(
            f" {DST_LOCAL_DATE}: SKIP, the table has not reached "
            f"{DST_END_UTC:%Y-%m-%dT%H:%MZ} yet (latest: {latest})"
        )
        dst_note = "DST day not loaded yet"
    else:
        dst_rows = query(
            ctx.stock,
            "select distinct system, captured_at, local_date, local_minute from t "
            f"where captured_at >= {ts(DST_START_UTC)} and captured_at < {ts(DST_END_UTC)}",
        )
        table: list[list[Any]] = []
        for system in SYSTEMS:
            mine = [r for r in dst_rows if r["system"] == system]
            if not mine:
                continue
            instants = sorted(ensure_utc(r["captured_at"]) for r in mine)
            span_hours = (instants[-1] - instants[0]).total_seconds() / 3600
            on_date = all(r["local_date"] == DST_LOCAL_DATE for r in mine)
            repeated = {
                ensure_utc(r["captured_at"]).hour
                for r in mine
                if 120 <= r["local_minute"] < 180
            }
            ok = on_date and repeated == {0, 1} and span_hours >= 24.9
            dst_failed = dst_failed or not ok
            table.append(
                [system, len(mine), f"{span_hours:.2f} h", str(on_date),
                 "+".join(f"{h:02d}Z" for h in sorted(repeated)), PASS if ok else FAIL]
            )
        ctx.report.add(
            f" {DST_LOCAL_DATE} (25 local hours):",
            *fmt_table(
                ["system", "captures", "span", "all on the date", "UTC hours of 02:xx",
                 "result"],
                table,
            ),
        )
        dst_note = "DST day FAIL" if dst_failed else "DST day PASS"
        if not dst_failed:
            ctx.state["dst_checked"] = True
    failed = bool(wrong) or dst_failed
    return Result(
        4,
        "local keys and DST",
        FAIL if failed else PASS,
        f"{len(by_capture):,} captures, {dst_note}",
    )


# --- main ---------------------------------------------------------------------


def self_test() -> None:
    """Check the script's own logic against the repository's bronze fixtures."""
    for system, date_dir in (("bicing", "2026-10-22"), ("ambici", "2026-10-19")):
        folder = FIXTURES / "raw" / system / "station_status" / date_dir
        path = sorted(folder.glob("*.json.gz"))[0]
        parsed = parse_key(path.relative_to(FIXTURES).as_posix())
        assert parsed is not None and parsed[0] == system, path
        doc = json.loads(gzip.decompress(path.read_bytes()))
        rows = expected_rows(system, doc)
        assert len(rows) == len(doc["data"]["stations"]) > 0
        first = next(iter(rows.values()))
        assert first["last_updated"] == parse_instant(doc["last_updated"])
        if system == "ambici":
            assert first["num_vehicles_disabled"] is None
            assert first["num_vehicles_available"] == doc["data"]["stations"][0][
                "num_bikes_available"
            ]
    out_of_service = {
        "data": {"stations": [{"station_id": 1, "is_renting": False,
                                "is_returning": False, "num_vehicles_available": 7,
                                "num_docks_available": 3}]},
        "last_updated": "2026-10-22T07:42:19Z",
    }
    assert expected_rows("bicing", out_of_service)["1"]["num_vehicles_available"] is None
    assert expected_rows("ambici", {**out_of_service, "data": {"stations": [
        {"station_id": 1, "is_renting": False, "is_returning": False,
         "num_bikes_available": 7}]}})["1"]["num_vehicles_available"] == 7
    t = datetime
    assert local_keys(t(2026, 10, 24, 22, 0, tzinfo=UTC)) == (DST_LOCAL_DATE, 0)
    assert local_keys(t(2026, 10, 25, 0, 30, tzinfo=UTC)) == (DST_LOCAL_DATE, 150)
    assert local_keys(t(2026, 10, 25, 1, 30, tzinfo=UTC)) == (DST_LOCAL_DATE, 150)
    assert local_keys(t(2026, 10, 25, 22, 59, tzinfo=UTC)) == (DST_LOCAL_DATE, 1439)
    assert local_keys(t(2026, 10, 25, 23, 0, tzinfo=UTC)) == (date(2026, 10, 26), 0)
    assert (DST_END_UTC - DST_START_UTC) == timedelta(hours=25)
    picked = draw(
        [t(2026, 10, 20, h, 0, tzinfo=UTC) for h in range(24)], 6, random.Random(1)
    )
    assert len(set(picked)) == 6
    print("self-test: OK")


def build_stores(args: argparse.Namespace) -> tuple[str, dict[str, str] | None, ObjectStore]:
    """Return the table's URI and options, and the bronze store."""
    if args.local_lakehouse or args.local_bronze:
        if not (args.local_lakehouse and args.local_bronze):
            sys.exit("--local-lakehouse and --local-bronze go together.")
        return (
            f"{args.local_lakehouse}/{STOCK_PATH}",
            None,
            LocalStore(args.local_bronze),
        )
    env = {**load_env(REPO / ".env"), **os.environ}
    endpoint = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
    options = {
        "AWS_ENDPOINT_URL": endpoint,
        "AWS_REGION": "auto",
        "AWS_ACCESS_KEY_ID": require(env, "LAKEHOUSE_READ_R2_ACCESS_KEY_ID"),
        "AWS_SECRET_ACCESS_KEY": require(env, "LAKEHOUSE_READ_R2_SECRET_ACCESS_KEY"),
    }
    bronze = S3Store(
        BRONZE_BUCKET,
        endpoint=endpoint,
        region="auto",
        access_key_id=require(env, "BRONZE_R2_ACCESS_KEY_ID"),
        secret_access_key=require(env, "BRONZE_R2_SECRET_ACCESS_KEY"),
    )
    return f"s3://{LAKEHOUSE_BUCKET}/{STOCK_PATH}", options, bronze


def load_state() -> dict[str, Any]:
    """Return the watermark saved by the last run without a failure."""
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--full", action="store_true", help="validate everything, ignoring the watermark")
    parser.add_argument("--all-days", action="store_true", help="check 1 over every day of the window")
    parser.add_argument("--seed", type=int, help="sampling seed (default: the table's version)")
    parser.add_argument("--sample", type=int, default=15, help="random captures per system in check 2")
    parser.add_argument("--no-save", action="store_true", help="do not update the watermark")
    parser.add_argument("--self-test", action="store_true", help="check the script's logic and exit")
    parser.add_argument("--local-lakehouse", help="a local lakehouse folder instead of R2 (for rehearsals)")
    parser.add_argument("--local-bronze", help="a local bronze folder instead of R2 (for rehearsals)")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0

    uri, options, bronze = build_stores(args)
    stock = DeltaTable(uri, storage_options=options)
    version = stock.version()
    state = {} if args.full else load_state()
    report = Report()
    started = datetime.now(UTC)
    requests = Requests()

    bounds = query(
        stock,
        "select system, min(captured_at) as first, max(captured_at) as last, "
        "count(*) as n from t group by system",
    )
    current = {s: None for s in SYSTEMS}
    total_rows = 0
    first = {s: None for s in SYSTEMS}
    for row in bounds:
        current[row["system"]] = ensure_utc(row["last"])
        first[row["system"]] = ensure_utc(row["first"])
        total_rows += row["n"]
    previous = {
        s: (datetime.fromisoformat(v) if v else None)
        for s, v in state.get("max_captured_at", {}).items()
    }
    window = window_sql(previous, current)
    seed = args.seed if args.seed is not None else version
    mode = "full" if args.full else ("incremental" if state else "first run")

    report.add(
        f"STATION STOCK VALIDATION · {started:%Y-%m-%d %H:%M} UTC",
        f"table: {LAKEHOUSE_BUCKET}/{STOCK_PATH} @ version {version:,} · rows: {total_rows:,}",
        "captures in table: "
        + " · ".join(
            f"{s} {first[s]:%Y-%m-%dT%H:%MZ} → {current[s]:%Y-%m-%dT%H:%MZ}"
            for s in SYSTEMS
            if current[s]
        ),
        f"window: {mode}"
        + (f", after {state.get('version'):,}" if state.get("version") is not None and not args.full else "")
        + f" · sample seed: {seed}",
    )

    captures: dict[str, dict[datetime, int]] = {s: {} for s in SYSTEMS}
    for row in query(
        stock,
        f"select system, captured_at, count(*) as n from t where {window} "
        "group by system, captured_at",
    ):
        captures[row["system"]][ensure_utc(row["captured_at"])] = row["n"]
    new_captures = sum(len(c) for c in captures.values())
    report.add(f"new captures in the window: {new_captures:,}")

    ctx = Context(
        stock=stock,
        bronze=bronze,
        requests=requests,
        previous=previous,
        current=current,
        window=window,
        captures=captures,
        args=args,
        rng=random.Random(seed),
        report=report,
        state=state,
    )
    if new_captures == 0:
        report.add("", "Nothing new since the last validated run.")
        results = [
            Result(n, name, SKIP, "no new captures")
            for n, name in enumerate(
                ("counts per day", "field by field", "ranges and nulls", "local keys and DST"),
                start=1,
            )
        ]
    else:
        results = [
            check_counts(ctx),
            check_fields(ctx),
            check_ranges(ctx),
            check_local_keys(ctx),
        ]

    failed = any(r.status == FAIL for r in results)
    report.add("", "SUMMARY")
    report.add(
        *fmt_table(
            ["#", "check", "result", "detail"],
            [[str(r.number), r.name, r.status, r.detail] for r in results],
        )
    )
    report.add(
        f" R2 requests made by this script (bronze): {requests.lists:,} list, "
        f"{requests.gets:,} get. The lakehouse is read by deltalake, which is not "
        "counted: subtract from R2's metrics (Do 5) by this run's time.",
        f" elapsed: {(datetime.now(UTC) - started).total_seconds():.0f} s",
        f" EXIT: {FAIL if failed else PASS}",
    )

    OUT_DIR.mkdir(exist_ok=True)
    stamp = f"{started:%Y%m%dT%H%M%SZ}"
    (OUT_DIR / f"report-{stamp}.txt").write_text("\n".join(report.lines) + "\n", encoding="utf-8")
    with (OUT_DIR / "requests.log").open("a", encoding="utf-8") as ledger:
        ledger.write(f"{stamp} lists={requests.lists} gets={requests.gets} version={version}\n")
    if not failed and not args.no_save and new_captures:
        state["version"] = version
        state["max_captured_at"] = {
            s: current[s].isoformat() for s in SYSTEMS if current[s]
        }
        state["last_run"] = started.isoformat()
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    report.add(f" report: {(OUT_DIR / f'report-{stamp}.txt').relative_to(REPO)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
