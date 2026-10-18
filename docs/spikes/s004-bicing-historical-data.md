# Spike — Bicing historical data (Open Data BCN)

**Status:** Ready for implementation. 
- Analysis plan approved 2026-10-08; 
- Steps approved 2026-10-08.
- Time used for Spec, Plan and Steps: 2,5h
- Current step: 7 ✓ (2026-10-09). Findings and Conclusion drafted by Chat (2026-10-09).
- Next: the owner checks Findings and Conclusion against the evidence.

**Task:** T005 — Profile Bicing historical data.
**Inputs:** Open Data BCN monthly archives, in `spikes/bicing-spike/historical-data/raw/` (ignored by Git, ADR-0009).

A spike is a short investigation to answer questions before building. Durable findings move to the source card (`docs/sources/bicing.md`) or to an ADR (`docs/decisions/`).

## Why

The Open Data BCN monthly archives are the only source of Bicing history. Before designing their ingestion we need to know how they fit with the data captured in real time (see [s002-bicing-realtime-capture.md](s002-bicing-realtime-capture.md)): same structure and meaning, how often they sample, and how complete they are.

## Scope

- **Months:** every 2026 month downloaded — February to June and August — fully profiled, both series (`ESTACIONS` = status, `INFORMACIO` = information). Consecutive months allow continuity checks across month cuts. January 2026 status is not in the catalogue.
- New monthly archives keep being downloaded as they are published; they may fill gaps.
- **Out of scope:**
  - Months before 2026.
  - Value-by-value match against the real-time capture (2026-10-03 to 2026-10-05): no archive overlaps it yet. Moved to T015, blocked until the October 2026 archive is published.

## Questions

Numbered like the real-time report so answers can be cross-referenced. The two questions re-pointed from it to T005 are 2 and 6.

1. **Schema:** which columns, types, nulls and ranges do `ESTACIONS` and `INFORMACIO` have, which GBFS version do they reflect, and does the schema change between 2026 months?
2. **Relation to the feed:** do the archives have the same structure and meaning as the feed's `station_status` and `station_information`? Column-by-column mapping to the common model on GBFS 3.0 (ADR-0008), with the categories of the real-time report's Findings 2a (direct / rename / transform / no equivalent).
3. **Freshness:** how often is each station sampled, and what do `last_reported` and `last_updated` mean in the archives?
5. **Coverage:** which time ranges have no data: months missing from the catalogue (July 2026), gaps inside a month (start of August), and the range between the last archive record and the first record of the continuous real-time capture (T012)? January 2026 (status) is not in the catalogue either. Are months cut at local time or UTC? The last range can only be described here; it closes when T012 has a start date.
6. **Identity:** do the stations match the real-time feed (count, IDs, coordinates)?
7. **Volume:** how large is each month, compressed and uncompressed?
8. **Quality:** which impossible or suspicious values appear (same checks as the real-time report, question 8)?

Dropped: question 4 (Sampling) — for history, what matters is which time ranges have no data (question 5), not activity lost between samples; the cadence is still measured in question 3.

## Early observations (preliminary)

From the header and the first and last line of each June and August CSV only (2026-10-08). To be checked in Findings.

- July 2026 is not in the catalogue and is not inside the August archive.
- June runs from 2026-05-31T22:01Z to 2026-06-30T21:55Z: months are cut at local time (Europe/Madrid). August starts at 2026-08-01T07:30Z, about 9.5 h after local midnight.
- The archives use GBFS 2.x fields although the feed is 3.0: `num_bikes_available`, `num_bikes_available_types.mechanical` / `.ebike`, `status`, `traffic`; timestamps in POSIX seconds.
- `INFORMACIO` has 19 columns in June and 18 in August (`is_valet_station` dropped). It also has columns the 3.0 feed lacks: `physical_configuration`, `altitude`, `nearby_distance`, `x_ride_code_support`.
- Nulls are written `NA`; booleans mix `TRUE` and `1`.
- Station IDs run from 1 to 614 in both months.
- Uncompressed sizes: June `ESTACIONS` 299 MB, `INFORMACIO` 1,035 MB; August 256 MB and 871 MB.

## Method

| Decision | Choice | Reason | Rejected |
|---|---|---|---|
| Script | New script `spikes/bicing-historical-analysis/analyse_bicing_historical.py`, Bicing history only; may take `spikes/realtime-capture-analysis/analyse_realtime_capture.py` as a base | AMBici has no history, so the shared real-time script would gain nothing | Extending the shared real-time script |
| Engine | DuckDB, SQL straight on the CSV files | Profiles 1 GB files without loading them into memory; type inference and `NA` as null built in; a de facto standard for local profiling of large files | Standard library `csv` streaming (hand-written type inference and aggregates, minutes per pass); pandas in chunks (aggregating across chunks complicates the code, no speed gain) |
| Evidence | `spikes/bicing-spike/historical-data/analysis/` | Next to the real-time evidence of the same system | — |

