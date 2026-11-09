"""Check ICGC reverse geocoding against the post codes Bicing publishes.

Inputs: the spike's raw/ folder (argv[1]) and the output CSV path (argv[2]).
Sample: up to 2 Bicing stations per published post code, chosen with a fixed seed.
Output: a CSV with one row per sampled station and a summary on stdout.
One request per second to the public ICGC geocoder.
"""
import collections
import csv
import gzip
import json
import pathlib
import random
import sys
import time
import urllib.parse
import urllib.request

raw = pathlib.Path(sys.argv[1])
out_path = pathlib.Path(sys.argv[2])
ENDPOINT = "https://eines.icgc.cat/geocodificador/invers"

path = max((raw / "bicing" / "station_information").glob("*/*.json.gz"))
with gzip.open(path, "rt", encoding="utf-8") as fh:
    stations = json.load(fh)["data"]["stations"]

by_code = collections.defaultdict(list)
for s in stations:
    code = str(s.get("post_code") or "").strip()
    if code:
        by_code[code.zfill(5)].append(s)
rng = random.Random(40)
sample = []
for code in sorted(by_code):
    group = sorted(by_code[code], key=lambda s: s["station_id"])
    sample.extend((code, s) for s in rng.sample(group, min(2, len(group))))
print(f"published post codes: {len(by_code)}, sampled stations: {len(sample)}")


def reverse(lat, lon):
    """Nearest address's properties, plus the distinct post codes of the 5 nearest addresses."""
    query = urllib.parse.urlencode({"lat": lat, "lon": lon, "layers": "address", "size": 5})
    request = urllib.request.Request(f"{ENDPOINT}?{query}", headers={"User-Agent": "bikesharing-portfolio-check"})
    with urllib.request.urlopen(request, timeout=20) as response:
        features = json.load(response).get("features") or []
    if not features:
        return {}
    props = dict(features[0]["properties"])
    props["nearby_codes"] = sorted({str(f["properties"].get("codi_postal") or "") for f in features})
    return props


rows = []
start = time.time()
for i, (code, s) in enumerate(sample, 1):
    try:
        props = reverse(s["lat"], s["lon"])
        error = ""
    except Exception as exc:  # recorded per row, so one failure does not stop the check
        props, error = {}, f"{type(exc).__name__}: {exc}"
    name = s["name"][0]["text"] if isinstance(s["name"], list) else s["name"]
    icgc_code = str(props.get("codi_postal") or "")
    rows.append({
        "station_id": s["station_id"],
        "name": name.strip(),
        "lat": s["lat"],
        "lon": s["lon"],
        "published_post_code": code,
        "icgc_post_code": icgc_code,
        "match": icgc_code == code,
        "doubtful": len(props.get("nearby_codes", [])) > 1,
        "nearby_codes": " ".join(props.get("nearby_codes", [])),
        "icgc_municipality": props.get("municipi", ""),
        "icgc_address": props.get("etiqueta", props.get("nom", "")),
        "error": error,
        "maps": f"https://www.google.com/maps?q={s['lat']},{s['lon']}",
    })
    if i % 20 == 0:
        print(f"  {i}/{len(sample)} ({time.time() - start:.0f} s)", flush=True)
    time.sleep(1)

with out_path.open("w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

answered = [r for r in rows if r["icgc_post_code"]]
hits = sum(r["match"] for r in rows)
print(f"\nstations with an ICGC post code: {len(answered)} of {len(rows)}; errors: {sum(bool(r['error']) for r in rows)}")
print(f"ICGC post code equals the published one: {hits} of {len(rows)} ({hits / len(rows):.1%})")
misses = [r for r in rows if not r["match"]]
flagged = [r for r in rows if r["doubtful"]]
print(f"flagged doubtful: {len(flagged)}; misses flagged: {sum(r['doubtful'] for r in misses)} of {len(misses)}")
print(f"misses among stations not flagged: {sum(not r['match'] for r in rows if not r['doubtful'])}")
print(f"municipalities returned: {collections.Counter(r['icgc_municipality'] for r in rows)}")
if rows and not answered:
    print("no post code in any answer; first error:", rows[0]["error"])
print(f"CSV: {out_path}\nelapsed: {time.time() - start:.0f} s")
