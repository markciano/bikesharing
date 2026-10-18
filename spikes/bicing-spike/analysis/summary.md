# Bicing realtime capture — analysis summary

Evidence for T006, produced by `spikes/realtime-capture-analysis/analyse_realtime_capture.py` (parts 1–3). Spec: [Analysis plan](../../../docs/spikes/s001-ambici-realtime-capture.md#analysis-plan).

## Analysis window

2026-10-03T17:11:00.000Z to 2026-10-05T14:26:00.000Z, both ticks included. Responses used: all in-window responses (4175 log lines, 4170 stored responses).

## Data discarded

None.

Raw files on disk outside the window: 0.

## Configuration used

| Item | Value |
|---|---|
| Declared GBFS version (configured) | 3.0 |
| Dynamic feeds (1-min grid) | `station_status` |
| Static feeds (15-min grid) | `gbfs`, `gbfs_versions`, `geofencing_zones`, `station_information`, `system_information`, `system_pricing_plans`, `system_regions`, `vehicle_types` |
| Timestamp format | RFC 3339 |
| Timestamp fields (from the official schemas) | `*`: `last_updated`; `station_status`: `data.stations[].last_reported`; `geofencing_zones`: `data.geofencing_zones.features[].properties.start`, `data.geofencing_zones.features[].properties.end` |

## Schema commit

MobilityData `gbfs-json-schema` commit `2e974fd51ae1db9c8006c97375d53e0b882cfedf` (from `schemas/SOURCE.md`).

## Verification › Reconciliation

Over the responses used. Any mismatch is reported, not corrected.

### Requests in the log = stored responses + failed requests

| Requests in the log | Stored responses (raw files on disk) | Failed requests | Holds |
|---|---|---|---|
| 4175 | 4170 | 5 | yes |

Stored responses counted from the raw files on disk whose file-name time is in the window. Logged as stored but missing on disk: 0. On disk but not in the log: 0. Stored responses that could not be read or parsed: 0.

### Per feed: expected ticks = ticks with a response + ticks without one

Ticks without a response are split into failed request and no log line. Off-grid responses (script start, `index_refresh`) are used by the metrics but are never expected ticks.

| Feed | Expected ticks | With a response | Without: failed request | Without: no log line | Holds | Off-grid responses | Duplicate responses on a tick |
|---|---|---|---|---|---|---|---|
| `station_status` | 2716 | 2710 | 5 | 1 | yes | 0 | 0 |
| `gbfs` | 181 | 181 | 0 | 0 | yes | 5 | 0 |
| `gbfs_versions` | 181 | 181 | 0 | 0 | yes | 1 | 0 |
| `geofencing_zones` | 181 | 181 | 0 | 0 | yes | 1 | 0 |
| `station_information` | 181 | 181 | 0 | 0 | yes | 1 | 0 |
| `system_information` | 181 | 181 | 0 | 0 | yes | 1 | 0 |
| `system_pricing_plans` | 181 | 181 | 0 | 0 | yes | 1 | 0 |
| `system_regions` | 181 | 181 | 0 | 0 | yes | 1 | 0 |
| `vehicle_types` | 181 | 181 | 0 | 0 | yes | 1 | 0 |

<!-- BEGIN metric:5d.check -->
### Ticks inside gaps = ticks without a response (`gaps.csv` check)

| Feed | Ticks inside gaps | Ticks without a response | Holds |
|---|---|---|---|
| `station_status` | 6 | 6 | yes |
| `gbfs` | 0 | 0 | yes |
| `gbfs_versions` | 0 | 0 | yes |
| `geofencing_zones` | 0 | 0 | yes |
| `station_information` | 0 | 0 | yes |
| `system_information` | 0 | 0 | yes |
| `system_pricing_plans` | 0 | 0 | yes |
| `system_regions` | 0 | 0 | yes |
| `vehicle_types` | 0 | 0 | yes |
<!-- END metric:5d.check -->

### Failed requests in the window

| Tick | Requested at | Purpose | Feed | HTTP status | Elapsed ms | Error |
|---|---|---|---|---|---|---|
| 2026-10-04T18:39:00.000Z | 2026-10-04T18:39:00.007Z | observation | `station_status` | None | 36093 | timeout |
| 2026-10-04T18:40:00.000Z | 2026-10-04T18:40:00.010Z | observation | `station_status` | None | 48200 | timeout |
| 2026-10-04T18:43:00.000Z | 2026-10-04T18:43:00.004Z | observation | `station_status` | None | 32415 | timeout |
| 2026-10-04T18:45:00.000Z | 2026-10-04T18:45:06.382Z | observation | `station_status` | None | 22292 | timeout |
| 2026-10-04T18:49:00.000Z | 2026-10-04T18:49:00.003Z | observation | `station_status` | None | 22348 | timeout |

### Check against the step 1 inventory

| Item | Expected (inventory) | Found |
|---|---|---|
| Ticks in the window | 2716 | 2716 |
| Failed requests in the window (Bicing) | 5 | 5 |
| Missing ticks: no log line at all (Bicing) | — | 2026-10-04T18:41:00.000Z |
| Missing ticks, total across both systems | 3 | 4 (system, tick) pairs on 3 distinct minutes |

## Verification › Hand-checkable examples

Raw file paths are relative to each system's capture folder.

<!-- BEGIN metric:4b.example -->
### 4b. One station, 1-min vs 5-min activity

Station `78` (highest 1-min activity over the window: 741), first 30-min block from the window start (offset 0) where the 5-min activity is lower than the 1-min activity. `num_vehicles_available` per tick:

| Tick | Raw file | Available | \|Δ\| 1 min | 5-min sample | \|Δ\| 5 min |
|---|---|---|---|---|---|
| 2026-10-03T17:11:00.000Z | `raw/station_status/2026-10-03/20261003T171100Z.json.gz` | 16 |  | yes |  |
| 2026-10-03T17:12:00.000Z | `raw/station_status/2026-10-03/20261003T171200Z.json.gz` | 15 | 1 |  |  |
| 2026-10-03T17:13:00.000Z | `raw/station_status/2026-10-03/20261003T171300Z.json.gz` | 15 | 0 |  |  |
| 2026-10-03T17:14:00.000Z | `raw/station_status/2026-10-03/20261003T171400Z.json.gz` | 15 | 0 |  |  |
| 2026-10-03T17:15:00.000Z | `raw/station_status/2026-10-03/20261003T171500Z.json.gz` | 17 | 2 |  |  |
| 2026-10-03T17:16:00.000Z | `raw/station_status/2026-10-03/20261003T171600Z.json.gz` | 19 | 2 | yes | 3 |
| 2026-10-03T17:17:00.000Z | `raw/station_status/2026-10-03/20261003T171700Z.json.gz` | 19 | 0 |  |  |
| 2026-10-03T17:18:00.000Z | `raw/station_status/2026-10-03/20261003T171800Z.json.gz` | 20 | 1 |  |  |
| 2026-10-03T17:19:00.000Z | `raw/station_status/2026-10-03/20261003T171900Z.json.gz` | 19 | 1 |  |  |
| 2026-10-03T17:20:00.000Z | `raw/station_status/2026-10-03/20261003T172000Z.json.gz` | 19 | 0 |  |  |
| 2026-10-03T17:21:00.000Z | `raw/station_status/2026-10-03/20261003T172100Z.json.gz` | 19 | 0 | yes | 0 |
| 2026-10-03T17:22:00.000Z | `raw/station_status/2026-10-03/20261003T172200Z.json.gz` | 19 | 0 |  |  |
| 2026-10-03T17:23:00.000Z | `raw/station_status/2026-10-03/20261003T172300Z.json.gz` | 19 | 0 |  |  |
| 2026-10-03T17:24:00.000Z | `raw/station_status/2026-10-03/20261003T172400Z.json.gz` | 17 | 2 |  |  |
| 2026-10-03T17:25:00.000Z | `raw/station_status/2026-10-03/20261003T172500Z.json.gz` | 18 | 1 |  |  |
| 2026-10-03T17:26:00.000Z | `raw/station_status/2026-10-03/20261003T172600Z.json.gz` | 18 | 0 | yes | 1 |
| 2026-10-03T17:27:00.000Z | `raw/station_status/2026-10-03/20261003T172700Z.json.gz` | 18 | 0 |  |  |
| 2026-10-03T17:28:00.000Z | `raw/station_status/2026-10-03/20261003T172800Z.json.gz` | 18 | 0 |  |  |
| 2026-10-03T17:29:00.000Z | `raw/station_status/2026-10-03/20261003T172900Z.json.gz` | 18 | 0 |  |  |
| 2026-10-03T17:30:00.000Z | `raw/station_status/2026-10-03/20261003T173000Z.json.gz` | 18 | 0 |  |  |
| 2026-10-03T17:31:00.000Z | `raw/station_status/2026-10-03/20261003T173100Z.json.gz` | 17 | 1 | yes | 1 |
| 2026-10-03T17:32:00.000Z | `raw/station_status/2026-10-03/20261003T173200Z.json.gz` | 17 | 0 |  |  |
| 2026-10-03T17:33:00.000Z | `raw/station_status/2026-10-03/20261003T173300Z.json.gz` | 17 | 0 |  |  |
| 2026-10-03T17:34:00.000Z | `raw/station_status/2026-10-03/20261003T173400Z.json.gz` | 16 | 1 |  |  |
| 2026-10-03T17:35:00.000Z | `raw/station_status/2026-10-03/20261003T173500Z.json.gz` | 16 | 0 |  |  |
| 2026-10-03T17:36:00.000Z | `raw/station_status/2026-10-03/20261003T173600Z.json.gz` | 16 | 0 | yes | 1 |
| 2026-10-03T17:37:00.000Z | `raw/station_status/2026-10-03/20261003T173700Z.json.gz` | 16 | 0 |  |  |
| 2026-10-03T17:38:00.000Z | `raw/station_status/2026-10-03/20261003T173800Z.json.gz` | 16 | 0 |  |  |
| 2026-10-03T17:39:00.000Z | `raw/station_status/2026-10-03/20261003T173900Z.json.gz` | 15 | 1 |  |  |
| 2026-10-03T17:40:00.000Z | `raw/station_status/2026-10-03/20261003T174000Z.json.gz` | 15 | 0 |  |  |
| 2026-10-03T17:41:00.000Z | `raw/station_status/2026-10-03/20261003T174100Z.json.gz` | 15 | 0 | yes | 1 |
| Sum |  |  | 13 |  | 7 |

1-min activity 13, 5-min activity 7, loss 46.15 %.
<!-- END metric:4b.example -->

<!-- BEGIN metric:5d.example -->
### 5d. One gap per class

**ours:** none, class empty.

**provider:** none, class empty.

**ours (probable):** `station_status` 2026-10-04T18:39:00.000Z to 2026-10-04T18:41:00.000Z, 3 tick(s), rule 4; 2. previous tick with log lines 2026-10-04T18:40:00.000Z; its last request ended 2026-10-04T18:41:02.315Z; failed requests on it: 1.

| Log line | Tick | Requested at | Purpose | Feed | HTTP | Elapsed ms | Error | File |
|---|---|---|---|---|---|---|---|---|
| bicing requests_2026-10-04.jsonl:1720 | 2026-10-04T18:39:00.000Z | 2026-10-04T18:39:00.007Z | observation | `station_status` | None | 36093 | timeout |  |
| ambici requests_2026-10-04.jsonl:2839 | 2026-10-04T18:39:00.000Z | 2026-10-04T18:39:00.007Z | observation | `station_status` | 200 | 6825 |  | `raw/station_status/2026-10-04/20261004T183900Z.json.gz` |
| ambici requests_2026-10-04.jsonl:2840 | 2026-10-04T18:39:00.000Z | 2026-10-04T18:39:06.838Z | observation | `free_bike_status` | None | 50916 | timeout |  |
| bicing requests_2026-10-04.jsonl:1722 | 2026-10-04T18:40:00.000Z | 2026-10-04T18:40:00.010Z | observation | `station_status` | None | 48200 | timeout |  |
| ambici requests_2026-10-04.jsonl:2841 | 2026-10-04T18:40:00.000Z | 2026-10-04T18:40:00.010Z | observation | `station_status` | None | 18572 | URLError: [Errno 54] Connection reset by peer |  |
| ambici requests_2026-10-04.jsonl:2842 | 2026-10-04T18:40:00.000Z | 2026-10-04T18:40:18.584Z | observation | `free_bike_status` | None | 47229 | timeout |  |

Raw files involved (Bicing files under `spikes/bicing-spike/realtime/`, the other system's under its own capture folder): last stored `station_status` before the gap, first after it, then the stored files of the log lines: `raw/station_status/2026-10-04/20261004T183800Z.json.gz`, `raw/station_status/2026-10-04/20261004T184200Z.json.gz`, `raw/station_status/2026-10-04/20261004T183900Z.json.gz` (ambici).
<!-- END metric:5d.example -->

<!-- BEGIN metric:6b.example -->
### 6b. One `station_status` response and its `station_information`

Chosen: first status response with an unmatched ID.

| Role | Raw file | Requested at | Stations |
|---|---|---|---|
| `station_status` | `raw/station_status/2026-10-04/20261004T163500Z.json.gz` | 2026-10-04T16:35:00.006Z | 543 |
| `station_information` (latest before it) | `raw/station_information/2026-10-04/20261004T163000Z.json.gz` | 2026-10-04T16:30:00.764Z | 542 |

IDs with status but no information: `309`. IDs with information but no status: none.
<!-- END metric:6b.example -->

## 1. Schema

<!-- BEGIN metric:1a -->
### 1a. Feeds published

186 `gbfs.json` responses used.

| Feed | Responses listing it | First seen (UTC) | Last seen (UTC) |
|---|---|---|---|
| `gbfs_versions` | 186 | 2026-10-03T17:11:00.005Z | 2026-10-05T14:15:00.001Z |
| `geofencing_zones` | 186 | 2026-10-03T17:11:00.005Z | 2026-10-05T14:15:00.001Z |
| `station_information` | 186 | 2026-10-03T17:11:00.005Z | 2026-10-05T14:15:00.001Z |
| `station_status` | 186 | 2026-10-03T17:11:00.005Z | 2026-10-05T14:15:00.001Z |
| `system_information` | 186 | 2026-10-03T17:11:00.005Z | 2026-10-05T14:15:00.001Z |
| `system_pricing_plans` | 186 | 2026-10-03T17:11:00.005Z | 2026-10-05T14:15:00.001Z |
| `system_regions` | 186 | 2026-10-03T17:11:00.005Z | 2026-10-05T14:15:00.001Z |
| `vehicle_types` | 186 | 2026-10-03T17:11:00.005Z | 2026-10-05T14:15:00.001Z |

Listed but not captured: none. Captured but never listed (index excluded): none.
<!-- END metric:1a -->

<!-- BEGIN metric:1b -->
### 1b. Declared version

Versions found across all feeds: 3.0 (expected one; configured 3.0).

| Feed | Version (responses) |
|---|---|
| `gbfs` | 3.0 (186) |
| `gbfs_versions` | 3.0 (182) |
| `geofencing_zones` | 3.0 (182) |
| `station_information` | 3.0 (182) |
| `station_status` | 3.0 (2710) |
| `system_information` | 3.0 (182) |
| `system_pricing_plans` | 3.0 (182) |
| `system_regions` | 3.0 (182) |
| `vehicle_types` | 3.0 (182) |
<!-- END metric:1b -->

### 1c. Versions offered

Desk research by Chat; not computed by the script.

<!-- BEGIN metric:1d -->
### 1d. Field profile

Full profile in `field_profile.csv`.

| Feed | Responses | Field paths | Paths with nulls |
|---|---|---|---|
| `gbfs` | 186 | 8 | 0 |
| `gbfs_versions` | 182 | 8 | 0 |
| `geofencing_zones` | 182 | 8 | 0 |
| `station_information` | 182 | 33 | 0 |
| `station_status` | 2710 | 24 | 0 |
| `system_information` | 182 | 14 | 0 |
| `system_pricing_plans` | 182 | 24 | 0 |
| `system_regions` | 182 | 5 | 0 |
| `vehicle_types` | 182 | 17 | 0 |

Paths with more than one non-null type:

None.

Timestamp values that could not be converted to UTC:

None.
<!-- END metric:1d -->

<!-- BEGIN metric:1e -->
### 1e. Schema stability

Field paths appearing or disappearing versus the previous response of the same feed: 0 rows in `schema_changes.csv` (expected empty).
<!-- END metric:1e -->

<!-- BEGIN metric:1f -->
### 1f. Compliance

Schemas: MobilityData `gbfs-json-schema` v3.0 at commit `2e974fd51ae1db9c8006c97375d53e0b882cfedf`. Responses validated per feed: `gbfs` 186, `gbfs_versions` 182, `geofencing_zones` 182, `station_information` 182, `station_status` 2710, `system_information` 182, `system_pricing_plans` 182, `system_regions` 182, `vehicle_types` 182.

Violation groups (feed + keyword + schema path): 0. Full rows in `schema_violations.csv`; the message is the first occurrence's.
<!-- END metric:1f -->

## 2. Common model

2a (field mapping) and 2b (effort summary) are done by Chat. Their input, `field_comparison.csv`, is in `spikes/bicing-spike/analysis/`.

<!-- BEGIN metric:2c -->
### 2c. ID collisions

Values compared as JSON values (type and value), from every key named `station_id` or `vehicle_type_id` in all responses used of `station_information`, `station_status`, `vehicle_types`.

| Field | AMBici distinct | AMBici types | Bicing distinct | Bicing types | Values in both |
|---|---|---|---|---|---|
| `station_id` | 237 | string | 543 | string | 0 |
| `vehicle_type_id` | 3 | string | 9 | string | 0 |

No value appears in both systems.

Bicing also has `vehicle_type_ids` arrays (not keys named `vehicle_type_id`, so not in the set above): 9 distinct values, 0 not in its own `vehicle_type_id` set, 0 in AMBici's `vehicle_type_id` set.

Paths the values came from (occurrences):

| System | Field | Feed: path | Occurrences |
|---|---|---|---|
| AMBici | `station_id` | `station_information: data.stations[].station_id` | 42897 |
| AMBici | `station_id` | `station_status: data.stations[].station_id` | 642270 |
| AMBici | `vehicle_type_id` | `station_status: data.stations[].vehicle_types_available[].vehicle_type_id` | 630154 |
| AMBici | `vehicle_type_id` | `vehicle_types: data.vehicle_types[].vehicle_type_id` | 543 |
| Bicing | `station_id` | `station_information: data.stations[].station_id` | 98731 |
| Bicing | `station_id` | `station_status: data.stations[].station_id` | 1470126 |
| Bicing | `vehicle_type_id` | `station_status: data.stations[].vehicle_types_available[].vehicle_type_id` | 5880504 |
| Bicing | `vehicle_type_id` | `vehicle_types: data.vehicle_types[].vehicle_type_id` | 1638 |
<!-- END metric:2c -->

<!-- BEGIN metric:2d -->
### 2d. Feeds without equivalent

Feed names from 1a (all `gbfs.json` responses used), compared literally by name.

| Published only by | Feeds |
|---|---|
| AMBici | `free_bike_status`, `system_hours` |
| Bicing | `gbfs_versions` |
<!-- END metric:2d -->

## 3. Freshness

<!-- BEGIN metric:3a -->
### 3a. Content change rate

One row per change in `content_changes.csv` (2712 rows). Intervals in seconds, by request time, between consecutive changes with no gap between them.

| Feed | Responses | Pairs compared | Pairs excluded (gap) | Changes | % changed | Intervals counted | Interval median | p95 | max |
|---|---|---|---|---|---|---|---|---|---|
| `station_status` | 2710 | 2705 | 4 | 2705 | 100.00 | 2702 | 60 | 60.146 | 63.27 |
| `gbfs` | 186 | 185 | 0 | 0 | 0.00 | 0 |  |  |  |
| `gbfs_versions` | 182 | 181 | 0 | 0 | 0.00 | 0 |  |  |  |
| `geofencing_zones` | 182 | 181 | 0 | 0 | 0.00 | 0 |  |  |  |
| `station_information` | 182 | 181 | 0 | 7 | 3.87 | 6 | 10800.042 | 28799.924 | 28799.924 |
| `system_information` | 182 | 181 | 0 | 0 | 0.00 | 0 |  |  |  |
| `system_pricing_plans` | 182 | 181 | 0 | 0 | 0.00 | 0 |  |  |  |
| `system_regions` | 182 | 181 | 0 | 0 | 0.00 | 0 |  |  |  |
| `vehicle_types` | 182 | 181 | 0 | 0 | 0.00 | 0 |  |  |  |
<!-- END metric:3a -->

<!-- BEGIN metric:3b -->
### 3b. Station reporting interval

`station_status` station items: 1470126; with `last_reported` equal to the response's `last_updated`: 0 (0.00 %); `last_reported` not convertible: 0. Response pairs exactly 1 tick apart: 2705; pairs excluded (gap): 4.

Station comparisons: 1467411; station skipped for a pair (in only one of the two responses): 1. Negative intervals (`last_reported` going backwards): 0. One row per station in `station_reporting.csv` (543 stations; 5 with no interval).

| Across stations, each station's median interval (s) | median | p95 | max |
|---|---|---|---|
| Value | 180.584 | 180.67 | 181.071 |

| Heartbeats (`last_reported` changed, counts did not) | Silent changes (counts changed, `last_reported` did not) |
|---|---|
| 420978 | 71699 |
<!-- END metric:3b -->

<!-- BEGIN metric:3c -->
### 3c. `last_updated` behaviour

Lag = request time (`requested_at_utc`) − `last_updated`, in seconds. Negative = `last_updated` later than the request time.

| Feed | Responses | ttl (responses) | Lag min | median | p95 | max | Going backwards | Older than ttl | `last_updated` not convertible |
|---|---|---|---|---|---|---|---|---|---|
| `station_status` | 2710 | 0 (2710) | -14.99 | 0.005 | 0.151 | 0.585 | 0 | n/a (ttl 0) | 0 |
| `gbfs` | 186 | 0 (186) | -13.788 | 0.005 | 0.01 | 0.102 | 0 | n/a (ttl 0) | 0 |
| `gbfs_versions` | 182 | 0 (182) | -0.324 | 0.595 | 0.772 | 0.864 | 0 | n/a (ttl 0) | 0 |
| `geofencing_zones` | 182 | 0 (182) | -0.15 | 0.667 | 0.846 | 0.875 | 0 | n/a (ttl 0) | 0 |
| `station_information` | 182 | 0 (182) | -0.368 | 0.118 | 0.864 | 0.889 | 0 | n/a (ttl 0) | 0 |
| `system_information` | 182 | 0 (182) | -0.32 | 0.463 | 0.815 | 0.868 | 0 | n/a (ttl 0) | 0 |
| `system_pricing_plans` | 182 | 0 (182) | -0.356 | 0.272 | 0.675 | 0.751 | 0 | n/a (ttl 0) | 0 |
| `system_regions` | 182 | 0 (182) | -1.109 | 0.228 | 0.785 | 0.87 | 0 | n/a (ttl 0) | 0 |
| `vehicle_types` | 182 | 0 (182) | -0.832 | 0.253 | 0.787 | 0.871 | 0 | n/a (ttl 0) | 0 |

Values going backwards:

None.
<!-- END metric:3c -->

<!-- BEGIN metric:3d -->
### 3d. Declared vs measured

Measured = the 3a interval between content changes, in seconds.

| Feed | Declared ttl (responses) | Measured median | p95 | max |
|---|---|---|---|---|
| `station_status` | 0 (2710) | 60 | 60.146 | 63.27 |
| `gbfs` | 0 (186) |  |  |  |
| `gbfs_versions` | 0 (182) |  |  |  |
| `geofencing_zones` | 0 (182) |  |  |  |
| `station_information` | 0 (182) | 10800.042 | 28799.924 | 28799.924 |
| `system_information` | 0 (182) |  |  |  |
| `system_pricing_plans` | 0 (182) |  |  |  |
| `system_regions` | 0 (182) |  |  |  |
| `vehicle_types` | 0 (182) |  |  |  |
<!-- END metric:3d -->

## 4. Sampling

<!-- BEGIN metric:4a -->
### 4a. Observed activity

Sum of |Δ| between `station_status` responses exactly 1 tick apart (lower bound of rentals + returns). Response pairs compared: 2705; excluded (gap): 4. Station comparisons: 1467411; station skipped for a pair (in only one of the two responses): 1. Per-type comparisons: 5869644, of which 0 with the type absent on one side (counted as 0).

| Measure | Activity (bikes) |
|---|---|
| Total (`num_vehicles_available`) | 107713 |
| Type `BOOST` | 91556 |
| Type `EFIT` | 0 |
| Type `FIT` | 0 |
| Type `ICONIC` | 16467 |
<!-- END metric:4a -->

<!-- BEGIN metric:4b -->
### 4b. Loss by interval

For each interval N and each of the N starting minutes, pairs exactly N ticks apart; a pair is kept only when every 1-min pair inside it exists. Loss per offset = 1 − activity at N ÷ 1-min activity over the same spans; the table shows the mean over the N offsets. Activities are means over offsets.

| Interval | Pairs kept (all offsets) | Pairs excluded (gap) | Activity at N (mean) | 1-min activity, same spans (mean) | Loss % (total) | Loss % type `BOOST` | Loss % type `EFIT` | Loss % type `FIT` | Loss % type `ICONIC` |
|---|---|---|---|---|---|---|---|---|---|
| 1 min | 2705 | 4 |  |  | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2 min | 2702 | 6 | 92324.5 | 107408.5 | 14.04 | 13.39 |  |  | 3.17 |
| 5 min | 2695 | 10 | 67764.2 | 106663.4 | 36.47 | 35.55 |  |  | 9.51 |
| 10 min | 2685 | 15 | 52758.1 | 105630.5 | 50.05 | 49.13 |  |  | 16.87 |
| 15 min | 2675 | 20 | 44341.1 | 104637.1 | 57.62 | 57.28 |  |  | 22.56 |
<!-- END metric:4b -->

<!-- BEGIN metric:4c -->
### 4c. Change size at 1 min

Station steps 1 tick apart where the total (`num_vehicles_available`) changed: 96342 of 1467411 station comparisons.

| \|Δ\| | Steps | % of changing steps |
|---|---|---|
| 1 | 87086 | 90.39 |
| ≥ 2 | 9256 | 9.61 |
<!-- END metric:4c -->

## 5. Reliability

<!-- BEGIN metric:5a -->
### 5a. Failed requests

All requests used, off-grid requests included. Failed = HTTP status ≠ 200, timeout or connection error.

| Feed | Requests | Failed | % failed | Errors (count) |
|---|---|---|---|---|
| `station_status` | 2715 | 5 | 0.18 | timeout (5) |
| `gbfs` | 186 | 0 | 0.00 | — |
| `gbfs_versions` | 182 | 0 | 0.00 | — |
| `geofencing_zones` | 182 | 0 | 0.00 | — |
| `station_information` | 182 | 0 | 0.00 | — |
| `system_information` | 182 | 0 | 0.00 | — |
| `system_pricing_plans` | 182 | 0 | 0.00 | — |
| `system_regions` | 182 | 0 | 0.00 | — |
| `vehicle_types` | 182 | 0 | 0.00 | — |

All feeds: 5 of 4175 (0.12 %).
<!-- END metric:5a -->

<!-- BEGIN metric:5b -->
### 5b. Latency

`elapsed_ms` of successful requests:

| Feed | Successful requests | Median ms | p95 ms | Max ms |
|---|---|---|---|---|
| `station_status` | 2710 | 516.5 | 1585 | 50616 |
| `gbfs` | 186 | 160 | 711 | 14103 |
| `gbfs_versions` | 182 | 131 | 182 | 857 |
| `geofencing_zones` | 182 | 127 | 173 | 440 |
| `station_information` | 182 | 657 | 3096 | 3846 |
| `system_information` | 182 | 153 | 220 | 1208 |
| `system_pricing_plans` | 182 | 271 | 340 | 1243 |
| `system_regions` | 182 | 134 | 219 | 1426 |
| `vehicle_types` | 182 | 163 | 316 | 1249 |

Failed requests, with their elapsed time:

| Feed | Tick | Requested at | Elapsed ms | Error |
|---|---|---|---|---|
| `station_status` | 2026-10-04T18:39:00.000Z | 2026-10-04T18:39:00.007Z | 36093 | timeout |
| `station_status` | 2026-10-04T18:40:00.000Z | 2026-10-04T18:40:00.010Z | 48200 | timeout |
| `station_status` | 2026-10-04T18:43:00.000Z | 2026-10-04T18:43:00.004Z | 32415 | timeout |
| `station_status` | 2026-10-04T18:45:00.000Z | 2026-10-04T18:45:06.382Z | 22292 | timeout |
| `station_status` | 2026-10-04T18:49:00.000Z | 2026-10-04T18:49:00.003Z | 22348 | timeout |
<!-- END metric:5b -->

<!-- BEGIN metric:5c -->
### 5c. Stale responses

From the request log (`server_last_updated`), stored responses of each feed ordered by request time; 4161 consecutive pairs compared. Stale responses: 0.

None (trivially empty result reported as a finding).
<!-- END metric:5c -->

<!-- BEGIN metric:5d -->
### 5d. Gaps

pmset excerpt: 392 dated lines read, by category: Assertions 391, Wake 1; sleep intervals overlapping the window: 0. Systems compared by scheduled tick.

Missing expected ticks per class and feed:

| Feed | ours | provider | ours (probable) | Total |
|---|---|---|---|---|
| `station_status` | 0 | 0 | 6 | 6 |
| `gbfs` | 0 | 0 | 0 | 0 |
| `gbfs_versions` | 0 | 0 | 0 | 0 |
| `geofencing_zones` | 0 | 0 | 0 | 0 |
| `station_information` | 0 | 0 | 0 | 0 |
| `system_information` | 0 | 0 | 0 | 0 |
| `system_pricing_plans` | 0 | 0 | 0 | 0 |
| `system_regions` | 0 | 0 | 0 | 0 |
| `vehicle_types` | 0 | 0 | 0 | 0 |
| All feeds | 0 | 0 | 6 | 6 |

Gaps (`gaps.csv`, 4 rows):

| Feed | Start | End | Duration (ticks) | Class | Rule | Log lines |
|---|---|---|---|---|---|---|
| `station_status` | 2026-10-04T18:39:00.000Z | 2026-10-04T18:41:00.000Z | 3 | ours (probable) | 4; 2 | bicing requests_2026-10-04.jsonl:1720; ambici requests_2026-10-04.jsonl:2839; ambici requests_2026-10-04.jsonl:2840; bicing requests_2026-10-04.jsonl:1722; ambici requests_2026-10-04.jsonl:2841; ambici requests_2026-10-04.jsonl:2842 |
| `station_status` | 2026-10-04T18:43:00.000Z | 2026-10-04T18:43:00.000Z | 1 | ours (probable) | 4 | bicing requests_2026-10-04.jsonl:1725 |
| `station_status` | 2026-10-04T18:45:00.000Z | 2026-10-04T18:45:00.000Z | 1 | ours (probable) | 4 | bicing requests_2026-10-04.jsonl:1729; ambici requests_2026-10-04.jsonl:2847; ambici requests_2026-10-04.jsonl:2848; ambici requests_2026-10-04.jsonl:2849; ambici requests_2026-10-04.jsonl:2850; ambici requests_2026-10-04.jsonl:2851; ambici requests_2026-10-04.jsonl:2852; ambici requests_2026-10-04.jsonl:2853; ambici requests_2026-10-04.jsonl:2854; ambici requests_2026-10-04.jsonl:2855; ambici requests_2026-10-04.jsonl:2856 |
| `station_status` | 2026-10-04T18:49:00.000Z | 2026-10-04T18:49:00.000Z | 1 | ours (probable) | 4 | bicing requests_2026-10-04.jsonl:1740; ambici requests_2026-10-04.jsonl:2863; ambici requests_2026-10-04.jsonl:2864 |
<!-- END metric:5d -->

## 6. Identity

<!-- BEGIN metric:6a -->
### 6a. Station set over time

182 `station_information` responses used; stations per response: min 542, max 543; distinct station IDs: 543. Stations not present in every response: 1.

| Station | Responses present | First seen (UTC) | Last seen (UTC) |
|---|---|---|---|
| `309` | 87 | 2026-10-04T16:45:00.867Z | 2026-10-05T14:15:01.141Z |
<!-- END metric:6a -->

<!-- BEGIN metric:6b -->
### 6b. Information ↔ status match

Each `station_status` response joined to the latest `station_information` requested before it. Status responses joined: 2709; skipped (no earlier information): 1; with at least one unmatched ID: 11.

IDs with status but no information:

| Station | Status responses affected |
|---|---|
| `309` | 11 |

IDs with information but no status:

None.
<!-- END metric:6b -->

<!-- BEGIN metric:6c -->
### 6c. Attribute stability

Fields compared: `name`, `lat`, `lon`, `capacity`, `vehicle_docks_capacity`; each station against its own previous appearance. Changes: 26 (`capacity` 13, `vehicle_docks_capacity` 13).

| Station | Field | Previous | New | Requested at | File |
|---|---|---|---|---|---|
| `77` | `capacity` | 24 | 0 | 2026-10-04T02:45:00.858Z | `raw/station_information/2026-10-04/20261004T024500Z.json.gz` |
| `77` | `vehicle_docks_capacity` | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 24}] | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 0}] | 2026-10-04T02:45:00.858Z | `raw/station_information/2026-10-04/20261004T024500Z.json.gz` |
| `91` | `capacity` | 34 | 35 | 2026-10-04T10:45:00.782Z | `raw/station_information/2026-10-04/20261004T104500Z.json.gz` |
| `91` | `vehicle_docks_capacity` | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 34}] | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 35}] | 2026-10-04T10:45:00.782Z | `raw/station_information/2026-10-04/20261004T104500Z.json.gz` |
| `298` | `capacity` | 33 | 32 | 2026-10-04T10:45:00.782Z | `raw/station_information/2026-10-04/20261004T104500Z.json.gz` |
| `298` | `vehicle_docks_capacity` | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 33}] | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 32}] | 2026-10-04T10:45:00.782Z | `raw/station_information/2026-10-04/20261004T104500Z.json.gz` |
| `91` | `capacity` | 35 | 34 | 2026-10-04T13:45:00.930Z | `raw/station_information/2026-10-04/20261004T134500Z.json.gz` |
| `91` | `vehicle_docks_capacity` | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 35}] | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 34}] | 2026-10-04T13:45:00.930Z | `raw/station_information/2026-10-04/20261004T134500Z.json.gz` |
| `258` | `capacity` | 26 | 27 | 2026-10-04T13:45:00.930Z | `raw/station_information/2026-10-04/20261004T134500Z.json.gz` |
| `258` | `vehicle_docks_capacity` | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 26}] | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 27}] | 2026-10-04T13:45:00.930Z | `raw/station_information/2026-10-04/20261004T134500Z.json.gz` |
| `298` | `capacity` | 32 | 33 | 2026-10-04T13:45:00.930Z | `raw/station_information/2026-10-04/20261004T134500Z.json.gz` |
| `298` | `vehicle_docks_capacity` | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 32}] | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 33}] | 2026-10-04T13:45:00.930Z | `raw/station_information/2026-10-04/20261004T134500Z.json.gz` |
| `343` | `capacity` | 27 | 26 | 2026-10-04T13:45:00.930Z | `raw/station_information/2026-10-04/20261004T134500Z.json.gz` |
| `343` | `vehicle_docks_capacity` | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 27}] | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 26}] | 2026-10-04T13:45:00.930Z | `raw/station_information/2026-10-04/20261004T134500Z.json.gz` |
| `94` | `capacity` | 47 | 46 | 2026-10-04T23:15:03.972Z | `raw/station_information/2026-10-04/20261004T231500Z.json.gz` |
| `94` | `vehicle_docks_capacity` | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 47}] | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 46}] | 2026-10-04T23:15:03.972Z | `raw/station_information/2026-10-04/20261004T231500Z.json.gz` |
| `188` | `capacity` | 26 | 27 | 2026-10-05T00:15:01.594Z | `raw/station_information/2026-10-05/20261005T001500Z.json.gz` |
| `188` | `vehicle_docks_capacity` | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 26}] | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 27}] | 2026-10-05T00:15:01.594Z | `raw/station_information/2026-10-05/20261005T001500Z.json.gz` |
| `256` | `capacity` | 32 | 31 | 2026-10-05T00:15:01.594Z | `raw/station_information/2026-10-05/20261005T001500Z.json.gz` |
| `256` | `vehicle_docks_capacity` | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 32}] | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 31}] | 2026-10-05T00:15:01.594Z | `raw/station_information/2026-10-05/20261005T001500Z.json.gz` |
| `462` | `capacity` | 28 | 27 | 2026-10-05T00:15:01.594Z | `raw/station_information/2026-10-05/20261005T001500Z.json.gz` |
| `462` | `vehicle_docks_capacity` | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 28}] | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 27}] | 2026-10-05T00:15:01.594Z | `raw/station_information/2026-10-05/20261005T001500Z.json.gz` |
| `91` | `capacity` | 34 | 35 | 2026-10-05T01:30:01.944Z | `raw/station_information/2026-10-05/20261005T013000Z.json.gz` |
| `91` | `vehicle_docks_capacity` | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 34}] | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 35}] | 2026-10-05T01:30:01.944Z | `raw/station_information/2026-10-05/20261005T013000Z.json.gz` |
| `298` | `capacity` | 33 | 32 | 2026-10-05T01:30:01.944Z | `raw/station_information/2026-10-05/20261005T013000Z.json.gz` |
| `298` | `vehicle_docks_capacity` | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 33}] | [{"vehicle_type_ids": ["ASTRO", "BOOST", "CHLOE", "COSMO", "EFIT", "FIT", "ICONIC", "METRO", "METRO_CONNECTED"], "count": 32}] | 2026-10-05T01:30:01.944Z | `raw/station_information/2026-10-05/20261005T013000Z.json.gz` |
<!-- END metric:6c -->

