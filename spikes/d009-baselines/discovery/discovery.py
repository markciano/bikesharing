"""Inventory every production event of capture and the pipeline, to find alerts.

Reads each log line as a whole JSON object, so an event or field this script
does not know still shows, and reports per component and event: the inventory,
the fields carried, the values of the fields with few distinct values, and the
daily rhythm of every event not at level info.

Inputs: capture's pass logs under ``logs/`` of ``bikesharing-bronze``
(``BRONZE_R2_*`` in ``.env``) from 2026-11-07, and the pipeline's run logs under
``logs/pipeline/`` of ``bikesharing-lakehouse`` (``LAKEHOUSE_READ_R2_*``).
Output: a report on screen, saved as ``out/report-<UTC time>.txt``. Nothing is
written to R2.

Usage::

    uv run --directory pipeline python ../spikes/d009-baselines/discovery/discovery.py
    uv run --directory pipeline python ../spikes/d009-baselines/discovery/discovery.py --self-test
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb

ACCOUNT_ID = "b88ece5b9aad94b83f1710afa6d24070"
LAKEHOUSE_BUCKET = "bikesharing-lakehouse"
BRONZE_BUCKET = "bikesharing-bronze"
FIRST_CAPTURE_LOG_DAY = date(2026, 11, 7)
MAX_VALUES = 12
# Fields unique to nearly every event, whose values say nothing about it.
SKIPPED_FIELDS = ("ts", "run_id")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT_DIR = HERE / "out"


def load_env(path: Path) -> dict[str, str]:
    """Return the ``KEY=value`` pairs of a dotenv file, or none if it is missing."""
    pairs: dict[str, str] = {}
    if not path.exists():
        return pairs
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            pairs[key.strip()] = value.strip().strip("'\"")
    return pairs


def require(env: dict[str, str], name: str) -> str:
    """Return a variable's value, or exit naming the one that is missing."""
    value = env.get(name)
    if not value:
        sys.exit(f"{name} is not set in .env or the environment.")
    return value


def connect_r2(con: duckdb.DuckDBPyConnection, env: dict[str, str]) -> None:
    """Give DuckDB one read secret per bucket, each scoped to its bucket."""
    con.sql("install httpfs")
    con.sql("load httpfs")
    pairs = {LAKEHOUSE_BUCKET: "LAKEHOUSE_READ_R2", BRONZE_BUCKET: "BRONZE_R2"}
    for i, (bucket, prefix) in enumerate(pairs.items()):
        con.sql(
            f"create secret r2_{i} (type r2, key_id '{require(env, f'{prefix}_ACCESS_KEY_ID')}', "
            f"secret '{require(env, f'{prefix}_SECRET_ACCESS_KEY')}', "
            f"account_id '{ACCOUNT_ID}', scope 'r2://{bucket}')"
        )


def create_raw(con: duckdb.DuckDBPyConnection) -> None:
    """Create the empty ``raw`` table, one JSON object per log line."""
    con.sql("set TimeZone = 'UTC'")
    con.sql("create table raw (obj json)")


def insert_logs(con: duckdb.DuckDBPyConnection, glob: str) -> None:
    """Append every line of the logs matching ``glob`` to ``raw``."""
    con.sql(f"insert into raw select json from read_ndjson_objects('{glob}')")


def read_logs(con: duckdb.DuckDBPyConnection, last: date) -> None:
    """Load capture's logs one day at a time, then the pipeline's."""
    day = FIRST_CAPTURE_LOG_DAY
    while day <= last:
        began = time.monotonic()
        before = con.sql("select count(*) from raw").fetchall()[0][0]
        try:
            insert_logs(con, f"r2://{BRONZE_BUCKET}/logs/date={day.isoformat()}/*.jsonl")
        except duckdb.Error as exc:
            print(f"  capture {day}: not read ({type(exc).__name__})", flush=True)
        else:
            n = con.sql("select count(*) from raw").fetchall()[0][0] - before
            print(f"  capture {day}: {n} events in {time.monotonic() - began:.1f} s", flush=True)
        day += timedelta(days=1)
    began = time.monotonic()
    insert_logs(con, f"r2://{LAKEHOUSE_BUCKET}/logs/pipeline/date=*/*.jsonl")
    print(f"  pipeline: read in {time.monotonic() - began:.1f} s", flush=True)


EVENTS_SQL = """
    create or replace table events as
    select
        obj->>'component' as component,
        obj->>'event' as event,
        obj->>'level' as level,
        (obj->>'ts')::timestamptz as ts,
        obj->>'run_id' as run_id,
        json_keys(obj) as keys,
        obj
    from raw
"""

# Each field of each event with its values, as text; arrays and objects come
# back as JSON text, so their many distinct values keep them out of the listing.
FIELDS_SQL = f"""
    create or replace table fields as
    select component, event, key,
        json_extract_string(obj, '$."' || key || '"') as value
    from (select component, event, obj, unnest(keys) as key from events)
    where key not in {SKIPPED_FIELDS}
"""


