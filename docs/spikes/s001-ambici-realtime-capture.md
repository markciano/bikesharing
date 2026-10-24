# Spike — AMBici GBFS observation

**Status:** Done — capture from 2026-10-03T12:59Z to 2026-10-05T14:26Z (UTC, first and last request); analysis window 2026-10-03T17:11Z to 2026-10-05T14:26Z.
**Script:** `spikes/ambici-spike/ambici-spike.py` (Python standard library, throwaway).
**Analysis:** `spikes/realtime-capture-analysis/analyse_realtime_capture.py`; evidence in `spikes/ambici-spike/analysis/`.

Context: no public historical AMBici data exists, so we must capture it ourselves (see [s003-ambici-historical-data.md](s003-ambici-historical-data.md)).

A spike is a short investigation to answer questions before building. Durable findings move to the source card (`docs/sources/ambici.md`) or to an ADR (`docs/decisions/`).

## Questions

Rewritten on 2026-10-05 (T006) around what each answer feeds: the ingestion design (T007), the long-term capture hosting, and later analysis.

Common to AMBici and Bicing:

1. **Schema:** which feeds and fields does each system publish (types, nulls, ranges), did the schema stay stable during the capture, and which GBFS versions does each provider offer (`gbfs_versions`)?
2. **Common model:** what would it take to bring both sources into one station-level model? Field-by-field mapping (direct / rename / transform / no equivalent), including possible ID collisions between systems.
3. **Freshness:** how often does each feed's content really change, and how often does each station report (`last_reported`)? Are `ttl` and `last_updated` usable?
4. **Sampling:** how much usage information is lost when polling every 5 minutes instead of every minute?
5. **Reliability:** how often do requests fail, run slow or return stale data, and are gaps on our side or the provider's?
6. **Identity:** are station IDs stable, and do `station_information` and `station_status` match?
7. **Volume:** how large is each feed, per request and per day, raw and compressed?
8. **Quality:** which impossible or suspicious values appear?

AMBici only:

1. What does `free_bike_status` add over `station_status`, and is it worth its volume?
2. Do the three languages differ beyond translated texts, i.e. is one language enough?

Dropped: "How different are weekday and weekend usage patterns?" — needs weeks of data; answerable only from the long-term capture.

## Method

| Aspect | Choice | Reason |
|---|---|---|
| Feeds | All 9 + `gbfs.json` index, in English | Know the whole dataset, not just the obvious feed |
| Languages | One-off copy in `ca` and `es` | Answer question 10 without tripling the capture |
| Frequency | Dynamic feeds every minute; static every 15 min | Feeds declare `ttl: 60`; static feeds only need enough samples to detect changes |
| Storage | Raw responses untouched, gzip | See ADR-0006 |
| Layout | `raw/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz` | Files organised the way they will be read |
| Request log | One JSONL file per day, all feeds, one line per request including failures | Explains gaps by comparing feeds at the same minute |
| Time | UTC | See ADR-0005 |
| Runtime | Local Mac with `caffeinate -i`, lid open, plugged in | Simple; any gap is itself a finding. Valid for this spike only: the machine cannot run 24/7, so long-term capture must run in the cloud (see Hosting the long-term capture) |
| Duration | Saturday afternoon → Monday afternoon | Weekend + one weekday; rain at the start |

Log fields: `tick_utc`, `requested_at_utc`, `purpose`, `feed`, `language`, `url`, `http_status`, `elapsed_ms`, `bytes_raw`, `bytes_gz`, `server_last_updated`, `file`, `error`.

Size estimate before starting: ~1 GB/day raw, ~70–100 MB/day compressed (dominated by `free_bike_status`).

## Analysis plan

Common to the AMBici and Bicing spikes (Bicing links here). Code implements it without making analysis decisions; any deviation is reported, not decided.

### Common settings

