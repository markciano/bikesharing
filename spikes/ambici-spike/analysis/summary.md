# AMBici realtime capture — analysis summary

Evidence for T006, produced by `spikes/realtime-capture-analysis/analyse_realtime_capture.py` (parts 1–3). Spec: [Analysis plan](../../../docs/spikes/s001-ambici-realtime-capture.md#analysis-plan).

## Analysis window

2026-10-03T17:11:00.000Z to 2026-10-05T14:26:00.000Z, both ticks included. Responses used: in-window `en` responses (6874 log lines, 6867 stored responses).

## Data discarded

| Reason | Requests | Stored responses | Bytes (gzip) | Ticks |
|---|---|---|---|---|
| language copy (used only by question 10) | 36 | 36 | 263850 | 2026-10-03T12:59:19.445Z to 2026-10-03T14:41:10.428Z |
| outside the analysis window | 600 | 600 | 12346013 | 2026-10-03T13:00:00.000Z to 2026-10-03T17:10:00.000Z |

Raw files on disk outside the window: 600.

## Configuration used

| Item | Value |
|---|---|
| Declared GBFS version (configured) | 2.3 |
| Dynamic feeds (1-min grid) | `station_status`, `free_bike_status` |
| Static feeds (15-min grid) | `gbfs`, `system_information`, `vehicle_types`, `station_information`, `system_hours`, `system_regions`, `system_pricing_plans`, `geofencing_zones` |
| Timestamp format | POSIX seconds |
| Timestamp fields (from the official schemas) | `*`: `last_updated`; `station_status`: `data.stations[].last_reported`; `free_bike_status`: `data.bikes[].last_reported`; `geofencing_zones`: `data.geofencing_zones.features[].properties.start`, `data.geofencing_zones.features[].properties.end` |

## Schema commit

MobilityData `gbfs-json-schema` commit `2e974fd51ae1db9c8006c97375d53e0b882cfedf` (from `schemas/SOURCE.md`).

## Verification › Reconciliation

Over the responses used. Any mismatch is reported, not corrected.

### Requests in the log = stored responses + failed requests

| Requests in the log | Stored responses (raw files on disk) | Failed requests | Holds |
|---|---|---|---|
| 6874 | 6867 | 7 | yes |

Stored responses counted from the raw files on disk whose file-name time is in the window. Logged as stored but missing on disk: 0. On disk but not in the log: 0. Stored responses that could not be read or parsed: 0.

### Per feed: expected ticks = ticks with a response + ticks without one

Ticks without a response are split into failed request and no log line. Off-grid responses (script start, `index_refresh`) are used by the metrics but are never expected ticks.

| Feed | Expected ticks | With a response | Without: failed request | Without: no log line | Holds | Off-grid responses | Duplicate responses on a tick |
|---|---|---|---|---|---|---|---|
| `station_status` | 2716 | 2710 | 3 | 3 | yes | 0 | 0 |
| `free_bike_status` | 2716 | 2709 | 4 | 3 | yes | 0 | 0 |
| `gbfs` | 181 | 181 | 0 | 0 | yes | 0 | 0 |
| `system_information` | 181 | 181 | 0 | 0 | yes | 0 | 0 |
| `vehicle_types` | 181 | 181 | 0 | 0 | yes | 0 | 0 |
| `station_information` | 181 | 181 | 0 | 0 | yes | 0 | 0 |
| `system_hours` | 181 | 181 | 0 | 0 | yes | 0 | 0 |
| `system_regions` | 181 | 181 | 0 | 0 | yes | 0 | 0 |
| `system_pricing_plans` | 181 | 181 | 0 | 0 | yes | 0 | 0 |
| `geofencing_zones` | 181 | 181 | 0 | 0 | yes | 0 | 0 |

<!-- BEGIN metric:5d.check -->
### Ticks inside gaps = ticks without a response (`gaps.csv` check)

| Feed | Ticks inside gaps | Ticks without a response | Holds |
|---|---|---|---|
| `station_status` | 6 | 6 | yes |
| `free_bike_status` | 7 | 7 | yes |
| `gbfs` | 0 | 0 | yes |
| `system_information` | 0 | 0 | yes |
| `vehicle_types` | 0 | 0 | yes |
| `station_information` | 0 | 0 | yes |
| `system_hours` | 0 | 0 | yes |
| `system_regions` | 0 | 0 | yes |
| `system_pricing_plans` | 0 | 0 | yes |
| `geofencing_zones` | 0 | 0 | yes |
<!-- END metric:5d.check -->

### Failed requests in the window

| Tick | Requested at | Purpose | Feed | HTTP status | Elapsed ms | Error |
|---|---|---|---|---|---|---|
| 2026-10-04T18:39:00.000Z | 2026-10-04T18:39:06.838Z | observation | `free_bike_status` | None | 50916 | timeout |
| 2026-10-04T18:40:00.000Z | 2026-10-04T18:40:00.010Z | observation | `station_status` | None | 18572 | URLError: [Errno 54] Connection reset by peer |
| 2026-10-04T18:40:00.000Z | 2026-10-04T18:40:18.584Z | observation | `free_bike_status` | None | 47229 | timeout |
| 2026-10-04T18:42:00.000Z | 2026-10-04T18:42:00.010Z | observation | `station_status` | None | 26230 | timeout |
| 2026-10-04T18:42:00.000Z | 2026-10-04T18:42:26.241Z | observation | `free_bike_status` | None | 43462 | timeout |
| 2026-10-04T18:45:00.000Z | 2026-10-04T18:45:00.002Z | observation | `station_status` | None | 26598 | timeout |
| 2026-10-04T18:49:00.000Z | 2026-10-04T18:49:18.955Z | observation | `free_bike_status` | None | 44062 | timeout |

### Check against the step 1 inventory

| Item | Expected (inventory) | Found |
|---|---|---|
| Ticks in the window | 2716 | 2716 |
| Failed requests in the window (AMBici) | 7 | 7 |
| Missing ticks: no log line at all (AMBici) | — | 2026-10-04T18:41:00.000Z, 2026-10-04T18:43:00.000Z, 2026-10-04T18:50:00.000Z |
| Missing ticks, total across both systems | 3 | 4 (system, tick) pairs on 3 distinct minutes |

## Verification › Hand-checkable examples

Raw file paths are relative to each system's capture folder.

<!-- BEGIN metric:4b.example -->
### 4b. One station, 1-min vs 5-min activity

Station `164427363` (highest 1-min activity over the window: 248), first 30-min block from the window start (offset 0) where the 5-min activity is lower than the 1-min activity. `num_bikes_available` per tick:

| Tick | Raw file | Available | \|Δ\| 1 min | 5-min sample | \|Δ\| 5 min |
|---|---|---|---|---|---|
| 2026-10-04T10:41:00.000Z | `raw/station_status/2026-10-04/20261004T104100Z.json.gz` | 5 |  | yes |  |
| 2026-10-04T10:42:00.000Z | `raw/station_status/2026-10-04/20261004T104200Z.json.gz` | 5 | 0 |  |  |
| 2026-10-04T10:43:00.000Z | `raw/station_status/2026-10-04/20261004T104300Z.json.gz` | 5 | 0 |  |  |
| 2026-10-04T10:44:00.000Z | `raw/station_status/2026-10-04/20261004T104400Z.json.gz` | 5 | 0 |  |  |
| 2026-10-04T10:45:00.000Z | `raw/station_status/2026-10-04/20261004T104500Z.json.gz` | 5 | 0 |  |  |
| 2026-10-04T10:46:00.000Z | `raw/station_status/2026-10-04/20261004T104600Z.json.gz` | 5 | 0 | yes | 0 |
| 2026-10-04T10:47:00.000Z | `raw/station_status/2026-10-04/20261004T104700Z.json.gz` | 5 | 0 |  |  |
| 2026-10-04T10:48:00.000Z | `raw/station_status/2026-10-04/20261004T104800Z.json.gz` | 5 | 0 |  |  |
| 2026-10-04T10:49:00.000Z | `raw/station_status/2026-10-04/20261004T104900Z.json.gz` | 5 | 0 |  |  |
| 2026-10-04T10:50:00.000Z | `raw/station_status/2026-10-04/20261004T105000Z.json.gz` | 5 | 0 |  |  |
| 2026-10-04T10:51:00.000Z | `raw/station_status/2026-10-04/20261004T105100Z.json.gz` | 5 | 0 | yes | 0 |
| 2026-10-04T10:52:00.000Z | `raw/station_status/2026-10-04/20261004T105200Z.json.gz` | 5 | 0 |  |  |
| 2026-10-04T10:53:00.000Z | `raw/station_status/2026-10-04/20261004T105300Z.json.gz` | 5 | 0 |  |  |
| 2026-10-04T10:54:00.000Z | `raw/station_status/2026-10-04/20261004T105400Z.json.gz` | 5 | 0 |  |  |
| 2026-10-04T10:55:00.000Z | `raw/station_status/2026-10-04/20261004T105500Z.json.gz` | 5 | 0 |  |  |
| 2026-10-04T10:56:00.000Z | `raw/station_status/2026-10-04/20261004T105600Z.json.gz` | 5 | 0 | yes | 0 |
| 2026-10-04T10:57:00.000Z | `raw/station_status/2026-10-04/20261004T105700Z.json.gz` | 5 | 0 |  |  |
| 2026-10-04T10:58:00.000Z | `raw/station_status/2026-10-04/20261004T105800Z.json.gz` | 5 | 0 |  |  |
| 2026-10-04T10:59:00.000Z | `raw/station_status/2026-10-04/20261004T105900Z.json.gz` | 4 | 1 |  |  |
| 2026-10-04T11:00:00.000Z | `raw/station_status/2026-10-04/20261004T110000Z.json.gz` | 2 | 2 |  |  |
| 2026-10-04T11:01:00.000Z | `raw/station_status/2026-10-04/20261004T110100Z.json.gz` | 3 | 1 | yes | 2 |
| 2026-10-04T11:02:00.000Z | `raw/station_status/2026-10-04/20261004T110200Z.json.gz` | 2 | 1 |  |  |
| 2026-10-04T11:03:00.000Z | `raw/station_status/2026-10-04/20261004T110300Z.json.gz` | 3 | 1 |  |  |
| 2026-10-04T11:04:00.000Z | `raw/station_status/2026-10-04/20261004T110400Z.json.gz` | 3 | 0 |  |  |
| 2026-10-04T11:05:00.000Z | `raw/station_status/2026-10-04/20261004T110500Z.json.gz` | 3 | 0 |  |  |
| 2026-10-04T11:06:00.000Z | `raw/station_status/2026-10-04/20261004T110600Z.json.gz` | 3 | 0 | yes | 0 |
| 2026-10-04T11:07:00.000Z | `raw/station_status/2026-10-04/20261004T110700Z.json.gz` | 3 | 0 |  |  |
| 2026-10-04T11:08:00.000Z | `raw/station_status/2026-10-04/20261004T110800Z.json.gz` | 3 | 0 |  |  |
| 2026-10-04T11:09:00.000Z | `raw/station_status/2026-10-04/20261004T110900Z.json.gz` | 3 | 0 |  |  |
| 2026-10-04T11:10:00.000Z | `raw/station_status/2026-10-04/20261004T111000Z.json.gz` | 3 | 0 |  |  |
| 2026-10-04T11:11:00.000Z | `raw/station_status/2026-10-04/20261004T111100Z.json.gz` | 3 | 0 | yes | 0 |
| Sum |  |  | 6 |  | 2 |

1-min activity 6, 5-min activity 2, loss 66.67 %.
<!-- END metric:4b.example -->

<!-- BEGIN metric:5d.example -->
### 5d. One gap per class

**ours:** none, class empty.

**provider:** `station_status` 2026-10-04T18:42:00.000Z to 2026-10-04T18:43:00.000Z, 2 tick(s), rule 3; 2. previous tick with log lines 2026-10-04T18:42:00.000Z; its last request ended 2026-10-04T18:43:09.703Z; failed requests on it: 2.

| Log line | Tick | Requested at | Purpose | Feed | HTTP | Elapsed ms | Error | File |
|---|---|---|---|---|---|---|---|---|
| ambici requests_2026-10-04.jsonl:2843 | 2026-10-04T18:42:00.000Z | 2026-10-04T18:42:00.010Z | observation | `station_status` | None | 26230 | timeout |  |
| bicing requests_2026-10-04.jsonl:1724 | 2026-10-04T18:42:00.000Z | 2026-10-04T18:42:00.010Z | observation | `station_status` | 200 | 50616 |  | `raw/station_status/2026-10-04/20261004T184200Z.json.gz` |
| ambici requests_2026-10-04.jsonl:2844 | 2026-10-04T18:42:00.000Z | 2026-10-04T18:42:26.241Z | observation | `free_bike_status` | None | 43462 | timeout |  |

Raw files involved (AMBici files under `spikes/ambici-spike/`, the other system's under its own capture folder): last stored `station_status` before the gap, first after it, then the stored files of the log lines: `raw/station_status/2026-10-04/20261004T183900Z.json.gz`, `raw/station_status/2026-10-04/20261004T184400Z.json.gz`, `raw/station_status/2026-10-04/20261004T184200Z.json.gz` (bicing).

**ours (probable):** `station_status` 2026-10-04T18:40:00.000Z to 2026-10-04T18:41:00.000Z, 2 tick(s), rule 4; 2. previous tick with log lines 2026-10-04T18:40:00.000Z; its last request ended 2026-10-04T18:41:05.813Z; failed requests on it: 2.

| Log line | Tick | Requested at | Purpose | Feed | HTTP | Elapsed ms | Error | File |
|---|---|---|---|---|---|---|---|---|
| ambici requests_2026-10-04.jsonl:2841 | 2026-10-04T18:40:00.000Z | 2026-10-04T18:40:00.010Z | observation | `station_status` | None | 18572 | URLError: [Errno 54] Connection reset by peer |  |
| bicing requests_2026-10-04.jsonl:1722 | 2026-10-04T18:40:00.000Z | 2026-10-04T18:40:00.010Z | observation | `station_status` | None | 48200 | timeout |  |
| bicing requests_2026-10-04.jsonl:1723 | 2026-10-04T18:40:00.000Z | 2026-10-04T18:40:48.212Z | index_refresh | `gbfs` | 200 | 14103 |  | `raw/gbfs/2026-10-04/20261004T184048Z.json.gz` |
| ambici requests_2026-10-04.jsonl:2842 | 2026-10-04T18:40:00.000Z | 2026-10-04T18:40:18.584Z | observation | `free_bike_status` | None | 47229 | timeout |  |

Raw files involved (AMBici files under `spikes/ambici-spike/`, the other system's under its own capture folder): last stored `station_status` before the gap, first after it, then the stored files of the log lines: `raw/station_status/2026-10-04/20261004T183900Z.json.gz`, `raw/station_status/2026-10-04/20261004T184400Z.json.gz`, `raw/gbfs/2026-10-04/20261004T184048Z.json.gz` (bicing).
<!-- END metric:5d.example -->

<!-- BEGIN metric:6b.example -->
### 6b. One `station_status` response and its `station_information`

Chosen: no status response has an unmatched ID; first status response in the window.

| Role | Raw file | Requested at | Stations |
|---|---|---|---|
| `station_status` | `raw/station_status/2026-10-03/20261003T171600Z.json.gz` | 2026-10-03T17:16:00.002Z | 237 |
| `station_information` (latest before it) | `raw/station_information/2026-10-03/20261003T171500Z.json.gz` | 2026-10-03T17:15:00.674Z | 237 |

IDs with status but no information: none. IDs with information but no status: none.
<!-- END metric:6b.example -->

## 1. Schema

<!-- BEGIN metric:1a -->
### 1a. Feeds published

181 `gbfs.json` responses used.

Language blocks: `ca,en,es` in 181 responses. Feed names taken from the `en` block. Responses whose language blocks list different feeds: 0.

| Feed | Responses listing it | First seen (UTC) | Last seen (UTC) |
|---|---|---|---|
| `free_bike_status` | 181 | 2026-10-03T17:15:00.332Z | 2026-10-05T14:15:00.342Z |
| `geofencing_zones` | 181 | 2026-10-03T17:15:00.332Z | 2026-10-05T14:15:00.342Z |
| `station_information` | 181 | 2026-10-03T17:15:00.332Z | 2026-10-05T14:15:00.342Z |
| `station_status` | 181 | 2026-10-03T17:15:00.332Z | 2026-10-05T14:15:00.342Z |
| `system_hours` | 181 | 2026-10-03T17:15:00.332Z | 2026-10-05T14:15:00.342Z |
| `system_information` | 181 | 2026-10-03T17:15:00.332Z | 2026-10-05T14:15:00.342Z |
| `system_pricing_plans` | 181 | 2026-10-03T17:15:00.332Z | 2026-10-05T14:15:00.342Z |
| `system_regions` | 181 | 2026-10-03T17:15:00.332Z | 2026-10-05T14:15:00.342Z |
| `vehicle_types` | 181 | 2026-10-03T17:15:00.332Z | 2026-10-05T14:15:00.342Z |

Listed but not captured: none. Captured but never listed (index excluded): none.
<!-- END metric:1a -->

<!-- BEGIN metric:1b -->
### 1b. Declared version

Versions found across all feeds: 2.3 (expected one; configured 2.3).

| Feed | Version (responses) |
|---|---|
| `free_bike_status` | 2.3 (2709) |
| `gbfs` | 2.3 (181) |
| `geofencing_zones` | 2.3 (181) |
| `station_information` | 2.3 (181) |
| `station_status` | 2.3 (2710) |
| `system_hours` | 2.3 (181) |
| `system_information` | 2.3 (181) |
| `system_pricing_plans` | 2.3 (181) |
| `system_regions` | 2.3 (181) |
| `vehicle_types` | 2.3 (181) |
<!-- END metric:1b -->

### 1c. Versions offered

Desk research by Chat; not computed by the script.

<!-- BEGIN metric:1d -->
### 1d. Field profile

Full profile in `field_profile.csv`.

| Feed | Responses | Field paths | Paths with nulls |
|---|---|---|---|
| `free_bike_status` | 2709 | 20 | 0 |
| `gbfs` | 181 | 19 | 0 |
| `geofencing_zones` | 181 | 7 | 0 |
| `station_information` | 181 | 18 | 0 |
| `station_status` | 2710 | 17 | 0 |
| `system_hours` | 181 | 12 | 0 |
| `system_information` | 181 | 23 | 0 |
| `system_pricing_plans` | 181 | 13 | 0 |
| `system_regions` | 181 | 8 | 0 |
| `vehicle_types` | 181 | 14 | 0 |

Paths with more than one non-null type:

| Feed | Path | Types (count) |
|---|---|---|
| `free_bike_status` | `data.bikes[].current_fuel_percent` | integer:2593111; number:3021945 |

Timestamp values that could not be converted to UTC:

None.
<!-- END metric:1d -->

<!-- BEGIN metric:1e -->
### 1e. Schema stability

Field paths appearing or disappearing versus the previous response of the same feed: 0 rows in `schema_changes.csv` (expected empty).
<!-- END metric:1e -->

<!-- BEGIN metric:1f -->
### 1f. Compliance

Schemas: MobilityData `gbfs-json-schema` v2.3 at commit `2e974fd51ae1db9c8006c97375d53e0b882cfedf`. Responses validated per feed: `free_bike_status` 2709, `gbfs` 181, `geofencing_zones` 181, `station_information` 181, `station_status` 2710, `system_hours` 181, `system_information` 181, `system_pricing_plans` 181, `system_regions` 181, `vehicle_types` 181.

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

One row per change in `content_changes.csv` (5308 rows). Intervals in seconds, by request time, between consecutive changes with no gap between them.

| Feed | Responses | Pairs compared | Pairs excluded (gap) | Changes | % changed | Intervals counted | Interval median | p95 | max |
|---|---|---|---|---|---|---|---|---|---|
| `station_status` | 2710 | 2706 | 3 | 2669 | 98.63 | 2666 | 60 | 60.008 | 120.009 |
| `free_bike_status` | 2709 | 2706 | 2 | 2637 | 97.45 | 2634 | 60.001 | 60.092 | 179.997 |
| `gbfs` | 181 | 180 | 0 | 0 | 0.00 | 0 |  |  |  |
| `system_information` | 181 | 180 | 0 | 0 | 0.00 | 0 |  |  |  |
| `vehicle_types` | 181 | 180 | 0 | 0 | 0.00 | 0 |  |  |  |
| `station_information` | 181 | 180 | 0 | 0 | 0.00 | 0 |  |  |  |
| `system_hours` | 181 | 180 | 0 | 2 | 1.11 | 1 | 44099.973 | 44099.973 | 44099.973 |
| `system_regions` | 181 | 180 | 0 | 0 | 0.00 | 0 |  |  |  |
| `system_pricing_plans` | 181 | 180 | 0 | 0 | 0.00 | 0 |  |  |  |
| `geofencing_zones` | 181 | 180 | 0 | 0 | 0.00 | 0 |  |  |  |
<!-- END metric:3a -->

<!-- BEGIN metric:3b -->
### 3b. Station reporting interval

`station_status` station items: 642270; with `last_reported` equal to the response's `last_updated`: 641781 (99.92 %); `last_reported` not convertible: 0. Response pairs exactly 1 tick apart: 2706; pairs excluded (gap): 3.

Station comparisons: 641322; station skipped for a pair (in only one of the two responses): 0. Negative intervals (`last_reported` going backwards): 1659. One row per station in `station_reporting.csv` (237 stations; 0 with no interval).

| Across stations, each station's median interval (s) | median | p95 | max |
|---|---|---|---|
| Value | 61 | 61 | 61 |

| Heartbeats (`last_reported` changed, counts did not) | Silent changes (counts changed, `last_reported` did not) |
|---|---|
| 615769 | 0 |
<!-- END metric:3b -->

<!-- BEGIN metric:3c -->
### 3c. `last_updated` behaviour

Lag = request time (`requested_at_utc`) − `last_updated`, in seconds. Negative = `last_updated` later than the request time.

| Feed | Responses | ttl (responses) | Lag min | median | p95 | max | Going backwards | Older than ttl | `last_updated` not convertible |
|---|---|---|---|---|---|---|---|---|---|
| `station_status` | 2710 | 60 (2710) | 0.003 | 31.009 | 58.009 | 64.006 | 7 | 78 of 2710 | 0 |
| `free_bike_status` | 2709 | 60 (2709) | 0.124 | 31.146 | 58.146 | 64.149 | 5 | 79 of 2709 | 0 |
| `gbfs` | 181 | 60 (181) | 0.385 | 30.399 | 57.337 | 60.607 | 0 | 1 of 181 | 0 |
| `system_information` | 181 | 60 (181) | 0.496 | 29.507 | 55.563 | 60.936 | 0 | 1 of 181 | 0 |
| `vehicle_types` | 181 | 60 (181) | 0.619 | 30.611 | 57.571 | 61.104 | 0 | 2 of 181 | 0 |
| `station_information` | 181 | 60 (181) | 0.054 | 30.069 | 56.731 | 59.867 | 0 | 0 of 181 | 0 |
| `system_hours` | 181 | 60 (181) | 0.871 | 30.215 | 56.836 | 60.236 | 0 | 2 of 181 | 0 |
| `system_regions` | 181 | 60 (181) | 0.352 | 30.984 | 56.004 | 61.502 | 0 | 3 of 181 | 0 |
| `system_pricing_plans` | 181 | 86400 (181) | 0.475 | 30.312 | 56.118 | 60.244 | 0 | 0 of 181 | 0 |
| `geofencing_zones` | 181 | 86400 (181) | 0.587 | 31.254 | 56.513 | 61.743 | 0 | 0 of 181 | 0 |

Values going backwards:

| Feed | Requested at | `last_updated` | Previous `last_updated` | File |
|---|---|---|---|---|
| `station_status` | 2026-10-04T07:08:00.006Z | 2026-10-04T07:06:56.000Z | 2026-10-04T07:06:59.000Z | `raw/station_status/2026-10-04/20261004T070800Z.json.gz` |
| `station_status` | 2026-10-04T10:45:00.010Z | 2026-10-04T10:43:58.000Z | 2026-10-04T10:43:59.000Z | `raw/station_status/2026-10-04/20261004T104500Z.json.gz` |
| `station_status` | 2026-10-04T20:55:00.010Z | 2026-10-04T20:53:58.000Z | 2026-10-04T20:53:59.000Z | `raw/station_status/2026-10-04/20261004T205500Z.json.gz` |
| `station_status` | 2026-10-05T00:59:00.002Z | 2026-10-05T00:57:56.000Z | 2026-10-05T00:57:59.000Z | `raw/station_status/2026-10-05/20261005T005900Z.json.gz` |
| `station_status` | 2026-10-05T03:56:00.010Z | 2026-10-05T03:54:57.000Z | 2026-10-05T03:54:58.000Z | `raw/station_status/2026-10-05/20261005T035600Z.json.gz` |
| `station_status` | 2026-10-05T04:57:00.007Z | 2026-10-05T04:55:59.000Z | 2026-10-05T04:56:00.000Z | `raw/station_status/2026-10-05/20261005T045700Z.json.gz` |
| `station_status` | 2026-10-05T10:45:00.004Z | 2026-10-05T10:43:56.000Z | 2026-10-05T10:43:57.000Z | `raw/station_status/2026-10-05/20261005T104500Z.json.gz` |
| `free_bike_status` | 2026-10-03T21:36:00.138Z | 2026-10-03T21:34:58.000Z | 2026-10-03T21:35:00.000Z | `raw/free_bike_status/2026-10-03/20261003T213600Z.json.gz` |
| `free_bike_status` | 2026-10-04T09:44:00.146Z | 2026-10-04T09:42:58.000Z | 2026-10-04T09:42:59.000Z | `raw/free_bike_status/2026-10-04/20261004T094400Z.json.gz` |
| `free_bike_status` | 2026-10-04T13:49:00.134Z | 2026-10-04T13:47:59.000Z | 2026-10-04T13:48:00.000Z | `raw/free_bike_status/2026-10-04/20261004T134900Z.json.gz` |
| `free_bike_status` | 2026-10-04T20:55:00.147Z | 2026-10-04T20:53:58.000Z | 2026-10-04T20:53:59.000Z | `raw/free_bike_status/2026-10-04/20261004T205500Z.json.gz` |
| `free_bike_status` | 2026-10-05T13:50:00.125Z | 2026-10-05T13:48:58.000Z | 2026-10-05T13:48:59.000Z | `raw/free_bike_status/2026-10-05/20261005T135000Z.json.gz` |
<!-- END metric:3c -->

<!-- BEGIN metric:3d -->
### 3d. Declared vs measured

Measured = the 3a interval between content changes, in seconds.

| Feed | Declared ttl (responses) | Measured median | p95 | max |
|---|---|---|---|---|
| `station_status` | 60 (2710) | 60 | 60.008 | 120.009 |
| `free_bike_status` | 60 (2709) | 60.001 | 60.092 | 179.997 |
| `gbfs` | 60 (181) |  |  |  |
| `system_information` | 60 (181) |  |  |  |
| `vehicle_types` | 60 (181) |  |  |  |
| `station_information` | 60 (181) |  |  |  |
| `system_hours` | 60 (181) | 44099.973 | 44099.973 | 44099.973 |
| `system_regions` | 60 (181) |  |  |  |
| `system_pricing_plans` | 86400 (181) |  |  |  |
| `geofencing_zones` | 86400 (181) |  |  |  |
<!-- END metric:3d -->

## 4. Sampling

<!-- BEGIN metric:4a -->
### 4a. Observed activity

Sum of |Δ| between `station_status` responses exactly 1 tick apart (lower bound of rentals + returns). Response pairs compared: 2706; excluded (gap): 3. Station comparisons: 641322; station skipped for a pair (in only one of the two responses): 0. Per-type comparisons: 629667, of which 825 with the type absent on one side (counted as 0).

| Measure | Activity (bikes) |
|---|---|
| Total (`num_bikes_available`) | 18303 |
| Type `196` | 12 |
| Type `204` | 18291 |
<!-- END metric:4a -->

<!-- BEGIN metric:4b -->
### 4b. Loss by interval

For each interval N and each of the N starting minutes, pairs exactly N ticks apart; a pair is kept only when every 1-min pair inside it exists. Loss per offset = 1 − activity at N ÷ 1-min activity over the same spans; the table shows the mean over the N offsets. Activities are means over offsets.

| Interval | Pairs kept (all offsets) | Pairs excluded (gap) | Activity at N (mean) | 1-min activity, same spans (mean) | Loss % (total) | Loss % type `196` | Loss % type `204` |
|---|---|---|---|---|---|---|---|
| 1 min | 2706 | 3 |  |  | 0.00 | 0.00 | 0.00 |
| 2 min | 2703 | 5 | 16860 | 18238 | 7.56 | 0.00 | 7.55 |
| 5 min | 2695 | 10 | 14912.2 | 18073.8 | 17.49 | 0.00 | 17.49 |
| 10 min | 2685 | 15 | 13083.7 | 17880.5 | 26.83 | 8.48 | 26.82 |
| 15 min | 2675 | 20 | 11761.2 | 17689.3 | 33.51 | 14.95 | 33.51 |
<!-- END metric:4b -->

<!-- BEGIN metric:4c -->
### 4c. Change size at 1 min

Station steps 1 tick apart where the total (`num_bikes_available`) changed: 16336 of 641322 station comparisons.

| \|Δ\| | Steps | % of changing steps |
|---|---|---|
| 1 | 14904 | 91.23 |
| ≥ 2 | 1432 | 8.77 |
<!-- END metric:4c -->

## 5. Reliability

<!-- BEGIN metric:5a -->
### 5a. Failed requests

All requests used, off-grid requests included. Failed = HTTP status ≠ 200, timeout or connection error.

| Feed | Requests | Failed | % failed | Errors (count) |
|---|---|---|---|---|
| `station_status` | 2713 | 3 | 0.11 | URLError: [Errno 54] Connection reset by peer (1); timeout (2) |
| `free_bike_status` | 2713 | 4 | 0.15 | timeout (4) |
| `gbfs` | 181 | 0 | 0.00 | — |
| `system_information` | 181 | 0 | 0.00 | — |
| `vehicle_types` | 181 | 0 | 0.00 | — |
| `station_information` | 181 | 0 | 0.00 | — |
| `system_hours` | 181 | 0 | 0.00 | — |
| `system_regions` | 181 | 0 | 0.00 | — |
| `system_pricing_plans` | 181 | 0 | 0.00 | — |
| `geofencing_zones` | 181 | 0 | 0.00 | — |

All feeds: 7 of 6874 (0.10 %).
<!-- END metric:5a -->

<!-- BEGIN metric:5b -->
### 5b. Latency

`elapsed_ms` of successful requests:

| Feed | Successful requests | Median ms | p95 ms | Max ms |
|---|---|---|---|---|
| `station_status` | 2710 | 131 | 188 | 18945 |
| `free_bike_status` | 2709 | 222 | 353 | 16392 |
| `gbfs` | 181 | 110 | 162 | 1149 |
| `system_information` | 181 | 111 | 152 | 1368 |
| `vehicle_types` | 181 | 112 | 155 | 2255 |
| `station_information` | 181 | 134 | 218 | 2467 |
| `system_hours` | 181 | 112 | 148 | 683 |
| `system_regions` | 181 | 114 | 163 | 605 |
| `system_pricing_plans` | 181 | 114 | 189 | 1108 |
| `geofencing_zones` | 181 | 112 | 164 | 1157 |

Failed requests, with their elapsed time:

| Feed | Tick | Requested at | Elapsed ms | Error |
|---|---|---|---|---|
| `station_status` | 2026-10-04T18:40:00.000Z | 2026-10-04T18:40:00.010Z | 18572 | URLError: [Errno 54] Connection reset by peer |
| `station_status` | 2026-10-04T18:42:00.000Z | 2026-10-04T18:42:00.010Z | 26230 | timeout |
| `station_status` | 2026-10-04T18:45:00.000Z | 2026-10-04T18:45:00.002Z | 26598 | timeout |
| `free_bike_status` | 2026-10-04T18:39:00.000Z | 2026-10-04T18:39:06.838Z | 50916 | timeout |
| `free_bike_status` | 2026-10-04T18:40:00.000Z | 2026-10-04T18:40:18.584Z | 47229 | timeout |
| `free_bike_status` | 2026-10-04T18:42:00.000Z | 2026-10-04T18:42:26.241Z | 43462 | timeout |
| `free_bike_status` | 2026-10-04T18:49:00.000Z | 2026-10-04T18:49:18.955Z | 44062 | timeout |
<!-- END metric:5b -->

<!-- BEGIN metric:5c -->
### 5c. Stale responses

From the request log (`server_last_updated`), stored responses of each feed ordered by request time; 6857 consecutive pairs compared. Stale responses: 12.

| Feed | Requested at | `last_updated` | Previous `last_updated` | File |
|---|---|---|---|---|
| `station_status` | 2026-10-04T07:08:00.006Z | 2026-10-04T07:06:56.000Z | 2026-10-04T07:06:59.000Z | `raw/station_status/2026-10-04/20261004T070800Z.json.gz` |
| `station_status` | 2026-10-04T10:45:00.010Z | 2026-10-04T10:43:58.000Z | 2026-10-04T10:43:59.000Z | `raw/station_status/2026-10-04/20261004T104500Z.json.gz` |
| `station_status` | 2026-10-04T20:55:00.010Z | 2026-10-04T20:53:58.000Z | 2026-10-04T20:53:59.000Z | `raw/station_status/2026-10-04/20261004T205500Z.json.gz` |
| `station_status` | 2026-10-05T00:59:00.002Z | 2026-10-05T00:57:56.000Z | 2026-10-05T00:57:59.000Z | `raw/station_status/2026-10-05/20261005T005900Z.json.gz` |
| `station_status` | 2026-10-05T03:56:00.010Z | 2026-10-05T03:54:57.000Z | 2026-10-05T03:54:58.000Z | `raw/station_status/2026-10-05/20261005T035600Z.json.gz` |
| `station_status` | 2026-10-05T04:57:00.007Z | 2026-10-05T04:55:59.000Z | 2026-10-05T04:56:00.000Z | `raw/station_status/2026-10-05/20261005T045700Z.json.gz` |
| `station_status` | 2026-10-05T10:45:00.004Z | 2026-10-05T10:43:56.000Z | 2026-10-05T10:43:57.000Z | `raw/station_status/2026-10-05/20261005T104500Z.json.gz` |
| `free_bike_status` | 2026-10-03T21:36:00.138Z | 2026-10-03T21:34:58.000Z | 2026-10-03T21:35:00.000Z | `raw/free_bike_status/2026-10-03/20261003T213600Z.json.gz` |
| `free_bike_status` | 2026-10-04T09:44:00.146Z | 2026-10-04T09:42:58.000Z | 2026-10-04T09:42:59.000Z | `raw/free_bike_status/2026-10-04/20261004T094400Z.json.gz` |
| `free_bike_status` | 2026-10-04T13:49:00.134Z | 2026-10-04T13:47:59.000Z | 2026-10-04T13:48:00.000Z | `raw/free_bike_status/2026-10-04/20261004T134900Z.json.gz` |
| `free_bike_status` | 2026-10-04T20:55:00.147Z | 2026-10-04T20:53:58.000Z | 2026-10-04T20:53:59.000Z | `raw/free_bike_status/2026-10-04/20261004T205500Z.json.gz` |
| `free_bike_status` | 2026-10-05T13:50:00.125Z | 2026-10-05T13:48:58.000Z | 2026-10-05T13:48:59.000Z | `raw/free_bike_status/2026-10-05/20261005T135000Z.json.gz` |
<!-- END metric:5c -->

<!-- BEGIN metric:5d -->
### 5d. Gaps

pmset excerpt: 392 dated lines read, by category: Assertions 391, Wake 1; sleep intervals overlapping the window: 0. Systems compared by scheduled tick.

Missing expected ticks per class and feed:

| Feed | ours | provider | ours (probable) | Total |
|---|---|---|---|---|
| `station_status` | 0 | 2 | 4 | 6 |
| `free_bike_status` | 0 | 2 | 5 | 7 |
| `gbfs` | 0 | 0 | 0 | 0 |
| `system_information` | 0 | 0 | 0 | 0 |
| `vehicle_types` | 0 | 0 | 0 | 0 |
| `station_information` | 0 | 0 | 0 | 0 |
| `system_hours` | 0 | 0 | 0 | 0 |
| `system_regions` | 0 | 0 | 0 | 0 |
| `system_pricing_plans` | 0 | 0 | 0 | 0 |
| `geofencing_zones` | 0 | 0 | 0 | 0 |
| All feeds | 0 | 4 | 9 | 13 |

Gaps (`gaps.csv`, 7 rows):

| Feed | Start | End | Duration (ticks) | Class | Rule | Log lines |
|---|---|---|---|---|---|---|
| `station_status` | 2026-10-04T18:40:00.000Z | 2026-10-04T18:41:00.000Z | 2 | ours (probable) | 4; 2 | ambici requests_2026-10-04.jsonl:2841; bicing requests_2026-10-04.jsonl:1722; bicing requests_2026-10-04.jsonl:1723; ambici requests_2026-10-04.jsonl:2842 |
| `station_status` | 2026-10-04T18:42:00.000Z | 2026-10-04T18:43:00.000Z | 2 | provider | 3; 2 | ambici requests_2026-10-04.jsonl:2843; bicing requests_2026-10-04.jsonl:1724; ambici requests_2026-10-04.jsonl:2844 |
| `station_status` | 2026-10-04T18:45:00.000Z | 2026-10-04T18:45:00.000Z | 1 | ours (probable) | 4 | ambici requests_2026-10-04.jsonl:2847; bicing requests_2026-10-04.jsonl:1728; bicing requests_2026-10-04.jsonl:1729; bicing requests_2026-10-04.jsonl:1730; bicing requests_2026-10-04.jsonl:1731; bicing requests_2026-10-04.jsonl:1732; bicing requests_2026-10-04.jsonl:1733; bicing requests_2026-10-04.jsonl:1734; bicing requests_2026-10-04.jsonl:1735; bicing requests_2026-10-04.jsonl:1736 |
| `station_status` | 2026-10-04T18:50:00.000Z | 2026-10-04T18:50:00.000Z | 1 | ours (probable) | 2 | ambici requests_2026-10-04.jsonl:2864; bicing requests_2026-10-04.jsonl:1740; bicing requests_2026-10-04.jsonl:1741 |
| `free_bike_status` | 2026-10-04T18:39:00.000Z | 2026-10-04T18:41:00.000Z | 3 | ours (probable) | 4; 2 | ambici requests_2026-10-04.jsonl:2840; bicing requests_2026-10-04.jsonl:1720; bicing requests_2026-10-04.jsonl:1721; ambici requests_2026-10-04.jsonl:2842; bicing requests_2026-10-04.jsonl:1722; bicing requests_2026-10-04.jsonl:1723; ambici requests_2026-10-04.jsonl:2841 |
| `free_bike_status` | 2026-10-04T18:42:00.000Z | 2026-10-04T18:43:00.000Z | 2 | provider | 3; 2 | ambici requests_2026-10-04.jsonl:2844; bicing requests_2026-10-04.jsonl:1724; ambici requests_2026-10-04.jsonl:2843 |
| `free_bike_status` | 2026-10-04T18:49:00.000Z | 2026-10-04T18:50:00.000Z | 2 | ours (probable) | 4; 2 | ambici requests_2026-10-04.jsonl:2864; bicing requests_2026-10-04.jsonl:1740; bicing requests_2026-10-04.jsonl:1741 |
<!-- END metric:5d -->

## 6. Identity

<!-- BEGIN metric:6a -->
### 6a. Station set over time

181 `station_information` responses used; stations per response: min 237, max 237; distinct station IDs: 237. Stations not present in every response: 0.

None.
<!-- END metric:6a -->

<!-- BEGIN metric:6b -->
### 6b. Information ↔ status match

Each `station_status` response joined to the latest `station_information` requested before it. Status responses joined: 2705; skipped (no earlier information): 5; with at least one unmatched ID: 0.

IDs with status but no information:

None.

IDs with information but no status:

None.
<!-- END metric:6b -->

<!-- BEGIN metric:6c -->
### 6c. Attribute stability

Fields compared: `name`, `lat`, `lon`, `capacity`; each station against its own previous appearance. Changes: 0.
<!-- END metric:6c -->

<!-- BEGIN metric:6d -->
### 6d. ID format

`station_id`, 237 distinct values (2c set); JSON type: string 237; numeric 237 (digits: 9–9), UUID 0, other 0.
<!-- END metric:6d -->

## 7. Volume

<!-- BEGIN metric:7a -->
### 7a. Size per request

Stored responses used, in bytes. `bytes_gz` is our own gzip size, which is what storage would hold.

| Feed | Stored responses | bytes_raw median | bytes_raw max | bytes_gz median | bytes_gz max |
|---|---|---|---|---|---|
| `station_status` | 2710 | 53420 | 53560 | 2283 | 2351 |
| `free_bike_status` | 2709 | 897464 | 927754 | 50958 | 53070 |
| `gbfs` | 181 | 3124 | 3124 | 374 | 375 |
| `system_information` | 181 | 687 | 687 | 447 | 449 |
| `vehicle_types` | 181 | 1439 | 1439 | 626 | 627 |
| `station_information` | 181 | 80130 | 80130 | 10561 | 10564 |
| `system_hours` | 181 | 348 | 348 | 209 | 210 |
| `system_regions` | 181 | 814 | 814 | 342 | 343 |
| `system_pricing_plans` | 181 | 209 | 209 | 204 | 205 |
| `geofencing_zones` | 181 | 126 | 126 | 157 | 158 |
<!-- END metric:7a -->

<!-- BEGIN metric:7b -->
### 7b. Size per day

2026-10-04 (UTC, by tick), as measured: sum of `bytes_gz` of every stored response, off-grid ones included.

| Feed | On-grid stored of expected | Off-grid stored | Off-grid bytes_gz | bytes_gz total | MB (10^6 bytes) |
|---|---|---|---|---|---|
| `station_status` | 1434 of 1440 | 0 | 0 | 3292078 | 3.29 |
| `free_bike_status` | 1433 of 1440 | 0 | 0 | 70810178 | 70.81 |
| `gbfs` | 96 of 96 | 0 | 0 | 35893 | 0.04 |
| `system_information` | 96 of 96 | 0 | 0 | 42889 | 0.04 |
| `vehicle_types` | 96 of 96 | 0 | 0 | 60064 | 0.06 |
| `station_information` | 96 of 96 | 0 | 0 | 1013879 | 1.01 |
| `system_hours` | 96 of 96 | 0 | 0 | 19567 | 0.02 |
| `system_regions` | 96 of 96 | 0 | 0 | 32852 | 0.03 |
| `system_pricing_plans` | 96 of 96 | 0 | 0 | 19576 | 0.02 |
| `geofencing_zones` | 96 of 96 | 0 | 0 | 15067 | 0.02 |
| All feeds |  |  |  | 75342043 | 75.34 |
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
| (i) available + docks available > capacity | `station_status` | 19551 | 3.04 | 43 | 18.14 | 2705 | 99.82 |

(ii): n/a, no disabled counts published.

As-of join with the latest `station_information` before each status response; status responses with no earlier information: 5; station items with no capacity in the joined information (skipped): 0.
<!-- END metric:8a -->

<!-- BEGIN metric:8b -->
### 8b. Negative counts

None found (station items checked: 642270, all count fields ≥ 0).
<!-- END metric:8b -->

<!-- BEGIN metric:8c -->
### 8c. Type breakdown mismatch

| Variant | Feed | Occurrences | % of items | Distinct stations/bikes | % of distinct | Responses affected | % of responses |
|---|---|---|---|---|---|---|---|
| Sum of type counts ≠ total available | `station_status` | 0 | 0.00 | 0 | 0.00 | 0 | 0.00 |
| Counted apart: types empty or missing, total = 0 | `station_status` | 14741 | 2.30 | 96 | 40.51 | 2596 | 95.79 |
| Counted apart: types empty or missing, total > 0 | `station_status` | 0 | 0.00 | 0 | 0.00 | 0 | 0.00 |
<!-- END metric:8c -->

<!-- BEGIN metric:8d -->
### 8d. Stale station

| Variant | Feed | Occurrences | % of items | Distinct stations/bikes | % of distinct | Responses affected | % of responses |
|---|---|---|---|---|---|---|---|
| `is_installed` true and `last_reported` older than 24 h | `station_status` | 0 | 0.00 | 0 | 0.00 | 0 | 0.00 |
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
| `is_installed` false | `station_status` | 0 | 0.00 | 0 | 0.00 | 0 | 0.00 |
| `is_renting` false | `station_status` | 21680 | 3.38 | 8 | 3.38 | 2710 | 100.00 |
| `is_returning` false | `station_status` | 21680 | 3.38 | 8 | 3.38 | 2710 | 100.00 |
| Any of the three false | `station_status` | 21680 | 3.38 | 8 | 3.38 | 2710 | 100.00 |
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

| Variant | Feed | Occurrences | % of items | Distinct stations/bikes | % of distinct | Responses affected | % of responses |
|---|---|---|---|---|---|---|---|
| `timezone` is `Europe/Berlin` | `system_information` | 181 |  |  |  | 181 | 100.00 |
| No `current_fuel_percent` and `current_range_meters` = 0 | `free_bike_status` | 36344 | 0.64 | 466 | 3.86 | 2709 | 100.00 |
| Breakdown: no `current_fuel_percent` and no `current_range_meters` | `free_bike_status` | 2636 | 0.05 | 7 | 0.06 | 2636 | 97.31 |
| Breakdown: no `current_fuel_percent` and `current_range_meters` > 0 | `free_bike_status` | 0 | 0.00 | 0 | 0.00 | 0 | 0.00 |
| Breakdown: `current_range_meters` = 0, fuel present | `free_bike_status` | 1009 | 0.02 | 25 | 0.21 | 769 | 28.39 |

The breakdown rows are exclusive of the combined row and of each other. "No" value = field absent or null.
<!-- END metric:8i -->

<!-- BEGIN metric:8j -->
### 8j. Inactive flags vs availability (added after first look)

| Variant | Feed | Occurrences | % of items | Distinct stations/bikes | % of distinct | Responses affected | % of responses |
|---|---|---|---|---|---|---|---|
| `is_renting` false, total available = 0 | `station_status` | 316 | 0.05 | 2 | 0.84 | 316 | 11.66 |
| `is_renting` false, total available > 0 | `station_status` | 21364 | 3.33 | 8 | 3.38 | 2710 | 100.00 |
| `is_returning` false, `num_docks_available` = 0 | `station_status` | 4314 | 0.67 | 5 | 2.11 | 2591 | 95.61 |
| `is_returning` false, `num_docks_available` > 0 | `station_status` | 17366 | 2.70 | 8 | 3.38 | 2710 | 100.00 |
| Total available = 0 and `is_renting` true | `station_status` | 14425 | 2.25 | 94 | 39.66 | 2596 | 95.79 |

Total available = `num_bikes_available`. Counted over station items; a station item can count in more than one row.
<!-- END metric:8j -->

## 9. `free_bike_status`

<!-- BEGIN metric:9a -->
### 9a. Extra fields

`free_bike_status` field paths with their 1d profile. The classification (equivalent in `station_status` or not) is done by Chat in the AMBici report.

| Path | Types | % present | % null | Min | Max | Distinct values or count | Classification (Chat) |
|---|---|---|---|---|---|---|---|
| `data` | object:2709 | 100.00 | 0.00 |  |  |  |  |
| `data.bikes` | array:2709 | 100.00 | 0.00 |  |  |  |  |
| `data.bikes[]` | object:5654036 |  | 0.00 |  |  |  |  |
| `data.bikes[].bike_id` | string:5654036 | 100.00 | 0.00 |  |  | 12065 |  |
| `data.bikes[].current_fuel_percent` | integer:2593111; number:3021945 | 99.31 | 0.00 | 0.02 | 1 | 95 |  |
| `data.bikes[].current_range_meters` | integer:5651400 | 99.95 | 0.00 | 0 | 60000 | 61 |  |
| `data.bikes[].is_disabled` | boolean:5654036 | 100.00 | 0.00 |  |  | [false] |  |
| `data.bikes[].is_reserved` | boolean:5654036 | 100.00 | 0.00 |  |  | [false, true] |  |
| `data.bikes[].lat` | number:5654036 | 100.00 | 0.00 | 41.265438 | 41.482205 | 236 |  |
| `data.bikes[].lon` | number:5654036 | 100.00 | 0.00 | 1.943849 | 2.267271 | 237 |  |
| `data.bikes[].pricing_plan_id` | string:5654036 | 100.00 | 0.00 |  |  | ["Rate0010"] |  |
| `data.bikes[].rental_uris` | object:5654036 | 100.00 | 0.00 |  |  |  |  |
| `data.bikes[].rental_uris.android` | string:5654036 | 100.00 | 0.00 |  |  | 237 |  |
| `data.bikes[].rental_uris.ios` | string:5654036 | 100.00 | 0.00 |  |  | 237 |  |
| `data.bikes[].rental_uris.web` | string:5654036 | 100.00 | 0.00 |  |  | 237 |  |
| `data.bikes[].station_id` | string:5654036 | 100.00 | 0.00 |  |  | 237 |  |
| `data.bikes[].vehicle_type_id` | string:5654036 | 100.00 | 0.00 |  |  | ["196", "204"] |  |
| `last_updated` | integer:2709 | 100.00 | 0.00 | 2026-10-03T17:10:21.000Z | 2026-10-05T14:25:35.000Z | 2679 |  |
| `ttl` | integer:2709 | 100.00 | 0.00 | 60 | 60 | [60] |  |
| `version` | string:2709 | 100.00 | 0.00 |  |  | ["2.3"] |  |
<!-- END metric:9a -->

<!-- BEGIN metric:9b -->
### 9b. Bikes outside stations

Bikes with no `station_id` (absent, null or empty): 0 of 5654036 bike items (0.00 %). Per response (2709 responses), % of bikes: min 0, median 0, max 0.
<!-- END metric:9b -->

<!-- BEGIN metric:9c -->
### 9c. Consistency

Per tick, available bikes per station from `free_bike_status` (not `is_reserved`, not `is_disabled`; a station with no such bike counts 0) vs `num_bikes_available`. Mismatch rate = mismatched (station, tick) pairs ÷ pairs compared.

| Response pairs | Ticks | (station, tick) pairs compared | Mismatches | Mismatch rate % |
|---|---|---|---|---|
| Same `last_updated` | 1548 | 366876 | 1177 | 0.32 |
| Different `last_updated` | 1160 | 274920 | 1011 | 0.37 |
| All | 2708 | 641796 | 2188 | 0.34 |

Ticks skipped: `station_status` without `free_bike_status` 2; `free_bike_status` without `station_status` 1. Available bikes at a `station_id` not in `station_status`: 0 (bike-tick occurrences), on 0 distinct station IDs.
<!-- END metric:9c -->

<!-- BEGIN metric:9d -->
### 9d. Cost

`free_bike_status` on 2026-10-04 (7b): 70810178 of 75342043 bytes_gz, 93.98 % of AMBici's daily volume.
<!-- END metric:9d -->

## 10. Languages

Exempt from the analysis window: both language-copy sets are used.

<!-- BEGIN metric:10a -->
### 10a. Structure

Copy sets: 2026-10-03T12:59:19.445Z, 2026-10-03T14:41:10.428Z (36 copy requests). Each copy is paired with the `en` observation of the same feed nearest in request time (any `en` response, window-exempt):

| Copy set | Feed | `en` response used | `en` − copy (s) |
|---|---|---|---|
| 2026-10-03T12:59:19.445Z | `station_status` | `raw/station_status/2026-10-03/20261003T130000Z.json.gz` | 40.558 |
| 2026-10-03T12:59:19.445Z | `free_bike_status` | `raw/free_bike_status/2026-10-03/20261003T130000Z.json.gz` | 40.422 |
| 2026-10-03T12:59:19.445Z | `system_information` | `raw/system_information/2026-10-03/20261003T130000Z.json.gz` | 40.572 |
| 2026-10-03T12:59:19.445Z | `vehicle_types` | `raw/vehicle_types/2026-10-03/20261003T130000Z.json.gz` | 40.578 |
| 2026-10-03T12:59:19.445Z | `station_information` | `raw/station_information/2026-10-03/20261003T130000Z.json.gz` | 40.56 |
| 2026-10-03T12:59:19.445Z | `system_hours` | `raw/system_hours/2026-10-03/20261003T130000Z.json.gz` | 40.544 |
| 2026-10-03T12:59:19.445Z | `system_regions` | `raw/system_regions/2026-10-03/20261003T130000Z.json.gz` | 40.532 |
| 2026-10-03T12:59:19.445Z | `system_pricing_plans` | `raw/system_pricing_plans/2026-10-03/20261003T130000Z.json.gz` | 40.534 |
| 2026-10-03T12:59:19.445Z | `geofencing_zones` | `raw/geofencing_zones/2026-10-03/20261003T130000Z.json.gz` | 40.536 |
| 2026-10-03T14:41:10.428Z | `station_status` | `raw/station_status/2026-10-03/20261003T144200Z.json.gz` | 49.573 |
| 2026-10-03T14:41:10.428Z | `free_bike_status` | `raw/free_bike_status/2026-10-03/20261003T144200Z.json.gz` | 49.538 |
| 2026-10-03T14:41:10.428Z | `system_information` | `raw/system_information/2026-10-03/20261003T144200Z.json.gz` | 49.686 |
| 2026-10-03T14:41:10.428Z | `vehicle_types` | `raw/vehicle_types/2026-10-03/20261003T144200Z.json.gz` | 49.687 |
| 2026-10-03T14:41:10.428Z | `station_information` | `raw/station_information/2026-10-03/20261003T144200Z.json.gz` | 49.689 |
| 2026-10-03T14:41:10.428Z | `system_hours` | `raw/system_hours/2026-10-03/20261003T144200Z.json.gz` | 49.705 |
| 2026-10-03T14:41:10.428Z | `system_regions` | `raw/system_regions/2026-10-03/20261003T144200Z.json.gz` | 49.705 |
| 2026-10-03T14:41:10.428Z | `system_pricing_plans` | `raw/system_pricing_plans/2026-10-03/20261003T144200Z.json.gz` | 49.699 |
| 2026-10-03T14:41:10.428Z | `geofencing_zones` | `raw/geofencing_zones/2026-10-03/20261003T144200Z.json.gz` | 49.695 |

| Feed | Compared | `ca` (both sets) | `es` (both sets) |
|---|---|---|---|
| `gbfs` | not copied (language-independent index) |  |  |
| `station_status` | same paths as `en` | yes | yes |
| `free_bike_status` | same paths as `en` | yes | yes |
| `system_information` | same paths as `en` | yes | yes |
| `vehicle_types` | same paths as `en` | yes | yes |
| `station_information` | same paths as `en` | yes | yes |
| `system_hours` | same paths as `en` | yes | yes |
| `system_regions` | same paths as `en` | yes | yes |
| `system_pricing_plans` | same paths as `en` | yes | yes |
| `geofencing_zones` | same paths as `en` | yes | yes |
<!-- END metric:10a -->

<!-- BEGIN metric:10b -->
### 10b. Values

Static feeds compared: `system_information`, `vehicle_types`, `station_information`, `system_hours`, `system_regions`, `system_pricing_plans`, `geofencing_zones`. Differing values, aggregated by feed, path and class (occurrences over both copy sets and both languages). "Other" occurrences: 15 (expected empty).

| Feed | Path | Class | Occurrences | Languages | Example |
|---|---|---|---|---|---|
| `geofencing_zones` | `last_updated` | other | 2 | ca, es | en: 1791038514 / ca: 1791038455 |
| `station_information` | `last_updated` | other | 3 | ca, es | en: 1791032354 / ca: 1791032353 |
| `system_hours` | `last_updated` | other | 2 | ca, es | en: 1791038514 / ca: 1791038454 |
| `system_information` | `data.language` | language-dependent | 4 | ca, es | en: en / ca: ca |
| `system_information` | `last_updated` | other | 2 | ca, es | en: 1791038514 / ca: 1791038454 |
| `system_pricing_plans` | `last_updated` | other | 2 | ca, es | en: 1791038514 / ca: 1791038454 |
| `system_regions` | `last_updated` | other | 2 | ca, es | en: 1791038514 / ca: 1791038454 |
| `vehicle_types` | `data.vehicle_types[]._description` | translated text | 4 | ca, es | en: - e-eco B frame with FrameLock - aluminum basket with ad p… / ca: - e-SMARTbike 2.0 reforzado - e-eco B cuadro con cierre cu… |
| `vehicle_types` | `data.vehicle_types[].name` | translated text | 12 | ca, es | en: E-Bike / ca: Bicicleta eléctrica |
| `vehicle_types` | `last_updated` | other | 2 | ca, es | en: 1791038514 / ca: 1791038455 |
<!-- END metric:10b -->

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
- 9b: no station = `station_id` absent, null or an empty string.
- 10: each copy is paired with the `en` observation of the same feed nearest in request time, from any `en` response (window-exempt).
- 10b: list items matched by a 3a ID key when every item carries it, otherwise by position; a URL that becomes equal once the language code is swapped for `en` = language-dependent; other differing strings except ID fields (`id`, `*_id`) = translated text; numbers, booleans, ID fields, other URLs and items on one side only = other.
