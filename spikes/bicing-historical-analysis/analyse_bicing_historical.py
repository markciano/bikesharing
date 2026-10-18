#!/usr/bin/env python3
"""Analyse the Bicing historical archives of Open Data BCN (T005).

Throwaway spike code. Implements the Analysis plan in
docs/spikes/s004-bicing-historical-data.md › Analysis plan, which is the
source of truth: this script makes no analysis decisions of its own.

Implemented (steps 1–7): common settings (configuration, extraction and
conversion to Parquet, typed view, month window, duplicates), metrics 1a, 1b,
1c, 2a input, 3a–3d, 5b, 5c, 6a–6d, 7a, 7b, 8a–8j, Verification › reconciliation (CSV
rows vs Parquet rows vs rows per snapshot, rows outside the month window, rows
dropped by deduplication), the 3b, 5b and 6d hand-checkable examples, and the
--only option. Rules added after step 2 (plan history, 2026-10-09): 3a counts
rows per snapshot after deduplication; 3b leaves out comparisons across a 5b
gap and counts them apart; 6c writes station_changes.csv.

Loading: a full run (no --only) rebuilds work/ from the .7z archives, one
month at a time: extract the CSV, read its header line and let DuckDB infer
the column types over every row, convert it to Parquet with every column read
as text, delete the CSV. The CSV facts later metrics need (bytes, data rows,
header line, inferred types) are stored in each Parquet file's key-value
metadata, so a run with --only reads them from work/ without extracting again.

Extraction uses the macOS built-in tar (bsdtar/libarchive) instead of 7z,
approved by the owner on 2026-10-08.

Usage, from the repository root, with the venv active:
    python spikes/bicing-historical-analysis/analyse_bicing_historical.py
    python spikes/bicing-historical-analysis/analyse_bicing_historical.py --only 1b,3a
"""

import argparse
import csv
import gzip
import json
import math
import re
import statistics
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DATA_DIR = REPO / "spikes/bicing-spike/historical-data"
RAW_DIR = DATA_DIR / "raw"
WORK_DIR = DATA_DIR / "work"
OUT_DIR = DATA_DIR / "analysis"

# Scope › Months: every 2026 month downloaded, both series.
MONTHS = ["2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-08"]
SERIES = ["ESTACIONS", "INFORMACIO"]

# Common settings › Timestamps and Month window.
TIMESTAMP_COLUMNS = ["last_reported", "last_updated"]
LOCAL_TZ = ZoneInfo("Europe/Madrid")

# Common settings › Reading: raw spellings of nulls and booleans. Empty fields are stored as
# null in Parquet (DuckDB's default null string), so "empty" is counted as Parquet null.
NULL_TOKEN = "NA"
BOOLEAN_TOKENS = ["TRUE", "FALSE", "1", "0"]

# 1b: distinct values are listed when there are at most this many, otherwise only counted.
DISTINCT_LIST_MAX = 20

# 3b "counts", as in the real-time plan: every numeric station field except last_reported. The
# archive's other numeric-looking columns are the ID, booleans (is_*, Common settings › Reading)
# and feed-level fields (last_updated, ttl).
COUNT_COLUMNS = ["num_bikes_available", "num_bikes_available_types.mechanical",
                 "num_bikes_available_types.ebike", "num_docks_available"]

# Common settings › Inputs: real-time reference.
REALTIME_PROFILE = REPO / "spikes/bicing-spike/analysis/field_profile.csv"
REALTIME_INFO_DIR = REPO / "spikes/bicing-spike/realtime/raw/station_information/2026-10-05"

# 2a input: the real-time feed each series is compared with, and the prefix of real-time station
# fields, dropped so their paths match archive column names literally (data.stations[].capacity → capacity).
FEED_OF_SERIES = {"ESTACIONS": "station_status", "INFORMACIO": "station_information"}
REALTIME_STATION_PREFIX = "data.stations[]."

# 6c: station attributes followed; coordinates are one attribute (lat and lon together).
INFO_ATTRIBUTES = ["name", "coordinates", "capacity"]

# 6d: archive month matched against the real-time response, distance listed above this, and the
# mean Earth radius (IUGG) for the haversine distance.
MATCH_MONTH = "2026-08"
MATCH_DISTANCE_M = 50
EARTH_RADIUS_M = 6_371_008.8

# 8. Quality: check id → (title, series, definition), in summary order. 8i has no computation.
QUALITY_CHECKS = {
    "8a": ("Over capacity", "ESTACIONS",
           "`num_bikes_available` + `num_docks_available` > `capacity`, with `capacity` from the as-of "
           "`INFORMACIO` snapshot (as in 6b). Rows whose station has no capacity there are counted apart."),
    "8b": ("Negative counts", "ESTACIONS", "Any of the four `num_*` counts < 0; one variant per count."),
    "8c": ("Type breakdown mismatch", "ESTACIONS",
           "`num_bikes_available_types.mechanical` + `.ebike` ≠ `num_bikes_available`; rows with a null "
           "breakdown counted apart."),
    "8d": ("Stale station", "ESTACIONS",
           "`is_installed` true and `last_reported` more than 24 h (86,400 s) before `last_updated`."),
    "8e": ("Future timestamp", "ESTACIONS", "`last_reported` later than `last_updated` + 60 s."),
    "8f": ("Inactive stations", "ESTACIONS",
           "`is_installed`, `is_renting` or `is_returning` false; `status` other than `IN_SERVICE`."),
    "8g": ("Duplicate ID", "both",
           "Same `station_id` more than once in one snapshot, before deduplication (Common settings › "
           "Duplicates), per (snapshot, station): exact duplicate (at least one exact copy), latest "
           "`last_reported` kept, tie (station left out). A (snapshot, station) can fall in more than one "
           "variant. Affected rows = every raw row of those (snapshot, station) pairs."),
    "8h": ("Out of area", "INFORMACIO", "Coordinates outside latitude 41.20–41.60, longitude 1.85–2.35."),
    "8i": ("Known issues", "—", "None listed for 2026."),
    "8j": ("Inactive flags vs availability", "ESTACIONS",
           "`is_renting` false split by `num_bikes_available` = 0 vs > 0; `is_returning` false split by "
           "`num_docks_available` = 0 vs > 0; and `num_bikes_available` = 0 with `is_renting` true."),
}

# --only: metric ids the script implements, in summary order.
METRICS = ["1a", "1b", "1c", "2a", "3a", "3b", "3c", "3d", "5b", "5c", "6a", "6b", "6c", "6d", "7a", "7b",
           *QUALITY_CHECKS]

# Metrics that read the deduplicated typed view (Common settings › Duplicates); each of them also
# writes the "dedup.check" reconciliation block.
DEDUP_METRICS = {"3a", "3b", "3c", "6a", "6b", "6c", "6d", *QUALITY_CHECKS}

# Summary blocks in document order. "load" (CSV vs Parquet reconciliation) is written by full
# runs only, since only they extract the CSVs; 3a also owns "3a.check" (snapshot reconciliation
# and month window); 3b, 5b and 6d own their hand-checkable examples.
BLOCK_ORDER = ["load", "3a.check", "dedup.check", "3b.example", "5b.example", "6d.example", "1a", "1b", "1c",
               "2a", "3a", "3b", "3c", "3d", "5b", "5c", "6a", "6b", "6c", "6d", "7a", "7b", *QUALITY_CHECKS]

# Key-value metadata stored in each Parquet file (values are text).
KV_KEYS = ["archive", "archive_bytes", "csv_name", "csv_bytes", "csv_rows", "header_line", "inferred_types"]

HEADER_CHECK_HEADER = ["month", "series", "position", "column", "change", "previous_position",
                       "inferred_type", "previous_type", "type_differs"]
PROFILE_HEADER = ["month", "series", "position", "column", "inferred_type", "rows", "null_pct",
                  "raw_NA", "raw_empty", "raw_TRUE", "raw_FALSE", "raw_1", "raw_0", "raw_other",
                  "distinct_count", "distinct_values", "min", "max", "min_utc", "max_utc"]
SNAPSHOTS_HEADER = ["month", "series", "last_updated_utc", "rows", "interval_s"]
REPORTING_HEADER = ["station_id", "month", "intervals", "interval_median_s", "interval_p95_s", "interval_max_s",
                    "heartbeats", "silent_changes"]
GAPS_HEADER = ["month", "series", "start_utc", "end_utc", "duration_min", "kind"]
CHANGES_HEADER = ["station_id", "month", "field", "old_value", "new_value", "first_seen_utc"]
COMPARISON_HEADER = ["series", "feed", "field", "archive_months", "archive_type", "archive_null_pct", "archive_min",
                     "archive_max", "archive_distinct_count", "archive_distinct_values", "realtime_path",
                     "realtime_present_pct", "realtime_type", "realtime_null_pct", "realtime_min", "realtime_max",
                     "realtime_distinct_count", "realtime_distinct_values"]
MATCH_HEADER = ["station_id", "in_archive", "in_realtime", "archive_external_id", "realtime_external_id",
                "same_external_id", "archive_name", "realtime_name", "same_name", "archive_lat", "archive_lon",
                "realtime_lat", "realtime_lon", "distance_m", "archive_capacity", "realtime_capacity", "same_capacity"]