| Aspect | Choice |
|---|---|
| Terms | **System** = AMBici or Bicing. **Feed** = each JSON file a system publishes (`station_status`, `station_information`, …) |
| Script | One script for both systems, configured per system: `spikes/realtime-capture-analysis/analyse_realtime_capture.py` |
| Environment | `venv` with `spikes/realtime-capture-analysis/requirements.txt` (`jsonschema`) |
| Evidence | Written to `spikes/<system>-spike/analysis/` and committed (small derived files, cited by the reports). Raw data stays ignored |
| Evidence files | Per system: `summary.md` (every table the report needs), `field_profile.csv`, `schema_changes.csv`, `schema_violations.csv`, `content_changes.csv`, `station_reporting.csv`, `gaps.csv`, `quality_cases.csv`. Bicing also: `field_comparison.csv` (both systems side by side, input for 2a) |
| Analysis window | Common to both systems: 2026-10-03 17:11Z to 2026-10-05 14:26Z (2,716 ticks). A tick is complete when every feed scheduled for it was requested. Data outside the window is discarded and the report says how much. Exceptions: 7b (4 October, the only complete UTC day) and question 10 (language copies) |
| Grid | Dynamic feeds: one expected tick per minute. Static feeds: expected ticks on the 15-min grid. Off-grid responses (script restarts, Bicing `index_refresh`) are normal responses, ordered by request time, but never expected ticks |
| Timestamps | Converted to UTC at load (ADR-0005), keeping milliseconds. The timestamp fields per system are the fields typed Timestamp/Datetime in the GBFS spec of the declared version (2.3 for AMBici: POSIX integers; 3.0 for Bicing: RFC 3339 strings), listed in the per-system configuration |
| Responses used | In-window `en` responses for AMBici, all in-window responses for Bicing. The AMBici `ca`/`es` copies are used only by question 10 |
| Resolution | Changes faster than the polling interval are not visible: 1 min for `station_status` (and `free_bike_status` in AMBici), 15 min for the other feeds |
| Review loop | (1) Code runs the planned metrics. (2) Owner and Chat review the field profile and results; new checks are added to this plan marked *added after first look*. (3) Code runs only the added checks (`--only`). (4) Before the reports are drafted, one full run without `--only` produces the evidence the reports cite. The report keeps planned and added results apart |

### 1. Schema

| Metric | Definition | Input | Output |
|---|---|---|---|
| 1a. Feeds published | Feed names listed in each `gbfs.json` response. AMBici: from the `en` block, checking that the `en`, `ca` and `es` blocks list the same feeds | `gbfs.json` responses | Feeds per system, first and last time seen (summary) |
| 1b. Declared version | `version` field of each response | Responses used | Versions found per feed; expected one per system (summary) |
| 1c. Versions offered | Versions listed in `gbfs_versions`; if absent, provider documentation and the provider's 3.0 endpoint | Desk research by Chat | Findings. Done 2026-10-05: AMBici publishes no `gbfs_versions` and no 3.0 endpoint was found |
| 1d. Field profile | Per feed and field path: type, % present, % null, min/max, distinct values. Field path = dotted JSON path, list items collapsed (`data.stations[].num_bikes_available`). **% present and % null** are over occurrences of the parent object (e.g. all station items across all responses); top-level fields over responses. **Mixed types:** each type listed with its count. **Distinct values** listed when there are ≤ 20, otherwise only the count. **Numbers:** min/max. **Timestamps** (per configuration): min/max after conversion. **Localised texts** (Bicing): profiled as `…[].text` and `…[].language` | Responses used | `field_profile.csv` with a `feed` column |
| 1e. Schema stability | A field path appears or disappears versus the previous response of the same feed (off-grid responses included, ordered by request time) | Responses used | `schema_changes.csv` (expected empty) |
| 1f. Compliance | Violations of the official MobilityData GBFS JSON Schema for the declared version (repository commit in `schemas/SOURCE.md`). Grouped by feed + JSON Schema keyword + schema path | Responses used + official schemas | `schema_violations.csv` with columns: feed, keyword, schema path, instance path (list indices collapsed), message, occurrences, responses affected, first example file, schema commit |

### 2. Common model

Target model: GBFS 3.0 (Bicing already uses it; AMBici 2.3 is mapped to it).

| Metric | Definition | Input | Output |
|---|---|---|---|
| 2a. Field mapping | For every field of the GBFS 3.0 feeds both systems publish (`station_information`, `station_status`, `vehicle_types`): **direct** (same name, type and meaning), **rename** (same meaning and type, other name), **transform** (needs a conversion of type, format, unit or structure), **no equivalent**. A Bicing field that violates the 3.0 schema counts as transform | Code: `field_comparison.csv`. Chat: classification using the MobilityData 2.3 → 3.0 changes and 1f | Markdown table in the Bicing report (field, AMBici category, Bicing category, note) |
| 2a input. Field comparison | One row per (feed, field path) in the union of both systems, for `station_information`, `station_status` and `vehicle_types`; outer join on feed + path, matched literally (renames are left to the 2a classification). Columns per system: present (yes/no), type, % present, % null, min, max, distinct values or count, 1f violation count | 1d + 1f | `field_comparison.csv` (Bicing analysis folder) |
| 2b. Effort summary | Count of fields per category and system | 2a | Table in the Bicing report |
| 2c. ID collisions | Same `station_id` or `vehicle_type_id` value in both systems | Full set of `station_id` and `vehicle_type_id` values from all responses used of `station_information`, `station_status` and `vehicle_types` | Count and list (summary) |
| 2d. Feeds without equivalent | Feeds published by only one system | 1a | List (summary) |

