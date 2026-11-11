"""Count how often each station status flag is false, per source.

Input: the spike's raw folder (argv[1]), with <source>/station_status/<date>/<ts>.json.gz.
Output: on stdout, per source and flag (is_installed, is_renting, is_returning): the
values seen with their row counts (missing fields included), and how many stations
were ever false; how is_renting behaves on empty stations and is_returning on full
ones; and how many rows have is_renting and is_returning disagree.
"""
import collections
import gzip
import json
import pathlib
import sys
import time

FLAGS = ("is_installed", "is_renting", "is_returning")

start = time.time()
root = pathlib.Path(sys.argv[1])

for source_dir in sorted(p for p in root.iterdir() if p.is_dir()):
    files = sorted((source_dir / "station_status").glob("*/*.json.gz"))
    print(f"\n{source_dir.name}: {len(files)} passes", flush=True)
    values = {flag: collections.Counter() for flag in FLAGS}
    false_stations = {flag: set() for flag in FLAGS}
    all_stations = set()
    empty = collections.Counter()  # is_renting value on rows with no bikes available
    full = collections.Counter()  # is_returning value on rows with no docks available
    disagree = 0
    rows = 0
    day = None
    for path in files:
        if path.parent.name != day:
            day = path.parent.name
            print(f"  day {day}  ({time.time() - start:.0f} s)", flush=True)
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            stations = json.load(fh)["data"]["stations"]
        for station in stations:
            rows += 1
            sid = station["station_id"]
            all_stations.add(sid)
            for flag in FLAGS:
                # repr keeps True apart from 1 and records missing fields as <missing>
                value = repr(station[flag]) if flag in station else "<missing>"
                values[flag][value] += 1
                if flag in station and not station[flag]:
                    false_stations[flag].add(sid)
            # GBFS 3.0 (Bicing) renamed num_bikes_available to num_vehicles_available
            if station.get("num_vehicles_available", station.get("num_bikes_available")) == 0:
                empty[station["is_renting"]] += 1
            if station["num_docks_available"] == 0:
                full[station["is_returning"]] += 1
            disagree += station["is_renting"] != station["is_returning"]
    print(f"  station rows: {rows}, distinct stations: {len(all_stations)}")
    for flag in FLAGS:
        seen = ", ".join(f"{v}: {n} ({n / rows:.3%})" for v, n in values[flag].most_common())
        print(f"  {flag}: {seen}; stations ever false: {len(false_stations[flag])}")
    for label, counter in (("empty rows (no bikes), is_renting", empty), ("full rows (no docks), is_returning", full)):
        total = sum(counter.values())
        seen = ", ".join(f"{v}: {n} ({n / total:.3%})" for v, n in counter.most_common()) if total else "none"
        print(f"  {label}: {total} rows; {seen}")
    print(f"  rows where is_renting != is_returning: {disagree}")

print(f"\nelapsed: {time.time() - start:.0f} s")
