"""Measure DQM7 and DQM10 over production captures and runs, to review their targets.

DQM7: the share of UTC minutes with at least one ``station_status`` capture in
the station stock, per system and month, against 99.5%; each missed minute is
given the cause its capture pass logged, ranked by minutes.
DQM10: for each page deployment, its time minus each system's latest capture
processed by the runs up to the deploying one, against one cadence plus one run.

Inputs: ``control/processed_objects`` and ``logs/pipeline/`` of
``bikesharing-lakehouse`` (``LAKEHOUSE_READ_R2_*`` in ``.env``), and capture's
pass logs under ``logs/`` of ``bikesharing-bronze`` (``BRONZE_R2_*``).
Output: a report on screen, saved as ``out/report-<UTC time>.txt``. Nothing is
written to R2.

Usage::

    uv run --directory pipeline python ../spikes/d009-baselines/indicator-targets/indicator_targets.py
    uv run --directory pipeline python ../spikes/d009-baselines/indicator-targets/indicator_targets.py --self-test
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
from arro3.core import Table
from deltalake import DeltaTable, QueryBuilder

ACCOUNT_ID = "b88ece5b9aad94b83f1710afa6d24070"
LAKEHOUSE_BUCKET = "bikesharing-lakehouse"
BRONZE_BUCKET = "bikesharing-bronze"
PROCESSED_PATH = "control/processed_objects"
FEED = "station_status"

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT_DIR = HERE / "out"

DQM7_TARGET = 0.995
WORST_SHOWN = 15

# Only the fields this check reads; read_json leaves a missing one null and
# ignores the rest, so every event of a log fits the same columns.
CAPTURE_COLUMNS = {
    "run_id": "VARCHAR",
    "event": "VARCHAR",
    "source": "VARCHAR",
    "feed": "VARCHAR",
    "status": "VARCHAR",
    "error_type": "VARCHAR",
}
PIPELINE_COLUMNS = {
    "ts": "TIMESTAMPTZ",
    "run_id": "VARCHAR",
    "event": "VARCHAR",
    "outcome": "VARCHAR",
    "duration_s": "DOUBLE",
    "peak_memory_mb": "DOUBLE",
    "data_instant": "TIMESTAMPTZ",
}


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


def read_captures(env: dict[str, str]) -> Table:
    """Return system, captured_at, status and run_id of every station_status object."""
    options = {
        "AWS_ENDPOINT_URL": f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com",
        "AWS_REGION": "auto",
        "AWS_ACCESS_KEY_ID": require(env, "LAKEHOUSE_READ_R2_ACCESS_KEY_ID"),
        "AWS_SECRET_ACCESS_KEY": require(env, "LAKEHOUSE_READ_R2_SECRET_ACCESS_KEY"),
    }
    table = DeltaTable(f"s3://{LAKEHOUSE_BUCKET}/{PROCESSED_PATH}", storage_options=options)
    sql = f"select system, captured_at, status, run_id from t where feed = '{FEED}'"
    return Table.from_arrow(QueryBuilder().register("t", table).execute(sql))


def connect_r2(con: duckdb.DuckDBPyConnection, env: dict[str, str]) -> None:
    """Give DuckDB one read secret per bucket, each scoped to its bucket."""
    con.sql("install httpfs")
    con.sql("load httpfs")
    pairs = {
        LAKEHOUSE_BUCKET: "LAKEHOUSE_READ_R2",
        BRONZE_BUCKET: "BRONZE_R2",
    }
    for i, (bucket, prefix) in enumerate(pairs.items()):
        key = require(env, f"{prefix}_ACCESS_KEY_ID")
        secret = require(env, f"{prefix}_SECRET_ACCESS_KEY")
        con.sql(
            f"create secret r2_{i} (type r2, key_id '{key}', secret '{secret}', "
            f"account_id '{ACCOUNT_ID}', scope 'r2://{bucket}')"
        )


def json_source(glob: str, columns: dict[str, str]) -> str:
    """Return a read_json call over newline-delimited logs with fixed columns."""
    cols = ", ".join(f"'{k}': '{v}'" for k, v in columns.items())
    return (
        f"read_json('{glob}', format = 'newline_delimited', columns = {{{cols}}}, "
        "hive_partitioning = false)"
    )


def read_capture_logs(con: duckdb.DuckDBPyConnection, first: date, last: date) -> None:
    """Load capture's pass logs into ``capture_events``, one day at a time."""
    con.sql(
        "create table capture_events (run_id varchar, event varchar, source varchar, "
        "feed varchar, status varchar, error_type varchar)"
    )
    day = first
    while day <= last:
        began = time.monotonic()
        glob = f"r2://{BRONZE_BUCKET}/logs/date={day.isoformat()}/*.jsonl"
        try:
            con.sql(f"insert into capture_events select * from {json_source(glob, CAPTURE_COLUMNS)}")
        except duckdb.Error as exc:
            print(f"  {day}: not read ({type(exc).__name__}: {exc})", flush=True)
        else:
            n = con.sql(
                "select count(distinct run_id) from capture_events "
                f"where pass_time(run_id)::date = '{day}'"
            ).fetchall()[0][0]
            print(f"  {day}: {n} passes in {time.monotonic() - began:.1f} s", flush=True)
        day += timedelta(days=1)