<!-- BEGIN metric:6d -->
### 6d. ID format

`station_id`, 543 distinct values (2c set); JSON type: string 543; numeric 543 (digits: 1–3), UUID 0, other 0.
<!-- END metric:6d -->

## 7. Volume

<!-- BEGIN metric:7a -->
### 7a. Size per request

Stored responses used, in bytes. `bytes_gz` is our own gzip size, which is what storage would hold.

| Feed | Stored responses | bytes_raw median | bytes_raw max | bytes_gz median | bytes_gz max |
|---|---|---|---|---|---|
| `station_status` | 2710 | 267742 | 267793 | 10262 | 10447 |
| `gbfs` | 186 | 968 | 968 | 287 | 288 |
| `gbfs_versions` | 182 | 331 | 331 | 202 | 203 |
| `geofencing_zones` | 182 | 152 | 152 | 173 | 175 |
| `station_information` | 182 | 515536 | 516510 | 45709 | 45784 |
| `system_information` | 182 | 478 | 478 | 296 | 297 |
| `system_pricing_plans` | 182 | 11171 | 11171 | 695 | 695 |
| `system_regions` | 182 | 85 | 85 | 129 | 130 |
| `vehicle_types` | 182 | 4022 | 4022 | 601 | 601 |
<!-- END metric:7a -->

