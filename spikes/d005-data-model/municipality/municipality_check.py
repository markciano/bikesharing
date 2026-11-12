"""Assign each station of both sources the municipality that contains it, from ICGC's boundaries.

Inputs: the spike's raw/ folder (argv[1]), the output CSV path (argv[2]) and a path to cache
ICGC's WFS response (argv[3], in the ignored municipality/data/; reused if it exists).
Boundaries: ICGC "Divisions administratives", layer divisions_administratives_municipis_5000
(1:5,000), one WFS request in EPSG:4326 for the stations' bounding box, as GML 3.2, the only
format the service returns. CC BY 4.0, ICGC.
Output: a CSV with one row per station (published region, computed municipality, whether they
match, distance to the nearest municipal boundary) and a summary on stdout.
"""
import collections
import csv
import gzip
import json
import math
import pathlib
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

raw = pathlib.Path(sys.argv[1])
out_path = pathlib.Path(sys.argv[2])
cache_path = pathlib.Path(sys.argv[3])
WFS = "https://geoserveis.icgc.cat/servei/catalunya/divisions-administratives/wfs"
LAYER = "divisions_administratives_municipis_5000"
CONTROL = (41.3870, 2.1701, "Barcelona")  # Plaça de Catalunya
start = time.time()


def latest(source, feed):
    path = max((raw / source / feed).glob("*/*.json.gz"))
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)["data"]


def text(value):
    # GBFS 3.0 localizes names as a list of {text, language}; 2.3 uses a plain string.
    return (value[0]["text"] if isinstance(value, list) else value).strip()


regions = {r["region_id"]: text(r["name"]) for r in latest("ambici", "system_regions")["regions"]}
stations = []
for source in ("ambici", "bicing"):
    for s in latest(source, "station_information")["stations"]:
        region = regions.get(s.get("region_id"), "") if source == "ambici" else ""
        stations.append({"source": source, "station_id": s["station_id"], "name": text(s["name"]),
                         "lat": float(s["lat"]), "lon": float(s["lon"]), "region": region})
print(f"stations: {collections.Counter(s['source'] for s in stations)}")

if not cache_path.exists():
    pad = 0.01  # about 1 km, so every station's municipality is complete in the response
    lats, lons = [s["lat"] for s in stations], [s["lon"] for s in stations]
    # WFS 2.0 with an EPSG URN uses latitude-first axis order, in the bbox too.
    bbox = f"{min(lats) - pad},{min(lons) - pad},{max(lats) + pad},{max(lons) + pad},urn:ogc:def:crs:EPSG::4326"
    query = urllib.parse.urlencode({
        "service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": LAYER,
        "outputFormat": "GML32", "srsName": "urn:ogc:def:crs:EPSG::4326", "bbox": bbox,
    })
    request = urllib.request.Request(f"{WFS}?{query}", headers={"User-Agent": "bikesharing-portfolio-check"})
    with urllib.request.urlopen(request, timeout=120) as response:
        body = response.read()
    if b"ExceptionReport" in body[:500]:  # an OGC error comes back as XML with HTTP 200
        sys.exit(f"WFS error:\n{body.decode('utf-8', 'replace')}")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(body)
    print(f"WFS response saved: {cache_path} ({cache_path.stat().st_size / 1e6:.1f} MB)")


def local(tag):
    return tag.rsplit("}", 1)[-1]


def gml_features(path):
    """Each WFS member as (properties, rings); a ring is the flat gml:posList read as pairs."""
    for member in ET.parse(path).getroot():
        if local(member.tag) != "member":
            continue
        feature = member[0]
        props = {local(e.tag): (e.text or "").strip() for e in feature if len(e) == 0}
        rings = []
        for ring in feature.iter():
            if local(ring.tag) == "LinearRing":
                values = [float(v) for e in ring if local(e.tag) == "posList" for v in e.text.split()]
                rings.append(list(zip(values[0::2], values[1::2])))
        yield props, rings


