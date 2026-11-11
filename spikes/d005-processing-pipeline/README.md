# d005 checks

Throwaway checks behind framing decisions of [d005](../../docs/designs/d005-processing-pipeline.md). Both read the capture spike's bronze copy, `spikes/cloudflare-capture-spike/data/V4/raw/` (2026-10-14 to 10-26, not in Git), and use the Python standard library only.

## `free-bike-status/`

Question: does AMBici's `free_bike_status` add anything to `station_status`? Evidence for [d005 › D3](../../docs/designs/d005-processing-pipeline.md#d3-feeds-that-enter-the-model).

- `free_bike_check.py` pairs each pass's two feeds by key and compares, per station, `num_bikes_available` with the bikes placed there, and counts disabled, reserved and station-less bikes. About 80 s.

```text
python3 -I spikes/d005-processing-pipeline/free-bike-status/free_bike_check.py spikes/cloudflare-capture-spike/data/V4/raw/ambici
```

## `post-code/`

Question: how accurately does ICGC's reverse geocoder give a station's post code? Evidence for d005 › Open questions, OQ4.

- `icgc_check.py` samples up to 2 Bicing stations per published post code, asks the public ICGC geocoder for the 5 nearest addresses, one request per second, and writes a CSV comparing the codes, with a doubt flag when those addresses disagree. About 100 s.

```text
python3 -I spikes/d005-processing-pipeline/post-code/icgc_check.py spikes/cloudflare-capture-spike/data/V4/raw <output.csv>
```

## `station-flags/`

Question: what do the station status flags `is_installed`, `is_renting` and `is_returning` carry in each source? Evidence for d005 › Open questions, OQ4.

- `flags_check.py` counts, per source and flag, the values seen in `station_status` and how many stations were ever false; the value of `is_renting` on empty stations and of `is_returning` on full ones; and the rows where those two flags disagree. About 35 s.

```text
python3 -I spikes/d005-processing-pipeline/station-flags/flags_check.py spikes/cloudflare-capture-spike/data/V4/raw
```