### 3. Freshness

| Metric | Definition | Input | Output |
|---|---|---|---|
| 3a. Content change rate | Per feed: % of consecutive responses whose `data` block differs (header fields `last_updated`, `ttl`, `version` ignored), and time between changes (median, p95) by request time. A pair of responses spanning a missing or failed tick is not counted as an interval. Off-grid responses included, ordered by request time. "Differs" means a different value: numbers are compared by value (50 = 50.0; a boolean never equals a number), key order is ignored, lists of objects with an ID field (`station_id`, `bike_id`, `vehicle_type_id`, `plan_id`, `region_id`) are compared as sets keyed by that ID, and other lists are compared in order | Responses used | `content_changes.csv`: one row per detected change; columns: feed, request time, previous change (request time), interval (s). Summary: per feed, responses, pairs compared, pairs excluded (gap), changes, % changed, interval median, p95, max |
| 3b. Station reporting interval | Per station: time between consecutive distinct `last_reported` values, over responses exactly 1 tick apart (pairs spanning a missing or failed tick are excluded, as in 3a). Also: `last_reported` changes with no count change (heartbeat), and count changes with no `last_reported` change (silent change). "Count" = any numeric field per station (available, docks, disabled, per type). If a system stamps every station with the feed time, report "3b not measurable" for it as a finding | `station_status` | `station_reporting.csv`: one row per station; columns: station_id, intervals, interval median, p95, max (s), heartbeats, silent changes. Summary: distribution across stations of each station's median interval (median, p95, max), and totals of heartbeats and silent changes |
| 3c. `last_updated` behaviour | Request time minus `last_updated`: lag distribution, values going backwards, values older than `ttl`. With `ttl: 0` (Bicing) "older than ttl" does not apply; only the lag is reported | Request log + responses | Summary |
| 3d. Declared vs measured | Declared `ttl` per feed next to the measured change interval from 3a | 3a | Summary |

### 4. Sampling

| Metric | Definition | Input | Output |
|---|---|---|---|
| 4a. Observed activity | Per station: sum of absolute changes in available bikes between consecutive responses exactly 1 tick apart (lower bound of rentals + returns). Total = available, disabled excluded; also per vehicle type from `vehicle_types_available` (both systems). Field names come from the per-system configuration. Pairs spanning a gap are excluded and counted; a station missing from either response is skipped for that pair | `station_status` | Totals per system (summary) |
| 4b. Loss by interval | Recompute 4a keeping one response every 2, 5, 10 and 15 min, comparing only responses exactly N ticks apart (same exclusion rules); loss % = 1 − activity at N min ÷ activity at 1 min; for each N, averaged over all N possible starting minutes | 4a | Table interval → loss % (summary) |
| 4c. Change size at 1 min | Distribution of the change per step: \|Δ\| = 1 vs ≥ 2 | 4a | Table (summary) |

### 5. Reliability

| Metric | Definition | Input | Output |
|---|---|---|---|
| 5a. Failed requests | Per feed: % of requests with HTTP status ≠ 200, timeout or connection error | Request log | Summary |
| 5b. Latency | Per feed: `elapsed_ms` median, p95, max over successful requests; failed requests reported separately with their elapsed time | Request log | Summary |
| 5c. Stale responses | `last_updated` earlier than that of the previous response of the same feed. A trivially empty result is a finding | Request log (`server_last_updated`) | Count and list (summary) |
| 5d. Gaps | Expected tick (see Grid) without a stored response. Each missing tick is classified, comparing systems by scheduled tick (not wall-clock time), in this order: (1) Mac asleep (from a `Sleep` line to the next `Wake`/`DarkWake` line in the pmset excerpt) → **ours**; (2) tick missing because the previous tick's requests overran the minute → inherits the class of the failures that caused it, or "blocked" if those failures have different classes; (3) request failed and every request of the other system on the same tick succeeded → **provider**; (4) request failed and at least one request of the other system on the same tick failed, or the other system has no log line on that tick → **ours (probable)**; (5) no log line and none of the above → **ours** | Request logs of both systems + `raw/` + `spikes/realtime-capture-analysis/inputs/pmset-sleep-wake-2026-10-03-to-2026-10-05.txt` (local time, UTC = local − 2 h) | `gaps.csv`: one row per run of consecutive missing expected ticks with the same feed and class; columns: feed, start, end, duration (ticks), class, rule (1–5), log lines. Summary: totals per class and feed |

### 6. Identity