def read_pipeline_logs(con: duckdb.DuckDBPyConnection) -> None:
    """Load the pipeline's run logs into ``pipeline_events``."""
    glob = f"r2://{LAKEHOUSE_BUCKET}/logs/pipeline/date=*/*.jsonl"
    con.sql(f"create table pipeline_events as select * from {json_source(glob, PIPELINE_COLUMNS)}")


def define_macros(con: duckdb.DuckDBPyConnection) -> None:
    """Define the macros that turn run IDs into instants.

    ``uuid7_time``: the instant in a pipeline run's UUIDv7, its first 48 bits in
    ms since epoch. ``pass_time``: a capture pass's start, its ``run_id`` being
    ISO 8601 basic format in UTC (``20261107T101939Z``).
    """
    con.sql(
        "create or replace macro uuid7_time(u) as "
        "epoch_ms(('0x' || replace(u[1:13], '-', ''))::bigint)::timestamptz"
    )
    con.sql(
        "create or replace macro pass_time(r) as "
        "strptime(r, '%Y%m%dT%H%M%SZ')::timestamptz"
    )


# Each missed minute takes the first cause that applies, from the most specific:
# a failure event of the minute's pass, a capture written but not processed,
# a pass that logged nothing for station_status, or no pass at all. Minutes
# before the first pass log have no evidence of their cause, so they say so
# rather than count as passes that never ran.
MINUTES_SQL = f"""
    create or replace table minutes as
    with span as (
        select system, date_trunc('minute', min(captured_at)) as first,
            date_trunc('minute', max(captured_at)) as last
        from captures group by system
    ),
    grid as (
        select system, unnest(generate_series(first, last, interval 1 minute)) as minute
        from span
    ),
    captured as (
        select distinct system, date_trunc('minute', captured_at) as minute from captures
    ),
    events as (
        select *, date_trunc('minute', pass_time(run_id)) as minute from capture_events
    ),
    logged_from as (select min(minute) as first_log from events),
    failed as (
        select source as system, minute,
            string_agg(distinct event || ' status=' || coalesce(status, '-')
                || ' error_type=' || coalesce(error_type, '-'), '; ') as failure
        from events
        where (event = 'feed_failed' and feed = '{FEED}') or event = 'index_rejected'
        group by all
    ),
    fed as (
        select distinct source as system, minute from events
        where event = 'feed_captured' and feed = '{FEED}'
    ),
    passes as (select distinct minute from events)
    select g.system, g.minute, c.minute is not null as captured,
        case
            when c.minute is not null then null
            when g.minute < l.first_log or l.first_log is null then 'before capture logs'
            when f.failure is not null then f.failure
            when fd.minute is not null then 'captured, not in processed_objects'
            when p.minute is not null then 'pass logged, no station_status event'
            else 'no pass logged'
        end as cause
    from grid g
    cross join logged_from l
    left join captured c using (system, minute)
    left join failed f using (system, minute)
    left join fed fd using (system, minute)
    left join passes p on p.minute = g.minute
"""