<!-- BEGIN metric:7b -->
### 7b. Size per day

2026-10-04 (UTC, by tick), as measured: sum of `bytes_gz` of every stored response, off-grid ones included.

| Feed | On-grid stored of expected | Off-grid stored | Off-grid bytes_gz | bytes_gz total | MB (10^6 bytes) |
|---|---|---|---|---|---|
| `station_status` | 1434 of 1440 | 0 | 0 | 14716227 | 14.72 |
| `gbfs` | 96 of 96 | 4 | 1151 | 28695 | 0.03 |
| `gbfs_versions` | 96 of 96 | 0 | 0 | 19389 | 0.02 |
| `geofencing_zones` | 96 of 96 | 0 | 0 | 16636 | 0.02 |
| `station_information` | 96 of 96 | 0 | 0 | 4390070 | 4.39 |
| `system_information` | 96 of 96 | 0 | 0 | 28422 | 0.03 |
| `system_pricing_plans` | 96 of 96 | 0 | 0 | 66719 | 0.07 |
| `system_regions` | 96 of 96 | 0 | 0 | 12435 | 0.01 |
| `vehicle_types` | 96 of 96 | 0 | 0 | 57664 | 0.06 |
| All feeds |  |  |  | 19336257 | 19.34 |
<!-- END metric:7b -->

