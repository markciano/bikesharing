# Bicing historical data — analysis summary (T005)

Generated 2026-10-08T23:04:08Z by `spikes/bicing-historical-analysis/analyse_bicing_historical.py`. Plan: `docs/spikes/s004-bicing-historical-data.md` › Analysis plan.

<!-- BEGIN metric:load -->
## Reconciliation — load

CSV data rows counted by line count (lines − header); Parquet rows by `count(*)` on the Parquet file.

| Month | Series | Parquet file | CSV rows | Parquet rows | Match |
|---|---|---|---|---|---|
| 2026-02 | ESTACIONS | 2026_02_Febrer_BicingNou_ESTACIONS.parquet | 4,358,950 | 4,358,950 | yes |
| 2026-02 | INFORMACIO | 2026_02_Febrer_BicingNou_INFORMACIO.parquet | 4,372,346 | 4,372,346 | yes |
| 2026-03 | ESTACIONS | 2026_03_Marc_BicingNou_ESTACIONS.parquet | 4,804,908 | 4,804,908 | yes |
| 2026-03 | INFORMACIO | 2026_03_Marc_BicingNou_INFORMACIO.parquet | 4,822,141 | 4,822,141 | yes |
| 2026-04 | ESTACIONS | 2026_04_Abril_BicingNou_ESTACIONS.parquet | 4,462,138 | 4,462,138 | yes |
| 2026-04 | INFORMACIO | 2026_04_Abril_BicingNou_INFORMACIO.parquet | 4,479,175 | 4,479,175 | yes |
| 2026-05 | ESTACIONS | 2026_05_Maig_BicingNou_ESTACIONS.parquet | 4,838,444 | 4,838,444 | yes |
| 2026-05 | INFORMACIO | 2026_05_Maig_BicingNou_INFORMACIO.parquet | 4,857,918 | 4,857,918 | yes |
| 2026-06 | ESTACIONS | 2026_06_Juny_BicingNou_ESTACIONS.parquet | 4,666,090 | 4,666,090 | yes |
| 2026-06 | INFORMACIO | 2026_06_Juny_BicingNou_INFORMACIO.parquet | 4,674,359 | 4,674,359 | yes |
| 2026-08 | ESTACIONS | 2026_08_Agost_BicingNou_ESTACIONS.parquet | 3,987,120 | 3,987,120 | yes |
| 2026-08 | INFORMACIO | 2026_08_Agost_BicingNou_INFORMACIO.parquet | 3,987,119 | 3,987,119 | yes |

Parquet files: 12. CSV rows = Parquet rows: 12 of 12.

CSV files left in `work/`: 0.
<!-- END metric:load -->

<!-- BEGIN metric:3a.check -->
## Reconciliation — snapshots and month window

Rows in snapshots = sum of raw rows per snapshot, before deduplication. Rows without a valid `last_updated` (null/`NA`, or not an integer) belong to no snapshot. Rows in snapshots after deduplication = sum of rows per snapshot in 3a (`snapshots.csv`); rows dropped by deduplication as in *Reconciliation — duplicates*; both sums leave out rows in no snapshot. Month window: `last_updated` in [local midnight of the 1st, local midnight of the 1st of the next month), Europe/Madrid; rows outside it are kept.

| Month | Series | CSV rows | Parquet rows | Rows in snapshots | Null/NA last_updated | Unparseable last_updated | Parquet = snapshots | Rows in snapshots after deduplication (3a) | Rows dropped by deduplication | Parquet = 3a + dropped | Snapshots outside window | Rows outside window |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-02 | ESTACIONS | 4,358,950 | 4,358,950 | 4,358,950 | 0 | 0 | yes | 4,358,950 | 0 | yes | 0 | 0 |
| 2026-02 | INFORMACIO | 4,372,346 | 4,372,346 | 4,372,346 | 0 | 0 | yes | 4,372,346 | 0 | yes | 0 | 0 |
| 2026-03 | ESTACIONS | 4,804,908 | 4,804,908 | 4,804,908 | 0 | 0 | yes | 4,804,908 | 0 | yes | 0 | 0 |
| 2026-03 | INFORMACIO | 4,822,141 | 4,822,141 | 4,822,141 | 0 | 0 | yes | 4,822,141 | 0 | yes | 0 | 0 |
| 2026-04 | ESTACIONS | 4,462,138 | 4,462,138 | 4,462,138 | 0 | 0 | yes | 4,462,138 | 0 | yes | 0 | 0 |
| 2026-04 | INFORMACIO | 4,479,175 | 4,479,175 | 4,479,175 | 0 | 0 | yes | 4,479,175 | 0 | yes | 0 | 0 |
| 2026-05 | ESTACIONS | 4,838,444 | 4,838,444 | 4,838,444 | 0 | 0 | yes | 4,827,667 | 10,777 | yes | 0 | 0 |
| 2026-05 | INFORMACIO | 4,857,918 | 4,857,918 | 4,857,918 | 0 | 0 | yes | 4,847,622 | 10,296 | yes | 0 | 0 |
| 2026-06 | ESTACIONS | 4,666,090 | 4,666,090 | 4,666,090 | 0 | 0 | yes | 4,640,678 | 25,412 | yes | 0 | 0 |
| 2026-06 | INFORMACIO | 4,674,359 | 4,674,359 | 4,674,359 | 0 | 0 | yes | 4,647,733 | 26,626 | yes | 0 | 0 |
| 2026-08 | ESTACIONS | 3,987,120 | 3,987,120 | 3,987,120 | 0 | 0 | yes | 3,987,120 | 0 | yes | 0 | 0 |
| 2026-08 | INFORMACIO | 3,987,119 | 3,987,119 | 3,987,119 | 0 | 0 | yes | 3,987,119 | 0 | yes | 0 | 0 |

Parquet rows = rows in snapshots: 12 of 12.

Parquet rows = rows in 3a snapshots + rows dropped by deduplication: 12 of 12.

Snapshots outside the month window:

None.
<!-- END metric:3a.check -->

<!-- BEGIN metric:dedup.check -->
## Reconciliation — duplicates

Common settings › Duplicates, within each snapshot: (1) exact duplicate rows dropped; (2) a station with more than one row keeps the one with the latest `last_reported`; (3) on a tie the station is left out of that snapshot (`INFORMACIO` has no `last_reported`: any station left after (1) is a tie). Metrics 3a (rows per snapshot), 3b, 3c, 6a–6d and 8 (except 8g, which counts before deduplication) read the rows kept.

| Month | Series | Parquet rows | (1) Exact duplicates dropped | (2) Older rows dropped | (3) Tie rows dropped | (3) Stations left out (station × snapshot) | Rows kept | Parquet = kept + dropped |
|---|---|---|---|---|---|---|---|---|
| 2026-02 | ESTACIONS | 4,358,950 | 0 | 0 | 0 | 0 | 4,358,950 | yes |
| 2026-02 | INFORMACIO | 4,372,346 | 0 | 0 | 0 | 0 | 4,372,346 | yes |
| 2026-03 | ESTACIONS | 4,804,908 | 0 | 0 | 0 | 0 | 4,804,908 | yes |
| 2026-03 | INFORMACIO | 4,822,141 | 0 | 0 | 0 | 0 | 4,822,141 | yes |
| 2026-04 | ESTACIONS | 4,462,138 | 0 | 0 | 0 | 0 | 4,462,138 | yes |
| 2026-04 | INFORMACIO | 4,479,175 | 0 | 0 | 0 | 0 | 4,479,175 | yes |
| 2026-05 | ESTACIONS | 4,838,444 | 10,763 | 4 | 10 | 5 | 4,827,667 | yes |
| 2026-05 | INFORMACIO | 4,857,918 | 10,296 | 0 | 0 | 0 | 4,847,622 | yes |
| 2026-06 | ESTACIONS | 4,666,090 | 25,398 | 8 | 6 | 3 | 4,640,678 | yes |
| 2026-06 | INFORMACIO | 4,674,359 | 26,626 | 0 | 0 | 0 | 4,647,733 | yes |
| 2026-08 | ESTACIONS | 3,987,120 | 0 | 0 | 0 | 0 | 3,987,120 | yes |
| 2026-08 | INFORMACIO | 3,987,119 | 0 | 0 | 0 | 0 | 3,987,119 | yes |

Parquet rows = rows kept + rows dropped: 12 of 12.
<!-- END metric:dedup.check -->

<!-- BEGIN metric:3b.example -->
## Example — 3b station reporting interval

2026-02 ESTACIONS (`2026_02_Febrer_BicingNou_ESTACIONS.7z`), station_id 1: the lowest station_id with three consecutive snapshots, neither comparison across a 5b gap, where `last_reported` moves at least once (first such triple). Rows from the deduplicated view.

