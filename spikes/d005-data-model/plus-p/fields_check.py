"""Profile every field of nextbike's live feed for AMBici.

Input: the downloaded feed (argv[1]), nextbike-live.json?domains=bs.
Output: a text file (argv[2]), one line per field path (list items share the path
`[]`): how many times it appears, its JSON types, its number of distinct values, its
range when numeric, and its most common values.
"""
import collections
import json
import pathlib
import sys

TOP = 6  # most common values shown per field

feed = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
seen = collections.Counter()
types = collections.defaultdict(collections.Counter)
values = collections.defaultdict(collections.Counter)


def walk(node, path):
    if isinstance(node, dict):
        for key, child in node.items():
            walk(child, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        seen[path] += 1
        types[path]["list"] += 1
        for item in node:
            walk(item, f"{path}[]")
    else:
        seen[path] += 1
        types[path][type(node).__name__] += 1
        values[path][repr(node)[:60]] += 1


walk(feed, "")
lines = []
for path in sorted(seen):
    line = f"{path}: {seen[path]} × {dict(types[path])}"
    if values[path]:
        counter = values[path]
        numbers = [float(v) for v in counter if v.lstrip("-").replace(".", "", 1).isdigit()]
        line += f"; distinct {len(counter)}"
        if numbers and len(numbers) == len(counter):
            line += f"; range {min(numbers):g}..{max(numbers):g}"
        common = ", ".join(f"{v} ({n})" for v, n in counter.most_common(TOP))
        line += f"; top: {common}"
    lines.append(line)
pathlib.Path(sys.argv[2]).write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(lines)} field paths written to {sys.argv[2]}")