<!-- BEGIN metric:7c -->
### 7c. Projection

Median `bytes_gz` per feed (7a) × expected responses per day: dynamic feeds 1,440 (1-min) or 288 (5-min), static feeds 96. Month = 30 days, year = 365 days, GB = 10^9 bytes. Limit: Cloudflare R2 free storage, 10 GB per account, both systems added up.

| Scenario | Dynamic polling | AMBici MB/day | Bicing MB/day | Both MB/day | Both GB/month | % of 10 GB | Both GB/year | % of 10 GB |
|---|---|---|---|---|---|---|---|---|
| All feeds as captured | 1 min | 77.91 | 19.39 | 97.30 | 2.92 | 29.19 | 35.52 | 355.15 |
| All feeds as captured | 5 min | 16.57 | 7.57 | 24.15 | 0.72 | 7.24 | 8.81 | 88.13 |
| Without `free_bike_status` (AMBici) | 1 min | 4.53 | 19.39 | 23.92 | 0.72 | 7.18 | 8.73 | 87.32 |
| Without `free_bike_status` (AMBici) | 5 min | 1.90 | 7.57 | 9.47 | 0.28 | 2.84 | 3.46 | 34.57 |
<!-- END metric:7c -->

## 8. Quality

<!-- BEGIN metric:8a -->
### 8a. Over capacity

