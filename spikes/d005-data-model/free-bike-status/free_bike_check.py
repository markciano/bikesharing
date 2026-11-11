"""Compare AMBici's station_status with free_bike_status from the same pass.

Input: the spike's raw/ambici folder (argv[1]), with <feed>/<date>/<ts>.json.gz.
Output: on stdout, how often each station's num_bikes_available matches the bikes
that free_bike_status places at that station, under three counting rules, plus
disabled, reserved and station-less bikes.
"""
import collections
import gzip
import json
import pathlib
import statistics
import sys
import time

start = time.time()
root = pathlib.Path(sys.argv[1])
status_files = {p.relative_to(root / "station_status"): p for p in (root / "station_status").glob("*/*.json.gz")}
bike_files = {p.relative_to(root / "free_bike_status"): p for p in (root / "free_bike_status").glob("*/*.json.gz")}
pairs = sorted(set(status_files) & set(bike_files))
print(f"passes with both feeds: {len(pairs)} (status only {len(status_files) - len(pairs)}, bikes only {len(bike_files) - len(pairs)})")

rules = ("all", "not_disabled", "not_disabled_not_reserved")
matches = collections.Counter()
station_rows = 0
mismatch_examples = []
per_pass = collections.defaultdict(list)
unknown_station_ids = 0
days_done = set()


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)["data"]


for key in pairs:
    if key.parts[0] not in days_done:
        days_done.add(key.parts[0])
        print(f"  day {key.parts[0]}  ({time.time() - start:.0f} s)", flush=True)
    stations = load(status_files[key])["stations"]
    bikes = load(bike_files[key])["bikes"]
    counts = {rule: collections.Counter() for rule in rules}
    no_station = disabled = reserved = disabled_at_station = 0
    station_ids = {s["station_id"] for s in stations}
    for bike in bikes:
        sid = bike.get("station_id") or None
        is_disabled = bool(bike.get("is_disabled"))
        is_reserved = bool(bike.get("is_reserved"))
        disabled += is_disabled
        reserved += is_reserved
        if sid is None:
            no_station += 1
            continue
        if sid not in station_ids:
            unknown_station_ids += 1
        disabled_at_station += is_disabled
        counts["all"][sid] += 1
        if not is_disabled:
            counts["not_disabled"][sid] += 1
            if not is_reserved:
                counts["not_disabled_not_reserved"][sid] += 1
    for station in stations:
        station_rows += 1
        sid = station["station_id"]
        available = station["num_bikes_available"]
        for rule in rules:
            if counts[rule][sid] == available:
                matches[rule] += 1
        if counts["not_disabled"][sid] != available and len(mismatch_examples) < 5:
            mismatch_examples.append((str(key), sid, available, counts["all"][sid], counts["not_disabled"][sid]))
    per_pass["bikes"].append(len(bikes))
    per_pass["no_station"].append(no_station)
    per_pass["disabled"].append(disabled)
    per_pass["disabled_at_station"].append(disabled_at_station)
    per_pass["reserved"].append(reserved)
    per_pass["bikes_at_stations_status"].append(sum(s["num_bikes_available"] for s in stations))

print(f"\nstation rows compared: {station_rows}")
for rule in rules:
    print(f"  match rate, {rule}: {matches[rule] / station_rows:.4%}")
print(f"bikes pointing to a station_id absent from station_status: {unknown_station_ids}")
print("\nper pass (mean / min / max):")
for name, values in per_pass.items():
    print(f"  {name}: {statistics.mean(values):.1f} / {min(values)} / {max(values)}")
print("\nfirst mismatches (pass, station, num_bikes_available, bikes all, bikes not disabled):")
for row in mismatch_examples:
    print(f"  {row}")
print(f"\nelapsed: {time.time() - start:.0f} s")