| CSV line | Snapshot k | last_updated (UTC) | last_reported (UTC) | num_bikes_available | num_bikes_available_types.mechanical | num_bikes_available_types.ebike | num_docks_available |
|---|---|---|---|---|---|---|---|
| 2 | 1 | 2026-01-31T23:00:06Z | 2026-01-31T22:58:00Z | 18 | 6 | 12 | 28 |
| 546 | 2 | 2026-01-31T23:05:03Z | 2026-01-31T23:04:01Z | 18 | 6 | 12 | 28 |
| 1090 | 3 | 2026-01-31T23:10:01Z | 2026-01-31T23:07:01Z | 17 | 6 | 11 | 29 |

Raw CSV lines (line 1 = header):

```text
line 2: 1,18,TRUE,"IN_SERVICE",NA,6,12,28,1769900280,1,1,1,1769900406,0
line 546: 1,18,TRUE,"IN_SERVICE",NA,6,12,28,1769900641,1,1,1,1769900703,0
line 1090: 1,17,TRUE,"IN_SERVICE",NA,6,11,29,1769900821,1,1,1,1769901001,0
```

Raw lines equal their Parquet rows: yes.

- Snapshot 1 → 2: `last_reported` 1769900280 → 1769900641 (interval 361 s); counts unchanged → interval + heartbeat.
- Snapshot 2 → 3: `last_reported` 1769900641 → 1769900821 (interval 180 s); counts changed → interval.
<!-- END metric:3b.example -->

<!-- BEGIN metric:5b.example -->
## Example — 5b gap

2026-02 ESTACIONS (`2026_02_Febrer_BicingNou_ESTACIONS.7z`): the first gap inside a month in `gaps.csv` order. Gap of 2099 s (35.0 min) against a threshold of 600 s.

| Snapshot | last_updated (UTC) | last_updated (local) | Rows | CSV lines |
|---|---|---|---|---|
| Before | 2026-02-19T06:55:06Z | 2026-02-19T07:55:06+01:00 | 542 | 2860859–2861400 |
| After | 2026-02-19T07:30:05Z | 2026-02-19T08:30:05+01:00 | 542 | 2861401–2861942 |

Raw CSV lines (first and last line of each snapshot; line 1 = header):

```text
line 2860859: 1,4,TRUE,"IN_SERVICE",NA,4,0,39,1771484093,1,1,1,1771484106,0
line 2861400: 610,10,TRUE,"IN_SERVICE",NA,4,6,16,1771483935,1,1,1,1771484106,0
line 2861401: 1,1,TRUE,"IN_SERVICE",NA,0,1,42,1771486079,1,1,1,1771486205,0
line 2861942: 610,17,TRUE,"IN_SERVICE",NA,6,11,9,1771486107,1,1,1,1771486205,0
```

Raw lines equal their Parquet rows: yes.
<!-- END metric:5b.example -->

<!-- BEGIN metric:6d.example -->
## Example — 6d station match

Station 1: the lowest station_id in both sides. Archive: 2026-08 INFORMACIO (`2026_08_Agost_BicingNou_INFORMACIO.7z`), last snapshot, deduplicated view. Real time: `spikes/bicing-spike/realtime/raw/station_information/2026-10-05/20261005T141500Z.json.gz`.

| Field | Archive | Real time |
|---|---|---|
| station_id | 1 | 1 |
| external_id | fc540556-eb2f-11ef-896d-0a9e2ea61361 | fc540556-eb2f-11ef-896d-0a9e2ea61361 |
| name | GRAN VIA CORTS CATALANES, 760 | GRAN VIA CORTS CATALANES, 760 |
| lat | 41.3979779 | 41.3979779 |
| lon | 2.1801069 | 2.1801069 |
| capacity | 45 | 45 |
| last_updated (UTC) | 2026-08-31T21:55:04Z | 2026-10-05T14:15:01Z |

Distance: 0.0 m.

Raw archive CSV line (line 1 = header):

```text
line 3986578: 1,"fc540556-eb2f-11ef-896d-0a9e2ea61361","GRAN VIA CORTS CATALANES, 760","ELECTRICBIKESTATION",41.3979779,2.1801069,16,"GRAN VIA CORTS CATALANES, 760","02-Eixample/05-el Fort Pienc",8013,45,TRUE,1,1000,TRUE,NA,1788213304,0
```

Raw line equals its Parquet row: yes.

Real-time station object:

```json
{"vehicle_types_capacity": [], "vehicle_docks_capacity": [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 45}], "station_id": "1", "external_id": "fc540556-eb2f-11ef-896d-0a9e2ea61361", "name": [{"text": "GRAN VIA CORTS CATALANES, 760", "language": "ca"}, {"text": "GRAN VIA CORTS CATALANES, 760", "language": "en"}, {"text": "GRAN VIA CORTS CATALANES, 760", "language": "fr"}, {"text": "GRAN VIA CORTS CATALANES, 760", "language": "nl"}, {"text": "GRAN VIA CORTS CATALANES, 760", "language": "es"}], "lat": 41.3979779, "lon": 2.1801069, "address": "GRAN VIA CORTS CATALANES, 760", "cross_street": "02-Eixample/05-el Fort Pienc", "post_code": "08013", "capacity": 45, "is_charging_station": true, "rental_methods": ["key", "transitcard", "creditcard", "phone"], "is_virtual_station": false, "short_name": [{"text": "1", "language": "ca"}, {"text": "1", "language": "en"}, {"text": "1", "language": "fr"}, {"text": "1", "language": "nl"}, {"text": "1", "language": "es"}], "rental_uris": {}}
```
<!-- END metric:6d.example -->

<!-- BEGIN metric:1a -->
### 1a. Header check

Details per column in `header_check.csv`. Changes are versus the previous month available (the first month of each series has none).

| Month | Series | Columns | Parquet columns = header | Changes |
|---|---|---|---|---|
| 2026-02 | ESTACIONS | 14 | yes | — |
| 2026-02 | INFORMACIO | 18 | yes | — |
| 2026-03 | ESTACIONS | 15 | yes | V1 added |
| 2026-03 | INFORMACIO | 20 | yes | V1 added; external_id added |
| 2026-04 | ESTACIONS | 14 | yes | V1 removed |
| 2026-04 | INFORMACIO | 19 | yes | external_id moved; name moved; physical_configuration moved; lat moved; lon moved; altitude moved; address moved; cross_street moved; post_code moved; capacity moved; is_charging_station moved; short_name moved; nearby_distance moved; x_ride_code_support moved; rental_uris moved; is_valet_station moved; last_updated moved; ttl moved; V1 removed |
| 2026-05 | ESTACIONS | 14 | yes | — |
| 2026-05 | INFORMACIO | 19 | yes | — |
| 2026-06 | ESTACIONS | 14 | yes | — |
| 2026-06 | INFORMACIO | 19 | yes | — |
| 2026-08 | ESTACIONS | 14 | yes | — |
| 2026-08 | INFORMACIO | 18 | yes | last_updated moved; ttl moved; is_valet_station removed |
<!-- END metric:1a -->

<!-- BEGIN metric:1b -->
### 1b. Field profile

`field_profile.csv`: 198 rows (one per month, series and column). Raw spellings counted per column: `NA`, empty, `TRUE`, `FALSE`, `1`, `0` and any other non-null value (`raw_other`); distinct values over the raw text, listed with their counts when ≤ 20; min/max over the typed view.
<!-- END metric:1b -->

<!-- BEGIN metric:1c -->
### 1c. Type stability

Inferred type per column in `header_check.csv` (`inferred_type`, `previous_type`, `type_differs`).

No column changes its inferred type versus the previous month available.
<!-- END metric:1c -->

<!-- BEGIN metric:2a -->
### 2a input. Field comparison

One row per field in `field_comparison.csv`: the union of archive columns (all months) and the real-time field paths of the paired feed, matched literally (real-time station fields without the `data.stations[].` prefix). Archive side as in 1b, over every month that has the column; real-time side copied from `spikes/bicing-spike/analysis/field_profile.csv`.

| Series | Feed | Fields | In both | Archive only | Real-time only | Fields in both |
|---|---|---|---|---|---|---|
| ESTACIONS | station_status | 31 | 8 | 7 | 16 | `station_id`, `num_docks_available`, `last_reported`, `is_installed`, `is_renting`, `is_returning`, `last_updated`, `ttl` |
| INFORMACIO | station_information | 39 | 14 | 6 | 19 | `station_id`, `name`, `lat`, `lon`, `address`, `cross_street`, `post_code`, `capacity`, `is_charging_station`, `short_name`, `rental_uris`, `last_updated`, `ttl`, `external_id` |
<!-- END metric:2a -->

