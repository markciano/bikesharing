# Data model (d005): evidence checks

Throwaway checks behind the framing decisions of [d005](../../docs/designs/d005-data-model.md) and the facts of the source cards ([AMBici](../../docs/sources/ambici.md), [Bicing](../../docs/sources/bicing.md)). Run them top to bottom: the data profile first, then one check per decision, in the order of d005. Each check runs on its own, so any one can be rerun alone.

## Prerequisites

- **Bronze copy:** the capture spike's copy, `spikes/cloudflare-capture-spike/data/V4/raw/` (2026-10-14 to 10-26, not in Git), with `<source>/<feed>/<date>/<ts>.json.gz`.
- **Bicing history archives:** the Bicing spike's copy, `spikes/bicing-spike/historical-data/raw/` (not in Git), with the monthly `..._BicingNou_{ESTACIONS,INFORMACIO}.7z` of December 2025 to October 2026; read in place, for `profile/bicing-historical/`.
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

## 10. `out-of-service/`

- **Question:** which combinations of the status flags occur, and does a station that goes out of service report the bikes it holds, its disabled bikes and its free docks?
- **Evidence for:** [d005 › D16](../../docs/designs/d005-data-model.md#d16-vehicles-at-an-out-of-service-station), and the out-of-service fact in [Bicing's source card › `station_status`](../../docs/sources/bicing.md#station_status).
- **Script:** `out_of_service_check.py` counts the rows and stations of each combination of `is_installed`, `is_renting` and `is_returning`, per source. For each change into or out of service (`is_renting` and `is_returning` both false), it records the vehicles available 15 passes before, the pass before and at the change, and the vehicles disabled and the docks available and disabled, the pass before and at the change. A station emptied before closing is already at 0 the pass before; a feed that only reports 0 drops at the change.
- **Output:** `out_of_service.csv`, next to the script, one row per change, and a summary per source on stdout.
- **Run time:** about 35 s.

```text
python3 -I spikes/d005-data-model/out-of-service/out_of_service_check.py spikes/cloudflare-capture-spike/data/V4/raw spikes/d005-data-model/out-of-service/out_of_service.csv
```

## 11. `plus-p/`

- **Question:** which AMBici stations have +P parking, and does it explain why their bikes exceed `capacity`?
- **Evidence for:** [d005 › D17](../../docs/designs/d005-data-model.md#d17-occupancy), and the facts of [AMBici's source card › `nextbike-live.json`](../../docs/sources/ambici.md#nextbike-livejson).
- **Inputs:** nextbike's live feed for AMBici, the data behind the map at `https://www.ambici.cat/ca/mapa/` (public, no key; downloaded 2026-11-12), and `over-capacity/over_capacity.csv` (check 2). Download the feed into `data/` before the run:

  ```text
  curl -s -o spikes/d005-data-model/plus-p/data/nextbike-live.json "https://maps.nextbike.net/maps/nextbike-live.json?domains=bs"
  ```

- **Scripts:**
  - `fields_check.py` profiles every field of the feed: occurrences, types, distinct values, range and most common values.
  - `plus_p_check.py` matches each nextbike place to the GBFS station with the same ID (`uid` = `station_id`) in the latest `station_information`, and per `place_type` counts the stations, those ever over capacity, how often and by how much, and how `bike_racks` compares with `capacity`. The map shows `place_type` 27 and 33 as +P stations (blue) and 14 and 16 as regular ones (red), checked by eye on 4 stations of each.
- **Output:** `fields.txt`, one line per field path; `plus_p.csv`, one row per station; and a summary per `place_type` on stdout.
- **Run time:** under 1 s each.

```text
python3 -I spikes/d005-data-model/plus-p/fields_check.py spikes/d005-data-model/plus-p/data/nextbike-live.json spikes/d005-data-model/plus-p/fields.txt
python3 -I spikes/d005-data-model/plus-p/plus_p_check.py spikes/d005-data-model/plus-p/data/nextbike-live.json spikes/cloudflare-capture-spike/data/V4/raw spikes/d005-data-model/over-capacity/over_capacity.csv spikes/d005-data-model/plus-p/plus_p.csv
```

## 12. `capacity-arithmetic/`

- **Question:** do Bicing's available and disabled vehicles and docks add up to a station's `capacity`, and which hypotheses fit the items where they do not?
- **Evidence for:** the consistency facts of [Bicing's source card › `station_status`](../../docs/sources/bicing.md#station_status).
- **Script:** `capacity_arithmetic.sql` computes, per in-service station item, the four counts minus the station's `capacity`. Over `capacity`, it tests two hypotheses: a disabled vehicle in a disabled dock counted twice (excess at most the lesser of `num_vehicles_disabled` and `num_docks_disabled`), and a vehicle counted as both available and disabled (excess at most the lesser of `num_vehicles_available` and `num_vehicles_disabled`). Under `capacity`, it groups consecutive deficit passes per station into runs and splits them by duration: runs of at most 6 min fit a reservation, longer ones docks counted in no term.
- **Output:** tables on stdout.
- **Run time:** about 10 s.

```text
duckdb -f spikes/d005-data-model/capacity-arithmetic/capacity_arithmetic.sql
```

## 13. `last-reported/`

- **Question:** does a Bicing station whose `last_reported` is old still send new counts?
- **Evidence for:** [d005 › D19](../../docs/designs/d005-data-model.md#d19-last-reported-time-in-the-stock), and the timeliness facts of [Bicing's source card › `station_status`](../../docs/sources/bicing.md#station_status).
- **Script:** `last_reported.sql` computes, per station item, the age of `last_reported` (the response's `last_updated` minus `last_reported`) and whether any of the four counts differs from the station's previous pass. It groups the items by age band, and lists the stations with any item 24 h old or more, with their count changes and status flags in those items.
- **Output:** `last_reported_by_age.csv`, one row per age band; `last_reported_stale.csv`, one row per station; both next to the script.
- **Run time:** about 3 s.

```text
duckdb -f spikes/d005-data-model/last-reported/last_reported.sql
```

## 14. `profile/bicing-historical/`

- **Question:** do Bicing's history archives fit the model as written for the real-time feeds, so that both make one continuous station stock?
  - **P1.** Which columns does each month have, and which real-time field (GBFS 3.0) does each map to? The archive has no disabled vehicles or docks. Evidence for [D3](../../docs/designs/d005-data-model.md#d3-feeds-that-enter-the-model), [D7](../../docs/designs/d005-data-model.md#d7-station-status-flags), [D15](../../docs/designs/d005-data-model.md#d15-disabled-vehicles-and-docks).
  - **P2.** Is there one row per station and snapshot, with every station in each snapshot? Evidence for [D4](../../docs/designs/d005-data-model.md#d4-business-processes-and-the-grain-of-the-stock).
  - **P3.** Are snapshots 5 minutes apart? Evidence for [D4](../../docs/designs/d005-data-model.md#d4-business-processes-and-the-grain-of-the-stock), [D23](../../docs/designs/d005-data-model.md#d23-movements-across-gaps-in-capture).
  - **P4.** Where are the gaps, with the threshold taken from the measured cadence, and do they match those the provider publishes ([Bicing › History](../../docs/sources/bicing.md#history))? Evidence for [D23](../../docs/designs/d005-data-model.md#d23-movements-across-gaps-in-capture).
  - **P5.** Do mechanical and electric bikes add up to `num_bikes_available`? Evidence for [D5](../../docs/designs/d005-data-model.md#d5-conformed-dimensions), [D8](../../docs/designs/d005-data-model.md#d8-vehicle-propulsion).
  - **P6.** Is the archive's `station_id` the real-time one, and does the information series give each station's capacity over time? Evidence for [D5](../../docs/designs/d005-data-model.md#d5-conformed-dimensions).
  - **P7.** Over the overlap with the bronze copy (2026-10-14 to 10-26): for one station and `last_updated`, do the archive and the real-time response give the same counts; and how far apart are a day's departures and arrivals from the archive (5 minutes, available bikes only) and from the real-time feeds (1 minute, available plus disabled)? Evidence for [D3](../../docs/designs/d005-data-model.md#d3-feeds-that-enter-the-model), [D22](../../docs/designs/d005-data-model.md#d22-departures-and-arrivals).
- **Scripts:**
  - `convert.py` extracts one archive at a time, converts its CSV to Parquet in `work/` (every column as text; ignored by Git) and deletes the CSV, so only one CSV of about 1 GB is on disk at once; it resumes an interrupted run. It writes `archives.csv` (one row per archive: bytes, CSV name, columns) and `headers.csv` (one row per archive and column, with its position): P1.
  - `profile.sql` answers P2–P7 over the Parquet files, reading columns by name, since they are added, removed and moved between months; P6 and P7 also read the bronze copy. For P1 it writes the field profile and the raw values of the coded columns; the mapping itself is done by Chat from those, `headers.csv` and [`profile/bicing/`](profile/bicing/), not by a script.
- **Output:** `archives.csv`, `headers.csv`, and `p<N>_<what>.csv` per question of `profile.sql`, next to the scripts.
- **Run time:** about 30 s for `convert.py`, about 1 min for `profile.sql`.

```text
python3 -I spikes/d005-data-model/profile/bicing-historical/convert.py spikes/bicing-spike/historical-data/raw
duckdb -f spikes/d005-data-model/profile/bicing-historical/profile.sql
```