| Variant | Feed | Occurrences | % of items | Distinct stations/bikes | % of distinct | Responses affected | % of responses |
|---|---|---|---|---|---|---|---|
| (i) available + docks available > capacity | `station_status` | 2 | 0.00 | 1 | 0.18 | 2 | 0.07 |
| (ii) (i) + disabled + docks disabled > capacity | `station_status` | 75380 | 5.13 | 52 | 9.58 | 2709 | 99.96 |
| `capacity` ≠ `count` of the single `vehicle_docks_capacity` group | `station_information` | 0 | 0.00 | 0 | 0.00 | 0 | 0.00 |
| `vehicle_docks_capacity` without exactly one group | `station_information` | 0 | 0.00 | 0 | 0.00 | 0 | 0.00 |

As-of join with the latest `station_information` before each status response; status responses with no earlier information: 1; station items with no capacity in the joined information (skipped): 11.
<!-- END metric:8a -->

<!-- BEGIN metric:8b -->
### 8b. Negative counts

None found (station items checked: 1470126, all count fields ≥ 0).
<!-- END metric:8b -->

<!-- BEGIN metric:8c -->
### 8c. Type breakdown mismatch

| Variant | Feed | Occurrences | % of items | Distinct stations/bikes | % of distinct | Responses affected | % of responses |
|---|---|---|---|---|---|---|---|
| Sum of type counts ≠ total available | `station_status` | 39686 | 2.70 | 521 | 95.95 | 2710 | 100.00 |
| Counted apart: types empty or missing, total = 0 | `station_status` | 0 | 0.00 | 0 | 0.00 | 0 | 0.00 |
| Counted apart: types empty or missing, total > 0 | `station_status` | 0 | 0.00 | 0 | 0.00 | 0 | 0.00 |
<!-- END metric:8c -->