| Metric | Definition | Input | Output |
|---|---|---|---|
| 6a. Station set over time | Station IDs per `station_information` response; stations added or removed (first and last time seen) | `station_information` | List (summary) |
| 6b. Information ↔ status match | Per `station_status` response, against the latest `station_information` received before it (as-of join): IDs with status but no information, and the reverse | Both feeds | Counts and IDs (summary) |
| 6c. Attribute stability | Per station: changes in name, coordinates or `capacity`. Bicing also: `vehicle_docks_capacity`, compared with the 3a rules | `station_information` | List (summary) |
| 6d. ID format | Type and pattern of `station_id`, by simple rules: numeric, UUID, other | Same full ID set as 2c | One line per system (summary) |

### 7. Volume

| Metric | Definition | Input | Output |
|---|---|---|---|
| 7a. Size per request | Per feed: `bytes_raw` and `bytes_gz` median and max. `bytes_gz` is our own gzip size, which is what storage would hold | Request log | Summary |
| 7b. Size per day | Per feed: sum of `bytes_gz` over 4 October (UTC), as measured, stating responses stored vs expected (1,434 of 1,440 for `station_status`) | Request log | Summary |
| 7c. Projection | Per month and per year, with median size × expected responses per day, against the Cloudflare R2 free limit (10 GB per account, both systems added up), for four scenarios: all feeds as captured / without `free_bike_status` (AMBici only), each at 1-min and 5-min polling of the dynamic feeds | 7a | Table (summary) |

### 8. Quality

Planned checks; checks found during the review loop are added below, marked *added after first look*.

| Check | Definition | Feed |
|---|---|---|
| 8a. Over capacity | Capacity = `capacity` from `station_information` (both systems publish it). Bicing: also check that `capacity` equals the `count` of its single `vehicle_docks_capacity` group. Two variants: (i) bikes available + docks available > capacity; (ii) (i) + bikes disabled + docks disabled, where published (Bicing only). Field names from the per-system configuration | status + information (as-of) |
| 8b. Negative counts | Any count < 0 | `station_status` |
| 8c. Type breakdown mismatch | Sum of `vehicle_types_available[].count` ≠ total available (`num_bikes_available` in AMBici, `num_vehicles_available` in Bicing). Stations with an empty or missing `vehicle_types_available` are counted apart, not as mismatches | `station_status` |
| 8d. Stale station | `is_installed` true and `last_reported` older than 24 h at request time | `station_status` |
| 8e. Future timestamp | `last_reported` later than request time + 1 min (clock tolerance) | `station_status` |
| 8f. Inactive stations | Stations with `is_installed`, `is_renting` or `is_returning` false | `station_status` |
| 8g. Duplicate ID | Same `station_id` twice in one response | status + information |
| 8h. Out of area | Coordinates outside latitude 41.20–41.60, longitude 1.85–2.35 | `station_information` |
| 8i. Known issues | AMBici: (1) `system_information.timezone` is `Europe/Berlin`; (2) bikes with no `current_fuel_percent` and `current_range_meters` = 0 (the combined condition from the source card), with a breakdown of the other bikes missing either value: no `current_fuel_percent` and no `current_range_meters`; no `current_fuel_percent` and `current_range_meters` > 0; `current_range_meters` = 0 and `current_fuel_percent` present. Bicing: none listed | `system_information`, `free_bike_status` |
| 8j. Inactive flags vs availability (*added after first look*) | `is_renting` false, split by total available = 0 vs > 0 (`num_bikes_available` in AMBici, `num_vehicles_available` in Bicing); `is_returning` false, split by `num_docks_available` = 0 vs > 0; and the reverse: total available = 0 with `is_renting` true. Counted over station items | `station_status` |

Output: per check, affected responses or stations and % (summary); affected cases in `quality_cases.csv`, one row per check + variant + case, with columns: check, variant, feed, case_id (station_id, bike_id or `(response)`), detail (values of the first occurrence), responses affected, first seen (UTC), last seen (UTC), first example file.

### 9. `free_bike_status` (AMBici only)

| Metric | Definition | Input | Output |
|---|---|---|---|
| 9a. Extra fields | Fields with no equivalent in `station_status` ("equivalent" = the data exists aggregated per station in `station_status`) | Code: list of `free_bike_status` field paths with their 1d profile. Chat: the classification | List (summary); classification in the AMBici report |
| 9b. Bikes outside stations | % of bikes with no `station_id`, per response | `free_bike_status` | Summary |
| 9c. Consistency | Available bikes per station from `free_bike_status` (not `is_reserved` and not `is_disabled`, as GBFS defines `num_bikes_available`) vs `num_bikes_available` for the same tick. Mismatch rate also reported split by whether both responses carry the same `last_updated`. | Both feeds | Mismatch rate (summary) |
| 9d. Cost | Share of AMBici's daily volume | 7b | One line (summary) |

