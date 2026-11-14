# Convert Bicing's monthly history archives (Open Data BCN, .7z with one CSV each) to Parquet, one month at a time.
# Input: the folder holding the archives, given as the only argument; they are read in place, never copied or modified.
# Output, in this check's folder:
#   work/<archive stem>.parquet  every column as text, so raw representations survive (ignored by Git);
#   work/<archive stem>.json     the archive's facts: name, bytes, CSV name and bytes, header line;
#   archives.csv                 one row per archive with those facts;
#   headers.csv                  one row per archive and column, with its position in the header.
# Only one CSV (about 1 GB) is on disk at a time: it is extracted, converted and deleted before the next.
# An archive whose Parquet and JSON already exist is skipped, so an interrupted run resumes.
# Needs the DuckDB CLI on PATH; extraction uses the macOS built-in tar (bsdtar), which reads .7z.

import csv
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
MONTHS = ["2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
          "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]  # November 2025 is not published
SERIES = ["ESTACIONS", "INFORMACIO"]
MEMORY_LIMIT = "2GB"


def sql_literal(text):
    return "'" + text.replace("'", "''") + "'"


def archive_path(raw, month, series):
    year, mm = month.split("-")
    matches = sorted(raw.glob(f"{year}_{mm}_*_BicingNou_{series}.7z"))
    if len(matches) != 1:
        sys.exit(f"{month} {series}: expected one archive in {raw}, found {len(matches)}")
    return matches[0]


def csv_entry(archive):
    listing = subprocess.run(["tar", "-tf", str(archive)], check=True, capture_output=True, text=True)
    entries = [line for line in listing.stdout.splitlines() if line]
    if len(entries) != 1 or not entries[0].endswith(".csv"):
        sys.exit(f"{archive.name}: expected one CSV entry, found {entries}")
    return entries[0]


def header_line(path):
    with open(path, "rb") as fh:
        return fh.readline().decode("utf-8").rstrip("\r\n")


def convert(archive):
    target = WORK / f"{archive.stem}.parquet"
    facts_path = WORK / f"{archive.stem}.json"
    if target.is_file() and facts_path.is_file():
        print(f"  {archive.name}: already converted, skipped")
        return
    entry = csv_entry(archive)
    csv_path = WORK / entry
    partial = WORK / f"{archive.stem}.parquet.partial"
    try:
        subprocess.run(["tar", "-xf", str(archive), "-C", str(WORK)], check=True)
        if not csv_path.is_file():
            sys.exit(f"{archive.name}: tar did not produce {entry}")
        facts = {
            "archive": archive.name,
            "archive_bytes": archive.stat().st_size,
            "csv_name": entry,
            "csv_bytes": csv_path.stat().st_size,
            "header_line": header_line(csv_path),
        }
        # DuckDB reads the CSV in chunks; the memory limit and temp directory bound its footprint.
        sql = (
            f"SET memory_limit = {sql_literal(MEMORY_LIMIT)}; "
            f"SET temp_directory = {sql_literal(str(WORK / 'tmp'))}; "
            f"COPY (SELECT * FROM read_csv({sql_literal(str(csv_path))}, header = true, delim = ',', "
            f"quote = '\"', all_varchar = true)) "
            f"TO {sql_literal(str(partial))} (FORMAT parquet, COMPRESSION zstd);"
        )
        subprocess.run(["duckdb", "-c", sql], check=True)
        partial.replace(target)
        facts_path.write_text(json.dumps(facts, indent=2) + "\n")
    finally:
        csv_path.unlink(missing_ok=True)
        partial.unlink(missing_ok=True)


def write_outputs(archives):
    facts = [(month, series, json.loads((WORK / f"{a.stem}.json").read_text())) for month, series, a in archives]
    with open(HERE / "archives.csv", "w", newline="") as fh:
        out = csv.writer(fh)
        out.writerow(["month", "series", "archive", "archive_bytes", "csv_name", "csv_bytes", "columns"])
        for month, series, f in facts:
            columns = len(next(csv.reader([f["header_line"]])))
            out.writerow([month, series, f["archive"], f["archive_bytes"], f["csv_name"], f["csv_bytes"], columns])
    with open(HERE / "headers.csv", "w", newline="") as fh:
        out = csv.writer(fh)
        out.writerow(["month", "series", "position", "column"])
        for month, series, f in facts:
            for position, column in enumerate(next(csv.reader([f["header_line"]])), start=1):
                out.writerow([month, series, position, column])


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: convert.py <folder with the .7z archives>")
    raw = Path(sys.argv[1]).resolve()
    WORK.mkdir(exist_ok=True)
    start = time.monotonic()
    archives = [(m, s, archive_path(raw, m, s)) for m in MONTHS for s in SERIES]  # fail before any work
    for i, (month, series, archive) in enumerate(archives, start=1):
        t = time.monotonic()
        print(f"[{i}/{len(archives)}] {month} {series}")
        convert(archive)
        print(f"  done in {time.monotonic() - t:.0f} s")
    write_outputs(archives)
    print(f"Total: {time.monotonic() - start:.0f} s")


if __name__ == "__main__":
    main()