<!-- BEGIN metric:8d -->
### 8d. Stale station

| Variant | Feed | Occurrences | % of items | Distinct stations/bikes | % of distinct | Responses affected | % of responses |
|---|---|---|---|---|---|---|---|
| `is_installed` true and `last_reported` older than 24 h | `station_status` | 13492 | 0.92 | 15 | 2.76 | 2710 | 100.00 |
<!-- END metric:8d -->

<!-- BEGIN metric:8e -->
### 8e. Future timestamp

| Variant | Feed | Occurrences | % of items | Distinct stations/bikes | % of distinct | Responses affected | % of responses |
|---|---|---|---|---|---|---|---|
| `last_reported` later than request time + 60 s | `station_status` | 0 | 0.00 | 0 | 0.00 | 0 | 0.00 |
<!-- END metric:8e -->

<!-- BEGIN metric:8f -->
### 8f. Inactive stations

| Variant | Feed | Occurrences | % of items | Distinct stations/bikes | % of distinct | Responses affected | % of responses |
|---|---|---|---|---|---|---|---|
| `is_installed` false | `station_status` | 2710 | 0.18 | 1 | 0.18 | 2710 | 100.00 |
| `is_renting` false | `station_status` | 557704 | 37.94 | 541 | 99.63 | 2710 | 100.00 |
| `is_returning` false | `station_status` | 19364 | 1.32 | 27 | 4.97 | 2710 | 100.00 |
| Any of the three false | `station_status` | 557704 | 37.94 | 541 | 99.63 | 2710 | 100.00 |
<!-- END metric:8f -->