<!-- BEGIN metric:3a -->
### 3a. Snapshot cadence

Snapshot = rows sharing one `last_updated` (typed view). Rows per snapshot counted after deduplication (Common settings › Duplicates). One row per snapshot in `snapshots.csv`. Intervals in seconds, between consecutive snapshots of the same month.

| Month | Series | Snapshots | Rows min | Rows median | Rows max | Interval median (s) | Interval p95 (s) | Interval max (s) |
|---|---|---|---|---|---|---|---|---|
| 2026-02 | ESTACIONS | 8,047 | 534 | 542 | 544 | 300 | 304 | 3,299 |
| 2026-02 | INFORMACIO | 8,043 | 536 | 544 | 546 | 300 | 304 | 3,299 |
| 2026-03 | ESTACIONS | 8,889 | 521 | 542 | 544 | 300 | 304 | 3,898 |
| 2026-03 | INFORMACIO | 8,888 | 523 | 544 | 546 | 300 | 304 | 3,903 |
| 2026-04 | ESTACIONS | 8,248 | 524 | 541 | 544 | 300 | 304 | 96,001 |
| 2026-04 | INFORMACIO | 8,249 | 526 | 543 | 546 | 300 | 304 | 96,002 |
| 2026-05 | ESTACIONS | 8,900 | 534 | 543 | 544 | 300 | 308 | 903 |
| 2026-05 | INFORMACIO | 8,904 | 536 | 545 | 546 | 300 | 308 | 904 |
| 2026-06 | ESTACIONS | 8,582 | 523 | 542 | 543 | 300 | 484 | 1,023 |
| 2026-06 | INFORMACIO | 8,580 | 523 | 542 | 545 | 300 | 483 | 905 |
| 2026-08 | ESTACIONS | 7,374 | 539 | 540 | 544 | 300 | 304 | 77,041 |
| 2026-08 | INFORMACIO | 7,374 | 539 | 540 | 544 | 300 | 304 | 54,302 |
<!-- END metric:3a -->

<!-- BEGIN metric:3b -->
### 3b. Station reporting interval

`ESTACIONS`, deduplicated view. A station is compared between consecutive snapshots of the month when it is in both; an interval (s) is recorded when `last_reported` moved. Heartbeat: `last_reported` moved, counts did not; silent change: counts changed, `last_reported` did not. Counts: `num_bikes_available`, `num_bikes_available_types.mechanical`, `num_bikes_available_types.ebike`, `num_docks_available`. Comparisons whose two snapshots are further apart than the month's 5b threshold (across a gap) are left out of intervals, heartbeats and silent changes and counted apart ("Excluded: across a 5b gap"). One row per station and month in `station_reporting.csv`. Rows with null `last_reported`: 0.

| Month | Station rows | `last_reported` = `last_updated` | Stations | Stations with no interval | Comparisons | Excluded: across a 5b gap | Skipped (station in one snapshot only) | Negative intervals | Station medians: median (s) | p95 (s) | max (s) | Heartbeats | Silent changes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-02 | 4,358,950 | 5,366 (0.12 %) | 544 | 0 | 4,357,308 | 1,083 | 34 | 0 | 361 | 361 | 361 | 2,829,707 | 2,397 |
| 2026-03 | 4,804,908 | 5,897 (0.12 %) | 544 | 0 | 4,801,073 | 3,246 | 97 | 0 | 361 | 361 | 361 | 3,048,010 | 3,464 |
| 2026-04 | 4,462,138 | 5,354 (0.12 %) | 546 | 2 | 4,457,777 | 3,790 | 57 | 0 | 361 | 361 | 361 | 2,722,495 | 3,176 |
| 2026-05 | 4,827,667 | 5,786 (0.12 %) | 546 | 2 | 4,773,573 | 53,517 | 70 | 0 | 361 | 361 | 362 | 2,799,925 | 21,785 |
| 2026-06 | 4,640,678 | 4,795 (0.10 %) | 546 | 2 | 4,517,923 | 122,170 | 89 | 0 | 361 | 361 | 361 | 2,531,610 | 45,453 |
| 2026-08 | 3,987,120 | 4,122 (0.10 %) | 544 | 1 | 3,965,492 | 21,079 | 12 | 0 | 361 | 361 | 362 | 2,483,898 | 2,963 |

| Total | Comparisons | Excluded: across a 5b gap | Skipped | Negative intervals | Heartbeats | Silent changes |
|---|---|---|---|---|---|---|
| All months | 26,873,146 | 204,885 | 359 | 0 | 16,415,645 | 79,238 |
<!-- END metric:3b -->

<!-- BEGIN metric:3c -->
### 3c. `last_updated` vs `last_reported`

`ESTACIONS`, deduplicated view: lag = `last_updated` − `last_reported` per row, in seconds.

| Month | Rows | Median (s) | p95 (s) | Max (s) | Negative |
|---|---|---|---|---|---|
| 2026-02 | 4,358,950 | 91 | 173 | 128,454 | 0 (0.00 %) |
| 2026-03 | 4,804,908 | 91 | 173 | 773,001 | 0 (0.00 %) |
| 2026-04 | 4,462,138 | 91 | 173 | 27,867,646 | 0 (0.00 %) |
| 2026-05 | 4,827,667 | 92 | 174 | 30,546,048 | 0 (0.00 %) |
| 2026-06 | 4,640,678 | 92 | 174 | 1,781,783,405 | 0 (0.00 %) |
| 2026-08 | 3,987,120 | 92 | 174 | 38,494,848 | 0 (0.00 %) |
<!-- END metric:3c -->

<!-- BEGIN metric:3d -->
### 3d. `ttl`

Raw values, all rows.

| Month | Series | Values |
|---|---|---|
| 2026-02 | ESTACIONS | `0` (4,358,950 rows) |
| 2026-02 | INFORMACIO | `0` (4,372,346 rows) |
| 2026-03 | ESTACIONS | `0` (4,804,908 rows) |
| 2026-03 | INFORMACIO | `0` (4,822,141 rows) |
| 2026-04 | ESTACIONS | `0` (4,462,138 rows) |
| 2026-04 | INFORMACIO | `0` (4,479,175 rows) |
| 2026-05 | ESTACIONS | `0` (4,838,444 rows) |
| 2026-05 | INFORMACIO | `0` (4,857,918 rows) |
| 2026-06 | ESTACIONS | `0` (4,666,090 rows) |
| 2026-06 | INFORMACIO | `0` (4,674,359 rows) |
| 2026-08 | ESTACIONS | `0` (3,987,120 rows) |
| 2026-08 | INFORMACIO | `0` (3,987,119 rows) |
<!-- END metric:3d -->

<!-- BEGIN metric:5b -->
### 5b. Gaps inside a month