### 10. Languages (AMBici only)

Exempt from the analysis window. Both sets of language copies are used (2026-10-03 12:59Z and 14:41Z), each paired with the nearest `en` response.

| Metric | Definition | Input | Output |
|---|---|---|---|
| 10a. Structure | Per feed: same field paths in `en`, `ca`, `es` | `ca`/`es` copies + nearest `en` responses | Yes/no per feed (summary) |
| 10b. Values | Static feeds only: fields whose values differ, classified as translated text, language-dependent by design (`system_information.language`, URLs containing the language) or other (numbers, IDs, coordinates) | Same | List (summary); "other" expected empty |

### Verification

Spike code is throwaway and exempt from the test rules in CLAUDE.md › Code › Testing (standard spike practice; decided in T006). Correctness is checked through the evidence instead. Code adds to each `summary.md`:

- **Reconciliation**, checked as soon as loading exists, over the responses used (see Common settings): requests in the log = stored responses + failed requests; per feed and system, expected ticks = ticks with a response + ticks without one. Requests outside the window and AMBici language-copy requests are not reconciled; they are counted in the data discarded. Once `gaps.csv` exists, the ticks inside gaps must equal the ticks without a response. Any mismatch is reported, not corrected.
- **Hand-checkable examples:** for 4b, one station and one time range showing the 1-min and 5-min activity side by side; for 5d, one gap of each class with its log lines (a class with no gaps is reported as "none, class empty"); for 6b, one `station_status` response and the `station_information` it was joined to. Each example names the raw files involved, so the owner can check it in Review.

### Plan history

- 2026-10-05: approved.
- 2026-10-05: amended after the step 1 inventory (window, grid, timestamps and per-metric rules).
- 2026-10-06: amended after review against the part 1 prompt (reconciliation, ID inputs, field comparison columns, profile denominators, timestamp fields, compliance grouping).
- 2026-10-06: reconciliation scoped to the responses used; 1b input aligned with 1d–1f.
- 2026-10-06: amended before part 2 (gap grouping in 5d, columns of content_changes.csv and station_reporting.csv, 3b gap rule).
- 2026-10-06: amended during part 2 (5d classification by scheduled tick and sleep definition; 3a comparison rules).
- 2026-10-06: amended before part 3 (final full run in the review loop; 8a capacity source and two variants; 4a per type and 8c for both systems; 9a classification by Chat).
- 2026-10-06: 8c row added to Quality (it was announced in the previous line but missing); Bicing-specific points aligned (4a per type and 8c are now common).
- 2026-10-06: amended at part 3 step 2 (6c capacity for Bicing, 8i combined condition, 9c split by `last_updated`, columns of quality_cases.csv).
- 2026-10-06: after first look at part 3: 8j added; 8i breakdown splits out bikes missing both values. Other candidates (AMBici `last_reported` ≠ `last_updated`, 5d slow successes, Bicing `last_updated` ahead of request time) go to Findings with the existing evidence (3b, 5d, 3c).

Earlier versions are in Git.

## Findings

### Hosting the long-term capture (2026-10-03)

Constraint: the owner's machine cannot run 24/7, so capture must run in the cloud.

| Option | Assessment |
|---|---|
| a. Cloudflare Worker (Cron Trigger) + R2 | **Preferred.** See details below |
| b. GitHub Actions schedule | Viable fallback, not preferred |
| c. Azure Functions + Blob/ADLS Gen2 | Closest to Fabric (ADR-0003); cost not verified |
| d. Always-on small machine (Raspberry Pi, free-tier VM, VPS) | Maintenance burden, single point of failure |

#### a. Cloudflare Worker + R2

- Free plan: 5 cron triggers per account, 1-minute minimum interval, 100,000 requests/day, 10 ms CPU per cron invocation.
- CPU time excludes waiting on `fetch()` and R2 operations. Cloudflare reports an average Worker uses ~2.2 ms, and the runtime tolerates occasional overruns.
- The Worker only fetches the feed and stores the body as received (no parsing), so it should fit. Risk: compressing inside the Worker costs CPU; fallback is storing uncompressed and compressing in a later batch.
- R2: 10 GB free, no egress fees, S3-compatible.
- To verify with a 1-day prototype: CPU time per invocation (Workers Logs), response sizes, R2 free operation limits.

#### b. GitHub Actions schedule

- The 5-minute minimum interval is acceptable for the baseline (weekday × time slot).
- Best-effort scheduling (delays, dropped runs) → irregular gaps.
- Scheduled workflows are disabled after 60 days without repo activity (likely, since raw data cannot be committed per CLAUDE.md).
- Free only for public repos; private: 2,000 min/month, each job rounded up to 1 min, so every 5 min ≈ 8,640 min/month.
- Still needs external storage: two services instead of one.