# A deployment publishes every capture processed so far, so its data instant per
# system is the latest capture of the runs started up to the deploying run.
DEPLOYS_SQL = """
    create or replace table deploys as
    with per_run as (
        select system, uuid7_time(run_id) as started, max(captured_at) as data_at
        from captures group by all
    ),
    cumulative as (
        select system, started,
            max(data_at) over (partition by system order by started) as data_at
        from per_run
    ),
    deployed as (
        select e.run_id, e.ts as deployed_at, uuid7_time(e.run_id) as run_started, s.system
        from pipeline_events e cross join (select distinct system from captures) s
        where e.event = 'page_deployed'
    )
    select d.run_id, d.deployed_at, d.system, c.data_at,
        epoch(d.deployed_at - c.data_at) as age_s,
        -- A visitor sees the deployed files until the next deployment replaces
        -- them, so the oldest data a visitor meets is just before that one.
        epoch(lead(d.deployed_at) over (partition by d.system order by d.deployed_at)
            - c.data_at) as visitor_age_s
    from deployed d
    asof join cumulative c on c.system = d.system and c.started <= d.run_started
"""

# The first runs catch up on the weeks captured before the pipeline went live,
# so steady state starts at the first deployment whose data is under 30 min old.
STEADY_FROM_SQL = "(select min(deployed_at) from deploys where age_s < 1800)"


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


def quantiles(column: str) -> str:
    """Return SQL selecting the min, p50, p90, p99 and max of a column."""
    return (
        f"min({column}) as min, quantile_cont({column}, 0.5) as p50, "
        f"quantile_cont({column}, 0.9) as p90, quantile_cont({column}, 0.99) as p99, "
        f"max({column}) as max"
    )


