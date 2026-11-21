"""Measure DQR12's volume drop over every capture the pipeline has processed.

Reads ``control/processed_objects`` of ``bikesharing-lakehouse``, one row per
bronze object with its ``station_count``, and recomputes the rule as the model
``capture_volume`` does: each capture against the median of its system's
captures in the window before it, the capture itself left out. It then varies
the threshold, the window and the minimum of captures, to review the
provisional values (d008 D4, Volume drop against a rolling median).

Inputs: the lakehouse read pair of ``.env`` (``LAKEHOUSE_READ_R2_*``).
Output: a report on screen, saved as ``out/report-<UTC time>.txt``. Nothing is
written to R2.

Usage::

    uv run --directory pipeline python ../spikes/d009-baselines/volume-drop/volume_drop.py
    uv run --directory pipeline python ../spikes/d009-baselines/volume-drop/volume_drop.py --self-test
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
from arro3.core import Table
from deltalake import DeltaTable, QueryBuilder

ACCOUNT_ID = "b88ece5b9aad94b83f1710afa6d24070"
LAKEHOUSE_BUCKET = "bikesharing-lakehouse"
PROCESSED_PATH = "control/processed_objects"
FEED = "station_status"

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT_DIR = HERE / "out"

# The rule's provisional values, and the alternatives this check compares.
CURRENT = {"threshold": 0.9, "window_h": 24, "minimum": 60}
THRESHOLDS = (0.98, 0.95, 0.9, 0.85, 0.8, 0.7, 0.5)
WINDOWS_H = (24, 168)
MINIMUMS = (30, 60, 120, 720)
WORST_SHOWN = 15


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


def read_captures() -> Table:
    """Return system, captured_at and station_count of every station_status object."""
    env = {**load_env(REPO / ".env"), **os.environ}
    options = {
        "AWS_ENDPOINT_URL": f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com",
        "AWS_REGION": "auto",
        "AWS_ACCESS_KEY_ID": require(env, "LAKEHOUSE_READ_R2_ACCESS_KEY_ID"),
        "AWS_SECRET_ACCESS_KEY": require(env, "LAKEHOUSE_READ_R2_SECRET_ACCESS_KEY"),
    }
    table = DeltaTable(f"s3://{LAKEHOUSE_BUCKET}/{PROCESSED_PATH}", storage_options=options)
    sql = (
        "select system, captured_at, station_count, status from t "
        f"where feed = '{FEED}'"
    )
    return Table.from_arrow(QueryBuilder().register("t", table).execute(sql))


def windowed(window_h: int) -> str:
    """Return SQL giving each capture the count and median of the window before it.

    The frame matches ``capture_volume``: a range over the capture instant,
    from ``window_h`` hours before it up to it, the capture itself excluded.
    """
    return f"""
        select
            system,
            captured_at,
            station_count,
            count(*) over w as in_window,
            median(station_count) over w as median_count
        from captures
        window w as (
            partition by system
            order by captured_at
            range between interval '{window_h} hours' preceding and current row
            exclude current row
        )
        """


def episodes_sql(ratio: str, threshold: float) -> str:
    """Return SQL listing each run of consecutive captures below ``threshold``."""
    return f"""
        with marked as (
            select *, ratio < {threshold} as flagged from ({ratio})
        ),
        grouped as (
            select *,
                sum(case when flagged then 0 else 1 end)
                    over (partition by system order by captured_at) as grp
            from marked
        )
        select system, min(captured_at) as start, max(captured_at) as last,
            count(*) as captures, min(station_count) as min_count,
            min(ratio) as min_ratio, any_value(median_count) as median
        from grouped where flagged
        group by system, grp order by start
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
        "Captures per system",
        "select system, count(*) as captures, min(captured_at) as first, "
        "max(captured_at) as last from captures group by system order by system",
    )
    show(
        "Station count per system",
        "select system, min(station_count) as min, "
        "quantile_cont(station_count, 0.001) as p0_1, "
        "quantile_cont(station_count, 0.01) as p1, "
        "median(station_count) as median, max(station_count) as max, "
        "count(distinct station_count) as distinct_values "
        "from captures group by system order by system",
    )
    show(
        "Station count per system and day (min, median, max)",
        "select system, captured_at::date as day, min(station_count) as min, "
        "median(station_count) as median, max(station_count) as max, "
        "count(*) as captures from captures group by all order by system, day",
    )

    for window_h in WINDOWS_H:
        con.sql(f"create or replace table w{window_h} as {windowed(window_h)}")
        ratio = (
            f"select system, captured_at, station_count, in_window, median_count, "
            f"station_count / median_count as ratio from w{window_h} "
            f"where in_window >= {CURRENT['minimum']}"
        )
        show(
            f"Ratio to the median, window {window_h} h, minimum {CURRENT['minimum']}",
            f"select system, count(*) as evaluated, min(ratio) as min, "
            f"quantile_cont(ratio, 0.0001) as p0_01, quantile_cont(ratio, 0.001) as p0_1, "
            f"quantile_cont(ratio, 0.01) as p1, median(ratio) as median, max(ratio) as max "
            f"from ({ratio}) group by system order by system",
        )
        flags = ", ".join(
            f"count(*) filter (where ratio < {t}) as \"<{t}\"" for t in THRESHOLDS
        )
        show(
            f"Captures flagged per threshold, window {window_h} h",
            f"select system, {flags} from ({ratio}) group by system order by system",
        )
        # An episode is a run of consecutive flagged captures of one system, so
        # a sustained drop counts once, as the owner would see it in alerts.
        for threshold in (0.95, CURRENT["threshold"]):
            show(
                f"Episodes at threshold {threshold}, window {window_h} h",
                episodes_sql(ratio, threshold),
            )
        if window_h == CURRENT["window_h"]:
            show(
                f"Worst {WORST_SHOWN} captures per system, window {window_h} h",
                f"""
                select * exclude (rn) from (
                    select system, captured_at, station_count, in_window,
                        median_count, round(ratio, 4) as ratio,
                        row_number() over (partition by system order by ratio) as rn
                    from ({ratio})
                ) where rn <= {WORST_SHOWN} order by system, ratio
                """,
            )

    con.sql(f"create or replace table wcur as {windowed(CURRENT['window_h'])}")
    counts = ", ".join(
        f"count(*) filter (where in_window < {m}) as \"<{m}\"" for m in MINIMUMS
    )
    show(
        f"Captures not evaluated per minimum, window {CURRENT['window_h']} h",
        f"select system, {counts} from wcur group by system order by system",
    )
    show(
        "Gaps between consecutive captures over 1 h",
        """
        select system, prev as gap_start, captured_at as gap_end,
            captured_at - prev as gap
        from (
            select system, captured_at,
                lag(captured_at) over (partition by system order by captured_at) as prev
            from captures
        ) where captured_at - prev > interval '1 hour' order by gap desc
        """,
    )