## Analysis plan

Code implements it without making analysis decisions; any deviation is reported, not decided. Same structure as the real-time plan ([s001-ambici-realtime-capture.md › Analysis plan](s001-ambici-realtime-capture.md#analysis-plan)); metric numbers follow the Questions (no 4).

### Common settings

| Aspect | Choice |
|---|---|
| Terms | **Series** = `ESTACIONS` (status) or `INFORMACIO` (information). **Month** = one archive of one series. **Snapshot** = all rows of a month sharing one `last_updated` value (one dump of the feed); 3a checks that this holds |
| Script | `spikes/bicing-historical-analysis/analyse_bicing_historical.py` (see Method) |
| Environment | `venv` in `spikes/bicing-historical-analysis/` with `requirements.txt` (`duckdb`, version as resolved by pip, recorded with the Python version). macOS built-in `tar` (bsdtar/libarchive) to extract the `.7z` files. The first step checks duckdb |
| Inputs | `spikes/bicing-spike/historical-data/raw/2026_MM_*_BicingNou_{ESTACIONS,INFORMACIO}.7z`, February to June and August. Real-time reference: `spikes/bicing-spike/analysis/field_profile.csv` and the last `station_information` response of the real-time capture (`spikes/bicing-spike/realtime/raw/station_information/2026-10-05/`) |
| Extraction | The `.7z` files stay untouched (ADR-0006). One month at a time: extract the CSV, convert it once to Parquet with DuckDB, delete the CSV. Parquet goes to `spikes/bicing-spike/historical-data/work/` (ignored by Git; rebuildable). |
| Reading | Profile (1b) over all columns read as text, so the raw representation (`NA`, `TRUE`/`1`) is visible. Metrics over a typed view: `NA` and empty → null; `TRUE`/`1` → true, `FALSE`/`0` → false; any other value is counted as a parse failure, not corrected |
| Duplicates | Gate 1 found snapshots of 2026-05-26 to 2026-06-15 holding 2–3 dumps under one `last_updated`. The typed view deduplicates within each snapshot: (1) exact duplicate rows are dropped; (2) if a station still has more than one row, the one with the latest `last_reported` is kept; (3) on a tie, the station is left out of that snapshot. `INFORMACIO` has no `last_reported`, so any duplicate left after (1) is a tie. Rows dropped at each stage are counted in the reconciliation and listed in 8g. Applies from step 3; step 7 reruns every metric with it |
| Timestamps | `last_reported` and `last_updated` are POSIX seconds; converted to UTC at load (ADR-0005). Local time (Europe/Madrid) only where a question asks about month cuts |
| Month window | A row belongs to the month of its file. Rows whose `last_updated` falls outside that month in local time are kept, counted and listed in the summary |
| Evidence | Written to `spikes/bicing-spike/historical-data/analysis/` and committed (small derived files). Files: `summary.md` (every table the report needs), `header_check.csv`, `field_profile.csv`, `field_comparison.csv`, `snapshots.csv`, `station_reporting.csv`, `gaps.csv`, `station_match.csv`, `station_changes.csv`, `quality_cases.csv` |
| Review loop | Same as the real-time plan: (1) Code runs the planned metrics; (2) owner and Chat review; added checks are marked *added after first look*; (3) Code runs only the added checks (`--only`); (4) one full run produces the evidence the report cites |

### 1. Schema

| Metric | Definition | Input | Output |
|---|---|---|---|
| 1a. Header check | Per month and series: column names and order; columns added or removed versus the previous month available | First line of each CSV, February to June and August | `header_check.csv`: month, series, position, column, change versus previous month |
| 1b. Field profile | Per month, series and column: type inferred by DuckDB, % null, raw representations of nulls and booleans, distinct values (listed when ≤ 20, otherwise the count), min/max; timestamps also as UTC | February to June and August, all rows | `field_profile.csv` with month and series columns |
| 1c. Type stability | Type inferred per column (1b) compared with the previous month available | 1b | Columns in `header_check.csv` (inferred type, differs from previous month) |
| 1d. GBFS version | Which GBFS version the columns reflect, comparing names and meaning with the 2.3 and 3.0 specs | Chat, from 1a and 1b | Findings |

### 2. Relation to the feed

| Metric | Definition | Input | Output |
|---|---|---|---|
| 2a input. Field comparison | One row per field in the union of archive columns (all months) and real-time Bicing field paths of `station_status` and `station_information`; matched literally (renames are left to 2a). Columns per side: present, type, % null, min, max, distinct values or count | 1b + real-time `field_profile.csv` | `field_comparison.csv` |
| 2a. Field mapping | Each archive column mapped to the common model on GBFS 3.0 (ADR-0008) as **direct**, **rename**, **transform** or **no equivalent**, with the categories of the real-time report's Findings 2a; and each GBFS 3.0 field Bicing publishes in real time with no archive column | Chat, from `field_comparison.csv` | Table in Findings |
| 2b. Effort summary | Count of fields per category | 2a | Table in Findings |

### 3. Freshness

| Metric | Definition | Input | Output |
|---|---|---|---|
| 3a. Snapshot cadence | Per month and series: number of snapshots, rows per snapshot (min, median, max) and interval between consecutive snapshots (median, p95, max) | February to June and August | `snapshots.csv`: one row per snapshot (month, series, `last_updated` UTC, rows, interval to previous in s). Summary per month and series |
| 3b. Station reporting interval | Per station: time between consecutive distinct `last_reported` values over consecutive snapshots. Also heartbeats (`last_reported` changed, counts did not) and silent changes (counts changed, `last_reported` did not); "counts" = the four `num_*` columns. Comparisons across a 5b gap are excluded and counted apart | `ESTACIONS`, February to June and August | `station_reporting.csv`: station_id, month, intervals, median, p95, max (s), heartbeats, silent changes. Summary: distribution across stations and totals |
| 3c. `last_updated` vs `last_reported` | Lag `last_updated` − `last_reported` per row (median, p95, max, negatives) | `ESTACIONS`, February to June and August | Summary |
| 3d. `ttl` | Distinct values per series | 1b | Summary |

### 5. Coverage

| Metric | Definition | Input | Output |
|---|---|---|---|
| 5a. Missing months | Months of 2026 not in the catalogue | Source card (status: January and July 2026; information: July 2026) and owner's downloads | Findings |
| 5b. Gaps inside a month | Interval between consecutive snapshots greater than 2 × the month's median interval (3a); also the range from the start of the month (local midnight) to the first snapshot and from the last snapshot to the end of the month, when longer than that threshold | `snapshots.csv` | `gaps.csv`: month, series, start (UTC), end (UTC), duration (min), kind (inside / start of month / end of month). Summary |
| 5c. Month cut | First and last `last_updated` per month, in UTC and local time | February to June and August | Summary |
| 5d. Range to real time | From the last archive record to the first record of the continuous real-time capture | Chat | Findings; open until T012 has a start date |

### 6. Identity

| Metric | Definition | Input | Output |
|---|---|---|---|
| 6a. Station set | Station IDs per month and series; stations added or removed between consecutive months available | February to June and August | Summary |
| 6b. Information ↔ status match | Per `ESTACIONS` snapshot, against the latest `INFORMACIO` snapshot at or before it (as-of join): IDs with status but no information, and the reverse | February to June and August | Counts and IDs (summary) |
| 6c. Attribute stability | Per station within each month and between consecutive months available: changes in name, coordinates, `capacity` | `INFORMACIO` | `station_changes.csv`: one row per change (station_id, month, field, old value, new value, first seen UTC). Count in the summary |
| 6d. Match with the real-time feed | Last `INFORMACIO` snapshot of August against the last real-time `station_information` response: IDs in both / only one; for shared IDs, same `external_id`, same name, distance between coordinates (m; > 50 m listed), same capacity | August + real-time response | `station_match.csv`: one row per station ID in either side. Summary |

### 7. Volume

| Metric | Definition | Input | Output |
|---|---|---|---|
| 7a. Size per month | Per month and series: `.7z` bytes, CSV bytes, data rows | February to June and August | Summary |
| 7b. Size per snapshot | Median CSV bytes per snapshot (CSV bytes ÷ snapshots) and Parquet bytes per month | February to June and August | Summary |

### 8. Quality

Same checks as the real-time report, with the archive's column names.

| Check | Definition | Series |
|---|---|---|
| 8a. Over capacity | `num_bikes_available` + `num_docks_available` > `capacity` (as-of `INFORMACIO`, as in 6b) | both |
| 8b. Negative counts | Any count < 0 | `ESTACIONS` |
| 8c. Type breakdown mismatch | `num_bikes_available_types.mechanical` + `.ebike` ≠ `num_bikes_available`; rows with a null breakdown counted apart | `ESTACIONS` |
| 8d. Stale station | `is_installed` true and `last_reported` older than 24 h at `last_updated` | `ESTACIONS` |
| 8e. Future timestamp | `last_reported` later than `last_updated` + 1 min | `ESTACIONS` |
| 8f. Inactive stations | `is_installed`, `is_renting` or `is_returning` false; `status` other than `IN_SERVICE` | `ESTACIONS` |
| 8g. Duplicate ID | Same `station_id` twice in one snapshot, before deduplication (Common settings › Duplicates); variants: exact duplicate, latest `last_reported` kept, tie (station left out) | both |
| 8h. Out of area | Coordinates outside latitude 41.20–41.60, longitude 1.85–2.35 | `INFORMACIO` |
| 8i. Known issues | None listed for 2026 | — |
| 8j. Inactive flags vs availability | As in the real-time report: `is_renting` false split by `num_bikes_available` = 0 vs > 0; `is_returning` false split by `num_docks_available` = 0 vs > 0; and `num_bikes_available` = 0 with `is_renting` true | `ESTACIONS` |

Output: per check, affected rows, snapshots and stations, and % (summary); cases in `quality_cases.csv`, one row per check + variant + case: check, variant, month, series, station_id, detail (values of the first occurrence), snapshots affected, first seen (UTC), last seen (UTC).

### Verification

Spike code is exempt from the test rules (CLAUDE.md › Code › Testing); correctness is checked through the evidence. Code adds to `summary.md`:

- **Reconciliation:** per month and series, data rows in the CSV = rows in Parquet = sum of rows per snapshot (3a); rows outside the month window counted. Any mismatch is reported, not corrected.
- **Hand-checkable examples:** for 3b, one station over three consecutive snapshots, with the raw CSV lines; for 5b, one gap with the snapshot before and after it; for 6d, one station with its archive and real-time values side by side, naming the real-time file.

### Plan history

- 2026-10-08: drafted.
- 2026-10-08: all downloaded 2026 months fully profiled (header-only check dropped); paths moved under `spikes/bicing-spike/historical-data/`.
- 2026-10-08: approved.
- 2026-10-08: first step checks duckdb only (`7z` known to be installed).
- 2026-10-08: extraction with macOS `tar` instead of `7z` (step 1 deviation, owner-approved).
- 2026-10-09: Gate 1 — snapshot deduplication rule added (Common settings › Duplicates); 8g counts before it.
- 2026-10-09: step 3 review — 3b counts = four `num_*` columns and excludes comparisons across 5b gaps; `INFORMACIO` duplicates after exact deduplication are ties; step 7 applies both rules to 3a and 3b.
- 2026-10-09: Gate 2 — no checks added, step 6 not needed. 6c moves to `station_changes.csv`; step 7 adds the script `README.md`. Confirmed Code's readings: 2a matches real-time fields without the `data.stations[].` prefix; 6b as-of join across months; 6d name equal in every language, distance by haversine (R = 6,371,008.8 m); 8a reported under `ESTACIONS`; 8g counts every raw row of a duplicated pair, a pair may fall in several variants; variants counted apart stay out of a check's headline line; booleans read with `TRY_CAST`.

Earlier versions are in Git.

## Steps

Run by Code, following CLAUDE.md › Code › Step protocol. One step = one reviewable result and one commit (made by the owner). Every step reads the Status, its own row, Analysis plan › Common settings and the metric sections it lists in R; nothing else unless listed in Reads. Files: `spikes/bicing-historical-analysis/` (`analyse_bicing_historical.py`, `requirements.txt`, `README.md`) and the evidence in `spikes/bicing-spike/historical-data/analysis/`.

| Step | Scope | R | Reads | Check | Commit | Done |
|---|---|---|---|---|---|---|
| 1 | Environment and load: venv, `requirements.txt` (duckdb, Python version recorded); script entry point with `--only`; extract each month, convert to Parquet in `work/`, delete the CSV; 7a; reconciliation of CSV rows vs Parquet rows | 7a, Verification (reconciliation) | `ls -l` of `historical-data/raw/` | `summary.md` lists 12 Parquet files (6 months × 2 series) with CSV rows = Parquet rows for each; `work/` holds no CSV; `git status` shows no files under `work/` or the venv | `chore(T005): load Bicing 2026 archives into Parquet` | ✓ |
| 2 | Schema and snapshots: 1a, 1b, 1c, 3a, 7b; reconciliation of rows per snapshot; rows outside the month window counted and listed (Common settings › Month window) | 1, 3a, 7b, Verification (reconciliation) | — | `header_check.csv`, `field_profile.csv`, `snapshots.csv` exist; sum of rows per snapshot = Parquet rows for each month and series; `summary.md` has the count of rows outside the month window per month and series | `feat(T005): schema profile and snapshot cadence` | ✓ |
| Gate 1 | Owner and Chat review `field_profile.csv` and `snapshots.csv` against the three assumptions (snapshot = same `last_updated`; booleans only `TRUE`/`FALSE`/`1`/`0`; the columns used by 3b and 8 — counts, `last_reported`, `last_updated` — have the expected types and ranges; their meaning against the feed is checked in 2a). All hold → step 3; otherwise stop and update the Analysis plan | | | Owner decides | — | ✓ |
| 3 | Freshness and coverage: 3b, 3c, 3d, 5b, 5c; hand-checkable examples for 3b and 5b | 3, 5, Verification (examples) | — | `station_reporting.csv` and `gaps.csv` exist; both examples in `summary.md` name their raw lines | `feat(T005): freshness and coverage metrics` | ✓ |
| 4 | Relation to the feed and identity: 2a input, 6a–6d; hand-checkable example for 6d | 2, 6, Verification (examples) | Real-time `spikes/bicing-spike/analysis/field_profile.csv`; last real-time `station_information` file of 2026-10-05 | `field_comparison.csv` and `station_match.csv` exist; the 6d example is in `summary.md` | `feat(T005): field comparison and station match` | ✓ |
| 5 | Quality: 8a–8j | 6b, 8 | — | `quality_cases.csv` exists; `summary.md` has one line per check (8i: none listed) | `feat(T005): quality checks` | ✓ |
| Gate 2 | First look (Analysis plan › Review loop): owner and Chat review the results. Checks added → Chat adds them to the plan marked *added after first look*, then step 6; none → step 7 | | | Owner decides | — | ✓ |
| 6 | Added checks only (`--only`) | Added checks | — | Added checks appear in `summary.md` and `quality_cases.csv` | `feat(T005): checks added after first look` | — (not needed) |
| 7 | Final full run without `--only`, with every rule added after step 2 (3a with deduplication; 3b without comparisons across gaps; 6c as `station_changes.csv`); `README.md` for the script, same structure as `spikes/realtime-capture-analysis/README.md`; the evidence the report cites | All | `spikes/realtime-capture-analysis/README.md` | Run ends without errors; every reconciliation line in `summary.md` matches; the 10 evidence files exist; `README.md` exists; the three hand-checkable examples are in `summary.md` | `chore(T005): final full analysis run` | ✓ |

After step 7 Chat drafts Findings and Conclusion from the evidence (1d, 2a, 2b, 5a and 5d are Chat's), and the owner checks them against it.

## Findings

Evidence: `spikes/bicing-spike/historical-data/analysis/` (final run 2026-10-08T23:04Z). Metric IDs refer to the Analysis plan; "summary" = `summary.md`. Reconciliation holds for every month and series: CSV rows = Parquet rows = rows in snapshots + rows dropped by deduplication; no snapshot falls outside its month window.

**1. Schema** — stable types, unstable headers, GBFS 2.3 shape.

- 1a. `ESTACIONS` has 14 columns in every month except March (15: an extra `V1`, always `NA`). `INFORMACIO` changes three times: March adds `V1` (always `NA`) and `external_id` at the end (20 columns); April drops `V1` and moves `external_id` to position 2, shifting every other column (19); August drops `is_valet_station` (18). Evidence: summary › 1a, `header_check.csv`.
- 1b. Nulls are written `NA`. Booleans use two encodings: `is_installed`, `is_renting`, `is_returning` as `1`/`0` (inferred `BIGINT`); `is_charging_station`, `x_ride_code_support`, `is_valet_station` as `TRUE`/`FALSE`. Always null: `traffic`, `rental_uris`, `V1`. `is_valet_station` is 99.67 % null, otherwise `FALSE`. `external_id` is 97.12 % null in March (the month it appears) and never null from April. `post_code` and `short_name` are inferred as integers (`post_code` 8001–8930: leading zero lost). `status` takes `IN_SERVICE`, `MAINTENANCE`, `NOT_IN_SERVICE`, `PLANNED`. Evidence: `field_profile.csv`, `field_comparison.csv`.
- 1c. No column changes its inferred type between months. Evidence: summary › 1c.
- 1d. The columns reflect GBFS 2.3, not 3.0: `num_bikes_available` (3.0: `num_vehicles_available`); `last_reported` and `last_updated` as POSIX seconds (3.0: RFC 3339); `name` and `short_name` as plain values (3.0: localised lists); and `is_charging_station`, a field added in 2.3. There is no `version` column. The `1`/`0` booleans break 2.3, which requires booleans. Not in 2.3 or 3.0 (operator extensions): `status`, `traffic`, `num_bikes_available_types.mechanical` / `.ebike`, `is_charging_station` in status, `physical_configuration`, `altitude`, `nearby_distance`, `x_ride_code_support`, `external_id`. The dotted column names suggest a flattened JSON feed (inference). Checked against the GBFS 2.3 spec (`gbfs.md`, tag v2.3) and the real-time report's 3.0 field list.

**2. Relation to the feed** — same meaning, older shape: 1 rename, 10 transforms; 9 fields of the 3.0 feed have no history.

- 2a. Field mapping to the common model on GBFS 3.0 (ADR-0008). Scope: the 3.0 fields of `station_information`, `station_status` and the header that Bicing publishes in real time (real-time report, 2a: Bicing = Direct). Evidence: `field_comparison.csv`, summary › 6d.

| Feed | Field (3.0) | Archive column | Category | Note |
|---|---|---|---|---|
| all | `last_updated` | `last_updated` (both series) | Transform | POSIX seconds → RFC 3339. Snapshot time, shared by all rows of a dump (3a) |
| all | `ttl` | `ttl` | Direct | Always 0, as in real time (3d) |
| all | `version` | — | No equivalent | Constant `2.3` by 1d, not published |
| `station_information` | `station_id` | `station_id` | Transform | Integer → string; values match the feed as text (6d) |
| `station_information` | `name` | `name` | Transform | String → list of `{text, language}`; the feed's 5 languages carry the same text (6d) |
| `station_information` | `short_name` | `short_name` | Transform | Integer → list of `{text, language}` |
| `station_information` | `lat`, `lon` | `lat`, `lon` | Direct | Counted as two fields |
| `station_information` | `capacity` | `capacity` | Direct | |
| `station_information` | `address` | `address` | Direct | |
| `station_information` | `cross_street` | `cross_street` | Direct | 0.33 % null (feed: 0 %) |
| `station_information` | `post_code` | `post_code` | Transform | Integer → 5-character string (left-pad the lost zero) |
| `station_information` | `is_charging_station` | `is_charging_station` | Direct | `FALSE` in 76,474 rows, as many as `physical_configuration` = `VALET`; feed always `true` |
| `station_information` | `is_virtual_station` | — | No equivalent | Feed always `false` |
| `station_information` | `rental_methods` | — | No equivalent | |
| `station_information` | `vehicle_docks_capacity` | — | No equivalent | Feed: one group equal to `capacity` |
| `station_information` | `vehicle_types_capacity` | — | No equivalent | Feed always empty |
| `station_status` | `station_id` | `station_id` | Transform | Integer → string |
| `station_status` | `num_vehicles_available` | `num_bikes_available` | Rename | |
| `station_status` | `num_docks_available` | `num_docks_available` | Direct | |
| `station_status` | `is_installed` | `is_installed` | Transform | `1`/`0` → boolean |
| `station_status` | `is_renting` | `is_renting` | Transform | `1`/`0` → boolean; meaning differs in practice (8j) |
| `station_status` | `is_returning` | `is_returning` | Transform | `1`/`0` → boolean |
| `station_status` | `last_reported` | `last_reported` | Transform | POSIX seconds → RFC 3339; contains 0 and frozen values (8) |
| `station_status` | `vehicle_types_available` | — | No equivalent | The archive splits by propulsion (`mechanical`, `ebike`); the feed by 4 vehicle type IDs. Not derivable without a type → propulsion rule |
| `station_status` | `num_vehicles_disabled` | — | No equivalent | |
| `station_status` | `num_docks_disabled` | — | No equivalent | |
| `station_status` | `vehicle_docks_available` | — | No equivalent | |

Outside the mapping (no 3.0 field): `ESTACIONS` `status`, `traffic` (always null), `is_charging_station` (always `TRUE`), `num_bikes_available_types.mechanical` / `.ebike`, `V1`; `INFORMACIO` `physical_configuration`, `altitude`, `nearby_distance`, `x_ride_code_support` (always `TRUE`), `is_valet_station`, `rental_uris` (always null; the real-time report also has it outside the mapping), `external_id` (an extension, also in the feed), `V1`.

- 2b. Effort summary (28 fields; `lat` and `lon` count as two):

| Source | Direct | Rename | Transform | No equivalent |
|---|---|---|---|---|
| Bicing archives | 8 | 1 | 10 | 9 |
| Bicing real time (for reference) | 28 | 0 | 0 | 0 |

**3. Freshness** — one snapshot every 5 min; `last_reported` is a per-station time 1–3 min before it.

- 3a. A snapshot every 300 s (median, every month and series); p95 304 s, except May (308 s) and June (484 s). Median 540–545 rows per snapshot. With deduplication, every snapshot holds one row per station (Gate 1). Evidence: summary › 3a, `snapshots.csv`.
- 3b. Every station's median reporting interval is 361 s (p95 and max of the station medians 361–362 s), in every month. Heartbeats (`last_reported` moved, counts did not): 16.4 M of 26.9 M comparisons. Silent changes: 79,238, of which 67,238 are in May and June (the duplicate period, 8g). No negative intervals. Evidence: summary › 3b, `station_reporting.csv`, example station 1.
- 3c. `last_updated` − `last_reported`: median 91–92 s, p95 173–174 s, never negative. Maximums up to 56 years come from frozen or zero `last_reported` (8d). Evidence: summary › 3c.
- 3d. `ttl` is 0 in every row of both series. Evidence: summary › 3d.
- Meaning: `last_updated` is the snapshot time (one value per dump); `last_reported` is the station's own report time, always before it (8e: 0 cases).

**5. Coverage** — July missing, August holed, and an open range from 2026-08-31 to the real-time capture.

- 5a. Missing from the catalogue on 2026-10-03: status January and July 2026; information July 2026 (source card `bicing.md`). January information exists but was not downloaded (Scope).
- 5b. Gaps longer than 10 min (2 × the 300 s median):

| Month | Status gaps (total) | Longest | Note |
|---|---|---|---|
| 2026-02 | 2 (90 min) | 55 min | |
| 2026-03 | 6 (152 min) | 65 min | 2026-03-03 |
| 2026-04 | 7 (1,983 min) | 1,600 min | 2026-04-13T07:25Z → 04-14T10:05Z (26.7 h); 311 min on 04-24 |
| 2026-05 | 99 (1,136 min) | 15 min | From 2026-05-25, the duplicate period |
| 2026-06 | 226 (2,678 min) | 17 min | Up to 2026-06-15, the duplicate period |
| 2026-08 | 39 (7,385 min) | 1,284 min | Starts 571 min late (07:31Z); the long gaps all fall on 2026-08-01 → 08-06T08:45Z |

`INFORMACIO` gaps follow the same pattern (summary › 5b). Evidence: summary › 5b, `gaps.csv`, example 2026-02-19.

- 5c. Months are cut at local midnight (Europe/Madrid), across the DST change: every month starts at local 00:00–00:05 and ends at 23:55–23:58, except August (starts 09:31 local). No row falls outside its month. The early observation of June starting at 22:01Z is corrected to 22:03Z (status) and 22:05Z (information). Evidence: summary › 5c, 3a.check.
- 5d. History ends at 2026-08-31T21:55:04Z (last August snapshot, 5c). The continuous real-time capture (T012) has no start date (task ⬜), so the range [2026-08-31T21:55Z, start of T012) is open. The T006 capture (2026-10-03 to 2026-10-05) is not continuous and does not close it. The September and October archives would shorten it when they are published. Inside the history, July leaves 2026-06-30T21:55Z → 2026-08-01T07:31Z (31.4 days) without data.

**6. Identity** — the same stations as the feed; capacity changes often.

- 6a. 544–546 stations in status and 544–548 in information each month; IDs 1–610, up to 614 from June. 1–5 stations are added or removed per month (listed in summary › 6a).
- 6b. Stations 542 and 543 are in information but never in status, in every snapshot from February to mid-June; they leave information in August. Apart from them, status-only stations: 34 in February (up to 40 snapshots each), 9–18 per month from March to June, mostly in one snapshot each; information-only: 9–21 per month, mostly in one snapshot each. A station can therefore appear in status before information does. August: 3 status-only pairs. Evidence: summary › 6b.
- 6c. 1,129 attribute changes: capacity 151–220 per month on 42–70 stations; names 1–13 per month; coordinates 0–6 per month. Between months, only August shows changes (29 capacities, over the missing July). Evidence: summary › 6c, `station_changes.csv`.
- 6d. Last August snapshot vs real time (2026-10-05T14:15Z): 543 stations on each side, 541 shared (archive only 292, 508; real time only 46, 245). Shared stations have the same `external_id` (0 differ), the same coordinates (max 0.0 m) and the same name except 507; 51 differ in capacity, consistent with 6c over five weeks. Evidence: summary › 6d, `station_match.csv`, example station 1.

**7. Volume** — about 29 MB per month compressed, both series.

- 7a. Per month: `ESTACIONS` .7z 18.0–22.2 MB, CSV 256–323 MB; `INFORMACIO` .7z 7.3–8.9 MB, CSV 796–1,076 MB; 4.0–4.9 M rows per series. Information is about 3× larger as CSV and 2.5× smaller compressed (it repeats static data every 5 min). Evidence: summary › 7a.
- 7b. Median CSV per snapshot: 34.9 KB status, 119.2 KB information. Parquet (all columns as text, defaults): 25–31 MB status, 7.2–10.0 MB information per month. Evidence: summary › 7b.

**8. Quality** — the real-time issues are present here too, plus duplicate dumps and two archive-only episodes.

- 8a. Over capacity: 39 rows (32 stations); 591 rows without an as-of capacity, 521 of them in February. 8b, 8e, 8h: 0 cases.
- 8c. Type breakdown mismatch in 0.20 % of rows (539 stations), every month.
- 8d. Stale while installed: 46,515 rows, 20 stations. Station 366 has `last_reported` frozen at 2025-06-12T08:54:16Z from April to August (every snapshot); station 264 from April to mid-June; station 614 reports `last_reported` = 0 once (2026-06-18). Evidence: `quality_cases.csv`.
- 8f. `is_installed` false only in March (37 rows, 1 station; `status` = `PLANNED` also has 37 rows). `status` ≠ `IN_SERVICE` has exactly as many rows as `is_returning` false in every month. `is_renting` false: 0.27–0.58 % of rows, except February (3.14 %, 543 stations).
- 8g. Duplicate rows only in the period 2026-05-26 to 2026-06-15 found at Gate 1 (19 May and 47–49 June snapshots, all stations), almost all exact copies; 12 rows resolved by latest `last_reported`, 8 station × snapshot ties left out. Evidence: summary › Reconciliation — duplicates, 8g.
- 8j. `is_renting` false almost always means no bikes, except February: 118,500 rows with bikes > 0 over 349 snapshots (about 29 h of snapshots) and 503 stations, a system-wide episode. 0 bikes with `is_renting` true: 9.6–14.8 % of rows. `is_returning` false splits between 0 docks and docks > 0.
- 8i. None listed for 2026.

## Conclusion

**For the archive ingestion design:**

- The archives are usable history for the common model at station level and 5-min resolution: map them as GBFS 2.3 to 3.0, with 1 rename and 10 transforms (POSIX → RFC 3339, integer IDs and codes → strings, `1`/`0` → boolean, strings → localised lists) after the raw layer (ADR-0006). The 9 fields without history (per-vehicle-type counts, disabled counts, dock groups, `rental_methods`) stay null for archive rows; the mechanical/ebike split can be kept only as an extension.
- Read columns by header name, not position, and validate each file's header: columns are added, removed and reordered between months (1a). Parse `NA` as null and both boolean encodings explicitly; read `post_code` and `short_name` as text.
- Deduplicate within each snapshot with the rule in Common settings › Duplicates; May–June 2026 needs it (8g).
- Assign months by local time but store UTC (ADR-0005); a month's file may not start at its first day (August).
- Key stations by (system, `station_id`): IDs, `external_id` and coordinates match the real-time feed (6d). Track `capacity`, name and coordinates as changing attributes over time (6c), and accept status rows for stations not yet in information (6b).
- Carry the real-time rules over: detect changes by content, not `last_reported` (3b, 8d); use `num_bikes_available` as the total (8c); do not interpret `is_renting` (8j).
- Volume is small: about 29 MB per month compressed, about 350 MB per year for both series (7a).

**For coverage:**

- Known holes: July 2026 (catalogue), 2026-08-01 to 08-06 (5b), 2026-04-13/14 (26.7 h). History can fill none of them; record them as known gaps.
- The range from 2026-08-31T21:55Z to the start of T012 stays open (5d); the September and October archives will shorten it. The value-by-value match is T015, still blocked on the October archive.

**Notes for merging history with real time** (to review when that merge is designed):

- The 2a mapping needs a field-by-field review. `vehicle_types_available` is classified as no equivalent until the meaning of the archive's `mechanical` / `ebike` split against the feed's vehicle type IDs is known (ask the operator if needed); the alternative is a lossy transform with a type → propulsion rule. The `1`/`0` booleans are counted as transforms, and `version` as no equivalent although 1d fixes it at 2.3. 2b changes if any category does.
- Three links rest on equal row counts only, not checked row by row: `is_charging_station` = `FALSE` ↔ `physical_configuration` = `VALET` (2a), `status` ≠ `IN_SERVICE` ↔ `is_returning` false, and `is_installed` false ↔ `status` = `PLANNED` (8f).
- `last_reported` = 0 and frozen `last_reported` values (8d) have no check of their own.
- TODO: check the catalogue for newly published archives (September 2026 onwards, and any missing month that appears).

**To move to the source card (`docs/sources/bicing.md`):** archive format (GBFS 2.3 shape, extensions, `NA`, two boolean encodings), month cut at local midnight, 5-min snapshots, header changes in 2026 (1a), duplicate period (8g), gaps (5b).

## Sources

- <https://opendata-ajuntament.barcelona.cat/data/es/dataset/estat-estacions-bicing> (station status history)
- <https://opendata-ajuntament.barcelona.cat/data/es/dataset/informacio-estacions-bicing> (station information history)
