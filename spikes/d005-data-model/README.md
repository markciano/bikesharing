# d005 checks

Throwaway checks behind framing decisions of [d005](../../docs/designs/d005-data-model.md). All read the capture spike's bronze copy, `spikes/cloudflare-capture-spike/data/V4/raw/` (2026-10-14 to 10-26, not in Git). Python scripts use the standard library only; the profile uses the DuckDB CLI (2.0.0).

## `free-bike-status/`

Question: does AMBici's `free_bike_status` add anything to `station_status`? Evidence for [d005 › D3](../../docs/designs/d005-data-model.md#d3-feeds-that-enter-the-model).

- `free_bike_check.py` pairs each pass's two feeds by key and compares, per station, `num_bikes_available` with the bikes placed there, and counts disabled, reserved and station-less bikes. About 80 s.

```text
python3 -I spikes/d005-data-model/free-bike-status/free_bike_check.py spikes/cloudflare-capture-spike/data/V4/raw/ambici
```

## `post-code/`

Question: how accurately does ICGC's reverse geocoder give a station's post code? Evidence for d005 › Open questions, OQ4.

- `icgc_check.py` samples up to 2 Bicing stations per published post code, asks the public ICGC geocoder for the 5 nearest addresses, one request per second, and writes a CSV comparing the codes, with a doubt flag when those addresses disagree. About 100 s.

```text
python3 -I spikes/d005-data-model/post-code/icgc_check.py spikes/cloudflare-capture-spike/data/V4/raw <output.csv>
```

## `station-flags/`

Question: what do the station status flags `is_installed`, `is_renting` and `is_returning` carry in each source? Evidence for d005 › Open questions, OQ4.

- `flags_check.py` counts, per source and flag, the values seen in `station_status` and how many stations were ever false; the value of `is_renting` on empty stations and of `is_returning` on full ones; and the rows where those two flags disagree. About 35 s.

```text
python3 -I spikes/d005-data-model/station-flags/flags_check.py spikes/cloudflare-capture-spike/data/V4/raw
```

## `profile/`

Question: what does each column of the feeds that enter the model hold, per source? A data profile of the feeds of [d005 › D3](../../docs/designs/d005-data-model.md#d3-feeds-that-enter-the-model), as evidence for its decisions.

- `<source>/profile.sql` runs DuckDB's `SUMMARIZE` over each feed of that source (type, min, max, approximate distinct values, quartiles, null percentage) and writes one CSV per feed next to it; `vehicle_types_available` is unnested into `station_status_vehicle_types.csv`. About 2 s for AMBici and 5 s for Bicing.
- `keys_check.py` lists every key path of each feed and the number of files that contain it, marking those missing from some files. It covers what `profile.sql` cannot: its schema detection samples only a few files, since sampling them all runs out of memory in DuckDB 2.0.0 ([duckdb#27806](https://github.com/duckdb/duckdb/issues/27806)). About 80 s.

```text
duckdb -f spikes/d005-data-model/profile/ambici/profile.sql
duckdb -f spikes/d005-data-model/profile/bicing/profile.sql
python3 -I spikes/d005-data-model/profile/keys_check.py spikes/cloudflare-capture-spike/data/V4/raw
```

## `municipality/`

Question: which municipality contains each station, and does it match the region AMBici publishes? Evidence for d005 › Open questions, OQ1.

- Boundaries: ICGC's "Divisions administratives" (v2r2, 2026-01-20), layer `divisions_administratives_municipis_5000` (1:5,000), from its WFS (`https://geoserveis.icgc.cat/servei/catalunya/divisions-administratives/wfs`), which returns GML 3.2 only. CC BY 4.0, "Geoinformació de l'Institut Cartogràfic i Geològic de Catalunya". The WFS serves the current version, so a later run may use newer boundaries.
- `municipality_check.py` reads the latest `station_information` of both sources and AMBici's `system_regions`, requests the municipalities in the stations' bounding box (EPSG:4326) once, and caches the response in `data/` (ignored by Git; delete it to fetch again). It checks that Plaça de Catalunya falls in Barcelona, places each station by the even-odd rule over all rings of each municipality, and measures its distance to that municipality's boundary. It writes `municipality.csv` (one row per station: published region, computed municipality, match, distance in metres) and prints a summary per source. About 2 s, plus the first request.

```text
python3 -I spikes/d005-data-model/municipality/municipality_check.py spikes/cloudflare-capture-spike/data/V4/raw spikes/d005-data-model/municipality/municipality.csv spikes/d005-data-model/municipality/data/municipis_5000.gml
```

## `over-capacity/`

Question: why do AMBici's available bikes exceed a station's `capacity`? Evidence for [AMBici's source card › `station_status`](../../docs/sources/ambici.md#station_status).

- `over_capacity.sql` lists, per AMBici station, the passes where available bikes exceed its capacity, with the largest count and the first and last time (UTC), into `over_capacity.csv` next to it. A few seconds.

```text
duckdb -f spikes/d005-data-model/over-capacity/over_capacity.sql
```
