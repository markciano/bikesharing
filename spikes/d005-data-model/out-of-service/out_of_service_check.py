"""Check which flag combinations occur and how stock behaves when a station goes out of service.

Input: the spike's raw folder (argv[1]), with <source>/station_status/<date>/<ts>.json.gz.
Output:
- on stdout, per source: the rows and stations seen with each combination of
  (is_installed, is_renting, is_returning); and, for each change into or out of
  service, how many vehicles the station reported around it;
- a CSV (argv[2]) with one row per change: source, station, direction, pass
  timestamp, vehicles available 15 passes before, the pass before and at the
  change, the vehicles disabled, and the docks available and disabled, the
  pass before and at the change.

Out of service means is_renting and is_returning both false (d005 D7). A station
that is emptied before closing reaches 0 while still in service; a feed that only
reports 0 drops from N to 0 in the pass where the flags change. On reopening,
the first pass in service shows whether the bikes were still there.
"""
import collections
import csv
import gzip
import json
import pathlib
import sys
import time

FLAGS = ("is_installed", "is_renting", "is_returning")
LOOKBACK = 15  # passes kept per station, about 15 min at one pass per minute

start = time.time()
root = pathlib.Path(sys.argv[1])
out_csv = pathlib.Path(sys.argv[2])


def available(station):
    # GBFS 3.0 (Bicing) renamed num_bikes_available to num_vehicles_available
    return station.get("num_vehicles_available", station.get("num_bikes_available"))


def disabled(station):
    # AMBici (2.3) publishes no disabled count
    return station.get("num_vehicles_disabled", station.get("num_bikes_disabled"))


def docks(station):
    # (available, disabled); AMBici (2.3) publishes no disabled docks
    return station.get("num_docks_available"), station.get("num_docks_disabled")


def summary(values):
    if not values:
        return "none"
    zero = sum(1 for v in values if v == 0)
    ordered = sorted(values)
    return (f"{len(values)} changes; at 0: {zero} ({zero / len(values):.1%}); "
            f"median {ordered[len(ordered) // 2]}, max {ordered[-1]}")


changes = []
for source_dir in sorted(p for p in root.iterdir() if p.is_dir()):
    source = source_dir.name
    files = sorted((source_dir / "station_status").glob("*/*.json.gz"))
    print(f"\n{source}: {len(files)} passes", flush=True)
    combo_rows = collections.Counter()
    combo_stations = collections.defaultdict(set)
    previous = {}  # station_id -> (out_of_service, available, disabled, docks) at its previous pass
    history = collections.defaultdict(lambda: collections.deque(maxlen=LOOKBACK))
    day = None
    for path in files:
        if path.parent.name != day:
            day = path.parent.name
            print(f"  day {day}  ({time.time() - start:.0f} s)", flush=True)
        ts = path.name.split(".")[0]
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            stations = json.load(fh)["data"]["stations"]
        for station in stations:
            sid = station["station_id"]
            combo = tuple(station[flag] for flag in FLAGS)
            combo_rows[combo] += 1
            combo_stations[combo].add(sid)
            out = not station["is_renting"] and not station["is_returning"]
            now = (out, available(station), disabled(station), docks(station))
            if sid in previous and previous[sid][0] != out:
                past = history[sid]
                changes.append({
                    "source": source,
                    "station_id": sid,
                    "direction": "closes" if out else "reopens",
                    "pass": ts,
                    f"available_{LOOKBACK}_before": past[0] if len(past) == LOOKBACK else "",
                    "available_before": previous[sid][1],
                    "available_at": now[1],
                    "disabled_before": previous[sid][2],
                    "disabled_at": now[2],
                    "docks_available_before": previous[sid][3][0],
                    "docks_available_at": now[3][0],
                    "docks_disabled_before": previous[sid][3][1],
                    "docks_disabled_at": now[3][1],
                })
            previous[sid] = now
            history[sid].append(now[1])
    rows = sum(combo_rows.values())
    print(f"  rows: {rows}")
    print("  (is_installed, is_renting, is_returning): rows, stations")
    for combo, n in combo_rows.most_common():
        print(f"    {combo}: {n} ({n / rows:.3%}), {len(combo_stations[combo])} stations")
    closes = [c for c in changes if c["source"] == source and c["direction"] == "closes"]
    reopens = [c for c in changes if c["source"] == source and c["direction"] == "reopens"]
    print(f"  closes, available the pass before: {summary([c['available_before'] for c in closes])}")
    print(f"  closes, available at the change: {summary([c['available_at'] for c in closes])}")
    print(f"  reopens, available the pass before: {summary([c['available_before'] for c in reopens])}")
    print(f"  reopens, available at the change: {summary([c['available_at'] for c in reopens])}")

with out_csv.open("w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=list(changes[0]) if changes else ["source"])
    writer.writeheader()
    writer.writerows(changes)
print(f"\n{len(changes)} changes written to {out_csv}")
print(f"elapsed: {time.time() - start:.0f} s")
