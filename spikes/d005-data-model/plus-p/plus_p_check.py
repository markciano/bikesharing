"""Check whether nextbike's place_type marks AMBici's +P stations.

Inputs:
- argv[1]: nextbike's live feed for AMBici (nextbike-live.json?domains=bs);
- argv[2]: the spike's raw folder; the latest ambici/station_information/<date>/<ts>.json.gz is read;
- argv[3]: over-capacity/over_capacity.csv, the passes where a station's bikes exceed its capacity.
Output:
- argv[4]: a CSV, one row per nextbike place: its uid and GBFS match, name in both,
  place_type, bike_racks, GBFS capacity, passes over capacity and the largest excess;
- on stdout: how many places match a GBFS station_id and name, and per place_type the
  stations, those ever over capacity, the median passes over, the largest excess,
  how bike_racks compares with capacity, and 4 sample names to check on the map.

The bronze copy (2026-10-14 to 10-26) is older than the nextbike download, so a
station may be in one and not the other.
"""
import collections
import csv
import gzip
import json
import pathlib
import statistics
import sys

feed = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
info_files = sorted(pathlib.Path(sys.argv[2], "ambici", "station_information").glob("*/*.json.gz"))
with gzip.open(info_files[-1], "rt", encoding="utf-8") as fh:
    gbfs = {s["station_id"]: s for s in json.load(fh)["data"]["stations"]}
with open(sys.argv[3], newline="", encoding="utf-8") as fh:
    over = {row["station_id"]: row for row in csv.DictReader(fh)}

rows = []
for country in feed["countries"]:
    for city in country["cities"]:
        for place in city["places"]:
            sid = str(place["uid"])
            station = gbfs.get(sid)
            excess = over.get(sid)
            rows.append({
                "uid": sid,
                "in_gbfs": station is not None,
                "nextbike_name": place["name"],
                "gbfs_name": station["name"] if station else "",
                "place_type": place["place_type"],
                "bike_racks": place["bike_racks"],
                "capacity": station["capacity"] if station else "",
                "passes_over": int(excess["passes_over"]) if excess else 0,
                "max_excess": int(excess["max_bikes"]) - int(excess["capacity"]) if excess else 0,
            })

matched = [r for r in rows if r["in_gbfs"]]
same_name = sum(r["nextbike_name"].strip() == r["gbfs_name"].strip() for r in matched)
print(f"nextbike places: {len(rows)}; GBFS stations: {len(gbfs)} (from {info_files[-1].name})")
print(f"uid = station_id: {len(matched)}; of those, same name: {same_name}")
print(f"GBFS stations not in nextbike: {sorted(set(gbfs) - {r['uid'] for r in rows})}")

by_type = collections.defaultdict(list)
for r in matched:
    by_type[r["place_type"]].append(r)
print("\nplace_type: stations; ever over capacity; median passes over (of those); "
      "largest excess; bike_racks = / > / < capacity")
for ptype in sorted(by_type):
    group = by_type[ptype]
    overs = [r for r in group if r["passes_over"] > 0]
    median = statistics.median(r["passes_over"] for r in overs) if overs else 0
    largest = max((r["max_excess"] for r in group), default=0)
    eq = sum(r["bike_racks"] == r["capacity"] for r in group)
    gt = sum(r["bike_racks"] > r["capacity"] for r in group)
    lt = sum(r["bike_racks"] < r["capacity"] for r in group)
    print(f"  {ptype}: {len(group)}; {len(overs)}; {median:g}; {largest}; {eq} / {gt} / {lt}")
    print(f"    samples: {', '.join(r['nextbike_name'] for r in group[:4])}")

with open(sys.argv[4], "w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(f"\n{len(rows)} rows written to {sys.argv[4]}")
