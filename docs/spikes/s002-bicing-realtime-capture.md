# Spike — Bicing GBFS observation

**Status:** Done — capture from 2026-10-03T17:11Z to 2026-10-05T14:26Z (UTC, first and last request), the same period as the AMBici spike; analysis window identical.
**Script:** `spikes/bicing-spike/bicing_spike.py` (copy of the AMBici script adapted to GBFS 3.0; Python standard library, throwaway).
**Analysis:** `spikes/realtime-capture-analysis/analyse_realtime_capture.py`; evidence in `spikes/bicing-spike/analysis/`.

A spike is a short investigation to answer questions before building. Durable findings move to the source card (`docs/sources/bicing.md`) or to an ADR (`docs/decisions/`).

## Questions

Rewritten on 2026-10-05 (T006) around what each answer feeds: the ingestion design (T007), the long-term capture hosting, and later analysis. Questions 1–8 are common to both spikes; see the AMBici report for questions 9–10 (AMBici only).

1. **Schema:** which feeds and fields does each system publish (types, nulls, ranges), did the schema stay stable during the capture, and which GBFS versions does each provider offer (`gbfs_versions`)?
2. **Common model:** what would it take to bring both sources into one station-level model? Field-by-field mapping (direct / rename / transform / no equivalent), including possible ID collisions between systems.
3. **Freshness:** how often does each feed's content really change, and how often does each station report (`last_reported`)? Are `ttl` and `last_updated` usable?
4. **Sampling:** how much usage information is lost when polling every 5 minutes instead of every minute?
5. **Reliability:** how often do requests fail, run slow or return stale data, and are gaps on our side or the provider's?
6. **Identity:** are station IDs stable, and do `station_information` and `station_status` match?
7. **Volume:** how large is each feed, per request and per day, raw and compressed?
8. **Quality:** which impossible or suspicious values appear?

Re-pointed to T005 (need the Open Data BCN archives):

- Are the Open Data BCN monthly archives dumps of this feed?
- Do the stations match the Open Data BCN information dataset (count, IDs, coordinates)?

Dropped: "How different are weekday and weekend usage patterns?" — needs weeks of data; answerable only from the long-term capture.

## Method

| Aspect | Choice | Reason |
|---|---|---|
| Feeds | Resolved from `gbfs.json` (`data.feeds`), no hard-coded URLs | The provider may change them; new feeds are captured automatically |
| Languages | No language copies | GBFS 3.0 localises texts inside each feed |
| Frequency | `station_status` every minute; the index and all other feeds every 15 min | Feeds declare `ttl: 0`, which says nothing; same ticks as AMBici so both are comparable |
| Storage | Raw responses untouched, gzip | See ADR-0006 |
| Layout | `raw/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz` under `spikes/bicing-spike/realtime/` | Files organised the way they will be read; folder ignored by Git |
| Request log | One JSONL file per day, all feeds, one line per request including failures | Explains gaps by comparing feeds at the same minute |
| Time | UTC | See ADR-0005 |
| Runtime | Local Mac with `caffeinate -i`, lid open, plugged in | Simple; any gap is itself a finding |
| Duration | Saturday afternoon → Monday afternoon | Weekend + one weekday; same period as AMBici |

Log fields: `tick_utc`, `requested_at_utc`, `purpose`, `feed`, `url`, `http_status`, `elapsed_ms`, `bytes_raw`, `bytes_gz`, `server_last_updated`, `file`, `error`. Same as AMBici without `language`.

## Early observations (preliminary)

From the first tick, 2026-10-03 17:11 UTC. Checked against the full capture: the facts hold (Findings 3c and 7), but `last_reported` turned out not to be reliable for measuring refresh (Findings 3b).