def self_test() -> None:
    """Check the window logic on synthetic captures and exit."""
    con = duckdb.connect()
    start = datetime(2026, 11, 1, tzinfo=UTC)
    rows = [("ambici", start + timedelta(minutes=i), 100) for i in range(90)]
    rows.append(("ambici", start + timedelta(minutes=90), 80))
    rows.append(("bicing", start + timedelta(minutes=90), 50))
    con.sql("create table captures (system varchar, captured_at timestamptz, station_count integer)")
    con.executemany("insert into captures values (?, ?, ?)", rows)
    got = {
        (r[0], r[1]): r[2:]
        for r in con.sql(windowed(24)).fetchall()
    }
    # The capture itself is left out of its own window.
    assert got[("ambici", start)][1] == 0, got[("ambici", start)]
    # A drop to 80 is measured against the 90 earlier captures of 100.
    last = got[("ambici", start + timedelta(minutes=90))]
    assert last[1] == 90 and last[2] == 100, last
    # One system's captures never enter another's window.
    assert got[("bicing", start + timedelta(minutes=90))][1] == 0
    # The frame is a range in time, bounds included: with a 1 h window, the
    # captures of minutes 30 to 89.
    one_hour = {(r[0], r[1]): r[3] for r in con.sql(windowed(1)).fetchall()}
    assert one_hour[("ambici", start + timedelta(minutes=90))] == 60, one_hour[
        ("ambici", start + timedelta(minutes=90))
    ]
    print("self-test: OK")


def main() -> int:
    """Run the check, print the report and save it."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--self-test", action="store_true", help="check the window logic and exit")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0

    began = time.monotonic()
    print("Reading control/processed_objects…", flush=True)
    data = read_captures()
    con = duckdb.connect()
    con.sql("set TimeZone = 'UTC'")
    con.register("raw", data)
    out: list[str] = [
        f"# DQR12 volume drop review — {datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}",
        f"Current values: {CURRENT}",
    ]
    out.append("\n## Rows per status\n")
    out.append(as_text(con.sql("select system, status, count(*) as n from raw group by all order by all")))
    con.sql(
        "create table captures as select system, captured_at, station_count from raw"
    )
    print(f"Read {con.sql('select count(*) from captures').fetchall()[0][0]} captures.", flush=True)
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