### Capture findings

Evidence: [`spikes/ambici-spike/analysis/summary.md`](../../../spikes/ambici-spike/analysis/summary.md) and the CSV files next to it, from the final full run of `spikes/realtime-capture-analysis/analyse_realtime_capture.py`. Analysis window 2026-10-03T17:11Z to 2026-10-05T14:26Z (2,716 one-minute ticks); 4 October is the only complete UTC day. Planned results come first; checks added after the first look are kept apart at the end.

#### 1. Schema

**Answer:** AMBici publishes 9 feeds plus the `gbfs.json` index, only in GBFS 2.3; the schema was stable and fully compliant during the capture.

- 1a. Every `gbfs.json` response lists the same 9 feeds in its `ca`, `en` and `es` blocks: `system_information`, `station_information`, `station_status`, `free_bike_status`, `vehicle_types`, `system_hours`, `system_regions`, `system_pricing_plans`, `geofencing_zones`.
- 1b. Every response of every feed declares `version` 2.3.
- 1c. AMBici publishes no `gbfs_versions` feed and offers only 2.3; no 3.0 endpoint was found (checked 2026-10-05; an email to nextbike got no answer).
- 1d. No field path has nulls. The only mixed type is `free_bike_status` `data.bikes[].current_fuel_percent` (2,593,111 integer and 3,021,945 non-integer values). Full profile in `field_profile.csv`.
- 1e. No field path appeared or disappeared between consecutive responses (`schema_changes.csv` is empty).
- 1f. 0 violations of the official MobilityData GBFS 2.3 JSON Schema (commit `2e974fd`). The check is structural only: `format` is not asserted, and timestamps are covered by the UTC conversion of 1d, which found no unconvertible value.

#### 2. Common model

**Answer:** see the Bicing report, which holds the field mapping (2a) and effort summary (2b) because Bicing already uses GBFS 3.0, the target model.

- 2c. No `station_id` or `vehicle_type_id` value appears in both systems (AMBici: 237 station IDs, 3 vehicle type IDs; all strings).
- 2d. Feeds published only by AMBici: `free_bike_status`, `system_hours`. Only by Bicing: `gbfs_versions`.

#### 3. Freshness

**Answer:** the dynamic feeds change every 60 s, as `ttl` 60 declares. `last_reported` carries the feed time, not the station's own report time, so station reporting cannot be measured (3b not measurable). `last_updated` is usable but can go back by 1–3 s.

- 3a. `station_status` content changed in 98.63 % of consecutive response pairs and `free_bike_status` in 97.45 %; median interval between changes 60 s for both. The static feeds never changed during the window, except `system_hours` (2 changes).
- 3b. `last_reported` equals the response's `last_updated` for 99.92 % of station items (641,781 of 642,270). Every station's median reporting interval is 61 s; 615,769 heartbeats and 0 silent changes. The 1,659 negative intervals are the 7 backward steps of `last_updated` (3c) repeated across the 237 stations.
- 3c. Lag (request time − `last_updated`): median 31 s, max 64 s for `station_status`; 78 of 2,710 responses older than `ttl`. `last_updated` went backwards 7 times in `station_status` and 5 times in `free_bike_status`, by 1–3 s each time.
- 3d. Measured change interval = declared `ttl` (60 s) for the two dynamic feeds. The static feeds declare `ttl` 60 (86,400 for `system_pricing_plans` and `geofencing_zones`) but did not change in two days, so `ttl` says nothing about their change rate.

#### 4. Sampling

**Answer:** polling every 5 minutes instead of every minute loses 17.5 % of the observed activity.

- 4a. Observed activity in the window (sum of |Δ| available bikes between responses 1 min apart, a lower bound of rentals + returns): 18,303 bikes; type `204` 18,291, type `196` 12. Type `420` never appears in `station_status`.
- 4b. Loss versus 1-min polling: 2 min 7.56 %, 5 min 17.49 %, 10 min 26.83 %, 15 min 33.51 %. Hand-checkable example in the summary (Verification).
- 4c. 91.23 % of the 1-min changes are |Δ| = 1; 8.77 % are ≥ 2.

#### 5. Reliability

**Answer:** 7 of 6,874 requests failed (0.10 %), all during one incident on 2026-10-04 from 18:39 to 18:50 UTC that affected both systems. No gap was caused by the Mac sleeping.

