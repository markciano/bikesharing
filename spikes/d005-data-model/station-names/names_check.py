"""Check whether Bicing's station names differ between languages, and count stray spaces.

Input: the spike's raw/ folder (argv[1]); reads every Bicing station_information file in it.
Output: a summary on stdout, per localized field (name, short_name): station items, stations whose
texts differ between languages (with a few examples), the languages seen, and texts with leading or
trailing spaces.
"""
import collections
import gzip
import json
import pathlib
import sys
import time

raw = pathlib.Path(sys.argv[1])
paths = sorted((raw / "bicing" / "station_information").glob("*/*.json.gz"))
start = time.time()
items = collections.Counter()
languages = collections.Counter()
differ = collections.defaultdict(dict)  # field -> station_id -> {language: text}
padded = collections.defaultdict(set)  # field -> station_ids

for i, path in enumerate(paths, 1):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        stations = json.load(fh)["data"]["stations"]
    for s in stations:
        for field in ("name", "short_name"):
            texts = {t["language"]: t["text"] for t in s.get(field) or []}
            items[field] += 1
            languages.update(texts.keys())
            if len(set(texts.values())) > 1:
                differ[field][s["station_id"]] = texts
            if any(t != t.strip() for t in texts.values()):
                padded[field].add(s["station_id"])
    if i % 50 == 0:
        print(f"  {i}/{len(paths)} files ({time.time() - start:.0f} s)", flush=True)

print(f"files: {len(paths)} ({paths[0].parent.name} to {paths[-1].parent.name})")
print(f"languages seen (text entries): {dict(languages)}")
for field in ("name", "short_name"):
    print(f"\n{field}: {items[field]} station items")
    print(f"  stations whose texts differ between languages: {len(differ[field])}")
    for station_id, texts in list(differ[field].items())[:5]:
        print(f"    {station_id}: {texts}")
    print(f"  stations with leading or trailing spaces: {len(padded[field])}")
print(f"\nelapsed: {time.time() - start:.0f} s")