Gap: interval between consecutive snapshots greater than the threshold (2 × the month's median interval, 3a); also the range from local midnight at the start of the month to the first snapshot, and from the last snapshot to local midnight at the end of the month, when longer than the threshold. One row per gap in `gaps.csv`.

| Month | Series | Threshold (s) | Gaps inside | Inside total (min) | Longest inside (min) | Start of month (min) | End of month (min) |
|---|---|---|---|---|---|---|---|
| 2026-02 | ESTACIONS | 600 | 2 | 90.0 | 55.0 | — | — |
| 2026-02 | INFORMACIO | 600 | 2 | 90.0 | 55.0 | — | — |
| 2026-03 | ESTACIONS | 600 | 6 | 152.0 | 65.0 | — | — |
| 2026-03 | INFORMACIO | 600 | 7 | 162.3 | 65.0 | — | — |
| 2026-04 | ESTACIONS | 600 | 7 | 1,982.9 | 1,600.0 | — | — |
| 2026-04 | INFORMACIO | 600 | 5 | 1,962.8 | 1,600.0 | — | — |
| 2026-05 | ESTACIONS | 600 | 99 | 1,136.2 | 15.1 | — | — |
| 2026-05 | INFORMACIO | 600 | 91 | 1,037.4 | 15.1 | — | — |
| 2026-06 | ESTACIONS | 600 | 226 | 2,678.2 | 17.1 | — | — |
| 2026-06 | INFORMACIO | 600 | 213 | 2,473.8 | 15.1 | — | — |
| 2026-08 | ESTACIONS | 600 | 39 | 7,385.2 | 1,284.0 | 571.0 | — |
| 2026-08 | INFORMACIO | 600 | 30 | 7,333.9 | 905.0 | 571.0 | — |
<!-- END metric:5b -->

<!-- BEGIN metric:5c -->
### 5c. Month cut

| Month | Series | First (UTC) | First (local) | Last (UTC) | Last (local) |
|---|---|---|---|---|---|
| 2026-02 | ESTACIONS | 2026-01-31T23:00:06Z | 2026-02-01T00:00:06+01:00 | 2026-02-28T22:55:04Z | 2026-02-28T23:55:04+01:00 |
| 2026-02 | INFORMACIO | 2026-01-31T23:00:04Z | 2026-02-01T00:00:04+01:00 | 2026-02-28T22:55:07Z | 2026-02-28T23:55:07+01:00 |
| 2026-03 | ESTACIONS | 2026-02-28T23:00:08Z | 2026-03-01T00:00:08+01:00 | 2026-03-31T21:55:02Z | 2026-03-31T23:55:02+02:00 |
| 2026-03 | INFORMACIO | 2026-02-28T23:00:06Z | 2026-03-01T00:00:06+01:00 | 2026-03-31T21:55:05Z | 2026-03-31T23:55:05+02:00 |
| 2026-04 | ESTACIONS | 2026-03-31T22:00:01Z | 2026-04-01T00:00:01+02:00 | 2026-04-30T21:55:02Z | 2026-04-30T23:55:02+02:00 |
| 2026-04 | INFORMACIO | 2026-03-31T22:00:05Z | 2026-04-01T00:00:05+02:00 | 2026-04-30T21:55:00Z | 2026-04-30T23:55:00+02:00 |
| 2026-05 | ESTACIONS | 2026-04-30T22:00:00Z | 2026-05-01T00:00:00+02:00 | 2026-05-31T21:55:04Z | 2026-05-31T23:55:04+02:00 |
| 2026-05 | INFORMACIO | 2026-04-30T22:00:02Z | 2026-05-01T00:00:02+02:00 | 2026-05-31T21:58:05Z | 2026-05-31T23:58:05+02:00 |
| 2026-06 | ESTACIONS | 2026-05-31T22:03:01Z | 2026-06-01T00:03:01+02:00 | 2026-06-30T21:55:01Z | 2026-06-30T23:55:01+02:00 |
| 2026-06 | INFORMACIO | 2026-05-31T22:05:03Z | 2026-06-01T00:05:03+02:00 | 2026-06-30T21:55:03Z | 2026-06-30T23:55:03+02:00 |
| 2026-08 | ESTACIONS | 2026-08-01T07:31:02Z | 2026-08-01T09:31:02+02:00 | 2026-08-31T21:55:04Z | 2026-08-31T23:55:04+02:00 |
| 2026-08 | INFORMACIO | 2026-08-01T07:31:02Z | 2026-08-01T09:31:02+02:00 | 2026-08-31T21:55:04Z | 2026-08-31T23:55:04+02:00 |
<!-- END metric:5c -->

<!-- BEGIN metric:6a -->
### 6a. Station set

Distinct `station_id` per month and series, deduplicated view. Added / removed: versus the previous month available of the same series (the first month has none).

| Month | Series | Stations | Min ID | Max ID | Added | Removed |
|---|---|---|---|---|---|---|
| 2026-02 | ESTACIONS | 544 | 1 | 610 |  |  |
| 2026-03 | ESTACIONS | 544 | 1 | 610 | 107, 536 | 56, 509 |
| 2026-04 | ESTACIONS | 546 | 1 | 610 | 366, 509 | — |
| 2026-05 | ESTACIONS | 546 | 1 | 610 | 317 | 104 |
| 2026-06 | ESTACIONS | 546 | 1 | 614 | 585, 614 | 526, 536 |
| 2026-08 | ESTACIONS | 544 | 1 | 614 | 526 | 133, 246, 585 |
| 2026-02 | INFORMACIO | 546 | 1 | 610 |  |  |
| 2026-03 | INFORMACIO | 546 | 1 | 610 | 107, 536 | 56, 509 |
| 2026-04 | INFORMACIO | 548 | 1 | 610 | 366, 509 | — |
| 2026-05 | INFORMACIO | 548 | 1 | 610 | 317 | 104 |
| 2026-06 | INFORMACIO | 548 | 1 | 614 | 585, 614 | 526, 536 |
| 2026-08 | INFORMACIO | 544 | 1 | 614 | 526 | 133, 246, 542, 543, 585 |
<!-- END metric:6a -->

<!-- BEGIN metric:6b -->
### 6b. Information ↔ status match

Per `ESTACIONS` snapshot, the latest `INFORMACIO` snapshot at or before it (as-of join over every month available, so it may belong to an earlier month), both deduplicated. "Status only": station in the status snapshot but not in its information snapshot; "information only": the reverse. Pairs = station × status snapshot.

| Month | Status snapshots | No information at or before | Information from an earlier month | Information at the same `last_updated` | Snapshots with a mismatch | Status only (pairs) | Status only (stations) | Information only (pairs) | Information only (stations) |
|---|---|---|---|---|---|---|---|---|---|
| 2026-02 | 8,047 | 0 | 0 | 1,536 | 8,047 | 521 | 34 | 16,104 | 12 |
| 2026-03 | 8,889 | 0 | 0 | 2,057 | 8,889 | 16 | 16 | 17,787 | 11 |
| 2026-04 | 8,248 | 0 | 1 | 1,936 | 8,248 | 16 | 16 | 16,508 | 14 |
| 2026-05 | 8,900 | 0 | 1 | 1,893 | 8,900 | 14 | 9 | 17,817 | 17 |
| 2026-06 | 8,582 | 0 | 2 | 1,583 | 4,101 | 21 | 18 | 8,202 | 23 |
| 2026-08 | 7,374 | 0 | 0 | 1,603 | 3 | 3 | 3 | 0 | 0 |

Station IDs, with the number of status snapshots affected:

| Month | Side | Station IDs (snapshots) |
|---|---|---|
| 2026-02 | status only | 3 (22), 4 (38), 10 (6), 72 (18), 76 (11), 105 (1), 110 (4), 112 (33), 125 (8), 127 (9), 170 (7), 171 (27), 199 (7), 206 (40), 241 (24), 335 (1), 354 (36), 394 (13), 409 (6), 411 (9), 432 (11), 447 (13), 477 (39), 509 (6), 539 (5), 540 (19), 541 (28), 572 (9), 581 (30), 598 (1), 600 (27), 604 (5), 608 (2), 609 (6) |
| 2026-02 | information only | 7 (1), 8 (1), 56 (1), 62 (1), 158 (1), 159 (1), 173 (1), 309 (1), 335 (1), 411 (1), 542 (8047), 543 (8047) |
| 2026-03 | status only | 7 (1), 62 (1), 63 (1), 94 (1), 104 (1), 107 (1), 151 (1), 237 (1), 380 (1), 395 (1), 511 (1), 526 (1), 527 (1), 537 (1), 538 (1), 602 (1) |
| 2026-03 | information only | 118 (1), 264 (1), 395 (1), 511 (1), 526 (1), 527 (1), 536 (1), 537 (1), 538 (1), 542 (8889), 543 (8889) |
| 2026-04 | status only | 60 (1), 64 (1), 65 (1), 66 (1), 92 (1), 246 (1), 287 (1), 309 (1), 364 (1), 374 (1), 394 (1), 496 (1), 509 (1), 510 (1), 511 (1), 536 (1) |
| 2026-04 | information only | 60 (1), 68 (1), 238 (1), 246 (1), 295 (1), 364 (1), 395 (1), 494 (1), 496 (1), 510 (1), 511 (1), 536 (1), 542 (8248), 543 (8248) |
| 2026-05 | status only | 8 (2), 62 (1), 63 (1), 83 (1), 179 (3), 346 (3), 461 (1), 464 (1), 536 (1) |
| 2026-05 | information only | 25 (1), 34 (1), 63 (1), 82 (1), 128 (1), 179 (1), 189 (1), 213 (1), 231 (1), 346 (1), 371 (1), 380 (1), 508 (1), 526 (1), 536 (3), 542 (8900), 543 (8900) |
| 2026-06 | status only | 31 (1), 32 (1), 33 (1), 96 (1), 149 (1), 170 (1), 173 (1), 224 (1), 270 (1), 309 (1), 370 (1), 398 (1), 424 (1), 427 (1), 465 (1), 537 (3), 538 (2), 585 (1) |
| 2026-06 | information only | 6 (1), 12 (1), 18 (2), 19 (2), 32 (2), 121 (1), 124 (1), 143 (1), 224 (1), 265 (1), 370 (1), 374 (2), 397 (1), 398 (1), 400 (1), 406 (1), 455 (1), 465 (2), 527 (1), 537 (1), 538 (1), 542 (4088), 543 (4088) |
| 2026-08 | status only | 106 (1), 229 (1), 394 (1) |
<!-- END metric:6b -->

<!-- BEGIN metric:6c -->
### 6c. Attribute stability

`INFORMACIO`, deduplicated view. A change: a station's name, coordinates (lat, lon) or `capacity` differs from its previous snapshot in the month (within month), or its first snapshot of a month differs from its last snapshot of the previous month available (between months, listed under the later month). One row per change in `station_changes.csv` (1,129 rows).

| Month | Kind | Attribute | Changes | Stations |
|---|---|---|---|---|
| 2026-02 | within month | capacity | 182 | 42 |
| 2026-02 | within month | name | 1 | 1 |
| 2026-03 | within month | capacity | 151 | 46 |
| 2026-03 | within month | coordinates | 2 | 2 |
| 2026-03 | within month | name | 13 | 8 |
| 2026-04 | within month | capacity | 172 | 51 |
| 2026-04 | within month | coordinates | 2 | 2 |
| 2026-04 | within month | name | 3 | 2 |
| 2026-05 | within month | capacity | 173 | 63 |
| 2026-05 | within month | coordinates | 6 | 5 |
| 2026-05 | within month | name | 4 | 4 |
| 2026-06 | within month | capacity | 169 | 54 |
| 2026-06 | within month | coordinates | 1 | 1 |
| 2026-06 | within month | name | 1 | 1 |
| 2026-08 | between months | capacity | 29 | 29 |
| 2026-08 | within month | capacity | 220 | 70 |
<!-- END metric:6c -->

<!-- BEGIN metric:6d -->
### 6d. Match with the real-time feed

Last `INFORMACIO` snapshot of 2026-08 (`last_updated` 2026-08-31T21:55:04Z, deduplicated view) against the real-time response `spikes/bicing-spike/realtime/raw/station_information/2026-10-05/20261005T141500Z.json.gz`. IDs compared as text. Same name: the archive name equals the text of every language of the real-time name. Distance: haversine, mean Earth radius 6,371,008.8 m. One row per station ID in `station_match.csv`.

| Measure | Value |
|---|---|
| Station IDs in the archive | 543 |
| Station IDs in real time | 543 |
| In both | 541 |
| Archive only | 2: 292, 508 |
| Real-time only | 2: 46, 245 |
| Shared: different `external_id` | 0: — |
| Shared: different name | 1: 507 |
| Shared: different `capacity` | 51: 2, 7, 13, 14, 42, 55, 64, 66, 67, 69, 77, 79, 84, 94, 97, 116, 121, 159, 163, 164, 167, 170, 186, 188, 194, 208, 214, 216, 229, 238, 256, 262, 266, 272, 274, 288, 314, 323, 324, 325, 341, 361, 370, 395, 415, 462, 497, 500, 501, 540, 581 |
| Shared: distance median / p95 / max (m) | 0.0 / 0.0 / 0.0 |
| Shared: distance > 50 m | 0 |
| Real-time stations whose name differs between languages | 0 |
<!-- END metric:6d -->

<!-- BEGIN metric:7a -->
### 7a. Size per month

| Month | Series | .7z bytes | CSV bytes | Data rows |
|---|---|---|---|---|
| 2026-02 | ESTACIONS | 18,997,508 | 280,306,240 | 4,358,950 |
| 2026-02 | INFORMACIO | 7,906,959 | 796,289,229 | 4,372,346 |
| 2026-03 | ESTACIONS | 21,561,252 | 323,298,255 | 4,804,908 |
| 2026-03 | INFORMACIO | 8,800,125 | 912,761,131 | 4,822,141 |
| 2026-04 | ESTACIONS | 20,331,187 | 286,959,369 | 4,462,138 |
| 2026-04 | INFORMACIO | 8,201,896 | 991,740,938 | 4,479,175 |
| 2026-05 | ESTACIONS | 22,163,129 | 310,990,806 | 4,838,444 |
| 2026-05 | INFORMACIO | 8,934,088 | 1,075,651,855 | 4,857,918 |
| 2026-06 | ESTACIONS | 21,317,611 | 299,478,322 | 4,666,090 |
| 2026-06 | INFORMACIO | 8,608,436 | 1,034,886,242 | 4,674,359 |
| 2026-08 | ESTACIONS | 17,984,361 | 256,371,890 | 3,987,120 |
| 2026-08 | INFORMACIO | 7,253,944 | 870,923,441 | 3,987,119 |
<!-- END metric:7a -->

<!-- BEGIN metric:7b -->
### 7b. Size per snapshot

| Month | Series | Snapshots | CSV bytes per snapshot | Parquet bytes |
|---|---|---|---|---|
| 2026-02 | ESTACIONS | 8,047 | 34,833.6 | 27,619,348 |
| 2026-02 | INFORMACIO | 8,043 | 99,004.0 | 7,503,504 |
| 2026-03 | ESTACIONS | 8,889 | 36,370.6 | 30,586,373 |
| 2026-03 | INFORMACIO | 8,888 | 102,695.9 | 8,039,939 |
| 2026-04 | ESTACIONS | 8,248 | 34,791.4 | 28,933,169 |
| 2026-04 | INFORMACIO | 8,249 | 120,225.6 | 9,981,853 |
| 2026-05 | ESTACIONS | 8,900 | 34,942.8 | 30,491,119 |
| 2026-05 | INFORMACIO | 8,904 | 120,805.5 | 9,012,207 |
| 2026-06 | ESTACIONS | 8,582 | 34,896.1 | 29,783,032 |
| 2026-06 | INFORMACIO | 8,580 | 120,616.1 | 9,154,645 |
| 2026-08 | ESTACIONS | 7,374 | 34,767.0 | 24,995,069 |
| 2026-08 | INFORMACIO | 7,374 | 118,107.3 | 7,167,290 |

Median across months of CSV bytes per snapshot:

| Series | Median CSV bytes per snapshot |
|---|---|
| ESTACIONS | 34,864.9 |
| INFORMACIO | 119,166.5 |
<!-- END metric:7b -->

<!-- BEGIN metric:8a -->
### 8a. Over capacity

Series: ESTACIONS. `num_bikes_available` + `num_docks_available` > `capacity`, with `capacity` from the as-of `INFORMACIO` snapshot (as in 6b). Rows whose station has no capacity there are counted apart. Deduplicated view unless stated; % of rows checked.

**8a. Over capacity:** 39 affected rows of 27,081,461 checked (0.00 %), 39 snapshots, 32 stations (variants counted apart excluded; snapshots summed over months and series).

| Variant | Series | Month | Rows checked | Affected rows | % | Snapshots | Stations |
|---|---|---|---|---|---|---|---|
| over capacity | ESTACIONS | 2026-02 | 4,358,950 | 3 | 0.00 | 3 | 3 |
| over capacity | ESTACIONS | 2026-03 | 4,804,908 | 9 | 0.00 | 9 | 8 |
| over capacity | ESTACIONS | 2026-04 | 4,462,138 | 1 | 0.00 | 1 | 1 |
| over capacity | ESTACIONS | 2026-05 | 4,827,667 | 9 | 0.00 | 9 | 7 |
| over capacity | ESTACIONS | 2026-06 | 4,640,678 | 4 | 0.00 | 4 | 4 |
| over capacity | ESTACIONS | 2026-08 | 3,987,120 | 13 | 0.00 | 13 | 10 |
| no capacity (counted apart) | ESTACIONS | 2026-02 | 4,358,950 | 521 | 0.01 | 408 | 34 |
| no capacity (counted apart) | ESTACIONS | 2026-03 | 4,804,908 | 16 | 0.00 | 12 | 16 |
| no capacity (counted apart) | ESTACIONS | 2026-04 | 4,462,138 | 16 | 0.00 | 13 | 16 |
| no capacity (counted apart) | ESTACIONS | 2026-05 | 4,827,667 | 14 | 0.00 | 10 | 9 |
| no capacity (counted apart) | ESTACIONS | 2026-06 | 4,640,678 | 21 | 0.00 | 15 | 18 |
| no capacity (counted apart) | ESTACIONS | 2026-08 | 3,987,120 | 3 | 0.00 | 3 | 3 |
<!-- END metric:8a -->

<!-- BEGIN metric:8b -->
### 8b. Negative counts

Series: ESTACIONS. Any of the four `num_*` counts < 0; one variant per count. Deduplicated view unless stated; % of rows checked.

**8b. Negative counts:** 0 affected rows of 27,081,461 checked (0.00 %), 0 snapshots, 0 stations (variants counted apart excluded; snapshots summed over months and series).

| Variant | Series | Month | Rows checked | Affected rows | % | Snapshots | Stations |
|---|---|---|---|---|---|---|---|
| num_bikes_available < 0 | ESTACIONS | 2026-02 | 4,358,950 | 0 | 0.00 | 0 | 0 |
| num_bikes_available < 0 | ESTACIONS | 2026-03 | 4,804,908 | 0 | 0.00 | 0 | 0 |
| num_bikes_available < 0 | ESTACIONS | 2026-04 | 4,462,138 | 0 | 0.00 | 0 | 0 |
| num_bikes_available < 0 | ESTACIONS | 2026-05 | 4,827,667 | 0 | 0.00 | 0 | 0 |
| num_bikes_available < 0 | ESTACIONS | 2026-06 | 4,640,678 | 0 | 0.00 | 0 | 0 |
| num_bikes_available < 0 | ESTACIONS | 2026-08 | 3,987,120 | 0 | 0.00 | 0 | 0 |
| num_bikes_available_types.mechanical < 0 | ESTACIONS | 2026-02 | 4,358,950 | 0 | 0.00 | 0 | 0 |
| num_bikes_available_types.mechanical < 0 | ESTACIONS | 2026-03 | 4,804,908 | 0 | 0.00 | 0 | 0 |
| num_bikes_available_types.mechanical < 0 | ESTACIONS | 2026-04 | 4,462,138 | 0 | 0.00 | 0 | 0 |
| num_bikes_available_types.mechanical < 0 | ESTACIONS | 2026-05 | 4,827,667 | 0 | 0.00 | 0 | 0 |
| num_bikes_available_types.mechanical < 0 | ESTACIONS | 2026-06 | 4,640,678 | 0 | 0.00 | 0 | 0 |
| num_bikes_available_types.mechanical < 0 | ESTACIONS | 2026-08 | 3,987,120 | 0 | 0.00 | 0 | 0 |
| num_bikes_available_types.ebike < 0 | ESTACIONS | 2026-02 | 4,358,950 | 0 | 0.00 | 0 | 0 |
| num_bikes_available_types.ebike < 0 | ESTACIONS | 2026-03 | 4,804,908 | 0 | 0.00 | 0 | 0 |
| num_bikes_available_types.ebike < 0 | ESTACIONS | 2026-04 | 4,462,138 | 0 | 0.00 | 0 | 0 |
| num_bikes_available_types.ebike < 0 | ESTACIONS | 2026-05 | 4,827,667 | 0 | 0.00 | 0 | 0 |
| num_bikes_available_types.ebike < 0 | ESTACIONS | 2026-06 | 4,640,678 | 0 | 0.00 | 0 | 0 |
| num_bikes_available_types.ebike < 0 | ESTACIONS | 2026-08 | 3,987,120 | 0 | 0.00 | 0 | 0 |
| num_docks_available < 0 | ESTACIONS | 2026-02 | 4,358,950 | 0 | 0.00 | 0 | 0 |
| num_docks_available < 0 | ESTACIONS | 2026-03 | 4,804,908 | 0 | 0.00 | 0 | 0 |
| num_docks_available < 0 | ESTACIONS | 2026-04 | 4,462,138 | 0 | 0.00 | 0 | 0 |
| num_docks_available < 0 | ESTACIONS | 2026-05 | 4,827,667 | 0 | 0.00 | 0 | 0 |
| num_docks_available < 0 | ESTACIONS | 2026-06 | 4,640,678 | 0 | 0.00 | 0 | 0 |
| num_docks_available < 0 | ESTACIONS | 2026-08 | 3,987,120 | 0 | 0.00 | 0 | 0 |
<!-- END metric:8b -->

<!-- BEGIN metric:8c -->
### 8c. Type breakdown mismatch

Series: ESTACIONS. `num_bikes_available_types.mechanical` + `.ebike` ≠ `num_bikes_available`; rows with a null breakdown counted apart. Deduplicated view unless stated; % of rows checked.

**8c. Type breakdown mismatch:** 53,162 affected rows of 27,081,461 checked (0.20 %), 28,988 snapshots, 539 stations (variants counted apart excluded; snapshots summed over months and series).

| Variant | Series | Month | Rows checked | Affected rows | % | Snapshots | Stations |
|---|---|---|---|---|---|---|---|
| mismatch | ESTACIONS | 2026-02 | 4,358,950 | 7,049 | 0.16 | 3,906 | 301 |
| mismatch | ESTACIONS | 2026-03 | 4,804,908 | 12,386 | 0.26 | 5,906 | 288 |
| mismatch | ESTACIONS | 2026-04 | 4,462,138 | 6,787 | 0.15 | 4,122 | 268 |
| mismatch | ESTACIONS | 2026-05 | 4,827,667 | 9,129 | 0.19 | 5,370 | 279 |
| mismatch | ESTACIONS | 2026-06 | 4,640,678 | 8,829 | 0.19 | 6,027 | 239 |
| mismatch | ESTACIONS | 2026-08 | 3,987,120 | 8,982 | 0.23 | 3,657 | 272 |
| null breakdown (counted apart) | ESTACIONS | 2026-02 | 4,358,950 | 0 | 0.00 | 0 | 0 |
| null breakdown (counted apart) | ESTACIONS | 2026-03 | 4,804,908 | 0 | 0.00 | 0 | 0 |
| null breakdown (counted apart) | ESTACIONS | 2026-04 | 4,462,138 | 0 | 0.00 | 0 | 0 |
| null breakdown (counted apart) | ESTACIONS | 2026-05 | 4,827,667 | 0 | 0.00 | 0 | 0 |
| null breakdown (counted apart) | ESTACIONS | 2026-06 | 4,640,678 | 0 | 0.00 | 0 | 0 |
| null breakdown (counted apart) | ESTACIONS | 2026-08 | 3,987,120 | 0 | 0.00 | 0 | 0 |
<!-- END metric:8c -->

<!-- BEGIN metric:8d -->
### 8d. Stale station

Series: ESTACIONS. `is_installed` true and `last_reported` more than 24 h (86,400 s) before `last_updated`. Deduplicated view unless stated; % of rows checked.

**8d. Stale station:** 46,515 affected rows of 27,081,461 checked (0.17 %), 29,161 snapshots, 20 stations (variants counted apart excluded; snapshots summed over months and series).

| Variant | Series | Month | Rows checked | Affected rows | % | Snapshots | Stations |
|---|---|---|---|---|---|---|---|
| stale | ESTACIONS | 2026-02 | 4,358,950 | 141 | 0.00 | 141 | 1 |
| stale | ESTACIONS | 2026-03 | 4,804,908 | 331 | 0.01 | 327 | 11 |
| stale | ESTACIONS | 2026-04 | 4,462,138 | 6,796 | 0.15 | 3,837 | 6 |
| stale | ESTACIONS | 2026-05 | 4,827,667 | 18,851 | 0.39 | 8,900 | 3 |
| stale | ESTACIONS | 2026-06 | 4,640,678 | 13,022 | 0.28 | 8,582 | 6 |
| stale | ESTACIONS | 2026-08 | 3,987,120 | 7,374 | 0.18 | 7,374 | 1 |
<!-- END metric:8d -->

<!-- BEGIN metric:8e -->
### 8e. Future timestamp

Series: ESTACIONS. `last_reported` later than `last_updated` + 60 s. Deduplicated view unless stated; % of rows checked.

**8e. Future timestamp:** 0 affected rows of 27,081,461 checked (0.00 %), 0 snapshots, 0 stations (variants counted apart excluded; snapshots summed over months and series).

| Variant | Series | Month | Rows checked | Affected rows | % | Snapshots | Stations |
|---|---|---|---|---|---|---|---|
| future | ESTACIONS | 2026-02 | 4,358,950 | 0 | 0.00 | 0 | 0 |
| future | ESTACIONS | 2026-03 | 4,804,908 | 0 | 0.00 | 0 | 0 |
| future | ESTACIONS | 2026-04 | 4,462,138 | 0 | 0.00 | 0 | 0 |
| future | ESTACIONS | 2026-05 | 4,827,667 | 0 | 0.00 | 0 | 0 |
| future | ESTACIONS | 2026-06 | 4,640,678 | 0 | 0.00 | 0 | 0 |
| future | ESTACIONS | 2026-08 | 3,987,120 | 0 | 0.00 | 0 | 0 |
<!-- END metric:8e -->

<!-- BEGIN metric:8f -->
### 8f. Inactive stations

Series: ESTACIONS. `is_installed`, `is_renting` or `is_returning` false; `status` other than `IN_SERVICE`. Deduplicated view unless stated; % of rows checked.

**8f. Inactive stations:** 231,881 affected rows of 27,081,461 checked (0.86 %), 41,387 snapshots, 548 stations (variants counted apart excluded; snapshots summed over months and series).

| Variant | Series | Month | Rows checked | Affected rows | % | Snapshots | Stations |
|---|---|---|---|---|---|---|---|
| is_installed false | ESTACIONS | 2026-02 | 4,358,950 | 0 | 0.00 | 0 | 0 |
| is_installed false | ESTACIONS | 2026-03 | 4,804,908 | 37 | 0.00 | 37 | 1 |
| is_installed false | ESTACIONS | 2026-04 | 4,462,138 | 0 | 0.00 | 0 | 0 |
| is_installed false | ESTACIONS | 2026-05 | 4,827,667 | 0 | 0.00 | 0 | 0 |
| is_installed false | ESTACIONS | 2026-06 | 4,640,678 | 0 | 0.00 | 0 | 0 |
| is_installed false | ESTACIONS | 2026-08 | 3,987,120 | 0 | 0.00 | 0 | 0 |
| is_renting false | ESTACIONS | 2026-02 | 4,358,950 | 136,905 | 3.14 | 4,563 | 543 |
| is_renting false | ESTACIONS | 2026-03 | 4,804,908 | 12,993 | 0.27 | 6,042 | 293 |
| is_renting false | ESTACIONS | 2026-04 | 4,462,138 | 14,274 | 0.32 | 5,926 | 275 |
| is_renting false | ESTACIONS | 2026-05 | 4,827,667 | 28,016 | 0.58 | 8,900 | 284 |
| is_renting false | ESTACIONS | 2026-06 | 4,640,678 | 22,679 | 0.49 | 8,582 | 244 |
| is_renting false | ESTACIONS | 2026-08 | 3,987,120 | 17,014 | 0.43 | 7,374 | 284 |
| is_returning false | ESTACIONS | 2026-02 | 4,358,950 | 7,804 | 0.18 | 4,252 | 307 |
| is_returning false | ESTACIONS | 2026-03 | 4,804,908 | 12,993 | 0.27 | 6,042 | 293 |
| is_returning false | ESTACIONS | 2026-04 | 4,462,138 | 14,274 | 0.32 | 5,926 | 275 |
| is_returning false | ESTACIONS | 2026-05 | 4,827,667 | 28,016 | 0.58 | 8,900 | 284 |
| is_returning false | ESTACIONS | 2026-06 | 4,640,678 | 22,574 | 0.49 | 8,582 | 243 |
| is_returning false | ESTACIONS | 2026-08 | 3,987,120 | 16,939 | 0.42 | 7,374 | 279 |
| status other than IN_SERVICE | ESTACIONS | 2026-02 | 4,358,950 | 7,804 | 0.18 | 4,252 | 307 |
| status other than IN_SERVICE | ESTACIONS | 2026-03 | 4,804,908 | 12,993 | 0.27 | 6,042 | 293 |
| status other than IN_SERVICE | ESTACIONS | 2026-04 | 4,462,138 | 14,274 | 0.32 | 5,926 | 275 |
| status other than IN_SERVICE | ESTACIONS | 2026-05 | 4,827,667 | 28,016 | 0.58 | 8,900 | 284 |
| status other than IN_SERVICE | ESTACIONS | 2026-06 | 4,640,678 | 22,574 | 0.49 | 8,582 | 243 |
| status other than IN_SERVICE | ESTACIONS | 2026-08 | 3,987,120 | 16,939 | 0.42 | 7,374 | 279 |
<!-- END metric:8f -->

<!-- BEGIN metric:8g -->
### 8g. Duplicate ID

Series: both. Same `station_id` more than once in one snapshot, before deduplication (Common settings › Duplicates), per (snapshot, station): exact duplicate (at least one exact copy), latest `last_reported` kept, tie (station left out). A (snapshot, station) can fall in more than one variant. Affected rows = every raw row of those (snapshot, station) pairs. Deduplicated view unless stated; % of rows checked.

**8g. Duplicate ID:** 145,666 affected rows of 54,310,708 checked (0.27 %), 134 snapshots, 546 stations (variants counted apart excluded; snapshots summed over months and series).

| Variant | Series | Month | Rows checked | Affected rows | % | Snapshots | Stations |
|---|---|---|---|---|---|---|---|
| exact duplicate | ESTACIONS | 2026-02 | 4,358,950 | 0 | 0.00 | 0 | 0 |
| exact duplicate | ESTACIONS | 2026-03 | 4,804,908 | 0 | 0.00 | 0 | 0 |
| exact duplicate | ESTACIONS | 2026-04 | 4,462,138 | 0 | 0.00 | 0 | 0 |
| exact duplicate | ESTACIONS | 2026-05 | 4,838,444 | 20,986 | 0.43 | 19 | 544 |
| exact duplicate | ESTACIONS | 2026-06 | 4,666,090 | 50,796 | 1.09 | 47 | 544 |
| exact duplicate | ESTACIONS | 2026-08 | 3,987,120 | 0 | 0.00 | 0 | 0 |
| exact duplicate | INFORMACIO | 2026-02 | 4,372,346 | 0 | 0.00 | 0 | 0 |
| exact duplicate | INFORMACIO | 2026-03 | 4,822,141 | 0 | 0.00 | 0 | 0 |
| exact duplicate | INFORMACIO | 2026-04 | 4,479,175 | 0 | 0.00 | 0 | 0 |
| exact duplicate | INFORMACIO | 2026-05 | 4,857,918 | 20,592 | 0.42 | 19 | 546 |
| exact duplicate | INFORMACIO | 2026-06 | 4,674,359 | 53,252 | 1.14 | 49 | 546 |
| exact duplicate | INFORMACIO | 2026-08 | 3,987,119 | 0 | 0.00 | 0 | 0 |
| latest kept | ESTACIONS | 2026-02 | 4,358,950 | 0 | 0.00 | 0 | 0 |
| latest kept | ESTACIONS | 2026-03 | 4,804,908 | 0 | 0.00 | 0 | 0 |
| latest kept | ESTACIONS | 2026-04 | 4,462,138 | 0 | 0.00 | 0 | 0 |
| latest kept | ESTACIONS | 2026-05 | 4,838,444 | 8 | 0.00 | 2 | 4 |
| latest kept | ESTACIONS | 2026-06 | 4,666,090 | 16 | 0.00 | 4 | 8 |
| latest kept | ESTACIONS | 2026-08 | 3,987,120 | 0 | 0.00 | 0 | 0 |
| latest kept | INFORMACIO | 2026-02 | 4,372,346 | 0 | 0.00 | 0 | 0 |
| latest kept | INFORMACIO | 2026-03 | 4,822,141 | 0 | 0.00 | 0 | 0 |
| latest kept | INFORMACIO | 2026-04 | 4,479,175 | 0 | 0.00 | 0 | 0 |
| latest kept | INFORMACIO | 2026-05 | 4,857,918 | 0 | 0.00 | 0 | 0 |
| latest kept | INFORMACIO | 2026-06 | 4,674,359 | 0 | 0.00 | 0 | 0 |
| latest kept | INFORMACIO | 2026-08 | 3,987,119 | 0 | 0.00 | 0 | 0 |
| tie | ESTACIONS | 2026-02 | 4,358,950 | 0 | 0.00 | 0 | 0 |
| tie | ESTACIONS | 2026-03 | 4,804,908 | 0 | 0.00 | 0 | 0 |
| tie | ESTACIONS | 2026-04 | 4,462,138 | 0 | 0.00 | 0 | 0 |
| tie | ESTACIONS | 2026-05 | 4,838,444 | 10 | 0.00 | 2 | 5 |
| tie | ESTACIONS | 2026-06 | 4,666,090 | 6 | 0.00 | 3 | 3 |
| tie | ESTACIONS | 2026-08 | 3,987,120 | 0 | 0.00 | 0 | 0 |
| tie | INFORMACIO | 2026-02 | 4,372,346 | 0 | 0.00 | 0 | 0 |
| tie | INFORMACIO | 2026-03 | 4,822,141 | 0 | 0.00 | 0 | 0 |
| tie | INFORMACIO | 2026-04 | 4,479,175 | 0 | 0.00 | 0 | 0 |
| tie | INFORMACIO | 2026-05 | 4,857,918 | 0 | 0.00 | 0 | 0 |
| tie | INFORMACIO | 2026-06 | 4,674,359 | 0 | 0.00 | 0 | 0 |
| tie | INFORMACIO | 2026-08 | 3,987,119 | 0 | 0.00 | 0 | 0 |
<!-- END metric:8g -->

<!-- BEGIN metric:8h -->
### 8h. Out of area

Series: INFORMACIO. Coordinates outside latitude 41.20–41.60, longitude 1.85–2.35. Deduplicated view unless stated; % of rows checked.

**8h. Out of area:** 0 affected rows of 27,156,136 checked (0.00 %), 0 snapshots, 0 stations (variants counted apart excluded; snapshots summed over months and series).

| Variant | Series | Month | Rows checked | Affected rows | % | Snapshots | Stations |
|---|---|---|---|---|---|---|---|
| out of area | INFORMACIO | 2026-02 | 4,372,346 | 0 | 0.00 | 0 | 0 |
| out of area | INFORMACIO | 2026-03 | 4,822,141 | 0 | 0.00 | 0 | 0 |
| out of area | INFORMACIO | 2026-04 | 4,479,175 | 0 | 0.00 | 0 | 0 |
| out of area | INFORMACIO | 2026-05 | 4,847,622 | 0 | 0.00 | 0 | 0 |
| out of area | INFORMACIO | 2026-06 | 4,647,733 | 0 | 0.00 | 0 | 0 |
| out of area | INFORMACIO | 2026-08 | 3,987,119 | 0 | 0.00 | 0 | 0 |
<!-- END metric:8h -->

<!-- BEGIN metric:8i -->
### 8i. Known issues

**8i. Known issues:** none listed for 2026.
<!-- END metric:8i -->

<!-- BEGIN metric:8j -->
### 8j. Inactive flags vs availability

Series: ESTACIONS. `is_renting` false split by `num_bikes_available` = 0 vs > 0; `is_returning` false split by `num_docks_available` = 0 vs > 0; and `num_bikes_available` = 0 with `is_renting` true. Deduplicated view unless stated; % of rows checked.

**8j. Inactive flags vs availability:** 3,214,624 affected rows of 27,081,461 checked (11.87 %), 50,040 snapshots, 549 stations (variants counted apart excluded; snapshots summed over months and series).

| Variant | Series | Month | Rows checked | Affected rows | % | Snapshots | Stations |
|---|---|---|---|---|---|---|---|
| is_renting false, no bikes | ESTACIONS | 2026-02 | 4,358,950 | 18,405 | 0.42 | 4,490 | 331 |
| is_renting false, no bikes | ESTACIONS | 2026-03 | 4,804,908 | 12,993 | 0.27 | 6,042 | 293 |
| is_renting false, no bikes | ESTACIONS | 2026-04 | 4,462,138 | 14,273 | 0.32 | 5,926 | 275 |
| is_renting false, no bikes | ESTACIONS | 2026-05 | 4,827,667 | 28,016 | 0.58 | 8,900 | 284 |
| is_renting false, no bikes | ESTACIONS | 2026-06 | 4,640,678 | 22,574 | 0.49 | 8,582 | 243 |
| is_renting false, no bikes | ESTACIONS | 2026-08 | 3,987,120 | 16,939 | 0.42 | 7,374 | 279 |
| is_renting false, bikes > 0 | ESTACIONS | 2026-02 | 4,358,950 | 118,500 | 2.72 | 349 | 503 |
| is_renting false, bikes > 0 | ESTACIONS | 2026-03 | 4,804,908 | 0 | 0.00 | 0 | 0 |
| is_renting false, bikes > 0 | ESTACIONS | 2026-04 | 4,462,138 | 1 | 0.00 | 1 | 1 |
| is_renting false, bikes > 0 | ESTACIONS | 2026-05 | 4,827,667 | 0 | 0.00 | 0 | 0 |
| is_renting false, bikes > 0 | ESTACIONS | 2026-06 | 4,640,678 | 105 | 0.00 | 105 | 1 |
| is_renting false, bikes > 0 | ESTACIONS | 2026-08 | 3,987,120 | 75 | 0.00 | 44 | 10 |
| is_returning false, no docks | ESTACIONS | 2026-02 | 4,358,950 | 327 | 0.01 | 316 | 35 |
| is_returning false, no docks | ESTACIONS | 2026-03 | 4,804,908 | 574 | 0.01 | 564 | 51 |
| is_returning false, no docks | ESTACIONS | 2026-04 | 4,462,138 | 4,466 | 0.10 | 4,088 | 86 |
| is_returning false, no docks | ESTACIONS | 2026-05 | 4,827,667 | 9,539 | 0.20 | 8,900 | 81 |
| is_returning false, no docks | ESTACIONS | 2026-06 | 4,640,678 | 9,496 | 0.20 | 8,582 | 76 |
| is_returning false, no docks | ESTACIONS | 2026-08 | 3,987,120 | 7,804 | 0.20 | 7,374 | 70 |
| is_returning false, docks > 0 | ESTACIONS | 2026-02 | 4,358,950 | 7,477 | 0.17 | 4,179 | 306 |
| is_returning false, docks > 0 | ESTACIONS | 2026-03 | 4,804,908 | 12,419 | 0.26 | 5,943 | 291 |
| is_returning false, docks > 0 | ESTACIONS | 2026-04 | 4,462,138 | 9,808 | 0.22 | 5,352 | 272 |
| is_returning false, docks > 0 | ESTACIONS | 2026-05 | 4,827,667 | 18,477 | 0.38 | 8,900 | 282 |
| is_returning false, docks > 0 | ESTACIONS | 2026-06 | 4,640,678 | 13,078 | 0.28 | 7,161 | 241 |
| is_returning false, docks > 0 | ESTACIONS | 2026-08 | 3,987,120 | 9,135 | 0.23 | 3,777 | 276 |
| no bikes, is_renting true | ESTACIONS | 2026-02 | 4,358,950 | 422,618 | 9.70 | 7,809 | 524 |
| no bikes, is_renting true | ESTACIONS | 2026-03 | 4,804,908 | 505,353 | 10.52 | 8,889 | 531 |
| no bikes, is_renting true | ESTACIONS | 2026-04 | 4,462,138 | 449,209 | 10.07 | 8,248 | 522 |
| no bikes, is_renting true | ESTACIONS | 2026-05 | 4,827,667 | 536,301 | 11.11 | 8,900 | 524 |
| no bikes, is_renting true | ESTACIONS | 2026-06 | 4,640,678 | 687,668 | 14.82 | 8,582 | 537 |
| no bikes, is_renting true | ESTACIONS | 2026-08 | 3,987,120 | 381,594 | 9.57 | 7,374 | 508 |
<!-- END metric:8j -->

## Implementation notes

- Python 3.14.4, duckdb 1.5.6.
- Extraction: macOS built-in tar (bsdtar 3.5.3 - libarchive 3.7.4 zlib/1.2.12 liblzma/5.4.3 bz2lib/1.0.8) instead of 7z, approved by the owner on 2026-10-08.
- Parquet: every CSV column stored as text (Common settings › Reading), DuckDB's default Parquet settings; CSV bytes, data rows, header line and inferred types stored in the Parquet key-value metadata.
- Inferred type (1b, 1c): DuckDB's CSV sniffer over every row of the CSV (`sample_size = -1`), with `NA` and empty as null.
- Typed view: `NA` and empty → null, then `TRY_CAST` to the inferred type.
- 2a input: archive side recomputed from the Parquet files with the 1b definitions, over the union of months that have the column (so distinct values cover all months); real-time side copied from the real-time `field_profile.csv`. Fields matched by literal name once real-time station fields lose the `data.stations[].` prefix.
- 6b: the as-of join runs over every month available, not only the status snapshot's month.
- 6d: station IDs compared as text (the archive's are integers, the feed's strings).
- 8: booleans read with `TRY_CAST(... AS BOOLEAN)` on the typed view (1/0 and TRUE/FALSE alike); 8a capacity from the as-of `INFORMACIO` snapshot over every month, as in 6b; a quality case is one station in one month for one check variant.
- Duplicates (3a rows per snapshot, 3b, 3c, 6a–6d, 8): exact duplicates compared over every raw column, keeping the first in CSV order; CSV line numbers come from the Parquet row number (Parquet keeps the CSV row order; line 1 = header), and each example checks its raw lines against the Parquet rows.
- 3b counts (as in the real-time plan, every numeric station field except `last_reported`): `num_bikes_available`, `num_bikes_available_types.mechanical`, `num_bikes_available_types.ebike`, `num_docks_available`; comparisons across a 5b gap (snapshots further apart than 2 × the month's median interval) left out and counted apart.
- 6c: `station_changes.csv` `first_seen_utc` is the snapshot where the new value first appears; within and between months are told apart in the summary counts only.
- Median and p95: median as Python `statistics.median` (mean of the two middle values for an even count); p95 by the nearest-rank method.
