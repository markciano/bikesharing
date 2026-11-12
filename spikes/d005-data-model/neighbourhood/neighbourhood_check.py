"""Place each station of both sources in Barcelona's official neighbourhoods, and compare with Bicing's cross_street.

Inputs: the spike's raw/ folder (argv[1]), the output CSV path (argv[2]) and the City Council's
BarcelonaCiutat_Barris.json (argv[3], downloaded to the ignored neighbourhood/data/).
Boundaries: one record per neighbourhood with its district; geometry as WKT in WGS84 (geometria_wgs84).
CC BY 4.0, Ajuntament de Barcelona.
Output: a CSV with one row per station inside Barcelona (published and computed district and
neighbourhood codes, match, distance to the neighbourhood's boundary) and a summary on stdout.
"""
import collections
import csv
import gzip
import json
import math
import pathlib
import re
import sys
import time

raw = pathlib.Path(sys.argv[1])
out_path = pathlib.Path(sys.argv[2])
barris_path = pathlib.Path(sys.argv[3])
CONTROL = (41.3797, 2.1682, "01", "01")  # Rambla del Raval: Ciutat Vella, el Raval
start = time.time()


def latest(source, feed):
    path = max((raw / source / feed).glob("*/*.json.gz"))
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)["data"]


def text(value):
    # GBFS 3.0 localizes names as a list of {text, language}; 2.3 uses a plain string.
    return (value[0]["text"] if isinstance(value, list) else value).strip()


def published(cross_street):
    """Bicing's cross_street, e.g. '01-CiutatVella/01-el Raval', as (district code, neighbourhood code)."""
    parts = (cross_street or "").split("/")
    if len(parts) != 2:
        return "", ""
    return parts[0].split("-", 1)[0].strip(), parts[1].split("-", 1)[0].strip()


stations = []
for source in ("ambici", "bicing"):
    for s in latest(source, "station_information")["stations"]:
        district, barri = published(s.get("cross_street")) if source == "bicing" else ("", "")
        stations.append({"source": source, "station_id": s["station_id"], "name": text(s["name"]),
                         "lat": float(s["lat"]), "lon": float(s["lon"]),
                         "published_district": district, "published_barri": barri})
print(f"stations: {collections.Counter(s['source'] for s in stations)}")


def wkt_rings(wkt):
    """Every ring of a WKT POLYGON or MULTIPOLYGON: each innermost parenthesis group is one ring."""
    return [[tuple(map(float, p.split())) for p in group.split(",")] for group in re.findall(r"\(([^()]+)\)", wkt)]


barris = []
for r in json.loads(barris_path.read_text(encoding="utf-8")):
    rings = wkt_rings(r["geometria_wgs84"])
    xs = [x for ring in rings for x, _ in ring]
    ys = [y for ring in rings for _, y in ring]
    barris.append({"district": r["codi_districte"], "district_name": r["nom_districte"],
                   "barri": r["codi_barri"], "barri_name": r["nom_barri"],
                   "rings": rings, "box": (min(xs), min(ys), max(xs), max(ys))})
print(f"neighbourhoods: {len(barris)}, districts: {len({b['district'] for b in barris})}")


def contains(b, lon, lat):
    """Even-odd rule over all rings, so holes and detached parts count correctly."""
    x0, y0, x1, y1 = b["box"]
    if not (x0 <= lon <= x1 and y0 <= lat <= y1):
        return False
    inside = False
    for ring in b["rings"]:
        for (xa, ya), (xb, yb) in zip(ring, ring[1:] + ring[:1]):
            if (ya > lat) != (yb > lat) and lon < xa + (lat - ya) * (xb - xa) / (yb - ya):
                inside = not inside
    return inside


def boundary_m(b, lon, lat):
    """Distance to the neighbourhood's own boundary, on a local flat projection (error well under 1%)."""
    kx, ky = 111_320 * math.cos(math.radians(lat)), 110_540
    best = math.inf
    for ring in b["rings"]:
        for (xa, ya), (xb, yb) in zip(ring, ring[1:] + ring[:1]):
            ax, ay, bx, by = (xa - lon) * kx, (ya - lat) * ky, (xb - lon) * kx, (yb - lat) * ky
            dx, dy = bx - ax, by - ay
            t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
            best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


def locate(lon, lat):
    found = [b for b in barris if contains(b, lon, lat)]
    return found[0] if len(found) == 1 else None


control = locate(CONTROL[1], CONTROL[0])
assert control and (control["district"], control["barri"]) == CONTROL[2:], f"control point misplaced: {control}"

rows = []
for s in stations:
    b = locate(s["lon"], s["lat"])
    if not b and not s["published_barri"]:
        continue  # outside Barcelona, and nothing published to compare
    rows.append({
        **s,
        "district": b["district"] if b else "",
        "district_name": b["district_name"] if b else "",
        "barri": b["barri"] if b else "",
        "barri_name": b["barri_name"] if b else "",
        "match": "" if s["source"] == "ambici" else bool(b) and (s["published_district"], s["published_barri"]) == (b["district"], b["barri"]),
        "boundary_m": round(boundary_m(b, s["lon"], s["lat"])) if b else "",
        "maps": f"https://www.google.com/maps?q={s['lat']},{s['lon']}",
    })

with out_path.open("w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

bicing = [r for r in rows if r["source"] == "bicing"]
print(f"\nbicing: {len(bicing)} stations, published codes missing {sum(not r['published_barri'] for r in bicing)}, "
      f"outside every neighbourhood {sum(not r['barri'] for r in bicing)}, match {sum(r['match'] is True for r in bicing)}")
print(f"  neighbourhoods with a Bicing station: {len({r['barri'] for r in bicing if r['barri']})} of {len(barris)}")
print("  mismatches (published -> computed, distance to boundary):")
for r in bicing:
    if r["match"] is not True:
        print(f"    {r['station_id']} {r['name']}: {r['published_district']}/{r['published_barri']} -> "
              f"{r['district']}/{r['barri']} {r['barri_name']} ({r['boundary_m']} m)")
print("\nambici stations in Barcelona:")
for r in rows:
    if r["source"] == "ambici":
        print(f"  {r['station_id']} {r['name']}: {r['district']} {r['district_name']} / {r['barri']} {r['barri_name']} ({r['boundary_m']} m)")
print(f"CSV: {out_path}\nelapsed: {time.time() - start:.0f} s")
