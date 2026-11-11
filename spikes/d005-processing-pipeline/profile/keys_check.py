"""List every key path in each feed that enters d005's model, and in how many files it appears.

Input: the spike's raw folder (argv[1]), with <source>/<feed>/<date>/<ts>.json.gz.
Output: on stdout, per source and feed, each key path (lists shown as []) with the number
of files that contain it; a path in fewer files than the feed has is marked "PARTIAL".
DuckDB's profile.sql samples only a few files to detect the schema, so this finds the keys
it could miss.
"""
import collections
import gzip
import json
import pathlib
import sys
import time

FEEDS = ("station_status", "station_information", "vehicle_types", "system_regions")


def paths(value, prefix=""):
    """Yield every key path in a JSON value; list items share the path prefix[]."""
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            yield path
            yield from paths(child, path)
    elif isinstance(value, list):
        for item in value:
            yield from paths(item, f"{prefix}[]")


start = time.time()
root = pathlib.Path(sys.argv[1])

for source_dir in sorted(p for p in root.iterdir() if p.is_dir()):
    for feed in FEEDS:
        files = sorted((source_dir / feed).glob("*/*.json.gz"))
        if not files:
            continue
        counts = collections.Counter()
        for path in files:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                counts.update(set(paths(json.load(fh))))
        print(f"\n{source_dir.name}/{feed}: {len(files)} files  ({time.time() - start:.0f} s)", flush=True)
        for key, n in sorted(counts.items()):
            mark = "" if n == len(files) else "  PARTIAL"
            print(f"  {key}: {n}{mark}")

print(f"\nelapsed: {time.time() - start:.0f} s")
