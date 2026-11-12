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
- `ambici/over_capacity.sql` lists, per AMBici station, the passes where available bikes exceed its capacity, with the largest count and the first and last time (UTC), into `over_capacity.csv`. A few seconds.
- `keys_check.py` lists every key path of each feed and the number of files that contain it, marking those missing from some files. It covers what `profile.sql` cannot: its schema detection samples only a few files, since sampling them all runs out of memory in DuckDB 2.0.0 ([duckdb#27806](https://github.com/duckdb/duckdb/issues/27806)). About 80 s.

```text
duckdb -f spikes/d005-data-model/profile/ambici/profile.sql
duckdb -f spikes/d005-data-model/profile/bicing/profile.sql
duckdb -f spikes/d005-data-model/profile/ambici/over_capacity.sql
python3 -I spikes/d005-data-model/profile/keys_check.py spikes/cloudflare-capture-spike/data/V4/raw
```