<!-- BEGIN metric:8g -->
### 8g. Duplicate ID

| Variant | Feed | Occurrences | % of items | Distinct stations/bikes | % of distinct | Responses affected | % of responses |
|---|---|---|---|---|---|---|---|
| Same `station_id` twice in one response | `station_status` | 0 | 0.00 | 0 | 0.00 | 0 | 0.00 |
| Same `station_id` twice in one response | `station_information` | 0 | 0.00 | 0 | 0.00 | 0 | 0.00 |
<!-- END metric:8g -->

<!-- BEGIN metric:8h -->
### 8h. Out of area

| Variant | Feed | Occurrences | % of items | Distinct stations/bikes | % of distinct | Responses affected | % of responses |
|---|---|---|---|---|---|---|---|
| Coordinates outside lat 41.20–41.60, lon 1.85–2.35 | `station_information` | 0 | 0.00 | 0 | 0.00 | 0 | 0.00 |
<!-- END metric:8h -->

<!-- BEGIN metric:8i -->
### 8i. Known issues

None listed in the plan for Bicing.
<!-- END metric:8i -->

<!-- BEGIN metric:8j -->
### 8j. Inactive flags vs availability (added after first look)

| Variant | Feed | Occurrences | % of items | Distinct stations/bikes | % of distinct | Responses affected | % of responses |
|---|---|---|---|---|---|---|---|
| `is_renting` false, total available = 0 | `station_status` | 37083 | 2.52 | 48 | 8.84 | 2710 | 100.00 |
| `is_renting` false, total available > 0 | `station_status` | 520621 | 35.41 | 519 | 95.58 | 2261 | 83.43 |
| `is_returning` false, `num_docks_available` = 0 | `station_status` | 8414 | 0.57 | 7 | 1.29 | 2710 | 100.00 |
| `is_returning` false, `num_docks_available` > 0 | `station_status` | 10950 | 0.74 | 24 | 4.42 | 2710 | 100.00 |
| Total available = 0 and `is_renting` true | `station_status` | 102886 | 7.00 | 335 | 61.69 | 2499 | 92.21 |