def report(con: duckdb.DuckDBPyConnection, out: list[str]) -> None:
    """Append every section of the report to ``out``."""

    def show(title: str, sql: str) -> None:
        out.append(f"\n## {title}\n")
        out.append(as_text(con.sql(sql)))

    out.append("\n# DQM7, capture completeness")
    show(
        f"Captured minutes per system and month (target {DQM7_TARGET:.1%})",
        f"""
        select system, strftime(minute, '%Y-%m') as month, min(minute) as first,
            max(minute) as last, count(*) as minutes,
            count(*) filter (where captured) as captured,
            count(*) filter (where not captured) as missed,
            round(100.0 * count(*) filter (where captured) / count(*), 3) as pct,
            count(*) filter (where captured) / count(*) >= {DQM7_TARGET} as met
        from minutes group by all order by system, month
        """,
    )
    show(
        "Missed minutes per cause, all months",
        """
        select system, cause, count(*) as minutes,
            round(100.0 * count(*) / sum(count(*)) over (partition by system), 1)
                as pct_of_missed
        from minutes where not captured group by system, cause order by system, minutes desc
        """,
    )
    show(
        "Missed minutes per cause and month",
        """
        select system, strftime(minute, '%Y-%m') as month, cause, count(*) as minutes
        from minutes where not captured group by all order by system, month, minutes desc
        """,
    )
    show(
        f"Worst {WORST_SHOWN} days per system",
        f"""
        select * exclude (rn) from (
            select system, minute::date as day, count(*) filter (where not captured) as missed,
                round(100.0 * count(*) filter (where captured) / count(*), 2) as pct,
                row_number() over (partition by system order by
                    count(*) filter (where not captured) desc) as rn
            from minutes group by system, minute::date
        ) where rn <= {WORST_SHOWN} and missed > 0 order by system, missed desc
        """,
    )
    show(
        "Runs of consecutive missed minutes, by length",
        """
        with marked as (
            select *, sum(case when captured then 1 else 0 end)
                over (partition by system order by minute) as grp
            from minutes
        ),
        gaps as (
            select system, grp, count(*) as length from marked where not captured
            group by all
        )
        select system,
            case when length = 1 then '1' when length <= 5 then '2-5'
                when length <= 30 then '6-30' when length <= 120 then '31-120'
                else '>120' end as minutes_in_a_row,
            count(*) as gaps, sum(length) as missed
        from gaps group by all order by system, min(length)
        """,
    )

    out.append("\n# DQM10, age of the data the page serves")
    show(
        "Runs per outcome",
        "select outcome, count(*) as runs, min(ts) as first, max(ts) as last "
        "from pipeline_events where event = 'run_finished' group by all order by all",
    )
    show(
        "Run duration_s and peak_memory_mb",
        f"""
        select 'duration_s' as measure, {quantiles('duration_s')}
        from pipeline_events where event = 'run_finished'
        union all
        select 'peak_memory_mb', {quantiles('peak_memory_mb')}
        from pipeline_events where event = 'run_finished'
        """,
    )
    show(
        "Interval between run starts, in minutes",
        f"""
        with starts as (
            select distinct uuid7_time(run_id) as started from pipeline_events
            where event = 'run_finished'
        ),
        gaps as (
            select epoch(started - lag(started) over (order by started)) / 60 as gap_min
            from starts
        )
        select count(*) as intervals, {quantiles('gap_min')} from gaps where gap_min is not null
        """,
    )
    show(
        "Deployments",
        "select event, count(*) as n from pipeline_events "
        "where event in ('page_deployed', 'page_deploy_failed') group by all order by all",
    )
    show(
        "Data age at deployment per system, in minutes, every deployment",
        f"select system, count(*) as deploys, {quantiles('age_s / 60')} "
        "from deploys group by system order by system",
    )
    show(
        "Steady state",
        f"select {STEADY_FROM_SQL} as steady_from, count(*) as deploys, max(deployed_at) as last "
        f"from deploys where system = 'ambici' and deployed_at >= {STEADY_FROM_SQL}",
    )
    page = (
        "select run_id, max(age_s) as age_s, max(visitor_age_s) as visitor_age_s "
        f"from deploys where deployed_at >= {STEADY_FROM_SQL} group by run_id"
    )
    show(
        "Page age in steady state (the older system), in minutes",
        f"""
        select 'at deployment' as measure, count(age_s) as n, {quantiles('age_s / 60')}
        from ({page})
        union all
        select 'oldest a visitor sees', count(visitor_age_s), {quantiles('visitor_age_s / 60')}
        from ({page})
        """,
    )
    # file_built carries the file's latest capture instant, a direct source for
    # the age the derivation above estimates from processed_objects.
    direct = f"""
        select d.run_id, d.ts as deployed_at, f.data_instant,
            epoch(d.ts - f.data_instant) as age_s,
            epoch(lead(d.ts) over (order by d.ts) - f.data_instant) as visitor_age_s
        from pipeline_events d
        join pipeline_events f on f.run_id = d.run_id and f.event = 'file_built'
        where d.event = 'page_deployed' and d.ts >= {STEADY_FROM_SQL}
    """
    show(
        "Page age in steady state from file_built.data_instant, in minutes",
        f"""
        select 'at deployment' as measure, count(age_s) as n, {quantiles('age_s / 60')}
        from ({direct})
        union all
        select 'oldest a visitor sees', count(visitor_age_s), {quantiles('visitor_age_s / 60')}
        from ({direct})
        """,
    )
    show(
        "data_instant minus the derived data instant, per deployment, in seconds",
        f"""
        with derived as (
            select run_id, min(data_at) as oldest_system, max(data_at) as newest_system
            from deploys group by run_id
        )
        select 'vs the older system' as compared, count(*) as n,
            {quantiles('epoch(x.data_instant - d.oldest_system)')}
        from ({direct}) x join derived d using (run_id)
        union all
        select 'vs the newer system', count(*),
            {quantiles('epoch(x.data_instant - d.newest_system)')}
        from ({direct}) x join derived d using (run_id)
        """,
    )
    show(
        "Steady-state runs: duration_s and interval between starts, in minutes",
        f"""
        with runs as (
            select uuid7_time(run_id) as started, duration_s from pipeline_events
            where event = 'run_finished' and ts >= {STEADY_FROM_SQL}
        ),
        gaps as (
            select duration_s,
                epoch(started - lag(started) over (order by started)) / 60 as gap_min
            from runs
        )
        select 'duration_s' as measure, {quantiles('duration_s')} from gaps
        union all
        select 'gap_min', {quantiles('gap_min')} from gaps
        """,
    )
    show(
        f"Worst {WORST_SHOWN} deployments by page age",
        f"""
        select run_id, deployed_at, arg_max(system, age_s) as oldest_system,
            round(max(age_s) / 60, 1) as age_min
        from deploys group by all order by age_min desc limit {WORST_SHOWN}
        """,
    )