def as_text(rel: duckdb.DuckDBPyRelation) -> str:
    """Return every row of a relation as a plain text table, nothing truncated."""
    header = rel.columns
    rows = [
        [f"{v:.4f}" if isinstance(v, float) else str(v) for v in row]
        for row in rel.fetchall()
    ]
    if not rows:
        return " | ".join(header) + "\n(no rows)"
    widths = [max(len(c), *(len(r[i]) for r in rows)) for i, c in enumerate(header)]
    lines = [" | ".join(c.ljust(w) for c, w in zip(header, widths, strict=True))]
    lines.append("-+-".join("-" * w for w in widths))
    lines += [" | ".join(v.ljust(w) for v, w in zip(r, widths, strict=True)) for r in rows]
    return "\n".join(line.rstrip() for line in lines)


VALUES_SQL = f"""
    with counted as (
        select component, event, key, value, count(*) as n from fields group by all
    ),
    small as (
        select component, event, key from counted group by all
        having count(*) <= {MAX_VALUES}
    )
    select c.component, c.event, c.key,
        string_agg(coalesce(c.value, 'null') || ': ' || c.n, ', ' order by c.n desc) as values
    from counted c join small s using (component, event, key)
    group by c.component, c.event, c.key order by c.component, c.event, c.key
"""


def report(con: duckdb.DuckDBPyConnection, out: list[str]) -> None:
    """Append every section of the report to ``out``."""

    def show(title: str, sql: str) -> None:
        out.append(f"\n## {title}\n")
        out.append(as_text(con.sql(sql)))

    show(
        "Span per component",
        "select component, count(*) as events, count(distinct run_id) as runs, "
        "min(ts) as first, max(ts) as last from events group by all order by all",
    )
    show(
        "Inventory per component, event and level",
        """
        select component, event, level, count(*) as events, count(distinct run_id) as runs,
            count(distinct ts::date) as days, min(ts) as first, max(ts) as last
        from events group by all order by component, event, level
        """,
    )
    show(
        "Fields per event, with the events carrying each",
        """
        select component, event,
            string_agg(key || ' (' || n || ')', ', ' order by key) as fields
        from (select component, event, key, count(*) as n from fields group by all)
        group by all order by component, event
        """,
    )
    show(f"Values of fields with at most {MAX_VALUES} distinct values", VALUES_SQL)
    show(
        "Daily rhythm of events not at level info (days with none count as 0)",
        """
        with span as (
            select component, min(ts)::date as first, max(ts)::date as last
            from events group by component
        ),
        days as (
            select component, unnest(generate_series(first, last, interval 1 day))::date as day
            from span
        ),
        kinds as (
            select distinct component, event, level from events where level <> 'info'
        ),
        daily as (
            select k.component, k.event, k.level, d.day,
                count(e.event) as n
            from kinds k join days d using (component)
            left join events e on e.component = k.component and e.event = k.event
                and e.level = k.level and e.ts::date = d.day
            group by all
        )
        select component, event, level, count(*) as days,
            count(*) filter (where n > 0) as days_seen,
            median(n) as median_per_day, max(n) as worst_day, sum(n) as total
        from daily group by all order by component, total desc
        """,
    )


def self_test() -> None:
    """Check the field and value listing on synthetic events, and exit."""
    con = duckdb.connect()
    create_raw(con)
    lines = [
        '{"ts":"2026-11-08T10:00:01Z","level":"error","component":"capture","run_id":"a",'
        '"event":"feed_failed","status":403,"error_type":"http"}',
        '{"ts":"2026-11-08T10:01:01Z","level":"error","component":"capture","run_id":"b",'
        '"event":"feed_failed","status":null,"error_type":"timeout"}',
        '{"ts":"2026-11-09T10:00:01Z","level":"info","component":"capture","run_id":"c",'
        '"event":"feed_captured","status":200,"latency_ms":120}',
    ]
    con.executemany("insert into raw values (?::json)", [(line,) for line in lines])
    con.sql(EVENTS_SQL)
    con.sql(FIELDS_SQL)
    fields = con.sql(
        "select key, count(*) from fields where event = 'feed_failed' group by key order by key"
    ).fetchall()
    # ts and run_id are left out; a field present but null still counts.
    assert ("ts", 2) not in fields and ("run_id", 2) not in fields, fields
    assert ("status", 2) in fields and ("error_type", 2) in fields, fields
    values = {
        (r[1], r[2]): r[3]
        for r in con.sql(VALUES_SQL).fetchall()
    }
    assert values[("feed_failed", "error_type")] in ("http: 1, timeout: 1", "timeout: 1, http: 1")
    assert "null: 1" in values[("feed_failed", "status")], values
    assert values[("feed_captured", "latency_ms")] == "120: 1", values
    print("self-test: OK")


def main() -> int:
    """Run the check, print the report and save it."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--self-test", action="store_true", help="check the logic and exit")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0

    began = time.monotonic()
    env = {**load_env(REPO / ".env"), **os.environ}
    con = duckdb.connect()
    create_raw(con)
    # Many small log objects: more threads keep more requests in flight.
    con.sql("set threads = 32")
    connect_r2(con, env)
    today = datetime.now(UTC).date()
    print(f"Reading logs, capture from {FIRST_CAPTURE_LOG_DAY} to {today}, then the pipeline…")
    read_logs(con, today)
    con.sql(EVENTS_SQL)
    con.sql(FIELDS_SQL)
    out = [f"# Production events discovery — {datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}"]
    report(con, out)

    text = "\n".join(out)
    print(text)
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"report-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.txt"
    path.write_text(text + "\n", encoding="utf-8")
    print(f"\nSaved {path.relative_to(REPO)} in {time.monotonic() - began:.1f} s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
