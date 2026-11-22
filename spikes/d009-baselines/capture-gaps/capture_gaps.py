"""Measure DQM11, the minutes with no capture of each dynamic feed, split by cause.

Every UTC minute from the first to the last pass logged, for each dynamic feed
of each source, is captured when its pass logged ``feed_captured`` for the feed.
Each missed minute gets its cause and its class by d009 D9 (A missed minute's
cause goes to whoever can act on it): provider, capture or unclassified.

Inputs: capture's pass logs under ``logs/`` of ``bikesharing-bronze``
(``BRONZE_R2_*`` in ``.env``), from 2026-11-07, the first production pass.
Output: a report on screen, saved as ``out/report-<UTC time>.txt``. Nothing is
written to R2.

Usage::

    uv run --directory pipeline python ../spikes/d009-baselines/capture-gaps/capture_gaps.py
    uv run --directory pipeline python ../spikes/d009-baselines/capture-gaps/capture_gaps.py --self-test
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
BRONZE_BUCKET = "bikesharing-bronze"
FIRST_LOG_DAY = date(2026, 11, 7)
# The feeds capture reads on every pass (capture/src/sources.js, dynamic).
DYNAMIC_FEEDS = (
    ("ambici", "station_status"),
    ("ambici", "free_bike_status"),
    ("bicing", "station_status"),
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT_DIR = HERE / "out"

COLUMNS = {
    "run_id": "VARCHAR",
    "event": "VARCHAR",
    "source": "VARCHAR",
    "feed": "VARCHAR",
    "status": "VARCHAR",
    "error_type": "VARCHAR",
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


def prepare(con: duckdb.DuckDBPyConnection) -> None:
    """Set UTC, define ``pass_time`` and create the empty ``capture_events`` and ``feeds``."""
    con.sql("set TimeZone = 'UTC'")
    # A pass's run_id is its start in ISO 8601 basic format, UTC (20261107T101939Z).
    con.sql(
        "create or replace macro pass_time(r) as "
        "strptime(r, '%Y%m%dT%H%M%SZ')::timestamptz"
    )
    con.sql(
        "create table capture_events (run_id varchar, event varchar, source varchar, "
        "feed varchar, status varchar, error_type varchar)"
    )
    con.sql("create table feeds (source varchar, feed varchar)")
    con.executemany("insert into feeds values (?, ?)", list(DYNAMIC_FEEDS))


def read_logs(con: duckdb.DuckDBPyConnection, env: dict[str, str], last: date) -> None:
    """Load capture's pass logs into ``capture_events``, one day at a time."""
    con.sql("install httpfs")
    con.sql("load httpfs")
    con.sql(
        f"create secret bronze (type r2, key_id '{require(env, 'BRONZE_R2_ACCESS_KEY_ID')}', "
        f"secret '{require(env, 'BRONZE_R2_SECRET_ACCESS_KEY')}', "
        f"account_id '{ACCOUNT_ID}', scope 'r2://{BRONZE_BUCKET}')"
    )
    cols = ", ".join(f"'{k}': '{v}'" for k, v in COLUMNS.items())
    day = FIRST_LOG_DAY
    while day <= last:
        began = time.monotonic()
        glob = f"r2://{BRONZE_BUCKET}/logs/date={day.isoformat()}/*.jsonl"
        try:
            con.sql(
                f"insert into capture_events select * from read_json('{glob}', "
                f"format = 'newline_delimited', columns = {{{cols}}}, hive_partitioning = false)"
            )
        except duckdb.Error as exc:
            print(f"  {day}: not read ({type(exc).__name__})", flush=True)
        else:
            n = con.sql(
                f"select count(distinct run_id) from capture_events where pass_time(run_id)::date = '{day}'"
            ).fetchall()[0][0]
            print(f"  {day}: {n} passes in {time.monotonic() - began:.1f} s", flush=True)
        day += timedelta(days=1)