Total available = `num_vehicles_available`. Counted over station items; a station item can count in more than one row.
<!-- END metric:8j -->

## Implementation notes

- 1d: list-item paths (`…[]`) are not keyed fields, so they have no % present; their % null is over the items.
- 1f: validated with `jsonschema` defaults for draft-07, where `format` is an annotation and is not asserted. 1f violation counts in `field_comparison.csv` match the collapsed instance path literally, so `required` and `additionalProperties` violations count on the parent object's path.
- Median and p95 (all metrics): median as Python `statistics.median` (mean of the two middle values for an even count); p95 by the nearest-rank method.
- 3a: an interval between two changes is not counted when a gap lies between them; the first change after a gap, and the first change of each feed, have no previous change. Lists of objects are compared as a multiset of whole items, so the result does not depend on which ID key is matched first.
- 3b: a station counts in a pair only when it is in both responses. Interval = new `last_reported` − previous `last_reported` (the values, not the request times). Counts = every numeric field of the station except `last_reported`, with list items matched by `vehicle_type_id` / `vehicle_type_ids` rather than by position. "Not measurable" = `last_reported` equals `last_updated` for 100 % of station items.
- 3c: lag = `requested_at_utc` − `last_updated`; "older than ttl" = lag > the `ttl` of the same response; not applicable with `ttl` 0.
- 5a: the denominator is every request used, off-grid ones (Bicing `index_refresh`) included.
- 5d rule 2: the "previous tick" is the latest earlier tick with log lines; it overran when its last request ended (`requested_at_utc` + `elapsed_ms`) at or after the missing tick. The `log lines` column lists the failed requests and the other system's requests on the tick compared.
- 7b: the day is taken by tick (file-name time); off-grid responses are included in the sum and shown separately.
- 7c: month = 30 days, year = 365 days, GB = 10^9 bytes (Cloudflare's own GB definition not checked).
- 4a: a vehicle type absent from `vehicle_types_available` counts as 0 (AMBici omits zero counts).
- 4b: an N-minute pair is kept only when every 1-minute pair inside it exists; otherwise it is excluded and counted.
- 4b: loss per starting offset = 1 − activity at N min ÷ 1-min activity over the same spans; the loss % is the mean over the N offsets.
- 4c: only steps where the total changed (Δ ≠ 0), total available only.
- 6b, 8a: as-of join with the latest `station_information` requested strictly before the `station_status` response; status responses with no earlier information are skipped and counted.
- 6c: each station is compared with its own previous appearance; coordinates exactly; Bicing's localised `name` as a language → text mapping.
- 8d, 8e: request time = `requested_at_utc`; 8d stale = age > 86,400 s; 8e future = `last_reported` > request time + 60 s.
- 8h: boundaries count as inside (41.20 ≤ lat ≤ 41.60, 1.85 ≤ lon ≤ 2.35).