CASES_HEADER = ["check", "variant", "month", "series", "station_id", "detail", "snapshots_affected",
                "first_seen_utc", "last_seen_utc"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sql_literal(text):
    """Quote a string as a SQL literal."""
    return "'" + text.replace("'", "''") + "'"


def sql_ident(name):
    """Quote a column name as a SQL identifier (archive names contain dots)."""
    return '"' + name.replace('"', '""') + '"'


def median(values):
    """Median as statistics.median (mean of the two middle values for an even count)."""
    return statistics.median(values) if values else None


def p95(values):
    """95th percentile by the nearest-rank method."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def histogram_stats(histogram):
    """Median, p95 and max of values given as sorted (value, count) pairs, as median() and p95() define them."""
    n = sum(count for _, count in histogram)
    if not n:
        return None, None, None

    def at(index):
        """Value at a 0-based position of the sorted values."""
        seen = 0
        for value, count in histogram:
            seen += count
            if index < seen:
                return value
        raise IndexError(index)

    lo, hi = at((n - 1) // 2), at(n // 2)
    return (lo + hi) / 2 if lo != hi else lo, at(math.ceil(0.95 * n) - 1), histogram[-1][0]


def raw_lines(archive, numbers):
    """Literal lines of the CSV inside an archive (1-based line numbers, header = 1), streamed with tar."""
    wanted, found = set(numbers), {}
    proc = subprocess.Popen(["tar", "-xOf", str(archive)], stdout=subprocess.PIPE)
    try:
        for number, line in enumerate(proc.stdout, 1):
            if number in wanted:
                found[number] = line.decode("utf-8").rstrip("\r\n")
                if len(found) == len(wanted):
                    break
    finally:
        proc.kill()
        proc.wait()
    return found


def csv_line(file_row_number):
    """CSV line number of a Parquet row: Parquet keeps the CSV row order, and line 1 is the header."""
    return file_row_number + 2


def pct(part, whole):
    """Percentage with two decimals, or an empty string when whole is zero."""
    return "" if not whole else f"{100 * part / whole:.2f}"


def fmt(value):
    """Format a number for tables: thousands separators, integral values without decimals."""
    if value is None:
        return ""
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.1f}"
    return f"{int(value):,}"


def fmt_plain(value):
    """Format a number for CSV files: no separators, integral values without decimals, empty for None."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def utc_text(epoch):
    """POSIX seconds as ISO 8601 UTC."""
    return datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_text(epoch):
    """POSIX seconds as ISO 8601 Europe/Madrid local time with offset."""
    return datetime.fromtimestamp(epoch, LOCAL_TZ).isoformat()


def month_window(month):
    """Common settings › Month window: [start, end) of a month in local time, as POSIX seconds."""
    year, mm = (int(part) for part in month.split("-"))
    start = datetime(year, mm, 1, tzinfo=LOCAL_TZ)
    end = datetime(year + mm // 12, mm % 12 + 1, 1, tzinfo=LOCAL_TZ)
    return int(start.timestamp()), int(end.timestamp())


def write_csv(path, header, rows):
    """Write a CSV file with a header row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def table(header, rows):
    """Markdown table."""
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def archive_path(month, series):
    """The one .7z archive of a month and series (Common settings › Inputs)."""
    year, mm = month.split("-")
    matches = sorted(RAW_DIR.glob(f"{year}_{mm}_*_BicingNou_{series}.7z"))
    if len(matches) != 1:
        sys.exit(f"{month} {series}: expected one archive in {RAW_DIR.relative_to(REPO)}, found {len(matches)}")
    return matches[0]


def parquet_path(archive):
    """Parquet file in work/ for an archive, with the archive's stem."""
    return WORK_DIR / f"{archive.stem}.parquet"


def csv_entry(archive):
    """Name of the single CSV inside an archive, as listed by tar."""
    listing = subprocess.run(["tar", "-tf", str(archive)], check=True, capture_output=True, text=True)
    entries = [line for line in listing.stdout.splitlines() if line]
    if len(entries) != 1 or not entries[0].endswith(".csv"):
        sys.exit(f"{archive.name}: expected one CSV entry, found {entries}")
    return entries[0]


def count_data_rows(path):
    """Data rows in a CSV: newline-terminated lines (plus an unterminated last one) minus the header.

    Counted independently of DuckDB, so the reconciliation compares two methods.
    """
    lines, last = 0, b""
    with open(path, "rb") as fh:
        while chunk := fh.read(16 * 1024 * 1024):
            lines += chunk.count(b"\n")
            last = chunk[-1:]
    if last and last != b"\n":
        lines += 1
    return lines - 1


def header_line(path):
    """1a input: the first line of a CSV, without its line ending."""
    with open(path, "rb") as fh:
        return fh.readline().decode("utf-8").rstrip("\r\n")


def inferred_types(con, path):
    """1b: column types DuckDB infers from every row of the CSV, with NA and empty as null."""
    rows = con.execute(
        f"DESCRIBE SELECT * FROM read_csv({sql_literal(str(path))}, header = true, delim = ',', "
        f"quote = '\"', nullstr = ['{NULL_TOKEN}', ''], sample_size = -1)"
    ).fetchall()
    return [[name, dtype] for name, dtype, *_ in rows]


def load_month(con, month, series):
    """Extract one archive, convert its CSV to Parquet in work/ and delete the CSV.

    Returns the load facts for the reconciliation and the metrics.
    """
    archive = archive_path(month, series)
    entry = csv_entry(archive)
    csv_path = WORK_DIR / entry
    target = parquet_path(archive)
    partial = target.with_suffix(".parquet.partial")
    try:
        subprocess.run(["tar", "-xf", str(archive), "-C", str(WORK_DIR)], check=True)
        if not csv_path.is_file():
            sys.exit(f"{archive.name}: tar did not produce {entry}")
        facts = {
            "archive": archive.name,
            "archive_bytes": archive.stat().st_size,
            "csv_name": entry,
            "csv_bytes": csv_path.stat().st_size,
            "csv_rows": count_data_rows(csv_path),
            "header_line": header_line(csv_path),
            "inferred_types": json.dumps(inferred_types(con, csv_path)),
        }
        # Common settings › Reading: every column as text, so raw representations survive.
        kv = ", ".join(f"{key}: {sql_literal(str(facts[key]))}" for key in KV_KEYS)
        con.execute(
            f"COPY (SELECT * FROM read_csv({sql_literal(str(csv_path))}, header = true, delim = ',', "
            f"quote = '\"', all_varchar = true)) "
            f"TO {sql_literal(str(partial))} (FORMAT parquet, KV_METADATA {{{kv}}})"
        )
        partial.replace(target)
    finally:
        csv_path.unlink(missing_ok=True)
        partial.unlink(missing_ok=True)
    return read_facts(con, month, series)


def read_facts(con, month, series):
    """Load facts of a month and series from its Parquet file in work/."""
    target = parquet_path(archive_path(month, series))
    if not target.is_file():
        sys.exit(f"{target.relative_to(REPO)} does not exist; run without --only first")
    rows = con.execute(f"SELECT key, value FROM parquet_kv_metadata({sql_literal(str(target))})").fetchall()
    kv = {bytes(k).decode(): bytes(v).decode() for k, v in rows}
    missing = [key for key in KV_KEYS if key not in kv]
    if missing:
        sys.exit(f"{target.relative_to(REPO)}: metadata lacks {missing}; run without --only first")
    source = f"read_parquet({sql_literal(str(target))})"
    parquet_rows = con.execute(f"SELECT count(*) FROM {source}").fetchone()[0]
    parquet_columns = [row[0] for row in con.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()]
    return {
        "month": month,
        "series": series,
        "archive": kv["archive"],
        "archive_bytes": int(kv["archive_bytes"]),
        "csv_name": kv["csv_name"],
        "csv_bytes": int(kv["csv_bytes"]),
        "csv_rows": int(kv["csv_rows"]),
        "header": next(csv.reader([kv["header_line"]])),
        "types": dict(json.loads(kv["inferred_types"])),
        "parquet": target.name,
        "path": target,
        "source": source,
        "parquet_bytes": target.stat().st_size,
        "parquet_rows": parquet_rows,
        "parquet_columns": parquet_columns,
    }


# ---------------------------------------------------------------------------
# 1. Schema
# ---------------------------------------------------------------------------

def header_check_rows(facts):
    """1a and 1c: one row per column per month and series, compared with the previous month available."""
    rows = []
    for series in SERIES:
        previous = None
        for f in (f for f in facts if f["series"] == series):
            columns = f["header"]
            for position, column in enumerate(columns, 1):
                dtype = f["types"].get(column, "")
                if previous is None:
                    rows.append([f["month"], series, position, column, "first month", "", dtype, "", ""])
                    continue
                if column not in previous["header"]:
                    rows.append([f["month"], series, position, column, "added", "", dtype, "", ""])
                    continue
                before = previous["header"].index(column) + 1
                before_type = previous["types"].get(column, "")
                rows.append([f["month"], series, position, column,
                             "unchanged" if before == position else "moved", before, dtype, before_type,
                             "yes" if dtype != before_type else "no"])
            if previous is not None:
                for before, column in enumerate(previous["header"], 1):
                    if column not in columns:
                        rows.append([f["month"], series, "", column, "removed", before, "",
                                     previous["types"].get(column, ""), ""])
            previous = f
    return rows


def render_1a(facts, check_rows):
    """1a summary: column count per month and series, and every change versus the previous month."""
    changes = {}
    for row in check_rows:
        if row[4] in ("added", "removed", "moved"):
            changes.setdefault((row[0], row[1]), []).append(f"{row[3]} {row[4]}")
    rows = []
    for f in facts:
        same = "yes" if f["parquet_columns"] == f["header"] else "**NO**"
        rows.append([f["month"], f["series"], len(f["header"]), same,
                     "; ".join(changes.get((f["month"], f["series"]), [])) or "—"])
    return "\n\n".join([
        "### 1a. Header check",
        "Details per column in `header_check.csv`. Changes are versus the previous month available "
        "(the first month of each series has none).",
        table(["Month", "Series", "Columns", "Parquet columns = header", "Changes"], rows),
    ])


def render_1c(check_rows):
    """1c summary: columns whose inferred type differs from the previous month available."""
    changed = [[row[0], row[1], row[3], row[7], row[6]] for row in check_rows if row[8] == "yes"]
    parts = ["### 1c. Type stability",
             "Inferred type per column in `header_check.csv` (`inferred_type`, `previous_type`, `type_differs`)."]
    if changed:
        parts.append(table(["Month", "Series", "Column", "Previous type", "Type"], changed))
    else:
        parts.append("No column changes its inferred type versus the previous month available.")
    return "\n\n".join(parts)


def typed(column, dtype):
    """Typed view of a raw text column (Common settings › Reading): NA and empty → null, then cast."""
    raw = f"NULLIF({sql_ident(column)}, '{NULL_TOKEN}')"
    return raw if dtype == "VARCHAR" else f"TRY_CAST({raw} AS {dtype})"


def profile_rows(con, f):
    """1b: one field_profile.csv row per column of one month and series."""
    columns = f["parquet_columns"]
    aggregates = ["count(*)"]
    for column in columns:
        c = sql_ident(column)
        t = typed(column, f["types"].get(column, "VARCHAR"))
        aggregates += [
            f"count(*) FILTER ({c} = '{NULL_TOKEN}')",
            f"count(*) FILTER ({c} IS NULL)",
            *[f"count(*) FILTER ({c} = '{token}')" for token in BOOLEAN_TOKENS],
            f"count(DISTINCT {c})",
            f"min({t})",
            f"max({t})",
        ]
    values = con.execute(f"SELECT {', '.join(aggregates)} FROM {f['source']}").fetchone()
    total, rest = values[0], values[1:]
    per_column = 3 + len(BOOLEAN_TOKENS) + 2
    rows = []
    for i, column in enumerate(columns):
        na, empty, *tokens, distinct, lo, hi = rest[i * per_column:(i + 1) * per_column]
        other = total - na - empty - sum(tokens)
        listed = ""
        if distinct <= DISTINCT_LIST_MAX:
            counts = con.execute(
                f"SELECT {sql_ident(column)}, count(*) FROM {f['source']} WHERE {sql_ident(column)} IS NOT NULL "
                f"GROUP BY 1 ORDER BY 2 DESC, 1"
            ).fetchall()
            listed = json.dumps(dict(counts), ensure_ascii=False)
        is_ts = column in TIMESTAMP_COLUMNS and isinstance(lo, int)
        rows.append([f["month"], f["series"], i + 1, column, f["types"].get(column, ""), total,
                     pct(na + empty, total), na, empty, *tokens, other, distinct, listed,
                     "" if lo is None else lo, "" if hi is None else hi,
                     utc_text(lo) if is_ts else "", utc_text(hi) if is_ts else ""])
    return rows


def render_1b(profile):
    """1b summary: where the profile is and how many rows it has."""
    return "\n\n".join([
        "### 1b. Field profile",
        f"`field_profile.csv`: {len(profile)} rows (one per month, series and column). Raw spellings counted "
        f"per column: `{NULL_TOKEN}`, empty, {', '.join(f'`{t}`' for t in BOOLEAN_TOKENS)} and any other "
        f"non-null value (`raw_other`); distinct values over the raw text, listed with their counts when "
        f"≤ {DISTINCT_LIST_MAX}; min/max over the typed view.",
    ])


# ---------------------------------------------------------------------------
# 3a. Snapshots and month window
# ---------------------------------------------------------------------------

def snapshots(con, f):
    """3a: rows per distinct last_updated (typed view, before deduplication), and rows with no valid last_updated.

    The snapshot times drive 3a intervals, 5b, 5c and 7b; the raw row counts drive the snapshot reconciliation.
    3a's rows per snapshot come from dedup_snapshot_counts.
    """
    raw = sql_ident("last_updated")
    t = typed("last_updated", "BIGINT")
    counts = con.execute(
        f"SELECT {t} AS lu, count(*) FROM {f['source']} WHERE {t} IS NOT NULL GROUP BY 1 ORDER BY 1"
    ).fetchall()
    missing, unparseable = con.execute(
        f"SELECT count(*) FILTER ({raw} IS NULL OR {raw} = '{NULL_TOKEN}'), "
        f"count(*) FILTER ({raw} IS NOT NULL AND {raw} <> '{NULL_TOKEN}' AND {t} IS NULL) FROM {f['source']}"
    ).fetchone()
    return {"snapshots": counts, "missing": missing, "unparseable": unparseable}


def dedup_snapshot_counts(con):
    """3a: {last_updated: rows} in the deduplicated view of the month just deduplicated."""
    return {"counts": dict(con.execute(
        "SELECT last_updated, count(*) FROM dedup WHERE last_updated IS NOT NULL GROUP BY 1").fetchall())}


def snapshot_rows(f, snaps, kept):
    """snapshots.csv rows of one month and series; rows per snapshot after deduplication."""
    rows, previous = [], None
    for lu, _ in snaps["snapshots"]:
        rows.append([f["month"], f["series"], utc_text(lu), kept["counts"].get(lu, 0),
                     "" if previous is None else lu - previous])
        previous = lu
    return rows


def render_3a(facts, snaps, kept):
    """3a summary: snapshots, rows per snapshot (deduplicated) and interval between snapshots per month and series."""
    rows = []
    for f in facts:
        key = (f["month"], f["series"])
        s = snaps[key]["snapshots"]
        sizes = [kept[key]["counts"].get(lu, 0) for lu, _ in s]
        intervals = [b[0] - a[0] for a, b in zip(s, s[1:])]
        rows.append([f["month"], f["series"], fmt(len(s)), fmt(min(sizes, default=None)), fmt(median(sizes)),
                     fmt(max(sizes, default=None)), fmt(median(intervals)), fmt(p95(intervals)),
                     fmt(max(intervals, default=None))])
    return "\n\n".join([
        "### 3a. Snapshot cadence",
        "Snapshot = rows sharing one `last_updated` (typed view). Rows per snapshot counted after deduplication "
        "(Common settings › Duplicates). One row per snapshot in `snapshots.csv`. Intervals in seconds, between "
        "consecutive snapshots of the same month.",
        table(["Month", "Series", "Snapshots", "Rows min", "Rows median", "Rows max",
               "Interval median (s)", "Interval p95 (s)", "Interval max (s)"], rows),
    ])


def render_3a_check(facts, snaps, kept, drops):
    """Verification › reconciliation: Parquet rows = rows per snapshot, before and after deduplication; rows
    outside the month window."""
    rows, outside_list = [], []
    matches = dedup_matches = 0
    for f in facts:
        key = (f["month"], f["series"])
        s = snaps[key]
        in_snapshots = sum(n for _, n in s["snapshots"])
        match = in_snapshots == f["parquet_rows"]
        matches += match
        d = drops[key]
        dropped = d["exact"] + d["older"] + d["tie_rows"]
        in_3a = sum(kept[key]["counts"].values())
        dedup_match = in_3a + dropped == f["parquet_rows"]
        dedup_matches += dedup_match
        start, end = month_window(f["month"])
        outside = [(lu, n) for lu, n in s["snapshots"] if not start <= lu < end]
        outside_list += [[f["month"], f["series"], utc_text(lu), local_text(lu), fmt(n)] for lu, n in outside]
        rows.append([f["month"], f["series"], fmt(f["csv_rows"]), fmt(f["parquet_rows"]), fmt(in_snapshots),
                     fmt(s["missing"]), fmt(s["unparseable"]), "yes" if match else "**NO**",
                     fmt(in_3a), fmt(dropped), "yes" if dedup_match else "**NO**",
                     fmt(len(outside)), fmt(sum(n for _, n in outside))])
    parts = [
        "## Reconciliation — snapshots and month window",
        "Rows in snapshots = sum of raw rows per snapshot, before deduplication. Rows without a valid "
        "`last_updated` (null/`NA`, or not an integer) belong to no snapshot. Rows in snapshots after "
        "deduplication = sum of rows per snapshot in 3a (`snapshots.csv`); rows dropped by deduplication as in "
        "*Reconciliation — duplicates*; both sums leave out rows in no snapshot. Month window: `last_updated` in [local midnight of the 1st, local "
        "midnight of the 1st of the next month), Europe/Madrid; rows outside it are kept.",
        table(["Month", "Series", "CSV rows", "Parquet rows", "Rows in snapshots", "Null/NA last_updated",
               "Unparseable last_updated", "Parquet = snapshots", "Rows in snapshots after deduplication (3a)",
               "Rows dropped by deduplication", "Parquet = 3a + dropped", "Snapshots outside window",
               "Rows outside window"], rows),
        f"Parquet rows = rows in snapshots: {matches} of {len(facts)}.",
        f"Parquet rows = rows in 3a snapshots + rows dropped by deduplication: {dedup_matches} of {len(facts)}.",
        "Snapshots outside the month window:",
    ]
    if outside_list:
        parts.append(table(["Month", "Series", "last_updated (UTC)", "last_updated (local)", "Rows"], outside_list))
    else:
        parts.append("None.")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Common settings › Duplicates: the deduplicated typed view
# ---------------------------------------------------------------------------

def build_dedup(con, f):
    """Build temp table `dedup`: the typed view of one month and series, deduplicated within each snapshot.

    (1) exact duplicate rows are dropped (the first in CSV order is kept); (2) if a station still has more
    than one row in a snapshot, the one with the latest last_reported is kept; (3) on a tie, the station is
    left out of that snapshot. INFORMACIO has no last_reported, so any station left after (1) is a tie.
    Every column is carried, typed; rn is the Parquet row number. Temp table `staged` keeps every row with
    its fate (exact copy, single, latest, older, tie) for 8g. Returns the rows dropped at each stage.
    """
    cols, types = f["parquet_columns"], f["types"]
    raw_cols = ", ".join(sql_ident(c) for c in cols)
    reported = typed("last_reported", types["last_reported"]) if "last_reported" in cols else "NULL::BIGINT"
    keys = {"station_id", "last_updated", "last_reported"}
    others = "".join(f", {typed(c, types[c])} AS {sql_ident(c)}" for c in cols if c not in keys)
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE staged AS
        WITH e AS (
            SELECT *, row_number() OVER (PARTITION BY {raw_cols} ORDER BY file_row_number) AS copy_no
            FROM read_parquet({sql_literal(str(f["path"]))}, file_row_number = true)),
        t AS (
            SELECT file_row_number AS rn, copy_no, {typed("station_id", types["station_id"])} AS station_id,
                   {typed("last_updated", types["last_updated"])} AS last_updated,
                   {reported} AS last_reported{others}
            FROM e),
        g AS (
            SELECT *, count(*) OVER w AS n, max(last_reported) OVER w AS latest
            FROM t WHERE copy_no = 1 WINDOW w AS (PARTITION BY last_updated, station_id)),
        h AS (
            SELECT *, sum(CASE WHEN last_reported = latest THEN 1 ELSE 0 END)
                      OVER (PARTITION BY last_updated, station_id) AS at_latest
            FROM g)
        SELECT * EXCLUDE (copy_no, n, latest, at_latest),
               CASE WHEN n = 1 THEN 'single'
                    WHEN at_latest = 1 AND last_reported = latest THEN 'latest'
                    WHEN at_latest = 1 THEN 'older'
                    ELSE 'tie' END AS fate
        FROM h
        UNION ALL BY NAME
        SELECT * EXCLUDE (copy_no), 'exact' AS fate FROM t WHERE copy_no > 1
    """)
    con.execute("CREATE OR REPLACE TEMP TABLE dedup AS "
                "SELECT * EXCLUDE (fate) FROM staged WHERE fate IN ('single', 'latest')")
    exact, older, tie_rows, tie_cases, kept = con.execute("""
        SELECT count(*) FILTER (fate = 'exact'), count(*) FILTER (fate = 'older'), count(*) FILTER (fate = 'tie'),
               count(DISTINCT (last_updated, station_id)) FILTER (fate = 'tie'),
               count(*) FILTER (fate IN ('single', 'latest'))
        FROM staged
    """).fetchone()
    return {"exact": exact, "older": older, "tie_rows": tie_rows, "tie_cases": tie_cases, "kept": kept}


def render_dedup_check(facts, drops):
    """Verification › reconciliation: rows dropped at each deduplication stage per month and series."""
    rows, matches = [], 0
    for f in facts:
        d = drops[(f["month"], f["series"])]
        match = f["parquet_rows"] == d["kept"] + d["exact"] + d["older"] + d["tie_rows"]
        matches += match
        rows.append([f["month"], f["series"], fmt(f["parquet_rows"]), fmt(d["exact"]), fmt(d["older"]),
                     fmt(d["tie_rows"]), fmt(d["tie_cases"]), fmt(d["kept"]), "yes" if match else "**NO**"])
    return "\n\n".join([
        "## Reconciliation — duplicates",
        "Common settings › Duplicates, within each snapshot: (1) exact duplicate rows dropped; (2) a station "
        "with more than one row keeps the one with the latest `last_reported`; (3) on a tie the station is left "
        "out of that snapshot (`INFORMACIO` has no `last_reported`: any station left after (1) is a tie). "
        "Metrics 3a (rows per snapshot), 3b, 3c, 6a–6d and 8 (except 8g, which counts before deduplication) read "
        "the rows kept.",
        table(["Month", "Series", "Parquet rows", "(1) Exact duplicates dropped", "(2) Older rows dropped",
               "(3) Tie rows dropped", "(3) Stations left out (station × snapshot)", "Rows kept",
               "Parquet = kept + dropped"], rows),
        f"Parquet rows = rows kept + rows dropped: {matches} of {len(facts)}.",
    ])


# ---------------------------------------------------------------------------
# 3b–3d. Freshness
# ---------------------------------------------------------------------------

def build_sequence(con):
    """Temp table `seq`: deduplicated rows with a valid station_id and last_reported, numbered by snapshot.

    k = position of the row's snapshot in the month (1 = first); prev_updated = last_updated of snapshot k − 1;
    pk / ppk / nk = the station's previous, second previous and next snapshot positions; plr / pplr, plu / pplu
    and p_<count> = previous values.
    """
    lags = "".join(f", lag({sql_ident(c)}) OVER w AS {sql_ident('p_' + c)}" for c in COUNT_COLUMNS)
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE seq AS
        WITH s AS (
            SELECT last_updated, row_number() OVER (ORDER BY last_updated) AS k,
                   lag(last_updated) OVER (ORDER BY last_updated) AS prev_updated
            FROM (SELECT DISTINCT last_updated FROM dedup WHERE last_updated IS NOT NULL)),
        x AS (
            SELECT d.*, s.k, s.prev_updated FROM dedup d JOIN s USING (last_updated)
            WHERE d.station_id IS NOT NULL AND d.last_reported IS NOT NULL)
        SELECT x.*, lag(k) OVER w AS pk, lag(k, 2) OVER w AS ppk, lead(k) OVER w AS nk,
               lag(last_reported) OVER w AS plr, lag(last_reported, 2) OVER w AS pplr,
               lag(last_updated) OVER w AS plu, lag(last_updated, 2) OVER w AS pplu{lags}
        FROM x WINDOW w AS (PARTITION BY station_id ORDER BY k)
    """)


def counts_changed(prefix_now="", prefix_before="p_"):
    """SQL: true when any 3b count differs between two rows of seq (null-safe)."""
    return " OR ".join(f"{sql_ident(prefix_now + c)} IS DISTINCT FROM {sql_ident(prefix_before + c)}"
                       for c in COUNT_COLUMNS)


def within_gap_threshold(threshold, now="last_updated", before="prev_updated"):
    """SQL: true when two snapshots are no further apart than the month's 5b threshold (always true without one)."""
    return "TRUE" if threshold is None else f"({now} - {before} <= {threshold})"


def station_reporting(con, threshold):
    """3b for one month of ESTACIONS: per-station rows of station_reporting.csv and the month's totals.

    A station is compared between consecutive snapshots of the month when it is in both (as the real-time
    plan compares consecutive responses); an interval is recorded when last_reported moved. Comparisons
    whose two snapshots are further apart than the month's 5b threshold (a gap) are left out and counted apart.
    """
    build_sequence(con)
    consecutive = "pk = k - 1"
    near = within_gap_threshold(threshold)
    paired = f"({consecutive} AND {near})"
    moved = f"({paired} AND last_reported <> plr)"
    changed = f"({counts_changed()})"
    per_station = con.execute(f"""
        WITH q AS (
            SELECT station_id, CASE WHEN {moved} THEN last_reported - plr END AS iv,
                   {paired} AS paired, {moved} AS moved, {changed} AS changed
            FROM seq),
        a AS (
            SELECT station_id, list_sort(list(iv) FILTER (iv IS NOT NULL)) AS l,
                   count(*) FILTER (paired AND moved AND NOT changed) AS heartbeats,
                   count(*) FILTER (paired AND NOT moved AND changed) AS silent
            FROM q GROUP BY 1)
        SELECT station_id, len(l), CASE WHEN len(l) > 0 THEN (l[(len(l) + 1) // 2] + l[len(l) // 2 + 1]) / 2 END,
               CASE WHEN len(l) > 0 THEN l[CAST(ceil(0.95 * len(l)) AS BIGINT)] END, list_max(l), heartbeats, silent
        FROM a ORDER BY station_id
    """).fetchall()
    last_k = con.execute("SELECT max(k) FROM seq").fetchone()[0]
    totals = con.execute(f"""
        SELECT count(*) FILTER ({paired}),
               count(*) FILTER ({consecutive} AND NOT {near}),
               count(*) FILTER (k > 1 AND (pk IS NULL OR pk < k - 1))
                 + count(*) FILTER (k < {last_k} AND (nk IS NULL OR nk > k + 1)),
               count(*) FILTER ({moved} AND last_reported < plr)
        FROM seq
    """).fetchone()
    items = con.execute("""
        SELECT count(*), count(*) FILTER (last_reported = last_updated), count(*) FILTER (last_reported IS NULL)
        FROM dedup
    """).fetchone()
    rows = [[sid, n, med, p, mx, hb, sc] for sid, n, med, p, mx, hb, sc in per_station]
    return {"rows": rows, "pairs": totals[0], "pairs_over_gap": totals[1], "skipped": totals[2],
            "negative": totals[3], "items": items[0], "stamped": items[1], "unparseable": items[2]}


def reporting_example(con, f, threshold):
    """3b hand-checkable example: the lowest station_id with three consecutive snapshots, neither comparison
    across a 5b gap, in which last_reported moves at least once, at its first such triple. Uses the `seq` of the
    month just measured."""
    found = con.execute(f"""
        SELECT station_id, k FROM seq
        WHERE pk = k - 1 AND ppk = k - 2 AND {within_gap_threshold(threshold, "last_updated", "plu")}
          AND {within_gap_threshold(threshold, "plu", "pplu")} AND (last_reported <> plr OR plr <> pplr)
        ORDER BY station_id, k LIMIT 1
    """).fetchone()
    if found is None:
        return None
    sid, k = found
    cols = ", ".join(sql_ident(c) for c in COUNT_COLUMNS)
    rows = con.execute(f"""
        SELECT rn, k, last_updated, last_reported, {cols} FROM seq
        WHERE station_id = {sid} AND k BETWEEN {k - 2} AND {k} ORDER BY k
    """).fetchall()
    return {"month": f["month"], "series": f["series"], "station_id": sid, "rows": rows}


def render_3b_example(con, example, f, lines):
    """3b example block: the three snapshots, the raw CSV lines and how each transition is classified."""
    header = ["CSV line", "Snapshot k", "last_updated (UTC)", "last_reported (UTC)", *COUNT_COLUMNS]
    rows, steps = [], []
    for i, (rn, k, lu, lr, *counts) in enumerate(example["rows"]):
        rows.append([csv_line(rn), k, utc_text(lu), utc_text(lr), *counts])
        if i:
            _, _, _, plr, *pcounts = example["rows"][i - 1]
            moved, changed = lr != plr, counts != pcounts
            kind = ("interval + heartbeat" if moved and not changed else "interval" if moved
                    else "silent change" if changed else "no change")
            steps.append(f"- Snapshot {k - 1} → {k}: `last_reported` {plr} → {lr}"
                         + (f" (interval {lr - plr} s)" if moved else " (unchanged)")
                         + f"; counts {'changed' if changed else 'unchanged'} → {kind}.")
    raw = [f"line {csv_line(rn)}: {lines.get(csv_line(rn), '(not found)')}" for rn, *_ in example["rows"]]
    return "\n\n".join([
        "## Example — 3b station reporting interval",
        f"{example['month']} {example['series']} (`{f['archive']}`), station_id {example['station_id']}: the "
        "lowest station_id with three consecutive snapshots, neither comparison across a 5b gap, where "
        "`last_reported` moves at least once (first such triple). Rows from the deduplicated view.",
        table(header, rows),
        "Raw CSV lines (line 1 = header):",
        "```\n" + "\n".join(raw) + "\n```",
        f"Raw lines equal their Parquet rows: {'yes' if lines_match_parquet(con, f, lines) else '**NO**'}.",
        "\n".join(steps),
    ])


def render_3b(results):
    """3b summary per month: comparisons, distribution across stations of each station's median, totals."""
    rows, totals = [], [0, 0, 0, 0, 0, 0]
    for month, r in results.items():
        medians = [row[2] for row in r["rows"] if row[1]]
        without = sum(1 for row in r["rows"] if not row[1])
        heartbeats, silent = sum(row[5] for row in r["rows"]), sum(row[6] for row in r["rows"])
        rows.append([month, fmt(r["items"]), f"{fmt(r['stamped'])} ({pct(r['stamped'], r['items'])} %)",
                     fmt(len(r["rows"])), fmt(without), fmt(r["pairs"]), fmt(r["pairs_over_gap"]),
                     fmt(r["skipped"]), fmt(r["negative"]), fmt(median(medians)), fmt(p95(medians)),
                     fmt(max(medians, default=None)), fmt(heartbeats), fmt(silent)])
        for i, v in enumerate([r["pairs"], r["pairs_over_gap"], r["skipped"], r["negative"], heartbeats, silent]):
            totals[i] += v
    unparseable = sum(r["unparseable"] for r in results.values())
    return "\n\n".join([
        "### 3b. Station reporting interval",
        "`ESTACIONS`, deduplicated view. A station is compared between consecutive snapshots of the month "
        "when it is in both; an interval (s) is recorded when `last_reported` moved. Heartbeat: "
        "`last_reported` moved, counts did not; silent change: counts changed, `last_reported` did not. Counts: "
        + ", ".join(f"`{c}`" for c in COUNT_COLUMNS) + ". Comparisons whose two snapshots are further apart than "
        "the month's 5b threshold (across a gap) are left out of intervals, heartbeats and silent changes and "
        "counted apart (\"Excluded: across a 5b gap\"). One row per station and month in "
        f"`station_reporting.csv`. Rows with null `last_reported`: {fmt(unparseable)}.",
        table(["Month", "Station rows", "`last_reported` = `last_updated`", "Stations", "Stations with no interval",
               "Comparisons", "Excluded: across a 5b gap", "Skipped (station in one snapshot only)",
               "Negative intervals", "Station medians: median (s)", "p95 (s)", "max (s)", "Heartbeats",
               "Silent changes"], rows),
        table(["Total", "Comparisons", "Excluded: across a 5b gap", "Skipped", "Negative intervals", "Heartbeats",
               "Silent changes"], [["All months", *(fmt(v) for v in totals)]]),
    ])


def lag_histogram(con):
    """3c for one month of ESTACIONS: (lag, rows) pairs of last_updated − last_reported, deduplicated view."""
    return con.execute("""
        SELECT last_updated - last_reported AS lag, count(*) FROM dedup
        WHERE last_updated IS NOT NULL AND last_reported IS NOT NULL GROUP BY 1 ORDER BY 1
    """).fetchall()


def render_3c(histograms):
    """3c summary per month: median, p95, max and negatives of the lag."""
    rows = []
    for month, h in histograms.items():
        med, p, mx = histogram_stats(h)
        n = sum(c for _, c in h)
        negative = sum(c for v, c in h if v < 0)
        rows.append([month, fmt(n), fmt(med), fmt(p), fmt(mx), f"{fmt(negative)} ({pct(negative, n)} %)"])
    return "\n\n".join([
        "### 3c. `last_updated` vs `last_reported`",
        "`ESTACIONS`, deduplicated view: lag = `last_updated` − `last_reported` per row, in seconds.",
        table(["Month", "Rows", "Median (s)", "p95 (s)", "Max (s)", "Negative"], rows),
    ])


def ttl_values(con, f):
    """3d: raw ttl values with their row counts for one month and series (all rows, as in 1b)."""
    if "ttl" not in f["parquet_columns"]:
        return None
    return con.execute(f"SELECT ttl, count(*) FROM {f['source']} GROUP BY 1 ORDER BY 2 DESC, 1").fetchall()


def render_3d(facts, ttls):
    """3d summary: distinct ttl values per month and series."""
    rows = []
    for f in facts:
        values = ttls[(f["month"], f["series"])]
        rows.append([f["month"], f["series"], "no `ttl` column" if values is None else
                     "; ".join(f"`{'(empty)' if v is None else v}` ({fmt(n)} rows)" for v, n in values)])
    return "\n\n".join(["### 3d. `ttl`", "Raw values, all rows.", table(["Month", "Series", "Values"], rows)])


# ---------------------------------------------------------------------------
# 5b–5c. Coverage
# ---------------------------------------------------------------------------

def gap_threshold(snaps):
    """5b threshold: 2 × the month's median interval between consecutive snapshots (3a)."""
    s = snaps["snapshots"]
    intervals = [b[0] - a[0] for a, b in zip(s, s[1:])]
    return 2 * median(intervals) if intervals else None


def gaps(f, snaps):
    """5b: gaps of one month and series as (start, end, kind), in POSIX seconds."""
    times = [lu for lu, _ in snaps["snapshots"]]
    threshold = gap_threshold(snaps)
    if not times or threshold is None:
        return []
    start, end = month_window(f["month"])
    found = []
    if times[0] - start > threshold:
        found.append((start, times[0], "start of month"))
    found += [(a, b, "inside") for a, b in zip(times, times[1:]) if b - a > threshold]
    if end - times[-1] > threshold:
        found.append((times[-1], end, "end of month"))
    return found


def gap_rows(f, found):
    """gaps.csv rows of one month and series."""
    return [[f["month"], f["series"], utc_text(a), utc_text(b), f"{(b - a) / 60:.1f}", kind] for a, b, kind in found]


def render_5b(facts, snaps, all_gaps):
    """5b summary per month and series: threshold, gaps inside, and the start / end of month ranges."""
    rows = []
    for f in facts:
        key = (f["month"], f["series"])
        found = all_gaps[key]
        inside = [b - a for a, b, kind in found if kind == "inside"]
        edge = {kind: (b - a) for a, b, kind in found if kind != "inside"}
        minutes = lambda s: "—" if s is None else f"{s / 60:,.1f}"
        rows.append([f["month"], f["series"], fmt(gap_threshold(snaps[key])), fmt(len(inside)),
                     minutes(sum(inside) if inside else None), minutes(max(inside, default=None)),
                     minutes(edge.get("start of month")), minutes(edge.get("end of month"))])
    return "\n\n".join([
        "### 5b. Gaps inside a month",
        "Gap: interval between consecutive snapshots greater than the threshold (2 × the month's median interval, "
        "3a); also the range from local midnight at the start of the month to the first snapshot, and from the "
        "last snapshot to local midnight at the end of the month, when longer than the threshold. One row per "
        "gap in `gaps.csv`.",
        table(["Month", "Series", "Threshold (s)", "Gaps inside", "Inside total (min)", "Longest inside (min)",
               "Start of month (min)", "End of month (min)"], rows),
    ])


def snapshot_lines(con, f, lu):
    """First and last CSV line and row count of one snapshot (raw rows, all copies)."""
    first, last, n = con.execute(f"""
        SELECT min(file_row_number), max(file_row_number), count(*)
        FROM read_parquet({sql_literal(str(f["path"]))}, file_row_number = true)
        WHERE {typed("last_updated", f["types"]["last_updated"])} = {lu}
    """).fetchone()
    return csv_line(first), csv_line(last), n


def lines_match_parquet(con, f, lines):
    """True when each raw CSV line, parsed as CSV, equals its Parquet row (empty field = Parquet null)."""
    for number, text in lines.items():
        row = con.execute(f"SELECT * EXCLUDE (file_row_number) FROM read_parquet({sql_literal(str(f['path']))}, "
                          f"file_row_number = true) WHERE file_row_number = {number - 2}").fetchone()
        parsed = next(csv.reader([text]))
        if row is None or ["" if v is None else v for v in row] != parsed:
            return False
    return True


def render_5b_example(con, facts, snaps, all_gaps):
    """5b example: the first inside gap, with the snapshot before and after it and their raw lines."""
    for f in facts:
        inside = [(a, b) for a, b, kind in all_gaps[(f["month"], f["series"])] if kind == "inside"]
        if inside:
            break
    else:
        return "## Example — 5b gap\n\nNo gap inside a month."
    a, b = inside[0]
    before, after = snapshot_lines(con, f, a), snapshot_lines(con, f, b)
    numbers = [before[0], before[1], after[0], after[1]]
    lines = raw_lines(archive_path(f["month"], f["series"]), numbers)
    rows = [["Before", utc_text(a), local_text(a), fmt(before[2]), f"{before[0]}–{before[1]}"],
            ["After", utc_text(b), local_text(b), fmt(after[2]), f"{after[0]}–{after[1]}"]]
    raw = [f"line {n}: {lines.get(n, '(not found)')}" for n in numbers]
    threshold = gap_threshold(snaps[(f["month"], f["series"])])
    return "\n\n".join([
        "## Example — 5b gap",
        f"{f['month']} {f['series']} (`{f['archive']}`): the first gap inside a month in `gaps.csv` order. "
        f"Gap of {b - a} s ({(b - a) / 60:.1f} min) against a threshold of {fmt(threshold)} s.",
        table(["Snapshot", "last_updated (UTC)", "last_updated (local)", "Rows", "CSV lines"], rows),
        "Raw CSV lines (first and last line of each snapshot; line 1 = header):",
        "```\n" + "\n".join(raw) + "\n```",
        f"Raw lines equal their Parquet rows: {'yes' if lines_match_parquet(con, f, lines) else '**NO**'}.",
    ])


def render_5c(facts, snaps):
    """5c summary: first and last last_updated per month and series, UTC and local time."""
    rows = []
    for f in facts:
        s = snaps[(f["month"], f["series"])]["snapshots"]
        first, last = s[0][0], s[-1][0]
        rows.append([f["month"], f["series"], utc_text(first), local_text(first), utc_text(last), local_text(last)])
    return "\n\n".join([
        "### 5c. Month cut",
        table(["Month", "Series", "First (UTC)", "First (local)", "Last (UTC)", "Last (local)"], rows),
    ])


# ---------------------------------------------------------------------------
# 2. Relation to the feed
# ---------------------------------------------------------------------------

def archive_field_profile(con, facts, series):
    """2a input, archive side: one profile per column of a series over every month that has it.

    Same definitions as 1b (null = `NA` or empty; distinct values over the raw text, listed with their
    counts when ≤ DISTINCT_LIST_MAX; min/max over the typed view), computed over the union of months so the
    distinct values are those of all months together. Returns {column: profile} in first-appearance order.
    """
    columns = {}
    for f in (f for f in facts if f["series"] == series):
        for column in f["parquet_columns"]:
            columns.setdefault(column, []).append(f)
    profiles = {}
    for column, having in columns.items():
        c = sql_ident(column)
        dtypes = sorted({f["types"].get(column, "VARCHAR") for f in having})
        t = typed(column, dtypes[0]) if len(dtypes) == 1 else c
        source = (f"read_parquet([{', '.join(sql_literal(str(f['path'])) for f in having)}], "
                  f"union_by_name = true)")
        total, nulls, distinct, lo, hi = con.execute(
            f"SELECT count(*), count(*) FILTER ({c} IS NULL OR {c} = '{NULL_TOKEN}'), count(DISTINCT {c}), "
            f"min({t}), max({t}) FROM {source}"
        ).fetchone()
        listed = ""
        if distinct <= DISTINCT_LIST_MAX:
            counts = con.execute(f"SELECT {c}, count(*) FROM {source} WHERE {c} IS NOT NULL "
                                 f"GROUP BY 1 ORDER BY 2 DESC, 1").fetchall()
            listed = json.dumps(dict(counts), ensure_ascii=False)
        profiles[column] = {"months": ";".join(f["month"] for f in having), "type": ";".join(dtypes),
                            "null_pct": pct(nulls, total), "min": "" if lo is None else lo,
                            "max": "" if hi is None else hi, "distinct": distinct, "listed": listed}
    return profiles


def realtime_field_key(path):
    """2a: the name a real-time field path is matched under: station fields lose the data.stations[]. prefix."""
    return path[len(REALTIME_STATION_PREFIX):] if path.startswith(REALTIME_STATION_PREFIX) else path


def field_comparison_rows(con, facts):
    """2a input: field_comparison.csv rows, one per field in the union of archive columns and real-time paths."""
    with open(REALTIME_PROFILE, newline="", encoding="utf-8") as fh:
        realtime = list(csv.DictReader(fh))
    rows = []
    for series, feed in FEED_OF_SERIES.items():
        archive = archive_field_profile(con, facts, series)
        live = {realtime_field_key(r["path"]): r for r in realtime if r["feed"] == feed}
        for field in [*archive, *(k for k in live if k not in archive)]:
            a, r = archive.get(field), live.get(field)
            rows.append([
                series, feed, field,
                *(["", "", "", "", "", "", ""] if a is None else
                  [a["months"], a["type"], a["null_pct"], a["min"], a["max"], a["distinct"], a["listed"]]),
                *(["", "", "", "", "", "", "", ""] if r is None else
                  [r["path"], r["present_pct"], r["types"], r["null_pct"], r["min"], r["max"],
                   r["distinct_count"], r["distinct_values"]]),
            ])
    return rows


def render_2a(rows):
    """2a input summary: fields per series in both sides, archive only and real-time only."""
    counts = []
    for series, feed in FEED_OF_SERIES.items():
        mine = [r for r in rows if r[0] == series]
        both = [r[2] for r in mine if r[3] and r[10]]
        archive_only = [r[2] for r in mine if r[3] and not r[10]]
        live_only = [r[2] for r in mine if not r[3] and r[10]]
        counts.append([series, feed, fmt(len(mine)), fmt(len(both)), fmt(len(archive_only)), fmt(len(live_only)),
                       ", ".join(f"`{x}`" for x in both) or "—"])
    return "\n\n".join([
        "### 2a input. Field comparison",
        f"One row per field in `field_comparison.csv`: the union of archive columns (all months) and the real-time "
        f"field paths of the paired feed, matched literally (real-time station fields without the "
        f"`{REALTIME_STATION_PREFIX}` prefix). Archive side as in 1b, over every month that has the column; "
        f"real-time side copied from `{REALTIME_PROFILE.relative_to(REPO)}`.",
        table(["Series", "Feed", "Fields", "In both", "Archive only", "Real-time only", "Fields in both"], counts),
    ])


# ---------------------------------------------------------------------------
# 6. Identity
# ---------------------------------------------------------------------------

def create_key_tables(con):
    """6b, 8a: empty tables of (month, last_updated, station_id) per series, filled month by month from dedup;
    INFORMACIO also keeps capacity (8a)."""
    con.execute("CREATE OR REPLACE TEMP TABLE keys_ESTACIONS (month VARCHAR, lu BIGINT, station_id BIGINT)")
    con.execute("CREATE OR REPLACE TEMP TABLE keys_INFORMACIO "
                "(month VARCHAR, lu BIGINT, station_id BIGINT, capacity BIGINT)")


def collect_keys(con, f):
    """6b, 8a: append the (snapshot, station) pairs of the month just deduplicated."""
    extra = ", capacity" if f["series"] == "INFORMACIO" else ""
    con.execute(f"INSERT INTO keys_{f['series']} SELECT {sql_literal(f['month'])}, last_updated, station_id{extra} "
                f"FROM dedup WHERE last_updated IS NOT NULL AND station_id IS NOT NULL")


def station_ids(con):
    """6a: distinct station IDs of the month just deduplicated."""
    return {sid for (sid,) in con.execute("SELECT DISTINCT station_id FROM dedup WHERE station_id IS NOT NULL").fetchall()}


def id_list(ids):
    """Station IDs as a sorted comma-separated list, or a dash."""
    return ", ".join(str(i) for i in sorted(ids)) or "—"


def render_6a(facts, ids):
    """6a summary: station IDs per month and series, and IDs added or removed versus the previous month available."""
    rows = []
    for series in SERIES:
        previous = None
        for f in (f for f in facts if f["series"] == series):
            now = ids[(f["month"], series)]
            added = id_list(now - previous) if previous is not None else ""
            removed = id_list(previous - now) if previous is not None else ""
            rows.append([f["month"], series, fmt(len(now)), fmt(min(now, default=None)), fmt(max(now, default=None)),
                         added, removed])
            previous = now
    return "\n\n".join([
        "### 6a. Station set",
        "Distinct `station_id` per month and series, deduplicated view. Added / removed: versus the previous month "
        "available of the same series (the first month has none).",
        table(["Month", "Series", "Stations", "Min ID", "Max ID", "Added", "Removed"], rows),
    ])


def information_match(con):
    """6b: per status snapshot, the as-of information snapshot and the stations in only one of the two.

    The as-of join runs over every month available, so a status snapshot can match an information
    snapshot of an earlier month. Returns per-month counts and per-month IDs with their snapshot counts.
    """
    con.execute("""
        CREATE OR REPLACE TEMP TABLE smap AS
        SELECT s.month, s.lu AS slu, i.lu AS ilu, i.month AS imonth
        FROM (SELECT DISTINCT month, lu FROM keys_ESTACIONS) s
        ASOF LEFT JOIN (SELECT DISTINCT month, lu FROM keys_INFORMACIO) i ON s.lu >= i.lu
    """)
    con.execute("""
        CREATE OR REPLACE TEMP TABLE mismatch AS
        SELECT m.month, m.slu, k.station_id, 'status only' AS side
        FROM keys_ESTACIONS k JOIN smap m ON k.month = m.month AND k.lu = m.slu
        WHERE m.ilu IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM keys_INFORMACIO i WHERE i.lu = m.ilu AND i.station_id = k.station_id)
        UNION ALL
        SELECT m.month, m.slu, i.station_id, 'information only'
        FROM smap m JOIN keys_INFORMACIO i ON i.month = m.imonth AND i.lu = m.ilu
        WHERE NOT EXISTS (
            SELECT 1 FROM keys_ESTACIONS k WHERE k.month = m.month AND k.lu = m.slu AND k.station_id = i.station_id)
    """)
    snapshots = {month: row for month, *row in con.execute("""
        SELECT month, count(*), count(*) FILTER (ilu IS NULL), count(*) FILTER (imonth <> month),
               count(*) FILTER (ilu = slu)
        FROM smap GROUP BY 1
    """).fetchall()}
    sides = {(month, side): row for month, side, *row in con.execute("""
        SELECT month, side, count(*), count(DISTINCT slu), count(DISTINCT station_id) FROM mismatch GROUP BY 1, 2
    """).fetchall()}
    ids = {}
    for month, side, sid, n in con.execute("""
        SELECT month, side, station_id, count(*) FROM mismatch GROUP BY 1, 2, 3 ORDER BY 1, 2, 3
    """).fetchall():
        ids.setdefault((month, side), []).append(f"{sid} ({n})")
    mismatched = dict(con.execute("SELECT month, count(DISTINCT slu) FROM mismatch GROUP BY 1").fetchall())
    return {"snapshots": snapshots, "sides": sides, "ids": ids, "mismatched": mismatched}


def render_6b(result):
    """6b summary: per month, status snapshots matched, and stations with status but no information or the reverse."""
    rows, listed = [], []
    for month in MONTHS:
        if month not in result["snapshots"]:
            continue
        total, without, other_month, same_time = result["snapshots"][month]
        so = result["sides"].get((month, "status only"), (0, 0, 0))
        io = result["sides"].get((month, "information only"), (0, 0, 0))
        rows.append([month, fmt(total), fmt(without), fmt(other_month), fmt(same_time),
                     fmt(result["mismatched"].get(month, 0)), fmt(so[0]), fmt(so[2]), fmt(io[0]), fmt(io[2])])
        for side in ("status only", "information only"):
            if (month, side) in result["ids"]:
                listed.append([month, side, ", ".join(result["ids"][(month, side)])])
    parts = [
        "### 6b. Information ↔ status match",
        "Per `ESTACIONS` snapshot, the latest `INFORMACIO` snapshot at or before it (as-of join over every month "
        "available, so it may belong to an earlier month), both deduplicated. \"Status only\": station in the "
        "status snapshot but not in its information snapshot; \"information only\": the reverse. Pairs = station "
        "× status snapshot.",
        table(["Month", "Status snapshots", "No information at or before", "Information from an earlier month",
               "Information at the same `last_updated`", "Snapshots with a mismatch", "Status only (pairs)",
               "Status only (stations)", "Information only (pairs)", "Information only (stations)"], rows),
        "Station IDs, with the number of status snapshots affected:",
    ]
    parts.append(table(["Month", "Side", "Station IDs (snapshots)"], listed) if listed else "None.")
    return "\n\n".join(parts)


def info_changes(con, f):
    """6c for one month of INFORMACIO: attribute changes between consecutive snapshots of each station, and each
    station's first and last values of the month (for the comparison between months). Deduplicated view."""
    rows = con.execute("""
        WITH x AS (
            SELECT station_id, last_updated, name, lat, lon, capacity,
                   lag(last_updated) OVER w AS plu, lag(name) OVER w AS pname, lag(lat) OVER w AS plat,
                   lag(lon) OVER w AS plon, lag(capacity) OVER w AS pcapacity,
                   row_number() OVER w AS i,
                   row_number() OVER (PARTITION BY station_id ORDER BY last_updated DESC) AS j
            FROM dedup WHERE station_id IS NOT NULL AND last_updated IS NOT NULL
            WINDOW w AS (PARTITION BY station_id ORDER BY last_updated))
        SELECT station_id, last_updated, name, lat, lon, capacity, plu, pname, plat, plon, pcapacity, i, j FROM x
        WHERE i = 1 OR j = 1 OR name IS DISTINCT FROM pname OR lat IS DISTINCT FROM plat
           OR lon IS DISTINCT FROM plon OR capacity IS DISTINCT FROM pcapacity
        ORDER BY station_id, last_updated
    """).fetchall()
    events, first, last = [], {}, {}
    for sid, lu, name, lat, lon, cap, plu, pname, plat, plon, pcap, i, j in rows:
        values = {"name": name, "coordinates": (lat, lon), "capacity": cap, "lu": lu}
        if i == 1:
            first[sid] = values
        if j == 1:
            last[sid] = values
        if i > 1:
            before = {"name": pname, "coordinates": (plat, plon), "capacity": pcap, "lu": plu}
            events += change_events(f["month"], sid, "within month", before, values)
    return {"events": events, "first": first, "last": last}


def change_events(month, sid, kind, before, after):
    """6c: one event per attribute that differs between two value sets of a station."""
    show = lambda v: f"{v[0]}, {v[1]}" if isinstance(v, tuple) else ("" if v is None else str(v))
    return [[month, sid, kind, attribute, show(before[attribute]), show(after[attribute]),
             utc_text(before["lu"]), utc_text(after["lu"])]
            for attribute in INFO_ATTRIBUTES if before[attribute] != after[attribute]]


def attribute_events(per_month):
    """6c: changes within each month and between consecutive months available (last values vs first values)."""
    events, previous = [], None
    for month in MONTHS:
        if month not in per_month:
            continue
        now = per_month[month]
        if previous is not None:
            for sid in sorted(previous["last"].keys() & now["first"].keys()):
                events += change_events(month, sid, "between months", previous["last"][sid], now["first"][sid])
        events += now["events"]
        previous = now
    return events


def station_change_rows(events):
    """station_changes.csv rows, one per change; first seen = the snapshot where the new value appears."""
    rows = [[sid, month, attribute, before, after, seen] for month, sid, _, attribute, before, after, _, seen in events]
    return sorted(rows, key=lambda r: (r[1], r[0], r[5], INFO_ATTRIBUTES.index(r[2])))


def render_6c(events):
    """6c summary: count of changes per month, kind and attribute."""
    counts = {}
    for month, sid, kind, attribute, *_ in events:
        entry = counts.setdefault((month, kind, attribute), [0, set()])
        entry[0] += 1
        entry[1].add(sid)
    rows = [[month, kind, attribute, fmt(n), fmt(len(stations))]
            for (month, kind, attribute), (n, stations) in sorted(counts.items())]
    return "\n\n".join([
        "### 6c. Attribute stability",
        "`INFORMACIO`, deduplicated view. A change: a station's name, coordinates (lat, lon) or `capacity` differs "
        "from its previous snapshot in the month (within month), or its first snapshot of a month differs from its "
        "last snapshot of the previous month available (between months, listed under the later month). One row "
        f"per change in `station_changes.csv` ({fmt(len(events))} rows).",
        table(["Month", "Kind", "Attribute", "Changes", "Stations"], rows) if rows else "No changes.",
    ])


def last_info_snapshot(con):
    """6d: the last snapshot of the INFORMACIO month just deduplicated, by station_id (as text)."""
    rows = con.execute("""
        SELECT station_id, rn, external_id, name, lat, lon, capacity, last_updated FROM dedup
        WHERE last_updated = (SELECT max(last_updated) FROM dedup) AND station_id IS NOT NULL
    """).fetchall()
    return {str(sid): {"rn": rn, "external_id": ext, "name": name, "lat": lat, "lon": lon, "capacity": cap,
                       "last_updated": lu}
            for sid, rn, ext, name, lat, lon, cap, lu in rows}


def realtime_info():
    """6d: the last real-time station_information response of 2026-10-05, by station_id."""
    path = sorted(REALTIME_INFO_DIR.glob("*.json.gz"))[-1]
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        response = json.load(fh)
    return path, response, {s["station_id"]: s for s in response["data"]["stations"]}


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres (haversine, mean Earth radius)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def realtime_names(station):
    """6d: the distinct texts of a real-time station's multilingual name."""
    return sorted({n["text"] for n in station.get("name", [])})


def station_match_rows(archive, live):
    """6d: station_match.csv rows, one per station ID in either side, sorted numerically where possible."""
    def order(sid):
        return (0, int(sid), "") if sid.isdigit() else (1, 0, sid)

    rows = []
    for sid in sorted(archive.keys() | live.keys(), key=order):
        a, r = archive.get(sid), live.get(sid)
        names = realtime_names(r) if r else []
        distance = (haversine_m(a["lat"], a["lon"], r["lat"], r["lon"])
                    if a and r and None not in (a["lat"], a["lon"], r.get("lat"), r.get("lon")) else None)
        both = a is not None and r is not None
        rows.append([
            sid, "yes" if a else "no", "yes" if r else "no",
            a["external_id"] if a else "", r.get("external_id", "") if r else "",
            ("yes" if a["external_id"] == r.get("external_id") else "no") if both else "",
            a["name"] if a else "", " | ".join(names),
            ("yes" if names == [a["name"]] else "no") if both else "",
            a["lat"] if a else "", a["lon"] if a else "", r.get("lat", "") if r else "", r.get("lon", "") if r else "",
            "" if distance is None else f"{distance:.1f}",
            a["capacity"] if a else "", r.get("capacity", "") if r else "",
            ("yes" if a["capacity"] == r.get("capacity") else "no") if both else "",
        ])
    return rows


def render_6d(rows, archive_lu, path, multilingual):
    """6d summary: IDs in both or one side, and for shared IDs the attribute comparisons."""
    both = [r for r in rows if r[1] == "yes" and r[2] == "yes"]
    only_a = [r[0] for r in rows if r[1] == "yes" and r[2] == "no"]
    only_r = [r[0] for r in rows if r[1] == "no" and r[2] == "yes"]
    distances = [float(r[13]) for r in both if r[13]]
    far = [[r[0], r[6], f"{r[9]}, {r[10]}", f"{r[11]}, {r[12]}", r[13]] for r in both
           if r[13] and float(r[13]) > MATCH_DISTANCE_M]
    differ = lambda i: [r[0] for r in both if r[i] == "no"]
    summary = [
        ["Station IDs in the archive", fmt(len(both) + len(only_a))],
        ["Station IDs in real time", fmt(len(both) + len(only_r))],
        ["In both", fmt(len(both))],
        ["Archive only", f"{fmt(len(only_a))}: {', '.join(only_a) or '—'}"],
        ["Real-time only", f"{fmt(len(only_r))}: {', '.join(only_r) or '—'}"],
        ["Shared: different `external_id`", f"{fmt(len(differ(5)))}: {', '.join(differ(5)) or '—'}"],
        ["Shared: different name", f"{fmt(len(differ(8)))}: {', '.join(differ(8)) or '—'}"],
        ["Shared: different `capacity`", f"{fmt(len(differ(16)))}: {', '.join(differ(16)) or '—'}"],
        ["Shared: distance median / p95 / max (m)",
         f"{median(distances) or 0:.1f} / {p95(distances) or 0:.1f} / {max(distances, default=0):.1f}"],
        [f"Shared: distance > {MATCH_DISTANCE_M} m", fmt(len(far))],
        ["Real-time stations whose name differs between languages", fmt(multilingual)],
    ]
    parts = [
        "### 6d. Match with the real-time feed",
        f"Last `INFORMACIO` snapshot of {MATCH_MONTH} (`last_updated` {utc_text(archive_lu)}, deduplicated view) "
        f"against the real-time response `{path.relative_to(REPO)}`. IDs compared as text. Same name: the archive "
        "name equals the text of every language of the real-time name. Distance: haversine, mean Earth radius "
        f"{EARTH_RADIUS_M:,.1f} m. One row per station ID in `station_match.csv`.",
        table(["Measure", "Value"], summary),
    ]
    if far:
        parts += [f"Shared stations more than {MATCH_DISTANCE_M} m apart:",
                  table(["Station", "Archive name", "Archive lat, lon", "Real-time lat, lon", "Distance (m)"], far)]
    return "\n\n".join(parts)


def render_6d_example(con, f, archive, response, live, path):
    """6d example: the lowest shared station_id, archive and real-time values side by side, with raw sources."""
    shared = sorted((archive.keys() & live.keys()), key=lambda s: (not s.isdigit(), int(s) if s.isdigit() else 0, s))
    if not shared:
        return "## Example — 6d station match\n\nNo station in both sides."
    sid = shared[0]
    a, r = archive[sid], live[sid]
    line = csv_line(a["rn"])
    lines = raw_lines(archive_path(f["month"], f["series"]), [line])
    distance = haversine_m(a["lat"], a["lon"], r["lat"], r["lon"])
    rows = [
        ["station_id", sid, r["station_id"]],
        ["external_id", a["external_id"], r.get("external_id", "")],
        ["name", a["name"], " | ".join(realtime_names(r))],
        ["lat", a["lat"], r.get("lat", "")],
        ["lon", a["lon"], r.get("lon", "")],
        ["capacity", a["capacity"], r.get("capacity", "")],
        ["last_updated (UTC)", utc_text(a["last_updated"]), response.get("last_updated", "")],
    ]
    return "\n\n".join([
        "## Example — 6d station match",
        f"Station {sid}: the lowest station_id in both sides. Archive: {f['month']} {f['series']} "
        f"(`{f['archive']}`), last snapshot, deduplicated view. Real time: `{path.relative_to(REPO)}`.",
        table(["Field", "Archive", "Real time"], rows),
        f"Distance: {distance:.1f} m.",
        "Raw archive CSV line (line 1 = header):",
        f"```\nline {line}: {lines.get(line, '(not found)')}\n```",
        f"Raw line equals its Parquet row: {'yes' if lines_match_parquet(con, f, lines) else '**NO**'}.",
        "Real-time station object:",
        "```json\n" + json.dumps(r, ensure_ascii=False) + "\n```",
    ])


# ---------------------------------------------------------------------------
# 8. Quality
# ---------------------------------------------------------------------------

def is_true(column):
    """SQL: a boolean column of the deduplicated view as true / false / null (1/0 and TRUE/FALSE alike)."""
    return f"TRY_CAST({sql_ident(column)} AS BOOLEAN)"


def quality_specs():
    """8: one spec per check variant, in summary order.

    Each spec: check, variant, source (status / information / duplicates), SQL condition over the source,
    detail columns (values of the first occurrence), and whether it is counted apart from the check's line.
    """
    bikes, docks = sql_ident("num_bikes_available"), sql_ident("num_docks_available")
    mech, ebike = sql_ident("num_bikes_available_types.mechanical"), sql_ident("num_bikes_available_types.ebike")
    counts = ["num_bikes_available", "num_docks_available", "capacity"]
    breakdown = ["num_bikes_available", "num_bikes_available_types.mechanical", "num_bikes_available_types.ebike"]
    flags = ["is_installed", "is_renting", "is_returning", "status"]
    stamps = ["last_reported", "last_updated"]
    dups = ["raw_rows", "exact_copies", "first_csv_line", "last_reported_values"]
    specs = [
        ("8a", "over capacity", "status", f"{bikes} + {docks} > capacity", counts, False),
        ("8a", "no capacity", "status", "capacity IS NULL", counts, True),
        *[("8b", f"{c} < 0", "status", f"{sql_ident(c)} < 0", COUNT_COLUMNS, False) for c in COUNT_COLUMNS],
        ("8c", "mismatch", "status", f"{mech} + {ebike} <> {bikes}", breakdown, False),
        ("8c", "null breakdown", "status", f"{mech} IS NULL OR {ebike} IS NULL", breakdown, True),
        ("8d", "stale", "status", f"{is_true('is_installed')} AND last_updated - last_reported > 86400",
         ["is_installed", *stamps], False),
        ("8e", "future", "status", "last_reported > last_updated + 60", stamps, False),
        *[("8f", f"{c} false", "status", f"{is_true(c)} = false", flags, False)
          for c in ["is_installed", "is_renting", "is_returning"]],
        ("8f", "status other than IN_SERVICE", "status", "status IS DISTINCT FROM 'IN_SERVICE'", flags, False),
        ("8g", "exact duplicate", "duplicates", "exact_copies > 0", dups, False),
        ("8g", "latest kept", "duplicates", "resolved", dups, False),
        ("8g", "tie", "duplicates", "tied", dups, False),
        ("8h", "out of area", "information", "NOT (lat BETWEEN 41.20 AND 41.60 AND lon BETWEEN 1.85 AND 2.35)",
         ["name", "lat", "lon"], False),
        ("8j", "is_renting false, no bikes", "status", f"{is_true('is_renting')} = false AND {bikes} = 0",
         ["is_renting", "num_bikes_available", "status"], False),
        ("8j", "is_renting false, bikes > 0", "status", f"{is_true('is_renting')} = false AND {bikes} > 0",
         ["is_renting", "num_bikes_available", "status"], False),
        ("8j", "is_returning false, no docks", "status", f"{is_true('is_returning')} = false AND {docks} = 0",
         ["is_returning", "num_docks_available", "status"], False),
        ("8j", "is_returning false, docks > 0", "status", f"{is_true('is_returning')} = false AND {docks} > 0",
         ["is_returning", "num_docks_available", "status"], False),
        ("8j", "no bikes, is_renting true", "status", f"{bikes} = 0 AND {is_true('is_renting')}",
         ["is_renting", "num_bikes_available", "status"], False),
    ]
    return [dict(zip(["check", "variant", "source", "condition", "detail", "apart"], s)) for s in specs]


def build_quality_sources(con, f, with_capacity):
    """8: temp tables of the month just deduplicated that the checks read; returns {source: (table, weight, rows)}.

    status: ESTACIONS deduplicated rows, plus capacity from the as-of INFORMACIO snapshot (as in 6b) when 8a
    runs. information: INFORMACIO deduplicated rows. duplicates: (snapshot, station) pairs with more than one
    raw row, from `staged` (weight = raw rows of the pair; rows checked = Parquet rows).
    """
    con.execute("""
        CREATE OR REPLACE TEMP TABLE dup_groups AS
        SELECT last_updated, station_id, count(*) AS raw_rows, count(*) FILTER (fate = 'exact') AS exact_copies,
               bool_or(fate IN ('latest', 'older')) AS resolved, bool_or(fate = 'tie') AS tied,
               min(rn) + 2 AS first_csv_line,
               string_agg(CAST(last_reported AS VARCHAR), ',' ORDER BY rn) AS last_reported_values
        FROM staged WHERE station_id IS NOT NULL AND last_updated IS NOT NULL
        GROUP BY 1, 2 HAVING count(*) > 1
    """)
    sources = {"duplicates": ("dup_groups", "raw_rows", f["parquet_rows"])}
    if f["series"] == "ESTACIONS":
        if with_capacity:
            con.execute("""
                CREATE OR REPLACE TEMP TABLE status_q AS
                WITH s AS (SELECT DISTINCT last_updated AS slu FROM dedup WHERE last_updated IS NOT NULL),
                m AS (SELECT s.slu, i.lu AS ilu FROM s
                      ASOF LEFT JOIN (SELECT DISTINCT lu FROM keys_INFORMACIO) i ON s.slu >= i.lu)
                SELECT d.*, c.capacity FROM dedup d
                LEFT JOIN m ON d.last_updated = m.slu
                LEFT JOIN keys_INFORMACIO c ON c.lu = m.ilu AND c.station_id = d.station_id
            """)
        else:
            con.execute("CREATE OR REPLACE TEMP TABLE status_q AS SELECT *, NULL::BIGINT AS capacity FROM dedup")
        sources["status"] = ("status_q", "1", con.execute("SELECT count(*) FROM status_q").fetchone()[0])
    else:
        sources["information"] = ("dedup", "1", con.execute("SELECT count(*) FROM dedup").fetchone()[0])
    return sources


def detail_sql(columns):
    """SQL: 'column=value; ...' of the given columns, null shown as null."""
    return "concat_ws('; ', " + ", ".join(
        f"'{c}=' || coalesce(CAST({sql_ident(c)} AS VARCHAR), 'null')" for c in columns) + ")"


def measure(con, table_name, weight, condition):
    """8: affected rows (weighted), snapshots and station IDs of the rows meeting a condition."""
    rows, snapshots, stations = con.execute(
        f"SELECT coalesce(sum({weight}), 0), count(DISTINCT last_updated), list(DISTINCT station_id) "
        f"FROM {table_name} WHERE ({condition}) AND station_id IS NOT NULL"
    ).fetchone()
    return {"rows": rows, "snapshots": snapshots, "stations": set(stations or [])}


def quality_month(con, f, checks, sources):
    """8 for one month and series: per-variant and per-check measures, and the cases of quality_cases.csv."""
    measures, cases = [], []
    specs = [s for s in quality_specs() if s["check"] in checks and s["source"] in sources]
    for s in specs:
        table_name, weight, checked = sources[s["source"]]
        m = measure(con, table_name, weight, s["condition"])
        measures.append({**m, "check": s["check"], "variant": s["variant"], "month": f["month"],
                         "series": f["series"], "checked": checked, "apart": s["apart"]})
        for sid, n, first, last, detail in con.execute(f"""
            SELECT station_id, count(DISTINCT last_updated), min(last_updated), max(last_updated),
                   arg_min({detail_sql(s["detail"])}, last_updated)
            FROM {table_name} WHERE ({s["condition"]}) AND station_id IS NOT NULL GROUP BY 1 ORDER BY 1
        """).fetchall():
            cases.append([s["check"], s["variant"], f["month"], f["series"], sid, detail, n,
                          utc_text(first), utc_text(last)])
    for check in dict.fromkeys(s["check"] for s in specs):
        line = [s for s in specs if s["check"] == check and not s["apart"]]
        table_name, weight, checked = sources[line[0]["source"]]
        m = measure(con, table_name, weight, " OR ".join(f"({s['condition']})" for s in line))
        measures.append({**m, "check": check, "variant": None, "month": f["month"], "series": f["series"],
                         "checked": checked, "apart": False})
    return measures, cases


def render_quality(check, measures):
    """8: one summary block per check: its one line (totals over months and series), then each variant per month."""
    title, series, definition = QUALITY_CHECKS[check]
    if check == "8i":
        return f"### 8i. {title}\n\n**8i. {title}:** none listed for 2026."
    mine = [m for m in measures if m["check"] == check]
    line = [m for m in mine if m["variant"] is None]
    rows, checked = sum(m["rows"] for m in line), sum(m["checked"] for m in line)
    stations = set().union(*(m["stations"] for m in line))
    parts = [
        f"### {check}. {title}",
        f"Series: {series}. {definition} Deduplicated view unless stated; % of rows checked.",
        f"**{check}. {title}:** {fmt(rows)} affected rows of {fmt(checked)} checked ({pct(rows, checked)} %), "
        f"{fmt(sum(m['snapshots'] for m in line))} snapshots, {fmt(len(stations))} stations"
        " (variants counted apart excluded; snapshots summed over months and series).",
    ]
    order = {s["variant"]: i for i, s in enumerate(quality_specs()) if s["check"] == check}
    by_variant = sorted((m for m in mine if m["variant"] is not None),
                        key=lambda m: (order[m["variant"]], m["series"], m["month"]))
    variants = [[m["variant"] + (" (counted apart)" if m["apart"] else ""), m["series"], m["month"],
                 fmt(m["checked"]), fmt(m["rows"]), pct(m["rows"], m["checked"]), fmt(m["snapshots"]),
                 fmt(len(m["stations"]))] for m in by_variant]
    parts.append(table(["Variant", "Series", "Month", "Rows checked", "Affected rows", "%", "Snapshots",
                        "Stations"], variants))
    return "\n\n".join(parts)


def write_cases(path, cases, checks, full):
    """quality_cases.csv: a full run writes every case; --only replaces the cases of the checks run."""
    order = {(s["check"], s["variant"]): i for i, s in enumerate(quality_specs())}
    if not full and path.exists():
        with open(path, newline="", encoding="utf-8") as fh:
            kept = [row for row in list(csv.reader(fh))[1:] if row[0] not in checks]
        cases = kept + cases
    write_csv(path, CASES_HEADER, sorted(cases, key=lambda r: (order[(r[0], r[1])], r[2], r[3], int(r[4]))))


# ---------------------------------------------------------------------------
# 7. Volume and load reconciliation
# ---------------------------------------------------------------------------

def render_load(facts):
    """Verification › reconciliation: CSV data rows vs Parquet rows, and no CSV left in work/."""
    rows = [[f["month"], f["series"], f["parquet"], f"{f['csv_rows']:,}", f"{f['parquet_rows']:,}",
             "yes" if f["csv_rows"] == f["parquet_rows"] else "**NO**"] for f in facts]
    matches = sum(f["csv_rows"] == f["parquet_rows"] for f in facts)
    leftover = sorted(p.name for p in WORK_DIR.glob("*.csv"))
    return "\n\n".join([
        "## Reconciliation — load",
        "CSV data rows counted by line count (lines − header); Parquet rows by `count(*)` on the Parquet file.",
        table(["Month", "Series", "Parquet file", "CSV rows", "Parquet rows", "Match"], rows),
        f"Parquet files: {len(facts)}. CSV rows = Parquet rows: {matches} of {len(facts)}.",
        f"CSV files left in `work/`: {len(leftover)}" + (f" ({', '.join(leftover)})" if leftover else "") + ".",
    ])


def render_7a(facts):
    """7a. Size per month: .7z bytes, CSV bytes, data rows per month and series."""
    rows = [[f["month"], f["series"], f"{f['archive_bytes']:,}", f"{f['csv_bytes']:,}", f"{f['csv_rows']:,}"]
            for f in facts]
    return "\n\n".join([
        "### 7a. Size per month",
        table(["Month", "Series", ".7z bytes", "CSV bytes", "Data rows"], rows),
    ])


def render_7b(facts, snaps):
    """7b. Size per snapshot: CSV bytes ÷ snapshots per month, its median per series, and Parquet bytes."""
    rows, per_series = [], {series: [] for series in SERIES}
    for f in facts:
        count = len(snaps[(f["month"], f["series"])]["snapshots"])
        per_snapshot = f["csv_bytes"] / count if count else None
        if per_snapshot is not None:
            per_series[f["series"]].append(per_snapshot)
        rows.append([f["month"], f["series"], fmt(count), fmt(per_snapshot), f"{f['parquet_bytes']:,}"])
    medians = [[series, fmt(median(values))] for series, values in per_series.items()]
    return "\n\n".join([
        "### 7b. Size per snapshot",
        table(["Month", "Series", "Snapshots", "CSV bytes per snapshot", "Parquet bytes"], rows),
        "Median across months of CSV bytes per snapshot:",
        table(["Series", "Median CSV bytes per snapshot"], medians),
    ])


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def wrap_block(block_id, text):
    """Wrap a block's text in the BEGIN/END markers that --only uses to find it."""
    return f"<!-- BEGIN metric:{block_id} -->\n{text}\n<!-- END metric:{block_id} -->"


def implementation_notes():
    """Versions, approved deviations and conventions, so the evidence can be reproduced."""
    tar = subprocess.run(["tar", "--version"], check=True, capture_output=True, text=True).stdout.strip()
    return "\n".join([
        "## Implementation notes",
        "",
        f"- Python {sys.version.split()[0]}, duckdb {duckdb.__version__}.",
        f"- Extraction: macOS built-in tar ({tar}) instead of 7z, approved by the owner on 2026-10-08.",
        "- Parquet: every CSV column stored as text (Common settings › Reading), DuckDB's default Parquet "
        "settings; CSV bytes, data rows, header line and inferred types stored in the Parquet key-value metadata.",
        "- Inferred type (1b, 1c): DuckDB's CSV sniffer over every row of the CSV (`sample_size = -1`), with "
        "`NA` and empty as null.",
        "- Typed view: `NA` and empty → null, then `TRY_CAST` to the inferred type.",
        "- 2a input: archive side recomputed from the Parquet files with the 1b definitions, over the union of "
        "months that have the column (so distinct values cover all months); real-time side copied from the "
        "real-time `field_profile.csv`. Fields matched by literal name once real-time station fields lose the "
        f"`{REALTIME_STATION_PREFIX}` prefix.",
        "- 6b: the as-of join runs over every month available, not only the status snapshot's month.",
        "- 6d: station IDs compared as text (the archive's are integers, the feed's strings).",
        "- 8: booleans read with `TRY_CAST(... AS BOOLEAN)` on the typed view (1/0 and TRUE/FALSE alike); 8a "
        "capacity from the as-of `INFORMACIO` snapshot over every month, as in 6b; a quality case is one "
        "station in one month for one check variant.",
        "- Duplicates (3a rows per snapshot, 3b, 3c, 6a–6d, 8): exact duplicates compared over every raw column, keeping the first in CSV order; "
        "CSV line numbers come from the Parquet row number (Parquet keeps the CSV row order; line 1 = header), "
        "and each example checks its raw lines against the Parquet rows.",
        "- 3b counts (as in the real-time plan, every numeric station field except `last_reported`): "
        + ", ".join(f"`{c}`" for c in COUNT_COLUMNS) + "; comparisons across a 5b gap (snapshots further apart "
        "than 2 × the month's median interval) left out and counted apart.",
        "- 6c: `station_changes.csv` `first_seen_utc` is the snapshot where the new value first appears; within "
        "and between months are told apart in the summary counts only.",
        "- Median and p95: median as Python `statistics.median` (mean of the two middle values for an even "
        "count); p95 by the nearest-rank method.",
    ])


def render_summary(blocks):
    """Whole summary.md for a full run."""
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts = [
        "# Bicing historical data — analysis summary (T005)",
        f"Generated {now} by `spikes/bicing-historical-analysis/analyse_bicing_historical.py`. "
        "Plan: `docs/spikes/s004-bicing-historical-data.md` › Analysis plan.",
    ]
    parts += [wrap_block(block_id, blocks[block_id]) for block_id in BLOCK_ORDER if block_id in blocks]
    parts.append(implementation_notes())
    return "\n\n".join(parts) + "\n"


def update_summary(path, blocks):
    """--only: replace the marked blocks that were run; leave every other byte of summary.md as it is.

    A block not yet in the file is inserted after the nearest preceding block in BLOCK_ORDER.
    """
    text = path.read_text(encoding="utf-8")
    for block_id in BLOCK_ORDER:
        if block_id not in blocks:
            continue
        new = wrap_block(block_id, blocks[block_id])
        tag = re.escape(f"metric:{block_id} -->")
        pattern = re.compile(rf"<!-- BEGIN {tag}\n.*?\n<!-- END {tag}", re.S)
        if pattern.search(text):
            text = pattern.sub(lambda _: new, text, count=1)
            continue
        anchor = next((f"<!-- END metric:{p} -->" for p in reversed(BLOCK_ORDER[:BLOCK_ORDER.index(block_id)])
                       if f"<!-- END metric:{p} -->" in text), None)
        if anchor is None:
            sys.exit(f"{path}: no block to insert {block_id} after; run without --only first")
        i = text.index(anchor) + len(anchor)
        text = text[:i] + "\n\n" + new + text[i:]
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_only(parser, args):
    """Validate --only before anything runs; return the set of metric ids to run."""
    if args.only is None:
        return set(METRICS)
    metrics = {m.strip() for m in args.only.split(",") if m.strip()}
    unknown = sorted(metrics - set(METRICS))
    if unknown or not metrics:
        parser.error(f"--only: unknown metric ids {unknown}; implemented: {', '.join(METRICS)}")
    path = OUT_DIR / "summary.md"
    if not path.exists():
        parser.error(f"--only: {path.relative_to(REPO)} does not exist; run without --only first")
    return metrics


def main():
    """Parse arguments, load or read the archives, run the metrics and write the evidence."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", metavar="IDS",
                        help="comma-separated metric ids to run (e.g. 1b,3a); reuses work/ and keeps other sections")
    args = parser.parse_args()
    metrics = parse_only(parser, args)
    full = args.only is None
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    facts = []
    for month in MONTHS:
        for series in SERIES:
            if full:
                print(f"Loading {month} {series}...", flush=True)
                facts.append(load_month(con, month, series))
            else:
                facts.append(read_facts(con, month, series))

    blocks = {}
    if full:
        blocks["load"] = render_load(facts)
    if {"1a", "1c"} & metrics:
        check_rows = header_check_rows(facts)
        write_csv(OUT_DIR / "header_check.csv", HEADER_CHECK_HEADER, check_rows)
        if "1a" in metrics:
            blocks["1a"] = render_1a(facts, check_rows)
        if "1c" in metrics:
            blocks["1c"] = render_1c(check_rows)
    if "1b" in metrics:
        profile = []
        for f in facts:
            print(f"Profiling {f['month']} {f['series']}...", flush=True)
            profile += profile_rows(con, f)
        write_csv(OUT_DIR / "field_profile.csv", PROFILE_HEADER, profile)
        blocks["1b"] = render_1b(profile)
    snaps = None
    if {"3a", "7b", "3b", "5b", "5c"} & metrics:
        snaps = {(f["month"], f["series"]): snapshots(con, f) for f in facts}
        if "7b" in metrics:
            blocks["7b"] = render_7b(facts, snaps)
    if "2a" in metrics:
        print("Comparing fields...", flush=True)
        comparison = field_comparison_rows(con, facts)
        write_csv(OUT_DIR / "field_comparison.csv", COMPARISON_HEADER, comparison)
        blocks["2a"] = render_2a(comparison)
    if DEDUP_METRICS & metrics:
        drops, kept, reporting, histograms, example = {}, {}, {}, {}, None
        ids, changes, match_info = {}, {}, None
        checks = set(QUALITY_CHECKS) & metrics
        quality, cases = [], []
        if {"6b", "8a"} & metrics:
            create_key_tables(con)
        # INFORMACIO first: 8a reads the as-of capacity of every information month while checking status.
        for f in sorted(facts, key=lambda f: f["series"] != "INFORMACIO"):
            print(f"Deduplicating {f['month']} {f['series']}...", flush=True)
            drops[(f["month"], f["series"])] = build_dedup(con, f)
            if "3a" in metrics:
                kept[(f["month"], f["series"])] = dedup_snapshot_counts(con)
            if "6a" in metrics:
                ids[(f["month"], f["series"])] = station_ids(con)
            if "6b" in metrics or ("8a" in metrics and f["series"] == "INFORMACIO"):
                collect_keys(con, f)
            if checks:
                measures, found = quality_month(con, f, checks, build_quality_sources(con, f, "8a" in metrics))
                quality += measures
                cases += found
            if f["series"] == "INFORMACIO":
                if "6c" in metrics:
                    changes[f["month"]] = info_changes(con, f)
                if "6d" in metrics and f["month"] == MATCH_MONTH:
                    match_info = (last_info_snapshot(con), f)
                continue
            if "3b" in metrics:
                threshold = gap_threshold(snaps[(f["month"], f["series"])])
                reporting[f["month"]] = station_reporting(con, threshold)
                if example is None:
                    example = (reporting_example(con, f, threshold), f)
            if "3c" in metrics:
                histograms[f["month"]] = lag_histogram(con)
        blocks["dedup.check"] = render_dedup_check(facts, drops)
        if "3a" in metrics:
            write_csv(OUT_DIR / "snapshots.csv", SNAPSHOTS_HEADER,
                      [row for f in facts for row in snapshot_rows(f, snaps[(f["month"], f["series"])],
                                                                    kept[(f["month"], f["series"])])])
            blocks["3a"] = render_3a(facts, snaps, kept)
            blocks["3a.check"] = render_3a_check(facts, snaps, kept, drops)
        if "3b" in metrics:
            write_csv(OUT_DIR / "station_reporting.csv", REPORTING_HEADER,
                      [[row[0], month, *(fmt_plain(v) for v in row[1:])]
                       for month, r in reporting.items() for row in r["rows"]])
            blocks["3b"] = render_3b(reporting)
            found, f = example
            if found is None:
                blocks["3b.example"] = "## Example — 3b station reporting interval\n\nNo station qualifies."
            else:
                lines = raw_lines(archive_path(f["month"], f["series"]), [csv_line(r[0]) for r in found["rows"]])
                blocks["3b.example"] = render_3b_example(con, found, f, lines)
        if "3c" in metrics:
            blocks["3c"] = render_3c(histograms)
        if "6a" in metrics:
            blocks["6a"] = render_6a(facts, ids)
        if "6b" in metrics:
            blocks["6b"] = render_6b(information_match(con))
        if "6c" in metrics:
            events = attribute_events(changes)
            write_csv(OUT_DIR / "station_changes.csv", CHANGES_HEADER, station_change_rows(events))
            blocks["6c"] = render_6c(events)
        if "6d" in metrics:
            archive, f = match_info
            path, response, live = realtime_info()
            match = station_match_rows(archive, live)
            write_csv(OUT_DIR / "station_match.csv", MATCH_HEADER, match)
            multilingual = sum(1 for s in live.values() if len(realtime_names(s)) > 1)
            archive_lu = next(iter(archive.values()))["last_updated"]
            blocks["6d"] = render_6d(match, archive_lu, path, multilingual)
            blocks["6d.example"] = render_6d_example(con, f, archive, response, live, path)
        if checks:
            for check in checks:
                blocks[check] = render_quality(check, quality)
            write_cases(OUT_DIR / "quality_cases.csv", cases, checks, full)
    if "3d" in metrics:
        blocks["3d"] = render_3d(facts, {(f["month"], f["series"]): ttl_values(con, f) for f in facts})
    if {"5b", "5c"} & metrics:
        if "5b" in metrics:
            all_gaps = {(f["month"], f["series"]): gaps(f, snaps[(f["month"], f["series"])]) for f in facts}
            write_csv(OUT_DIR / "gaps.csv", GAPS_HEADER,
                      [row for f in facts for row in gap_rows(f, all_gaps[(f["month"], f["series"])])])
            blocks["5b"] = render_5b(facts, snaps, all_gaps)
            blocks["5b.example"] = render_5b_example(con, facts, snaps, all_gaps)
        if "5c" in metrics:
            blocks["5c"] = render_5c(facts, snaps)
    if "7a" in metrics:
        blocks["7a"] = render_7a(facts)

    path = OUT_DIR / "summary.md"
    if full:
        path.write_text(render_summary(blocks), encoding="utf-8")
    else:
        update_summary(path, blocks)
    print(f"wrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