# The class of each cause, by d009 D9: a response from the provider with no data,
# or a timeout reaching it, is the provider's; what happens inside capture or R2
# is capture's. Any other error type is left unclassified so a new one shows.
MINUTES_SQL = """
    create or replace table minutes as
    with events as (
        select *, date_trunc('minute', pass_time(run_id)) as minute from capture_events
    ),
    -- The last minute's pass may still be running when the logs are read.
    span as (select min(minute) as first, max(minute) - interval 1 minute as last from events),
    grid as (
        select f.source, f.feed, unnest(generate_series(s.first, s.last, interval 1 minute)) as minute
        from feeds f cross join span s
    ),
    captured as (
        select distinct source, feed, minute from events where event = 'feed_captured'
    ),
    -- index_rejected fails every feed of its source in that pass.
    failures as (
        select source, feed, minute, status, error_type from events where event = 'feed_failed'
        union all
        select e.source, f.feed, e.minute, e.status, e.error_type
        from events e join feeds f on f.source = e.source
        where e.event = 'index_rejected'
    ),
    failed as (
        select source, feed, minute,
            string_agg(distinct coalesce(error_type, '-') || ' ' || coalesce(status, '-'), '; ')
                as cause,
            case
                when bool_or(error_type = 'write') then 'capture'
                when bool_and(error_type in ('http', 'timeout')) then 'provider'
                else 'unclassified'
            end as class
        from failures group by source, feed, minute
    ),
    fed_any as (select distinct source, minute from events),
    passes as (select distinct minute from events)
    select g.source, g.feed, g.minute, c.minute is not null as captured,
        case
            when c.minute is not null then null
            when f.cause is not null then f.cause
            when a.minute is not null then 'pass logged, no event for the feed'
            when p.minute is not null then 'pass logged, no event for the source'
            else 'no pass logged'
        end as cause,
        case
            when c.minute is not null then null
            when f.class is not null then f.class
            else 'capture'
        end as class
    from grid g
    left join captured c using (source, feed, minute)
    left join failed f using (source, feed, minute)
    left join fed_any a using (source, minute)
    left join passes p on p.minute = g.minute
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
    return "\n".join(lines)


def report(con: duckdb.DuckDBPyConnection, out: list[str]) -> None:
    """Append every section of the report to ``out``."""

    def show(title: str, sql: str) -> None:
        out.append(f"\n## {title}\n")
        out.append(as_text(con.sql(sql)))

    show(
        "Span",
        "select min(minute) as first, max(minute) as last, count(distinct minute) as minutes "
        "from minutes",
    )
    show(
        "Missed minutes per feed, class and cause",
        """
        select source, feed, class, cause, count(*) as minutes
        from minutes where not captured
        group by source, feed, class, cause order by source, feed, class, minutes desc
        """,
    )
    show(
        "Missed minutes per feed, class and month",
        """
        select source, feed, strftime(minute, '%Y-%m') as month, count(*) as minutes,
            count(*) filter (where class = 'provider') as provider,
            count(*) filter (where class = 'capture') as capture,
            count(*) filter (where class = 'unclassified') as unclassified
        from minutes group by source, feed, month order by source, feed, month
        """,
    )
    show(
        "Missed minutes per day, per feed and class (days with none count as 0)",
        """
        with days as (
            select source, feed, minute::date as day,
                count(*) filter (where class = 'provider') as provider,
                count(*) filter (where class = 'capture') as capture
            from minutes group by source, feed, day
        )
        select source, feed, count(*) as days,
            median(provider) as provider_p50, max(provider) as provider_max,
            median(capture) as capture_p50, max(capture) as capture_max,
            sum(capture) as capture_total
        from days group by source, feed order by source, feed
        """,
    )
    show(
        "Days with capture's own missed minutes",
        """
        select source, feed, minute::date as day, count(*) as minutes,
            string_agg(distinct cause, '; ') as causes
        from minutes where class = 'capture'
        group by source, feed, day order by source, feed, day
        """,
    )
    show(
        "Runs of consecutive missed minutes, per feed and class",
        """
        with marked as (
            select *, sum(case when captured then 1 else 0 end)
                over (partition by source, feed order by minute) as grp
            from minutes
        ),
        gaps as (
            select source, feed, grp, count(*) as length,
                case when count(distinct class) = 1 then any_value(class) else 'mixed' end as class
            from marked where not captured group by source, feed, grp
        )
        select source, feed, class,
            case when length = 1 then '1' when length <= 5 then '2-5'
                when length <= 30 then '6-30' else '>30' end as minutes_in_a_row,
            count(*) as gaps, sum(length) as missed
        from gaps group by source, feed, class, minutes_in_a_row
        order by source, feed, class, min(length)
        """,
    )


def self_test() -> None:
    """Check the class given to each cause on synthetic events, and exit."""
    con = duckdb.connect()
    prepare(con)
    t0 = datetime(2026, 11, 8, 10, 0, tzinfo=UTC)

    def run_id(minute: int) -> str:
        return (t0 + timedelta(minutes=minute, seconds=7)).strftime("%Y%m%dT%H%M%SZ")

    ok = ("feed_captured", None, None)
    rows = []
    for source, feed in DYNAMIC_FEEDS:
        rows.append((run_id(0), ok[0], source, feed, "200", None))
        rows.append((run_id(6), ok[0], source, feed, "200", None))
    rows += [
        (run_id(1), "feed_failed", "bicing", "station_status", "403", "http"),
        (run_id(2), "feed_failed", "bicing", "station_status", None, "timeout"),
        (run_id(3), "feed_failed", "bicing", "station_status", "200", "write"),
        (run_id(4), "feed_failed", "bicing", "station_status", None, "dns"),
        # AMBici's index rejected: every AMBici feed misses minute 1.
        (run_id(1), "index_rejected", "ambici", None, "403", "http"),
        # Minute 2: AMBici's pass logged station_status only.
        (run_id(2), ok[0], "ambici", "station_status", "200", None),
    ]
    con.executemany("insert into capture_events values (?, ?, ?, ?, ?, ?)", rows)
    con.sql(MINUTES_SQL)

    def get(source: str, feed: str, minute: int) -> tuple:
        return con.sql(
            "select captured, class, cause from minutes "
            f"where source = '{source}' and feed = '{feed}' "
            f"and minute = '{(t0 + timedelta(minutes=minute)).isoformat()}'"
        ).fetchall()[0]

    assert get("bicing", "station_status", 0) == (True, None, None)
    assert get("bicing", "station_status", 1)[1] == "provider"
    assert get("bicing", "station_status", 2)[1] == "provider"
    assert get("bicing", "station_status", 3)[1] == "capture"
    assert get("bicing", "station_status", 4)[1] == "unclassified"
    assert get("bicing", "station_status", 5) == (False, "capture", "no pass logged")
    assert get("ambici", "free_bike_status", 1)[1] == "provider"
    assert get("ambici", "station_status", 2)[0] is True
    assert get("ambici", "free_bike_status", 2) == (
        False, "capture", "pass logged, no event for the feed"
    )
    # Minute 3 had a pass, for bicing only.
    assert get("ambici", "station_status", 3) == (
        False, "capture", "pass logged, no event for the source"
    )
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
    prepare(con)
    # Many small log objects: more threads keep more requests in flight.
    con.sql("set threads = 32")
    today = datetime.now(UTC).date()
    print(f"Reading capture's logs, {FIRST_LOG_DAY} to {today}…", flush=True)
    read_logs(con, env, today)
    con.sql(MINUTES_SQL)
    out = [f"# DQM11 capture gaps review — {datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}"]
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