- 5a. Failures: 3 in `station_status` (2 timeouts, 1 connection reset), 4 in `free_bike_status` (timeouts); none in the static feeds.
- 5b. Median latency 131 ms for `station_status` and 222 ms for `free_bike_status`; p95 under 400 ms for every feed. The failed requests took 18.6–50.9 s with a 20 s timeout configured: the urllib timeout applies per socket operation, not per request.
- 5c. 12 stale responses (`last_updated` earlier than the previous one): the backward steps of 3c.
- 5d. 13 missing expected ticks (6 `station_status`, 7 `free_bike_status`), all in the incident: 4 classed provider, 9 ours (probable), 0 ours. The requests are sequential, so slow requests consumed the following ticks (rule 2). Caveat: the 4 provider ticks (18:42–18:43) are classed so because Bicing's request on 18:42 succeeded, but it took 50.6 s; as the incident affected both systems, that class is uncertain. Three minutes have no AMBici log line at all (18:41, 18:43, 18:50); across both systems that is 4 system–minute pairs, not 4 distinct minutes.

#### 6. Identity

**Answer:** station IDs were stable and `station_information` and `station_status` always matched.

- 6a. 237 stations in every `station_information` response; none added or removed.
- 6b. No status response has an ID without information or the reverse (2,705 joined; the 5 status responses before the first `station_information` of the window were skipped).
- 6c. No change in name, coordinates or `capacity`.
- 6d. `station_id` is a 9-digit numeric string.

#### 7. Volume

**Answer:** about 75 MB per day compressed, of which `free_bike_status` is 94 %.

- 7a. Median per request, raw / gzip: `station_status` 53 KB / 2.3 KB; `free_bike_status` 897 KB / 51 KB; `station_information` 80 KB / 10.6 KB; every other feed under 4 KB raw.
- 7b. 4 October (UTC): 75.34 MB gzip in total; `free_bike_status` 70.81 MB, `station_status` 3.29 MB, `station_information` 1.01 MB. The pre-capture estimate (70–100 MB/day) holds.
- 7c. Both systems together against the Cloudflare R2 free storage (10 GB): all feeds at 1-min polling, 35.5 GB per year (355 %); without `free_bike_status` at 1 min, 8.7 GB (87 %); without it at 5 min, 3.5 GB (35 %). GB = 10⁹ bytes; Cloudflare's own GB definition was not checked.

#### 8. Quality

**Answer:** no impossible values (negative counts, duplicates, future timestamps, out-of-area coordinates); three suspicious patterns: available bikes + docks above `capacity`, 8 stations permanently inactive, and the two known issues of the source card, both confirmed.

- 8a. Available bikes + available docks > `capacity` in 3.04 % of station items, at 43 of 237 stations, in 99.82 % of responses. AMBici publishes no disabled counts, so variant (ii) does not apply.
- 8b, 8d, 8e, 8g, 8h. None found.
- 8c. The per-type counts always add up to `num_bikes_available`. 96 stations at times list no vehicle types; this happens only with 0 bikes available (AMBici omits zero counts).
- 8f. 8 stations have `is_renting` and `is_returning` false in every response.
- 8i. `system_information.timezone` is `Europe/Berlin` in all 181 responses (Barcelona is `Europe/Madrid`). Bikes with no `current_fuel_percent` and `current_range_meters` = 0: 36,344 bike items, 466 distinct bikes, present in every response.

#### 9. `free_bike_status`

**Answer:** it adds only battery data and reservations to `station_status`, at 94 % of AMBici's volume.

9a. Each field, classified against `station_status` (equivalent = the data exists aggregated per station there):

| Field (`data.bikes[].…`) | Classification | Note |
|---|---|---|
| `station_id` | Equivalent | The aggregation key itself |
| `vehicle_type_id` | Equivalent | `vehicle_types_available[].count` per station |
| `is_disabled` | No equivalent | Always `false`; `station_status` publishes no disabled count |
| `is_reserved` | No equivalent | `false`/`true`; `station_status` has no reserved count (GBFS excludes reserved bikes from `num_bikes_available`) |
| `current_fuel_percent` | No equivalent | Battery level, 0.02–1; absent for 0.69 % of bike items (8i) |
| `current_range_meters` | No equivalent | 0–60,000 m |
| `bike_id` | No equivalent | 12,065 distinct IDs in the window, while a response holds ~2,087 bikes; consistent with the ID rotation GBFS 2.x requires, so bikes cannot be followed across trips (not confirmed) |
| `lat`, `lon` | No equivalent in `station_status` | 236–237 distinct values: the station coordinates (all bikes are docked, 9b); redundant with `station_information` |
| `rental_uris.android/ios/web` | No equivalent in `station_status` | 237 distinct values: one per station, not per bike |
| `pricing_plan_id` | No equivalent in `station_status` | Constant `Rate0010` |
| `last_updated`, `ttl`, `version` | Equivalent | Same header as every feed |