- `last_updated` equals the request time (to the second) on every feed. The server generates the file on request, so it says nothing about data freshness. The refresh rate must be measured with each station's `last_reported`.
- `station_status`: 267 KB raw → 10 KB gzip. Estimated ~20 MB/day compressed in total, against ~75 MB/day for AMBici, which publishes per-bike data.
- `geofencing_zones` and `system_regions` are essentially empty (152 and 85 bytes).

## Analysis plan

Common to both spikes: see [s001-ambici-realtime-capture.md › Analysis plan](s001-ambici-realtime-capture.md#analysis-plan). Questions 9–10 there apply to AMBici only.

Bicing-specific points:

- The common-model mapping (question 2) is published in this report's Findings, because Bicing already uses GBFS 3.0, the target model. Its input is `spikes/bicing-spike/analysis/field_comparison.csv`.

## Findings

Evidence: [`spikes/bicing-spike/analysis/summary.md`](../../../spikes/bicing-spike/analysis/summary.md) and the CSV files next to it, from the final full run of `spikes/realtime-capture-analysis/analyse_realtime_capture.py`. Analysis window 2026-10-03T17:11Z to 2026-10-05T14:26Z (2,716 one-minute ticks), common to both spikes; no Bicing data fell outside it. Planned results come first; checks added after the first look are kept apart at the end.

### 1. Schema

**Answer:** Bicing publishes 8 feeds plus the `gbfs.json` index, in GBFS 3.0, and also announces 1.1 and 2.3 endpoints. The schema was stable and fully compliant during the capture.

- 1a. Every `gbfs.json` response lists the same 8 feeds: `gbfs_versions`, `system_information`, `station_information`, `station_status`, `vehicle_types`, `system_regions`, `system_pricing_plans`, `geofencing_zones`.
- 1b. Every response of every feed declares `version` 3.0.
- 1c. `gbfs_versions` lists 1.1 (`…/ube/gbfs/v1/`), 2.3 (`…/customer/gbfs/v2/`) and 3.0 (`…/customer/gbfs/v3.0/`), identical in all 182 responses (`field_profile.csv`: 546 entries, 3 per response; version–URL pairing in `raw/gbfs_versions/2026-10-05/20261005T000000Z.json.gz`). The 2.3 endpoint was not requested.
- 1d. No field path has nulls and none has mixed types. Localised texts (`name`, `short_name`) come in 5 languages: `ca`, `en`, `es`, `fr`, `nl`. Full profile in `field_profile.csv`.
- 1e. No field path appeared or disappeared between consecutive responses (`schema_changes.csv` is empty).
- 1f. 0 violations of the official MobilityData GBFS 3.0 JSON Schema (commit `2e974fd`). Structural check only (`format` is not asserted); every timestamp converted to UTC in 1d.

### 2. Common model

**Answer:** one station-level model on GBFS 3.0 is feasible. Bicing maps directly; AMBici needs 1 rename and 6 transforms (two timestamps and four localised texts).

2a. Field mapping to GBFS 3.0, for the fields either system publishes in `station_information`, `station_status` and `vehicle_types`, plus the header of every feed. Checked against the official 3.0 schema (same commit as 1f) and `field_comparison.csv`. Bicing already uses 3.0, so its fields are direct or not published; with 0 violations in 1f, none needs a transform.

| Feed | Field (3.0) | AMBici (2.3) | Bicing (3.0) | Note |
|---|---|---|---|---|
| all | `last_updated` | Transform | Direct | POSIX seconds → RFC 3339 |
| all | `ttl` | Direct | Direct | AMBici 60 (86,400 for two static feeds); Bicing 0 |
| all | `version` | Direct | Direct | Value differs: 2.3 / 3.0 |
| `station_information` | `station_id` | Direct | Direct | Strings in both; formats differ (6d) |
| `station_information` | `name` | Transform | Direct | String → list of `{text, language}` |
| `station_information` | `short_name` | Transform | Direct | String → list of `{text, language}` |
| `station_information` | `lat`, `lon` | Direct | Direct | Counted as two fields |
| `station_information` | `capacity` | Direct | Direct | Bicing: equals `vehicle_docks_capacity` (8a) |
| `station_information` | `is_virtual_station` | Direct | Direct | Always `false` in both |
| `station_information` | `region_id` | Direct | No equivalent | |
| `station_information` | `rental_uris` | Direct | No equivalent | Bicing publishes the object, always empty |
| `station_information` | `address` | No equivalent | Direct | |
| `station_information` | `cross_street` | No equivalent | Direct | |
| `station_information` | `post_code` | No equivalent | Direct | Present for 99.63 % of Bicing stations |
| `station_information` | `is_charging_station` | No equivalent | Direct | Always `true` |
| `station_information` | `rental_methods` | No equivalent | Direct | |
| `station_information` | `vehicle_docks_capacity` | No equivalent | Direct | One group listing 9 vehicle types |
| `station_information` | `vehicle_types_capacity` | No equivalent | Direct | Always an empty list |
| `station_status` | `station_id` | Direct | Direct | |
| `station_status` | `num_vehicles_available` | Rename | Direct | AMBici `num_bikes_available` |
| `station_status` | `num_vehicles_disabled` | No equivalent | Direct | |
| `station_status` | `num_docks_available` | Direct | Direct | |
| `station_status` | `num_docks_disabled` | No equivalent | Direct | |
| `station_status` | `is_installed` | Direct | Direct | |
| `station_status` | `is_renting` | Direct | Direct | Meaning differs in practice (8j) |
| `station_status` | `is_returning` | Direct | Direct | |
| `station_status` | `last_reported` | Transform | Direct | POSIX seconds → RFC 3339; AMBici's value is the feed time (3b) |
| `station_status` | `vehicle_types_available` | Direct | Direct | AMBici omits types with count 0 |
| `station_status` | `vehicle_docks_available` | No equivalent | Direct | |
| `vehicle_types` | `vehicle_type_id` | Direct | Direct | |
| `vehicle_types` | `form_factor` | Direct | Direct | Bicing also has `scooter_standing` |
| `vehicle_types` | `propulsion_type` | Direct | Direct | |
| `vehicle_types` | `name` | Transform | Direct | String → list of `{text, language}` |
| `vehicle_types` | `description` | Transform | No equivalent | AMBici publishes the non-standard `_description` (string) |
| `vehicle_types` | `max_range_meters` | Direct | Direct | AMBici: only for the electric types |
| `vehicle_types` | `rider_capacity` | Direct | No equivalent | |
| `vehicle_types` | `vehicle_image` | Direct | No equivalent | |
| `vehicle_types` | `default_pricing_plan_id` | No equivalent | Direct | Bicing: some values are an empty string |
| `vehicle_types` | `pricing_plan_ids` | No equivalent | Direct | |

Outside the mapping: Bicing's `station_information.external_id` is not a GBFS 3.0 field (extension; 543 distinct values).

2b. Effort summary (40 fields; `lat` and `lon` count as two):

| System | Direct | Rename | Transform | No equivalent |
|---|---|---|---|---|
| AMBici | 21 | 1 | 6 | 12 |
| Bicing | 35 | 0 | 0 | 5 |

- 2c. No `station_id` or `vehicle_type_id` value appears in both systems (Bicing: 543 station IDs, 9 vehicle type IDs; AMBici: 237 and 3).
- 2d. Feed published only by Bicing: `gbfs_versions`. Only by AMBici: `free_bike_status`, `system_hours`.

### 3. Freshness

**Answer:** `station_status` changes every 60 s, while each station reports about every 3 minutes. `last_reported` is a real station time but misses count changes; `last_updated` is the time the response was generated; `ttl` 0 says nothing.

- 3a. `station_status` content changed in 100 % of consecutive response pairs, median interval 60 s. `station_information` changed 7 times in two days (capacity changes and one new station, 6a and 6c); every other static feed never changed.
- 3b. `last_reported` never equals `last_updated`. Each station's median reporting interval is about 180 s (median across stations 180.6 s, max 181.1 s). 420,978 heartbeats (`last_reported` changed, counts did not) and 71,699 silent changes (counts changed, `last_reported` did not): `last_reported` is not reliable to detect changes.
- 3c. `last_updated` equals the request time (median lag 0.005 s for `station_status`): the server generates the response on request. It can be up to 15 s ahead of our request time (min lag −14.99 s). It never went backwards.
- 3d. Every feed declares `ttl` 0. Measured change interval of `station_status`: 60 s.

### 4. Sampling

**Answer:** polling every 5 minutes instead of every minute loses 36.5 % of the observed activity, about twice AMBici's loss.

- 4a. Observed activity in the window (lower bound of rentals + returns): 107,713 vehicles on `num_vehicles_available`; per type `BOOST` 91,556, `ICONIC` 16,467, `EFIT` 0, `FIT` 0. The per-type sum (108,023) differs from the total because the type counts do not always add up (8c).
- 4b. Loss versus 1-min polling: 2 min 14.04 %, 5 min 36.47 %, 10 min 50.05 %, 15 min 57.62 % (`ICONIC` alone: 9.51 % at 5 min). Hand-checkable example in the summary (Verification).
- 4c. 90.39 % of the 1-min changes are |Δ| = 1; 9.61 % are ≥ 2.

### 5. Reliability

**Answer:** 5 of 4,175 requests failed (0.12 %), all `station_status` timeouts during the incident of 2026-10-04 from 18:39 to 18:50 UTC shared with AMBici. Bicing is slower than AMBici.

- 5a. Failures: 5 `station_status` timeouts; none in the other feeds.
- 5b. Median latency 517 ms for `station_status` (p95 1.6 s) and 657 ms for `station_information` (p95 3.1 s); the other feeds under 300 ms median. The failed requests took 22–48 s with a 20 s timeout configured (the urllib timeout is per socket operation); one successful request took 50.6 s.
- 5c. No stale response (`last_updated` never went backwards).
- 5d. 6 missing `station_status` ticks, all in the incident and all classed ours (probable): AMBici failed on the same ticks or the previous tick's requests overran the minute. No gap was caused by the Mac sleeping.

### 6. Identity

**Answer:** station IDs were stable. One station was added, and `station_status` listed it before `station_information` did.

- 6a. 542 stations in every `station_information` response until station `309` appeared at 2026-10-04T16:45Z (543 from then on).
- 6b. `station_status` listed `309` in 11 responses before its first `station_information`; no other mismatch.
- 6c. 13 `capacity` changes at 9 stations, each with the same change in `vehicle_docks_capacity`; most are ±1, and station `77` went from 24 to 0. No change in name or coordinates.
- 6d. `station_id` is a numeric string of 1–3 digits.

### 7. Volume

**Answer:** about 19 MB per day compressed, of which `station_status` is 76 %.

- 7a. Median per request, raw / gzip: `station_status` 268 KB / 10.3 KB; `station_information` 516 KB / 45.7 KB; `system_pricing_plans` 11 KB / 0.7 KB; every other feed under 5 KB raw. `geofencing_zones` (152 bytes) and `system_regions` (85 bytes) are essentially empty.
- 7b. 4 October (UTC): 19.34 MB gzip in total; `station_status` 14.72 MB, `station_information` 4.39 MB.
- 7c. Bicing alone, as captured: 19.4 MB/day at 1-min polling (about 7.1 GB per year, 71 % of the R2 free storage) and 7.6 MB/day at 5-min. Both systems together: see the AMBici report.

### 8. Quality

**Answer:** no impossible values (negative counts, duplicates, future `last_reported`, out-of-area coordinates); suspicious patterns: per-type counts that do not add up, stations not reporting for over 24 h, disabled counts that push the total above capacity, and `is_renting` false at almost every station.

- 8a. `capacity` always equals the `count` of the single `vehicle_docks_capacity` group. Available vehicles + available docks > `capacity`: 2 occurrences, at station `298` (around its capacity changes). Including disabled vehicles and docks: 5.13 % of station items, 52 stations.
- 8b, 8e, 8g, 8h. None found.
- 8c. Sum of `vehicle_types_available[].count` ≠ `num_vehicles_available` in 2.70 % of station items, at 521 stations, in every response.
- 8d. 15 installed stations have `last_reported` older than 24 h in every response (the oldest dates from 2025-06-12).
- 8f. `is_installed` false at 1 station; `is_returning` false in 1.32 % of items (27 stations); `is_renting` false in 37.94 % of items, at 541 of 543 stations.
- 8i. No known issues were listed for Bicing.

### Added after first look

Checks added to the plan after reviewing the first results (Analysis plan › Review loop).

- 8j. Inactive flags vs availability. `is_renting` false with vehicles available: 520,621 station items (35.41 %), 519 stations; with 0 vehicles: 37,083 items (48 stations). Conversely, 102,886 items (335 stations) have 0 vehicles and `is_renting` true. So `is_renting` false does not mean an empty station, and its meaning in Bicing cannot be derived from this evidence (open question for the long-term capture analysis). `is_returning` false: 10,950 items with free docks (24 stations), 8,414 with none (7 stations).
- Reviewed and left as a finding without a new check: `last_updated` up to 15 s ahead of the request time (3c).

## Conclusion

**For T007 (ingestion design):**

- Read Bicing as GBFS 3.0 (`…/customer/gbfs/v3.0/`), discovering the feeds from `gbfs.json`. The 2.3 endpoint listed in `gbfs_versions` was not verified. The schema was stable and compliant, so validating against the official 3.0 schema is realistic.
- The common model on GBFS 3.0 is feasible (2a, 2b): Bicing maps directly; AMBici needs one rename and six transforms (POSIX → RFC 3339 timestamps, strings → localised lists). Key stations by (system, `station_id`).
- `last_updated` is the response generation time, not data freshness, and can be ahead of the local clock by up to 15 s: do not reject or reorder responses on it. `ttl` 0 gives no refresh hint.
- `last_reported` is a real per-station time (about every 3 min) but counts change without it: detect changes by content, not by `last_reported`. Some stations have not reported for more than 24 h while installed.
- `station_status` can list a station before `station_information` does: handle unknown station IDs (late-arriving dimension) instead of dropping them.
- Use `num_vehicles_available` as the total; the per-type counts do not always add up. Do not interpret `is_renting` until its meaning is known.
- Localised texts come in 5 languages: choose which to keep at ingestion.

**For the long-term capture:**

- `station_status` changes every 60 s, so 1-min polling captures every published state. Bicing is much busier than AMBici: 5-min polling loses 36.5 % of observed activity, 15-min 57.6 %.
- Volume: about 19 MB per day compressed (7.1 GB per year at 1-min polling). `station_information` is 23 % of it and changed only 7 times in two days, so a lower frequency for the static feeds is a candidate saving. The combined budget for both systems is in the AMBici report.
- Reliability was high (0.12 % failed requests, all in the incident shared with AMBici), but latency is higher than AMBici's (p95 1.6 s; one success took 50.6 s): the same lessons apply (total deadline per request, feeds not run sequentially in one loop).
- The two Open Data BCN questions stay with T005 (see Questions).

## Sources

- <https://github.com/MobilityData/gbfs/blob/v3.0/gbfs.md> (GBFS 3.0 specification)
- <https://github.com/MobilityData/gbfs-json-schema> (official JSON Schemas, commit `2e974fd51ae1db9c8006c97375d53e0b882cfedf`)
- <https://barcelona.publicbikesystem.net/customer/gbfs/v3.0/> (Bicing GBFS 3.0 feeds)
