"""One-off tooling for the switch from the spike's capture to production (d004 > D11).

Both commands read `rclone lsf -R` listings: one path per line, relative to the
listed root, `<source>/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz`. Lines ending
in `/` are folders and are skipped.

- keys: writes (or reads, if it exists) the cutoffs file, JSON mapping
  `<source>/<feed>` to the minute of that feed's first object in production
  (`YYYYMMDDTHHMM`), then writes to --out every spike path earlier than its
  feed's cutoff, for `rclone copy --files-from`. Exits 1, writing neither file,
  if a spike feed has no cutoff.
- count: for each source, feed and day before the cutoff, prints the object
  count in both listings and exits 1 on any difference.

Inputs: the listings and the cutoffs file. Outputs: the cutoffs file, the keys
file and the counts on stdout. All timestamps are UTC.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def read_listing(path):
    """Return the object paths of a listing as (feed, day, minute, path) tuples."""
    objects = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.endswith("/"):
            continue
        source, feed, day, name = line.split("/")
        # `YYYYMMDDTHHMMSSZ.json.gz` -> `YYYYMMDDTHHMM`: the cutoff is per minute.
        minute = name[:13]
        objects.append((f"{source}/{feed}", day, minute, line))
    return objects


def first_minutes(objects):
    """Map each feed to the minute of its first object."""
    cutoffs = {}
    for feed, _day, minute, _path in objects:
        if feed not in cutoffs or minute < cutoffs[feed]:
            cutoffs[feed] = minute
    return dict(sorted(cutoffs.items()))


def missing_cutoffs(spike_objects, cutoffs):
    return sorted({feed for feed, *_ in spike_objects} - cutoffs.keys())


def load_cutoffs(path, prod_objects, spike_objects):
    """Read the cutoffs file; write it from production first if it does not exist.

    Once written it is never changed, so a repeated copy uses the same cutoffs
    even though copied objects then come first in production. It is not written
    while a spike feed has no object in production, since that feed would then
    never get a cutoff.
    """
    path = Path(path)
    if not path.exists():
        cutoffs = first_minutes(prod_objects)
        if missing_cutoffs(spike_objects, cutoffs):
            return cutoffs
        path.write_text(json.dumps(cutoffs, indent=2) + "\n")
        print(f"cutoffs written to {path}")
    return json.loads(path.read_text())


def before_cutoff(objects, cutoffs):
    # Fixed-width `YYYYMMDDTHHMM` strings compare in time order.
    return [o for o in objects if o[0] in cutoffs and o[2] < cutoffs[o[0]]]


def cmd_keys(args):
    prod = read_listing(args.prod)
    spike = read_listing(args.spike)
    cutoffs = load_cutoffs(args.cutoffs, prod, spike)
    missing = missing_cutoffs(spike, cutoffs)
    if missing:
        print(f"no object in production yet for: {', '.join(missing)}", file=sys.stderr)
        return 1
    keys = sorted(path for *_, path in before_cutoff(spike, cutoffs))
    Path(args.out).write_text("".join(f"{k}\n" for k in keys))
    print(f"{len(keys)} keys written to {args.out}")
    return 0


def cmd_count(args):
    cutoffs_path = Path(args.cutoffs)
    if not cutoffs_path.exists():
        print(f"cutoffs file not found: {cutoffs_path}; run keys first", file=sys.stderr)
        return 1
    cutoffs = json.loads(cutoffs_path.read_text())
    prod = read_listing(args.prod)
    spike = read_listing(args.spike)
    missing = missing_cutoffs(spike, cutoffs)
    if missing:
        print(f"no cutoff for: {', '.join(missing)}", file=sys.stderr)
        return 1
    prod_counts = Counter((f, d) for f, d, *_ in before_cutoff(prod, cutoffs))
    spike_counts = Counter((f, d) for f, d, *_ in before_cutoff(spike, cutoffs))
    differences = 0
    print("feed\tday\tspike\tprod")
    for feed, day in sorted(prod_counts.keys() | spike_counts.keys()):
        s, p = spike_counts[(feed, day)], prod_counts[(feed, day)]
        mark = "" if s == p else "\tDIFF"
        differences += s != p
        print(f"{feed}\t{day}\t{s}\t{p}{mark}")
    print(f"{differences} differences")
    return 1 if differences else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    keys = sub.add_parser("keys", help="write the cutoffs and the keys to copy")
    keys.add_argument("--prod", required=True, help="listing of bikesharing-bronze/raw/")
    keys.add_argument("--spike", required=True, help="listing of V4/raw/")
    keys.add_argument("--cutoffs", required=True, help="cutoffs file, written if missing")
    keys.add_argument("--out", required=True, help="keys file for rclone --files-from")
    keys.set_defaults(run=cmd_keys)

    count = sub.add_parser("count", help="compare object counts before the cutoffs")
    count.add_argument("--prod", required=True, help="listing of bikesharing-bronze/raw/")
    count.add_argument("--spike", required=True, help="listing of V4/raw/")
    count.add_argument("--cutoffs", required=True, help="cutoffs file written by keys")
    count.set_defaults(run=cmd_count)

    args = parser.parse_args()
    sys.exit(args.run(args))


if __name__ == "__main__":
    main()