- 9b. Every bike has a `station_id`: AMBici has no free-floating bikes.
- 9c. Available bikes per station from `free_bike_status` differ from `num_bikes_available` in 0.34 % of (station, tick) pairs: 0.32 % when both responses carry the same `last_updated`, 0.37 % when they don't, so the timing difference does not explain the mismatch.
- 9d. 93.98 % of AMBici's daily volume (4 October).

#### 10. Languages

**Answer:** one language is enough: the `ca` and `es` copies have the same structure as `en`, and only vehicle type names and descriptions differ.

- 10a. Same field paths in `en`, `ca` and `es` for all 9 feeds (the `gbfs.json` index is language-independent and was not copied).
- 10b. In the static feeds, the only values that differ are `system_information.language` (by design), `vehicle_types[].name` and the non-standard `vehicle_types[]._description`. The `ca` and `es` copies are identical: type `204` is named "Bicicleta eléctrica" with a Spanish description, type `196` keeps the German name "SMARTbike 2.0 armiert", and the other descriptions stay in English. No Catalan text was found. The 15 "other" differences are all `last_updated` (the copies were taken 40–50 s before their `en` pair).

#### Added after first look

Checks added to the plan after reviewing the first results (Analysis plan › Review loop).

- 8i breakdown. Of the bikes missing a battery value outside the combined condition: no `current_fuel_percent` and no `current_range_meters`, 2,636 bike items, 7 bikes; `current_range_meters` = 0 with `current_fuel_percent` present, 1,009 items, 25 bikes; no `current_fuel_percent` with `current_range_meters` > 0, none.
- 8j. Inactive flags vs availability. The 8 stations with `is_renting` false hold bikes: 21,364 station items with bikes available, at 8 stations, in every response; only 316 items (2 stations) have `is_renting` false with 0 bikes. Conversely, 14,425 items (94 stations) have 0 bikes and `is_renting` true. An empty station is therefore not flagged as not renting. `is_returning` false: 17,366 items with free docks (8 stations), 4,314 with none (5 stations).
- Reviewed and left as findings without a new check: `last_reported` ≠ `last_updated` for 0.08 % of station items (3b); the 5d provider class on 18:42 (see 5d).

## Conclusion

**Recommendation (Proposed, pending owner's OK):** option (a), Cloudflare Worker + R2, for the long-term AMBici capture. Next step: a 1-day prototype capturing `station_status` every minute, measuring CPU time and size, before any decision entry.

**For T007 (ingestion design):**

- Configure AMBici as GBFS 2.3, English only (`…/nextbike_bs/en/`); no other version is offered. The 9 feeds and their schema were stable and compliant, so validating against the official 2.3 schema is realistic.
- Timestamps are POSIX seconds, converted to UTC (ADR-0005). `last_reported` is the feed time, not a station event time: do not use it to detect station changes; compare content instead. `last_updated` is not strictly monotonic (steps back of 1–3 s), so ordering and deduplication cannot rely on it alone.
- Parse `current_fuel_percent` as a number (integer or float). Treat a vehicle type missing from `vehicle_types_available` as 0.
- Do not treat `capacity` as an upper bound (exceeded in 3 % of station items), and do not read `is_renting` false as "empty".
- Station IDs do not collide with Bicing's, but the formats differ: key stations by (system, `station_id`).
- Known source issues to handle in configuration: `timezone` `Europe/Berlin` (should be `Europe/Madrid`) and the non-standard `_description` field.

**For the long-term capture:**

- The dynamic feeds change every 60 s, so 1-min polling captures every published state. 5-min polling loses 17.5 % of observed activity, 15-min 33.5 % (lower bounds).
- The static feeds did not change in two days: polling them every 15 min is more than enough.
- `free_bike_status` is 94 % of the volume and adds only battery and reservation data (question 9). With every feed of both systems at 1 min, one year needs 355 % of the R2 free storage; without `free_bike_status`, 87 % at 1 min and 35 % at 5 min. Which feeds and which interval to keep is part of the scope decision, taken after all sources are analysed.
- Reliability was high (0.10 % failed requests, all in one 11-minute incident shared with Bicing). Lessons for the capture code: enforce a total deadline per request (the urllib timeout is per socket operation) and do not run feeds sequentially in one loop, so that one slow request cannot consume the following ticks.

The hosting prototype and its ADR become a new task in `docs/tasks.md`, added when T006 closes.

## Sources

- <https://developers.cloudflare.com/workers/platform/limits/>
- <https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions>
- <https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md> (GBFS 2.3 specification)
- <https://github.com/MobilityData/gbfs-json-schema> (official JSON Schemas, commit `2e974fd51ae1db9c8006c97375d53e0b882cfedf`)
- <https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_bs/> (AMBici GBFS feeds, one folder per language)