def self_test() -> None:
    """Check the minute count, the causes and the UUIDv7 time on synthetic rows, and exit."""
    con = duckdb.connect()
    con.sql("set TimeZone = 'UTC'")
    define_macros(con)
    t0 = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)

    def at(minute: int, second: int = 0) -> datetime:
        return t0 + timedelta(minutes=minute, seconds=second)

    con.sql("create table captures (system varchar, captured_at timestamptz, run_id varchar)")
    # Minute 0 twice, minutes 1-5 missed, minute 6 captured; logs start at minute 2.
    con.executemany(
        "insert into captures values ('bicing', ?, 'r')",
        [(at(0, 5),), (at(0, 40),), (at(6, 5),)],
    )
    con.sql(
        "create table capture_events (run_id varchar, event varchar, source varchar, "
        "feed varchar, status varchar, error_type varchar)"
    )

    def pass_id(minute: int) -> str:
        return at(minute, 7).strftime("%Y%m%dT%H%M%SZ")

    con.executemany(
        "insert into capture_events values (?, ?, ?, ?, ?, ?)",
        [
            (pass_id(2), "feed_failed", "bicing", FEED, "403", "http"),
            # Another source's failure never explains bicing's minute.
            (pass_id(3), "feed_failed", "ambici", FEED, "500", "http"),
            (pass_id(4), "feed_captured", "bicing", FEED, "200", None),
        ],
    )
    con.sql(MINUTES_SQL)
    got = dict(
        con.sql("select minute, cause from minutes where system = 'bicing' order by minute").fetchall()
    )
    assert len(got) == 7, got
    assert got[at(0)] is None and got[at(6)] is None, got
    assert got[at(1)] == "before capture logs", got[at(1)]
    assert got[at(2)] == "feed_failed status=403 error_type=http", got[at(2)]
    assert got[at(3)] == "pass logged, no station_status event", got[at(3)]
    assert got[at(4)] == "captured, not in processed_objects", got[at(4)]
    assert got[at(5)] == "no pass logged", got[at(5)]

    # A UUIDv7 whose first 48 bits are 2026-11-01T10:00:00.123Z in ms.
    ms = int(datetime(2026, 11, 1, 10, 0, 0, 123000, tzinfo=UTC).timestamp() * 1000)
    hex48 = f"{ms:012x}"
    uuid = f"{hex48[:8]}-{hex48[8:]}-7000-8000-000000000000"
    decoded = con.sql(f"select uuid7_time('{uuid}')").fetchall()[0][0]
    assert decoded == datetime(2026, 11, 1, 10, 0, 0, 123000, tzinfo=UTC), decoded
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
    con.sql("set TimeZone = 'UTC'")
    # Many small log objects: more threads keep more requests in flight.
    con.sql("set threads = 32")
    define_macros(con)
    connect_r2(con, env)

    print("Reading control/processed_objects…", flush=True)
    con.register("raw", read_captures(env))
    out: list[str] = [f"# DQM7 and DQM10 target review — {datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}"]
    out.append("\n## processed_objects rows per status\n")
    out.append(as_text(con.sql("select system, status, count(*) as n from raw group by all order by all")))
    con.sql(
        "create table captures as select system, captured_at, run_id from raw "
        "where status = 'processed'"
    )
    first, last = con.sql("select min(captured_at)::date, max(captured_at)::date from captures").fetchall()[0]
    print(f"Reading capture's logs, {first} to {last}…", flush=True)
    read_capture_logs(con, first, last)
    print("Reading the pipeline's logs…", flush=True)
    read_pipeline_logs(con)
    con.sql(MINUTES_SQL)
    con.sql(DEPLOYS_SQL)
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
