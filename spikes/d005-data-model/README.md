# Data model (d005): evidence checks

Throwaway checks behind the framing decisions of [d005](../../docs/designs/d005-data-model.md) and the facts of the source cards ([AMBici](../../docs/sources/ambici.md), [Bicing](../../docs/sources/bicing.md)). Run them top to bottom: the data profile first, then one check per decision, in the order of d005. Each check runs on its own, so any one can be rerun alone.

## Prerequisites

- **Bronze copy:** the capture spike's copy, `spikes/cloudflare-capture-spike/data/V4/raw/` (2026-10-14 to 10-26, not in Git), with `<source>/<feed>/<date>/<ts>.json.gz`.
- **Python 3**, standard library only; every script runs with `python3 -I`.
- **DuckDB CLI 2.0.0**, for the `.sql` checks.
- **Network**, for `post-code/` and `municipality/` (public ICGC services) and the download of `neighbourhood/`. Downloads go to the check's `data/` folder, ignored by Git.

## 1. `profile/`

- **Question:** what does each column of the feeds that enter the model hold, per source?
- **Evidence for:** the source cards' facts, and [d005 › D3](../../docs/designs/d005-data-model.md#d3-feeds-that-enter-the-model)'s feeds.
- **Scripts:**
  - `<source>/profile.sql` runs DuckDB's `SUMMARIZE` over each feed of that source (type, min, max, approximate distinct values, quartiles, null percentage); `vehicle_types_available` is unnested into its own CSV.
  - `keys_check.py` lists every key path of each feed and the number of files that contain it, marking those missing from some files. It covers what `profile.sql` cannot: its schema detection samples only a few files, since sampling them all runs out of memory in DuckDB 2.0.0 ([duckdb#27806](https://github.com/duckdb/duckdb/issues/27806)).
- **Output:** one CSV per feed in `<source>/`, and `station_status_vehicle_types.csv`; `keys_check.py` prints to stdout.
- **Run time:** about 2 s for AMBici's profile, 5 s for Bicing's, 80 s for `keys_check.py`.

```text
duckdb -f spikes/d005-data-model/profile/ambici/profile.sql
duckdb -f spikes/d005-data-model/profile/bicing/profile.sql
python3 -I spikes/d005-data-model/profile/keys_check.py spikes/cloudflare-capture-spike/data/V4/raw
```

## 2. `over-capacity/`

- **Question:** why do AMBici's available bikes exceed a station's `capacity`?
- **Evidence for:** [AMBici's source card › `station_status`](../../docs/sources/ambici.md#station_status).
- **Script:** `over_capacity.sql` lists, per AMBici station, the passes where available bikes exceed its capacity, with the largest count and the first and last time (UTC).
- **Output:** `over_capacity.csv`, next to the script.
- **Run time:** a few seconds.

```text
duckdb -f spikes/d005-data-model/over-capacity/over_capacity.sql
```

## 3. `free-bike-status/`

- **Question:** does AMBici's `free_bike_status` add anything to `station_status`?
- **Evidence for:** [d005 › D3](../../docs/designs/d005-data-model.md#d3-feeds-that-enter-the-model).
- **Script:** `free_bike_check.py` pairs each pass's two feeds by key and compares, per station, `num_bikes_available` with the bikes placed there, and counts disabled, reserved and station-less bikes.
- **Output:** stdout.
- **Run time:** about 80 s.

```text
python3 -I spikes/d005-data-model/free-bike-status/free_bike_check.py spikes/cloudflare-capture-spike/data/V4/raw/ambici
```

## 4. `post-code/`

- **Question:** how accurately does ICGC's reverse geocoder give a station's post code?
- **Evidence for:** [d005 › D6](../../docs/designs/d005-data-model.md#d6-ambicis-post-code).
- **Inputs:** ICGC's public reverse geocoder, `https://eines.icgc.cat/geocodificador/invers`, one request per second, no key.
- **Script:** `icgc_check.py` samples up to 2 Bicing stations per published post code, asks the geocoder for the 5 nearest addresses, and compares their codes with the published one, with a doubt flag when those addresses disagree.
- **Output:** the CSV given as second argument, one row per sampled station, and a summary on stdout.
- **Run time:** about 100 s.

```text
python3 -I spikes/d005-data-model/post-code/icgc_check.py spikes/cloudflare-capture-spike/data/V4/raw <output.csv>
```

## 5. `station-flags/`

- **Question:** what do the station status flags `is_installed`, `is_renting` and `is_returning` carry in each source?
- **Evidence for:** [d005 › D7](../../docs/designs/d005-data-model.md#d7-station-status-flags).
- **Script:** `flags_check.py` counts, per source and flag, the values seen in `station_status` and how many stations were ever false; the value of `is_renting` on empty stations and of `is_returning` on full ones; and the rows where those two flags disagree.
- **Output:** stdout.
- **Run time:** about 35 s.

```text
python3 -I spikes/d005-data-model/station-flags/flags_check.py spikes/cloudflare-capture-spike/data/V4/raw
```

## 6. `vehicle-types/`

- **Question:** which vehicle types does each source publish, with which form factor and propulsion, and do they change over time?
- **Evidence for:** [d005 › D8](../../docs/designs/d005-data-model.md#d8-vehicle-propulsion), and the rename of Bicing's `METRO` to `METRO_BASE` in [Bicing's source card › `vehicle_types`](../../docs/sources/bicing.md#vehicle_types).
- **Script:** `vehicle_types_check.py` reads every `vehicle_types` file of each source and lists each distinct (`vehicle_type_id`, `form_factor`, `propulsion_type`) with the number of passes it appears in and its first and last day.
- **Output:** stdout.
- **Run time:** under 1 s.

```text
python3 -I spikes/d005-data-model/vehicle-types/vehicle_types_check.py spikes/cloudflare-capture-spike/data/V4/raw
```

## 7. `municipality/`

- **Question:** which municipality contains each station, and does it match the region AMBici publishes?
- **Evidence for:** [d005 › D9](../../docs/designs/d005-data-model.md#d9-station-municipality).
- **Inputs:** ICGC's "Divisions administratives" (v2r2, 2026-01-20), layer `divisions_administratives_municipis_5000` (1:5,000), from its WFS (`https://geoserveis.icgc.cat/servei/catalunya/divisions-administratives/wfs`), which returns GML 3.2 only. CC BY 4.0, "Geoinformació de l'Institut Cartogràfic i Geològic de Catalunya". The script requests it once and caches it in `data/`; delete the cache to fetch again. The WFS serves the current version, so a later run may use newer boundaries.
- **Script:** `municipality_check.py` reads the latest `station_information` of both sources and AMBici's `system_regions`, requests the municipalities in the stations' bounding box (EPSG:4326), checks that Plaça de Catalunya falls in Barcelona, places each station by the even-odd rule over all rings of each municipality, and measures its distance to that municipality's boundary.
- **Output:** `municipality.csv`, one row per station (published region, computed municipality, match, distance in metres), and a summary per source on stdout.
- **Run time:** about 2 s, plus the first request.

```text
python3 -I spikes/d005-data-model/municipality/municipality_check.py spikes/cloudflare-capture-spike/data/V4/raw spikes/d005-data-model/municipality/municipality.csv spikes/d005-data-model/municipality/data/municipis_5000.gml
```

## 8. `neighbourhood/`

- **Question:** which Barcelona district and neighbourhood contains each station, and does it match the one Bicing publishes in `cross_street`?
- **Evidence for:** [d005 › D10](../../docs/designs/d005-data-model.md#d10-barcelona-district-and-neighbourhood).
- **Inputs:** the City Council's "Unitats administratives" (dataset `20170706-districtes-barris` on Open Data BCN, last modified 2024-11-12), file `BarcelonaCiutat_Barris.json`: one record per neighbourhood with its district's code and name, and its polygon as WKT in ETRS89 and in WGS84. CC BY 4.0, Ajuntament de Barcelona. Download it into `data/` before the run:

  ```text
  curl -s -o spikes/d005-data-model/neighbourhood/data/BarcelonaCiutat_Barris.json https://opendata-ajuntament.barcelona.cat/resources/bcn/EstadisticaUnitatsAdministratives/BarcelonaCiutat_Barris.json
  ```

- **Script:** `neighbourhood_check.py` reads the latest `station_information` of both sources and splits Bicing's `cross_street` into district and neighbourhood codes. It checks that Rambla del Raval falls in Ciutat Vella / el Raval, places each station by the even-odd rule on the WGS84 polygons, and measures its distance to that neighbourhood's boundary.
- **Output:** `neighbourhood.csv`, one row per station in Barcelona (published and computed codes, match, distance in metres), and on stdout Bicing's mismatches and AMBici's stations in Barcelona.
- **Run time:** under 1 s.

```text
python3 -I spikes/d005-data-model/neighbourhood/neighbourhood_check.py spikes/cloudflare-capture-spike/data/V4/raw spikes/d005-data-model/neighbourhood/neighbourhood.csv spikes/d005-data-model/neighbourhood/data/BarcelonaCiutat_Barris.json
```

## 9. `station-names/`

- **Question:** do Bicing's station names differ between the 5 languages it publishes, and do they carry stray spaces?
- **Evidence for:** [d005 › D12](../../docs/designs/d005-data-model.md#d12-station-names).
- **Script:** `names_check.py` reads every Bicing `station_information` file and counts, for `name` and `short_name`, the stations whose texts differ between languages and those with leading or trailing spaces.
- **Output:** stdout.
- **Run time:** about 1 s.

```text
python3 -I spikes/d005-data-model/station-names/names_check.py spikes/cloudflare-capture-spike/data/V4/raw
```