features = list(gml_features(cache_path))
# EPSG:4326 in WFS 2.0 is latitude first; a latitude near 41 tells the order apart from a longitude near 2.
first = features[0][1][0][0]
lat_first = abs(first[0]) > abs(first[1])
municipalities = []
for props, rings in features:
    rs = [[(b, a) if lat_first else (a, b) for a, b in ring] for ring in rings]
    xs = [x for r in rs for x, _ in r]
    ys = [y for r in rs for _, y in r]
    municipalities.append({"code": props["CODIMUNI"], "name": props["NOMMUNI"],
                           "rings": rs, "box": (min(xs), min(ys), max(xs), max(ys))})
print(f"municipalities in the response: {len(municipalities)} (lat first: {lat_first})")


def contains(m, lon, lat):
    """Even-odd rule over all rings, so holes and detached parts count correctly."""
    x0, y0, x1, y1 = m["box"]
    if not (x0 <= lon <= x1 and y0 <= lat <= y1):
        return False
    inside = False
    for ring in m["rings"]:
        for (xa, ya), (xb, yb) in zip(ring, ring[1:] + ring[:1]):
            if (ya > lat) != (yb > lat) and lon < xa + (lat - ya) * (xb - xa) / (yb - ya):
                inside = not inside
    return inside


def boundary_m(m, lon, lat):
    """Distance to the municipality's own boundary, on a local flat projection (error well under 1%)."""
    kx, ky = 111_320 * math.cos(math.radians(lat)), 110_540
    best = math.inf
    for ring in m["rings"]:
        for (xa, ya), (xb, yb) in zip(ring, ring[1:] + ring[:1]):
            ax, ay, bx, by = (xa - lon) * kx, (ya - lat) * ky, (xb - lon) * kx, (yb - lat) * ky
            dx, dy = bx - ax, by - ay
            t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
            best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


def locate(lon, lat):
    found = [m for m in municipalities if contains(m, lon, lat)]
    return found[0] if len(found) == 1 else None


control = locate(CONTROL[1], CONTROL[0])
assert control and control["name"] == CONTROL[2], f"control point not in {CONTROL[2]}: {control and control['name']}"


def same(region, name):
    # AMBici's region names drop the leading article ICGC keeps, e.g. "Hospitalet de Llobregat".
    def bare(value):
        value = value.casefold().replace("’", "'")
        for article in ("l'", "el ", "la ", "els ", "les "):
            value = value.removeprefix(article)
        return value
    return bare(region) == bare(name)


rows = []
for s in stations:
    m = locate(s["lon"], s["lat"])
    expected = s["region"] if s["source"] == "ambici" else "Barcelona"
    rows.append({
        **s,
        "municipality_code": m["code"] if m else "",
        "municipality": m["name"] if m else "",
        "match": bool(m) and same(expected, m["name"]),
        "boundary_m": round(boundary_m(m, s["lon"], s["lat"])) if m else "",
        "maps": f"https://www.google.com/maps?q={s['lat']},{s['lon']}",
    })

with out_path.open("w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

for source in ("ambici", "bicing"):
    group = [r for r in rows if r["source"] == source]
    print(f"\n{source}: {len(group)} stations, unlocated {sum(not r['municipality'] for r in group)}, "
          f"match {sum(r['match'] for r in group)}, within 25 m of a boundary "
          f"{sum(r['boundary_m'] != '' and r['boundary_m'] < 25 for r in group)}")
    print("  municipalities:", dict(collections.Counter(r["municipality"] for r in group)))
print("\nAMBici region vs municipality (mismatches only):")
pairs = collections.Counter((r["region"], r["municipality"]) for r in rows if r["source"] == "ambici" and not r["match"])
for (region, name), n in pairs.most_common():
    print(f"  {region} -> {name or '(none)'}: {n}")
print(f"CSV: {out_path}\nelapsed: {time.time() - start:.0f} s")
