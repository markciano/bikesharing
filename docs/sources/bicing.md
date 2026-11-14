# Source card — Bicing

Facts about the Bicing data source, confirmed against captured data and the providers' portals.

## Source

| | |
|---|---|
| System | Bicing — public bike sharing of the city of Barcelona |
| Coverage | Barcelona city |
| Publisher (real time) | The technology provider, not the city: the feed contact is a Lyft address |
| Publisher (history) | Ajuntament de Barcelona, source B:SM, on Open Data BCN |
| Standard (real time) | GBFS 3.0 ([s002 › 1b](../spikes/s002-bicing-realtime-capture.md#1-schema), 2026-10-05) |
| Standard (history) | None declared: CSV whose columns take GBFS 2.3 `station_status` names where GBFS has the field ([Status archive](#status-archive-estacions)) |
| Licence (real time) | No licence fields → CC0 by the GBFS 3.0 default; attributed anyway as good practice |
| Licence (history) | CC BY 4.0 — **attribution required** in any published output |

## Access

### Real time

Always read `gbfs.json` and follow its URLs instead of hard-coding feed URLs, since the provider may change them.

| | |
|---|---|
| Index | `https://barcelona.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json` |
| Format | JSON, GBFS 3.0; `gbfs_versions` also lists 1.1 (`…/ube/gbfs/v1/`) and 2.3 (`…/customer/gbfs/v2/`), the 2.3 endpoint not requested ([s002 › 1c](../spikes/s002-bicing-realtime-capture.md#1-schema), 2026-10-05) |
| Auth | Public, no token |
| Languages | `ca`, `en`, `es`, `fr`, `nl` ([s002 › 1d](../spikes/s002-bicing-realtime-capture.md#1-schema), 2026-10-05) |
| Declared refresh | `ttl` 0 on every feed (no hint) |

### Open Data BCN secured JSON

- One resource per dataset; token sent raw in the `Authorization` header, stored in `.env` as `OPEN_DATA_BCN_TOKEN`.
- Both returned HTTP 500 with a valid token (2026-10-03). Not needed while the operator feed works.

### History

| | |
|---|---|
| Station status | `https://opendata-ajuntament.barcelona.cat/data/es/dataset/estat-estacions-bicing` |
| Station information | `https://opendata-ajuntament.barcelona.cat/data/es/dataset/informacio-estacions-bicing` |
| Format | Monthly `.7z` archives from March 2019: `..._ESTACIONS.7z` (status, 16–26 MB per month) and `..._INFORMACIO.7z` (information, 6–9 MB per month) |
| Auth | Public, no token; listable through the CKAN API (`/data/api/3/action/package_show?id=<dataset>`) |

- **Completeness:** months not listed (2026-11-14): November 2025, in both series; December 2025 to October 2026 are published.
- **Completeness:** gaps published by the provider, useful to validate an automatic gap detector:
  - 2019: 20 June 07:40–14:00; 26 July 13:30 → 29 July 10:40; 26 Nov 22:00 → 27 Nov 11:00 (possibly).
  - 2020: 7 Aug 02:25 → 10 Aug 10:40; November: 4th 01:45–11:05, 20th 19:50 → 21st 10:50, 27th 02:50 → 30th 09:50. Service stopped during COVID-19 measures.
  - 2023: 22–31 August and 1–5 September missing.
  - 2024: 5 February 12:50–13:05.
  - 2025: from 28 October 21:55 to end of month; November missing; December before the 9th missing, 9th–11th incomplete, normal from 11th 18:40.
- **Validity:** suspected wrong uploads, with the same byte size as the other series (2026-10-03): 2025-10 status and information (8,187,733 bytes); 2022-03 information equals 2022-03 status (25,816,125 bytes).
- **Content:** both series hold one row per station and snapshot, 48.3 million rows each from December 2025 to October 2026 ([p1_values.csv](../../spikes/d005-data-model/profile/bicing-historical/p1_values.csv), 2026-11-14); the status series is described in [Status archive](#status-archive-estacions).
- **Consistency:** columns are added, removed and moved between months, so they are read by name: `V1` appears in some months, `external_id` from March 2026, `is_valet_station` until June 2026 ([headers.csv](../../spikes/d005-data-model/profile/bicing-historical/headers.csv), 2026-11-14).
- **Consistency:** 290 stations change `capacity` at least once between December 2025 and October 2026 ([p6_capacity.csv](../../spikes/d005-data-model/profile/bicing-historical/p6_capacity.csv), 2026-11-14).

## General facts

Facts that hold for the whole source, not for one feed: how it publishes its data and how the system runs.

- **Stable schema:** every key path appears in every file of `station_status`, `station_information`, `vehicle_types` and `system_regions` ([`keys_check.py`](../../spikes/d005-data-model/profile/keys_check.py), 2026-10-14 to 2026-10-26).
- **`last_updated`:** the time the response was generated, equal to the request time, not data freshness; it can be up to 15 s ahead of the client clock and never went backwards ([s002 › 3c](../spikes/s002-bicing-realtime-capture.md#3-freshness), 2026-10-05).
- **Timestamps:** RFC 3339 in UTC (`Z`) ([s002 › 1f](../spikes/s002-bicing-realtime-capture.md#1-schema), 2026-10-05).
- **`ttl` gives no cadence:** every feed declares `ttl` 0 ([d004 › D3](../designs/d004-bronze-data-capture.md#d3-feed-cadence), [spike-log-queries.sql › 6](../../spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql), 2026-10-14 to 2026-11-05).
- **Static feeds:** over 12.5 days of hourly captures, `station_information` changed 68 times, `system_pricing_plans` and `vehicle_types` once each, and the other static feeds never ([d004 › D3](../designs/d004-bronze-data-capture.md#d3-feed-cadence), [spike-log-queries.sql › 6](../../spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql), 2026-10-14 to 2026-10-26).
- **Stable index:** the `gbfs` index was 968 B in every hourly read ([d004 › D5](../designs/d004-bronze-data-capture.md#d5-hourly-index-refresh), [spike-log-queries.sql › 5](../../spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql), 2026-10-14 to 2026-11-05).
- **Latency shifts:** median response latency moved from about 158 ms to 37 ms on 2026-10-29 and to about 139 ms on 2026-11-03, with no change on the capture side ([d004 › D4](../designs/d004-bronze-data-capture.md#d4-static-feeds-spread-across-passes), [spike-log-queries.sql › 5](../../spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql), 2026-11-05).
- **No `content-length`:** the origin sends none, also when serving gzip, so a response's size is known only by reading its body ([s006 › F7](../spikes/s006-cloudflare-capture.md#findings), [d004 › Source fetch](../designs/d004-bronze-data-capture.md#source-fetch), 2026-10-12).
- **Volume:** about 19 MB per day as gzip, with static feeds every 15 min ([s002 › 7b](../spikes/s002-bicing-realtime-capture.md#7-volume), 2026-10-04).
- **Reservations:** the app reserves a bike at a given station up to 5 min before picking it up (Bicing app, 2026-11-13).

## Feeds

One section per feed: what it holds, how often it changes and its quality issues; a feed the data model reads adds its field dictionary.

### `station_status`

- **Content:** vehicles and docks per station, available and disabled, per-type counts, the status flags and `last_reported`.
- **Change:** content changes every 60 s; 14.7 MB per day as gzip ([s002 › 3a, 7b](../spikes/s002-bicing-realtime-capture.md#3-freshness), 2026-10-04).
- **Quality:**
  - Consistency: the per-type counts do not add up to `num_vehicles_available` in 2.7% of station items, at 521 stations ([s002 › 8c](../spikes/s002-bicing-realtime-capture.md#8-quality), 2026-10-05).
  - Consistency: GBFS defines no relation between `capacity` ("total docking points installed at this station, both available and unavailable") and the station's counts of vehicles and docks ([GBFS](https://github.com/MobilityData/gbfs/blob/master/gbfs.md), read 2026-11-13).
  - Consistency: at in-service stations, available + disabled vehicles and docks equal `capacity` in 86.1% of station items, exceed it in 3.8%, at 63 stations, and fall below it in 10.1% ([capacity_arithmetic.sql](../../spikes/d005-data-model/capacity-arithmetic/capacity_arithmetic.sql), 2026-10-14 to 2026-10-26).
  - Consistency: above `capacity`, the excess is 1 in 97.4% of items and never more than 2, and every such item has at least as many disabled vehicles as the excess. In 90.4% of them `num_docks_disabled` is lower than the excess, so a disabled vehicle in a disabled dock counted twice does not explain it. A vehicle counted as both available and disabled fits all but 2 items, but the feed cannot prove it ([capacity_arithmetic.sql](../../spikes/d005-data-model/capacity-arithmetic/capacity_arithmetic.sql), 2026-10-14 to 2026-10-26).
  - Consistency: below `capacity`, 38.2% of items fall in runs of at most 6 min, 1 short in 85.7% of those runs, which fits a reservation or a vehicle being docked or released. Another 49.5% fall in runs of more than 1 day at 48 stations, with a shortfall that varies within the run from 1 up to 26, which fits docks counted in no term. The feed proves neither ([capacity_arithmetic.sql](../../spikes/d005-data-model/capacity-arithmetic/capacity_arithmetic.sql), 2026-10-14 to 2026-10-26).
  - Accuracy: station `7` (Pg. Pujades, 1) has 27 docks on Google Street View (imagery of August 2024) against a `capacity` of 25; at 4 other stations over `capacity` the docks match it (checked 2026-11-13).
  - Consistency: a new station can appear in `station_status` before `station_information` (station `309`, in 11 status responses) ([s002 › 6b](../spikes/s002-bicing-realtime-capture.md#6-identity), 2026-10-05).
  - Timeliness: 15 installed stations had not reported for more than 24 h in every response ([s002 › 8d](../spikes/s002-bicing-realtime-capture.md#8-quality), 2026-10-05); the oldest `last_reported` is still 2025-06-12 ([profile › station_status](../../spikes/d005-data-model/profile/bicing/station_status.csv), 2026-10-14 to 2026-10-26).
  - Timeliness: a station stops sending counts while its `last_reported` is old. With `last_reported` 24 h old or more, the counts differ from the station's previous pass in 0.02% of station items (9 of 59,994), against 16.1% when it is under 10 min. 5 of the 11 stations with such items were in service (`is_renting` true) during them, station `346` for 1,883 passes ([last_reported_by_age.csv](../../spikes/d005-data-model/last-reported/last_reported_by_age.csv), [last_reported_stale.csv](../../spikes/d005-data-model/last-reported/last_reported_stale.csv), 2026-10-14 to 2026-10-26).

#### Field dictionary

Every field of `station_status` as Bicing publishes it: its meaning, its definition in GBFS 3.0 and the values profiled from 2026-10-14 to 2026-10-26.

| Field | Description | Type | Required | Unit or format | Domain | Observed | Example | Notes |
|---|---|---|---|---|---|---|---|---|
| `last_updated` | [When the server generated the file][gbfs-output] | string | required | RFC 3339, UTC | — | No nulls; 2026-10-14T10:51:48Z to 2026-10-26T23:46:33Z | `2026-11-07T00:28:29Z` | Timeliness: the request time, not data freshness (see [General facts](#general-facts)) |
| `ttl` | [Declared seconds until the file is refreshed][gbfs-output] | integer | required | seconds | — | Always 0 | `0` | Gives no cadence (see [General facts](#general-facts)) |
| `version` | [GBFS version of the file][gbfs-output] | string | required | — | — | Always `3.0` | `3.0` | — |
| `data.stations[].station_id` | [The station's identifier, the same as in `station_information`][gbfs-ss] | string | required | — | — | No nulls; ≈547 distinct | `1` | Consistency: a new station can appear here first (see Quality) |
| `data.stations[].num_vehicles_available` | [Vehicles available for rental at the station][gbfs-ss] | integer | required | vehicles | — | No nulls; 0 to 54, mean 7.5, median 5 | `11` | Consistency: the per-type counts do not always add up to it (see Quality); see Field notes |
| `data.stations[].vehicle_types_available` | [Available vehicles by vehicle type][gbfs-ss] | array | conditionally required: when `vehicle_types` is published | — | — | No nulls; always one item each for `FIT`, `EFIT`, `BOOST` and `ICONIC` | `[{"vehicle_type_id": "BOOST", "count": 6}, …]` | — |
| `data.stations[].vehicle_types_available[].vehicle_type_id` | [The vehicle type, by its ID in `vehicle_types`][gbfs-ss] | string | required | — | — | `BOOST`, `EFIT`, `FIT`, `ICONIC`; no other | `BOOST` | See Field notes |
| `data.stations[].vehicle_types_available[].count` | [Available vehicles of that type][gbfs-ss] | integer | required | vehicles | — | No nulls; 0 to 51, median 0; 0 when the station has none | `6` | — |
| `data.stations[].num_vehicles_disabled` | [Vehicles at the station that cannot be rented][gbfs-ss] | integer | optional | vehicles | — | No nulls; 0 to 50, mean 2.9, median 2 | `3` | See Field notes |
| `data.stations[].num_docks_available` | [Free docks at the station][gbfs-ss] | integer | conditionally required: except at a station with unlimited docks | docks | — | No nulls; 0 to 54, median 17 | `32` | See Field notes |
| `data.stations[].num_docks_disabled` | [Docks at the station that are out of service][gbfs-ss] | integer | optional | docks | — | No nulls; 0 to 44, median 0 | `0` | — |
| `data.stations[].vehicle_docks_available` | [Free docks by the vehicle types they accept][gbfs-ss] | array | conditionally required: when `vehicle_types` is published | — | — | No nulls; one group of `ICONIC`, `BOOST`, `FIT` and `EFIT` at both ends of the profiled range | `[{"vehicle_type_ids": ["ICONIC", "BOOST", "FIT", "EFIT"], "count": 32}]` | — |
| `data.stations[].vehicle_docks_available[].vehicle_type_ids` | [The vehicle types those docks accept][gbfs-ss] | array | required | — | — | `ICONIC`, `BOOST`, `FIT`, `EFIT` | `["ICONIC", "BOOST", "FIT", "EFIT"]` | — |
| `data.stations[].vehicle_docks_available[].count` | [Free docks that accept those types][gbfs-ss] | integer | required | docks | — | 0 to 54 | `32` | — |
| `data.stations[].is_installed` | [Whether the station is installed on the street][gbfs-ss] | boolean | required | — | — | No nulls; true and false | `true` | See Field notes |
| `data.stations[].is_renting` | [Whether the station lets vehicles be rented][gbfs-ss] | boolean | required | — | — | No nulls; true and false | `true` | See Field notes |
| `data.stations[].is_returning` | [Whether the station accepts returned vehicles][gbfs-ss] | boolean | required | — | — | No nulls; true and false | `true` | See Field notes |
| `data.stations[].last_reported` | [The station's last report to the operator's backend][gbfs-ss] | string | required | RFC 3339, UTC, with milliseconds | — | No nulls; 2025-06-12T08:54:16.043Z to 2026-10-26T23:46:31.359Z, ≈3,140,143 distinct | `2026-11-07T00:26:25.523Z` | Timeliness: old at stations that stopped reporting (see Quality); see Field notes |

- **Field notes:**
  - `num_vehicles_available`: an out-of-service station reports 0 vehicles while its bikes stay there. Of 157 closings, 131 had bikes the pass before (median 4, up to 34) and all reported 0 at the closing pass; 127 reopened with bikes in their first pass in service (median 10), after a median of 70 min. Only 63 reopened within 2 bikes of their count before closing, so the operator may remove some during a closure ([out_of_service.csv](../../spikes/d005-data-model/out-of-service/out_of_service.csv), 2026-10-14 to 2026-10-26).
  - `num_vehicles_disabled` and `num_docks_available`: an out-of-service station keeps reporting its disabled vehicles and its free and disabled docks: its bikes do not move to `num_vehicles_disabled`, and `num_docks_available` does not count their docks as free. Of 157 closings, the free docks stayed the same at 126 and changed by 1 to 3 at 29, as between any two passes, and the disabled vehicles and the disabled docks changed at one each; at the reopening, the bikes came back with no change in the free docks at 135 of 160 ([out_of_service.csv](../../spikes/d005-data-model/out-of-service/out_of_service.csv), 2026-10-14 to 2026-10-26).
  - `vehicle_type_id`: `FIT` and `EFIT` showed no activity ([s002 › 4a](../spikes/s002-bicing-realtime-capture.md#4-sampling), 2026-10-05).
  - `is_installed` is false at 1 station ([s002 › 8f](../spikes/s002-bicing-realtime-capture.md#8-quality), 2026-10-05).
  - `is_renting` and `is_returning` follow their GBFS meaning: false only while a station is out of service, about 5 stations per pass and 121 in all, and the two never disagree ([d005 › D7](../designs/d005-data-model.md#d7-station-status-flags), 2026-10-14 to 2026-10-26).
  - `is_renting` alone also marks a suspension of rentals: from 2026-10-03T18:14Z to 10-04T09:49Z it was false at 90–99% of stations while `is_returning` stayed true, and stations reopened gradually until 10-04T18:27Z; it matches the torrential rain episode in Catalonia of 3 and 4 October ([AEMET](https://aemetblog.es/2026/10/21/analisis-del-episodio-de-lluvias-torrenciales-en-cataluna-del-3-y-4-de-octubre-de-2026/)). Outside it, about 5 stations per pass were out of service, as later ([s002 › 8f, 8j](../spikes/s002-bicing-realtime-capture.md#8-quality), 2026-11-12).
  - `last_reported` is a real per-station time, about every 3 min, but counts often change without it (71,699 silent changes in two days): changes are detected by content ([s002 › 3b](../spikes/s002-bicing-realtime-capture.md#3-freshness), 2026-10-05).
- **Evidence:** [profile › station_status](../../spikes/d005-data-model/profile/bicing/station_status.csv) and [station_status_vehicle_types](../../spikes/d005-data-model/profile/bicing/station_status_vehicle_types.csv), 9,681,888 station items from [profile.sql](../../spikes/d005-data-model/profile/bicing/profile.sql), 2026-10-14 to 2026-10-26; examples from the capture fixture [station_status.json](../../capture/test/fixtures/bicing/station_status.json), 2026-11-07.

### `station_information`

- **Content:** station name, coordinates, address, post code and capacity; 543 stations ([s002 › 6a](../spikes/s002-bicing-realtime-capture.md#6-identity), 2026-10-05).
- **Change:** 68 changes in 12.5 days (see [General facts](#general-facts)); 4.4 MB per day as gzip ([s002 › 7b](../spikes/s002-bicing-realtime-capture.md#7-volume), 2026-10-04).
- **Quality:**
  - Validity: `external_id` is not a GBFS 3.0 field ([s002 › 2a](../spikes/s002-bicing-realtime-capture.md#2-common-model), 2026-10-05).
  - Validity: `post_code` comes both with and without its leading zero (`08001`, `8001`) ([profile › station_information](../../spikes/d005-data-model/profile/bicing/station_information.csv), 2026-10-14 to 2026-10-26).
  - Completeness: `post_code` is missing in 0.37% of station items ([profile › station_information](../../spikes/d005-data-model/profile/bicing/station_information.csv), 2026-10-14 to 2026-10-26).
  - Validity: in 7 of 541 stations, `cross_street` pairs a neighbourhood with a district it does not belong to, e.g. `01/67`, where neighbourhood 67 is in district 10 ([neighbourhood.csv](../../spikes/d005-data-model/neighbourhood/neighbourhood.csv), stations of 2026-10-26, City Council boundaries of 2024-11-12).
  - Accuracy: the neighbourhood in `cross_street` is the one that contains the station in 522 of 541 stations; the other 19 name a neighbouring one, 0 to 82 m from the boundary, most on streets that form it, such as Gran Via or Paral·lel ([neighbourhood.csv](../../spikes/d005-data-model/neighbourhood/neighbourhood.csv), stations of 2026-10-26, City Council boundaries of 2024-11-12).
  - Validity: some `name` and `address` values start with a space ([profile › station_information](../../spikes/d005-data-model/profile/bicing/station_information.csv), 2026-10-14 to 2026-10-26).

#### Field dictionary

Every field of `station_information` as Bicing publishes it: its meaning, its definition in GBFS 3.0 and the values profiled from 2026-10-14 to 2026-10-26.

| Field | Description | Type | Required | Unit or format | Domain | Observed | Example | Notes |
|---|---|---|---|---|---|---|---|---|
| `last_updated` | [When the server generated the file][gbfs-output] | string | required | RFC 3339, UTC | — | No nulls; 2026-10-14T11:17:48Z to 2026-10-26T23:17:34Z | `2026-11-07T00:28:29Z` | — |
| `ttl` | [Declared seconds until the file is refreshed][gbfs-output] | integer | required | seconds | — | Always 0 | `0` | — |
| `version` | [GBFS version of the file][gbfs-output] | string | required | — | — | Always `3.0` | `3.0` | — |
| `data.stations[].station_id` | [The station's identifier][gbfs-si] | string | required | — | — | No nulls; ≈547 distinct | `1` | — |
| `data.stations[].external_id` | The station's UUID in the operator's system | string | — | UUID | — | No nulls; ≈564 distinct | `fc540556-eb2f-11ef-896d-0a9e2ea61361` | Validity: not a GBFS 3.0 field (see Quality) |
| `data.stations[].name` | [The station's public name, one item per language][gbfs-si] | array | required | — | — | No nulls; 5 items, one per language | `[{"text": "GRAN VIA CORTS CATALANES, 760", "language": "ca"}, …]` | — |
| `data.stations[].name[].text` | [The name in that language][gbfs-ls] | string | required | — | — | ≈518 distinct; the same text in all 5 languages | `GRAN VIA CORTS CATALANES, 760` | Validity: 7 stations have leading or trailing spaces (see Field notes) |
| `data.stations[].name[].language` | [The language of the name][gbfs-ls] | string | required | IETF BCP 47 | — | `ca`, `en`, `es`, `fr`, `nl` | `ca` | — |
| `data.stations[].short_name` | [A short station code, one item per language][gbfs-si] | array | optional | — | — | No nulls; 5 items, one per language | `[{"text": "1", "language": "ca"}, …]` | — |
| `data.stations[].short_name[].text` | [The code in that language][gbfs-ls] | string | required | — | — | ≈524 distinct; the same text in all 5 languages | `1` | — |
| `data.stations[].short_name[].language` | [The language of the code][gbfs-ls] | string | required | IETF BCP 47 | — | `ca`, `en`, `es`, `fr`, `nl` | `ca` | — |
| `data.stations[].lat` | [The station's latitude][gbfs-si] | number | required | WGS 84 degrees | — | 41.3467746 to 41.462095 | `41.3979779` | — |
| `data.stations[].lon` | [The station's longitude][gbfs-si] | number | required | WGS 84 degrees | — | 2.1091535 to 2.2206913 | `2.1801069` | — |
| `data.stations[].address` | [The station's street address][gbfs-si] | string | optional | — | — | No nulls; ≈538 distinct | `GRAN VIA CORTS CATALANES, 760` | Validity: some start with a space (see Quality) |
| `data.stations[].cross_street` | [The district and neighbourhood, by the City Council's two-digit codes and names][gbfs-si] | string | optional | `DD-District/NN-Neighbourhood` | — | No nulls; 71 distinct | `02-Eixample/05-el Fort Pienc` | Differs from GBFS: a district and neighbourhood, not a cross street; validity and accuracy issues (see Quality) |
| `data.stations[].post_code` | [The station's post code][gbfs-si] | string | optional | — | — | 0.37% null; 45 distinct | `08013` | Validity and completeness issues (see Quality) |
| `data.stations[].capacity` | [Docks at the station, available and unavailable][gbfs-si] | integer | optional | docks | — | 0 to 54, median 27 | `46` | See Field notes and [`station_status`](#station_status) › Quality |
| `data.stations[].vehicle_types_capacity` | [Vehicles of each type the station can hold][gbfs-si] | array | optional | — | — | Always empty | `[]` | — |
| `data.stations[].vehicle_docks_capacity` | [Docks by the vehicle types they accept][gbfs-si] | array | optional | — | — | One group at both ends of the profiled range | `[{"vehicle_type_ids": ["ASTRO", "BOOST", …], "count": 46}]` | — |
| `data.stations[].vehicle_docks_capacity[].vehicle_type_ids` | [The vehicle types those docks accept][gbfs-si] | array | required | — | — | IDs of `vehicle_types`: 9 at the low end of the profiled range (with `METRO`), 10 at the high end (with `METRO_BASE` and `TRAILER`) | `["ASTRO", "BOOST", "CHLOE", …]` | — |
| `data.stations[].vehicle_docks_capacity[].count` | [Docks that accept those types][gbfs-si] | integer | required | docks | — | 0 to 54 | `46` | Equals `capacity` (see Field notes) |
| `data.stations[].is_charging_station` | [Whether the station charges electric vehicles][gbfs-si] | boolean | optional | — | — | Always true | `true` | — |
| `data.stations[].rental_methods` | [Payment methods accepted at the station][gbfs-si] | array | optional | — | `key`, `creditcard`, `paypass`, `applepay`, `androidpay`, `transitcard`, `accountnumber`, `phone` | Always `key`, `transitcard`, `creditcard`, `phone` | `["key", "transitcard", "creditcard", "phone"]` | — |
| `data.stations[].is_virtual_station` | [Whether the station has no physical docks][gbfs-si] | boolean | optional | — | — | Always false | `false` | — |
| `data.stations[].rental_uris` | [Links to the station in the apps and on the web][gbfs-si] | object | optional | — | — | Always empty | `{}` | — |

- **Field notes:**
  - `name` and `short_name`: localised in 5 languages ([s002 › 1d](../spikes/s002-bicing-realtime-capture.md#1-schema), 2026-10-05), always with the same text in all 5; 7 stations have a `name` with leading or trailing spaces ([`names_check.py`](../../spikes/d005-data-model/station-names/names_check.py), 2026-10-14 to 2026-10-26).
  - `capacity` equals the `count` of the single `vehicle_docks_capacity` group and can change: 13 changes in two days, and station `77` went from 24 to 0 ([s002 › 6c, 8a](../spikes/s002-bicing-realtime-capture.md#6-identity), 2026-10-05).
- **Evidence:** [profile › station_information](../../spikes/d005-data-model/profile/bicing/station_information.csv), 163,108 station items from [profile.sql](../../spikes/d005-data-model/profile/bicing/profile.sql), and [`keys_check.py`](../../spikes/d005-data-model/profile/keys_check.py), 2026-10-14 to 2026-10-26; examples from the capture fixture [station_information.json](../../capture/test/fixtures/bicing/station_information.json), 2026-11-07.

### `vehicle_types`

- **Content:** 11 type IDs over the window, 9 or 10 per response: bicycles, a standing scooter (`CHLOE`) and a trailer (`TRAILER`), with 3 values of `form_factor` and 3 of `propulsion_type` ([profile › vehicle_types](../../spikes/d005-data-model/profile/bicing/vehicle_types.csv), 2026-10-14 to 2026-10-26); `METRO` became `METRO_BASE` on 2026-10-22 ([`vehicle_types_check.py`](../../spikes/d005-data-model/vehicle-types/vehicle_types_check.py)).
- **Quality:**
  - Validity: `default_pricing_plan_id` is sometimes an empty string ([s002 › 2a](../spikes/s002-bicing-realtime-capture.md#2-common-model), 2026-10-05).
  - Completeness: `pricing_plan_ids` is missing in 14.89% of type items ([profile › vehicle_types](../../spikes/d005-data-model/profile/bicing/vehicle_types.csv), 2026-10-14 to 2026-10-26).

#### Field dictionary

Every field of `vehicle_types` as Bicing publishes it: its meaning, its definition in GBFS 3.0 and the values profiled from 2026-10-14 to 2026-10-26.

| Field | Description | Type | Required | Unit or format | Domain | Observed | Example | Notes |
|---|---|---|---|---|---|---|---|---|
| `last_updated` | [When the server generated the file][gbfs-output] | string | required | RFC 3339, UTC | — | No nulls; 2026-10-14T11:17:48Z to 2026-10-26T23:17:35Z | `2026-11-07T00:28:30Z` | — |
| `ttl` | [Declared seconds until the file is refreshed][gbfs-output] | integer | required | seconds | — | Always 0 | `0` | — |
| `version` | [GBFS version of the file][gbfs-output] | string | required | — | — | Always `3.0` | `3.0` | — |
| `data.vehicle_types[].vehicle_type_id` | [The type's identifier, the one `station_status` cites][gbfs-vt] | string | required | — | — | 11 distinct, `ASTRO` to `TRAILER` | `ICONIC` | See Content |
| `data.vehicle_types[].form_factor` | [The vehicle's form][gbfs-vt] | string | required | — | `bicycle`, `cargo_bicycle`, `car`, `moped`, `scooter_standing`, `scooter_seated`, `other` | 3 distinct, `bicycle` to `scooter_standing` | `bicycle` | — |
| `data.vehicle_types[].propulsion_type` | [How the vehicle is propelled][gbfs-vt] | string | required | — | `human`, `electric_assist`, `electric`, `combustion`, `combustion_diesel`, `hybrid`, `plug_in_hybrid`, `hydrogen_fuel_cell` | `electric`, `electric_assist`, `human` | `electric_assist` | — |
| `data.vehicle_types[].max_range_meters` | [Distance the vehicle can travel on a full charge][gbfs-vt] | number | conditionally required: when `propulsion_type` is not `human` | metres | — | No nulls; 0 to 70,000, 3 distinct; 0 for most types | `0` | Accuracy: 0 also for `BOOST`, an `electric_assist` type ([vehicle_types.json](../../capture/test/fixtures/bicing/vehicle_types.json), 2026-11-07) |
| `data.vehicle_types[].name` | [The type's name, one item per language][gbfs-vt] | array | optional | — | — | No nulls; 5 items, one per language | `[{"text": "ICONIC", "language": "ca"}, …]` | — |
| `data.vehicle_types[].name[].text` | [The name in that language][gbfs-ls] | string | required | — | — | 11 distinct, `ASTRO` to `TRAILER` | `ICONIC` | — |
| `data.vehicle_types[].name[].language` | [The language of the name][gbfs-ls] | string | required | IETF BCP 47 | — | `ca`, `en`, `es`, `fr`, `nl` | `ca` | — |
| `data.vehicle_types[].default_pricing_plan_id` | [The pricing plan that applies by default, by its ID in `system_pricing_plans`][gbfs-vt] | string | conditionally required: when `system_pricing_plans` is published | — | — | No nulls; 3 distinct, an empty string among them | `8-4` | Validity: sometimes an empty string (see Quality) |
| `data.vehicle_types[].pricing_plan_ids` | [Every pricing plan that applies to the type][gbfs-vt] | array | optional | — | — | 14.89% null; 2 distinct lists | `["8-4", "8-5", …]` | Completeness: see Quality |

- **Evidence:** [profile › vehicle_types](../../spikes/d005-data-model/profile/bicing/vehicle_types.csv), 2,820 type items from [profile.sql](../../spikes/d005-data-model/profile/bicing/profile.sql), 2026-10-14 to 2026-10-26; examples from the capture fixture [vehicle_types.json](../../capture/test/fixtures/bicing/vehicle_types.json), 2026-11-07.

### `system_information`

- **Content:** `system_id` `bike_barcelona`, timezone `Europe/Madrid`, and the provider's contact.

### `system_pricing_plans`

- **Content:** prices.
- **Change:** 0.1 MB per day as gzip ([s002 › 7a](../spikes/s002-bicing-realtime-capture.md#7-volume), 2026-10-04).

### `system_regions`

- **Content:** empty: no region in any response ([`keys_check.py`](../../spikes/d005-data-model/profile/keys_check.py), 2026-10-14 to 2026-10-26).

### `geofencing_zones`

- **Content:** essentially empty, 152 B ([s002 › 7a](../spikes/s002-bicing-realtime-capture.md#7-volume), 2026-10-05).

### Status archive (`ESTACIONS`)

- **Content:** the status series of the [History](#history) archives, `..._ESTACIONS.7z`: one row per station and snapshot, 513–546 stations per snapshot; each archive covers one local month (Europe/Madrid) and holds no rows outside it ([p2_grain.csv](../../spikes/d005-data-model/profile/bicing-historical/p2_grain.csv), December 2025 to October 2026, 2026-11-14).
- **Quality:**
  - Consistency: mechanical plus electric equals `num_bikes_available` in 99.6–99.8% of rows per month; the rest differ by up to 53 bikes ([p5_split.csv](../../spikes/d005-data-model/profile/bicing-historical/p5_split.csv), 2026-11-14).
  - Consistency: over the overlap with real-time capture (2026-10-14 to 10-26), all 543 stations match the real-time `station_id`, position and `capacity`; paired with the latest real-time response within 60 s (median 18 s), `num_bikes_available` equals `num_vehicles_available` in 92% of rows and `num_vehicles_available` plus `num_vehicles_disabled` in 13%; only 543 rows share the exact `last_updated`. The remaining 8% was not investigated ([p6_identity.csv](../../spikes/d005-data-model/profile/bicing-historical/p6_identity.csv), [p7_counts.csv](../../spikes/d005-data-model/profile/bicing-historical/p7_counts.csv), 2026-11-14).
  - Timeliness: snapshots are 5 minutes apart (median 300 s every month); in May and June 2026 the cadence is irregular, with 90% and 76% of intervals between 240 and 360 s ([p3_cadence.csv](../../spikes/d005-data-model/profile/bicing-historical/p3_cadence.csv), 2026-11-14).
  - Uniqueness: duplicate station and snapshot rows only in May (10,772), June (25,409) and July 2026 (2,164); the duplicates of 8 keys differ ([p2_grain.csv](../../spikes/d005-data-model/profile/bicing-historical/p2_grain.csv), 2026-11-14).
  - Completeness: gaps not in the provider's list, December 2025 to October 2026: 13 April 07:25 → 14 April 10:05; 24 April 11:10–16:20; intermittent from 29 July 18:50 to 6 August 08:45; 29 September 20:05 → 6 October 08:00 (UTC) ([p4_gaps.csv](../../spikes/d005-data-model/profile/bicing-historical/p4_gaps.csv), 2026-11-14).

#### Field dictionary

Every column of the status archive as Bicing publishes it: its meaning, its definition in GBFS 2.3 where GBFS has the field, and the values profiled in the archives of December 2025 to October 2026. The archive is CSV, so Type is the type its text holds.

| Field | Description | Type | Required | Unit or format | Domain | Observed | Example | Notes |
|---|---|---|---|---|---|---|---|---|
| `last_updated` | [The snapshot's time, shared by all its rows][gbfs23-output] | integer | required | POSIX time | — | No nulls; 2025-12-09T08:35:42Z to 2026-10-31T22:55:04Z | `1765269342` | Timeliness: 5 minutes apart (see Quality) |
| `ttl` | [Declared seconds until the file is refreshed][gbfs23-output] | integer | required | seconds | — | Always 0 | `0` | — |
| `station_id` | [The station's identifier, the same as in real time][gbfs23-ss] | integer | required | — | — | No nulls; 1 to 614, ≈551 distinct | `1` | — |
| `num_bikes_available` | [Bikes available for rental at the station][gbfs23-ss] | integer | required | bikes | — | No nulls; 0 to 54, median 6 | `6` | Consistency: matches real-time `num_vehicles_available` in 92% of paired rows (see Quality) |
| `num_bikes_available_types.mechanical` | Mechanical bikes among `num_bikes_available` | integer | — | bikes | — | No nulls; 0 to 51, median 2 | `2` | Differs from GBFS: not a GBFS field; consistency: with `.ebike`, does not always add up (see Quality) |
| `num_bikes_available_types.ebike` | Electric bikes among `num_bikes_available` | integer | — | bikes | — | No nulls; 0 to 52, median 2 | `2` | Differs from GBFS: not a GBFS field |
| `num_docks_available` | [Free docks at the station][gbfs23-ss] | integer | conditionally required: except at a station with unlimited docks | docks | — | No nulls; 0 to 54, median 16 | `16` | — |
| `last_reported` | [The station's last report][gbfs23-ss] | integer | required | POSIX time | — | No nulls; 0 to 2026-10-31T22:55:03Z | `1793487303` | Validity: reaches 0, the POSIX epoch (1970-01-01); the rows were not counted |
| `is_installed` | [Whether the station is installed on the street][gbfs23-ss] | integer | required | — | — | `1` (48,273,428 rows), `0` (17,130) | `1` | Differs from GBFS: `0` or `1`, not a boolean; see Field notes |
| `is_renting` | [Whether the station lets bikes be rented][gbfs23-ss] | integer | required | — | — | `1` (47,934,249 rows), `0` (356,309) | `1` | Differs from GBFS: `0` or `1`, not a boolean |
| `is_returning` | [Whether the station accepts returned bikes][gbfs23-ss] | integer | required | — | — | `1` (48,063,837 rows), `0` (226,721) | `1` | Differs from GBFS: `0` or `1`, not a boolean |
| `status` | The station's operating state | string | — | — | — | `IN_SERVICE` (48,063,837 rows), `MAINTENANCE` (105,460), `NOT_IN_SERVICE` (104,131), `PLANNED` (17,130) | `IN_SERVICE` | Differs from GBFS: not a GBFS field; see Field notes |
| `is_charging_station` | [Whether the station charges electric bikes][gbfs23-si] | string | optional | — | — | Always `TRUE` | `TRUE` | Differs from GBFS: a `station_information` field in GBFS, here as the text `TRUE`, not a boolean |
| `traffic` | Holds no value | string | — | — | — | Always `NA` | `NA` | Differs from GBFS: not a GBFS field |
| `V1` | Holds no value | string | — | — | — | Always `NA`; only in January and March 2026 | `NA` | Differs from GBFS: not a GBFS field; see [History](#history) › Consistency |

- **Field notes:**
  - `status` is `PLANNED` in exactly the rows with `is_installed = 0` ([p1_values.csv](../../spikes/d005-data-model/profile/bicing-historical/p1_values.csv), 2026-11-14).
  - The archive has no `version` column, and no disabled vehicles or docks ([headers.csv](../../spikes/d005-data-model/profile/bicing-historical/headers.csv), 2026-11-14).
  - No numeric column holds a non-numeric value ([p1_invalid.csv](../../spikes/d005-data-model/profile/bicing-historical/p1_invalid.csv), 2026-11-14).
- **Evidence:** [p1_fields_estacions.csv](../../spikes/d005-data-model/profile/bicing-historical/p1_fields_estacions.csv) and [p1_values.csv](../../spikes/d005-data-model/profile/bicing-historical/p1_values.csv), 48,290,558 rows from [profile.sql](../../spikes/d005-data-model/profile/bicing-historical/profile.sql), archives of December 2025 to October 2026, profiled 2026-11-14.

## Open questions

- Whether the monthly archives are dumps of this feed, and whether they keep the GBFS 2.x fields (`num_bikes_available`, `num_bikes_available_types` with `mechanical` and `ebike`, `is_charging_station`, `status`) (T005).
- Content and schema changes inside the archives, 2019–2026 (T005).
- Whether the suspected wrong uploads are really wrong (T005).
- Whether a reserved bike still counts in `num_vehicles_available`: `station_status` has no count of reserved vehicles.

[gbfs-output]: https://github.com/MobilityData/gbfs/blob/v3.0/gbfs.md#output-format
[gbfs-ss]: https://github.com/MobilityData/gbfs/blob/v3.0/gbfs.md#station_statusjson
[gbfs-si]: https://github.com/MobilityData/gbfs/blob/v3.0/gbfs.md#station_informationjson
[gbfs-vt]: https://github.com/MobilityData/gbfs/blob/v3.0/gbfs.md#vehicle_typesjson
[gbfs-ls]: https://github.com/MobilityData/gbfs/blob/v3.0/gbfs.md#localized-string
[gbfs23-output]: https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md#output-format
[gbfs23-ss]: https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md#station_statusjson
[gbfs23-si]: https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md#station_informationjson
