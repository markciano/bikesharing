"""List the vehicle types each source publishes, and whether they change over time.

Input: the spike's raw folder (argv[1]), with <source>/vehicle_types/<date>/<ts>.json.gz.
Output: on stdout, per source, each distinct (vehicle_type_id, form_factor,
propulsion_type) with the number of passes it appears in and its first and last day.
"""
import collections
import gzip
import json
import pathlib
import sys
import time

start = time.time()
root = pathlib.Path(sys.argv[1])

for source_dir in sorted(p for p in root.iterdir() if p.is_dir()):
    files = sorted((source_dir / "vehicle_types").glob("*/*.json.gz"))
    print(f"\n{source_dir.name}: {len(files)} passes", flush=True)
    seen = collections.Counter()
    days = collections.defaultdict(list)
    day = None
    for path in files:
        if path.parent.name != day:
            day = path.parent.name
            print(f"  day {day}  ({time.time() - start:.0f} s)", flush=True)
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            types = json.load(fh)["data"]["vehicle_types"]
        for vt in types:
            key = (vt.get("vehicle_type_id"), vt.get("form_factor"), vt.get("propulsion_type"))
            seen[key] += 1
            days[key].append(day)
    for key, n in sorted(seen.items()):
        print(f"  {key}: {n} passes, {min(days[key])} to {max(days[key])}")

print(f"\nelapsed: {time.time() - start:.0f} s")
