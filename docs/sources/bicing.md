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

- **Completeness:** months not listed (2026-10-03): status November 2025, January 2026 and July 2026; information November 2025 and July 2026.
- **Completeness:** gaps published by the provider, useful to validate an automatic gap detector:
  - 2019: 20 June 07:40–14:00; 26 July 13:30 → 29 July 10:40; 26 Nov 22:00 → 27 Nov 11:00 (possibly).
  - 2020: 7 Aug 02:25 → 10 Aug 10:40; November: 4th 01:45–11:05, 20th 19:50 → 21st 10:50, 27th 02:50 → 30th 09:50. Service stopped during COVID-19 measures.
  - 2023: 22–31 August and 1–5 September missing.
  - 2024: 5 February 12:50–13:05.
  - 2025: from 28 October 21:55 to end of month; November missing; December before the 9th missing, 9th–11th incomplete, normal from 11th 18:40.
- **Validity:** suspected wrong uploads, with the same byte size as the other series (2026-10-03): 2025-10 status and information (8,187,733 bytes); 2022-03 information equals 2022-03 status (25,816,125 bytes).

## Facts

### Service

- **Stable schema:** every key path appears in every file of `station_status`, `station_information`, `vehicle_types` and `system_regions` ([`keys_check.py`](../../spikes/d005-data-model/profile/keys_check.py), 2026-10-14 to 2026-10-26).
- **`last_updated`:** the time the response was generated, equal to the request time, not data freshness; it can be up to 15 s ahead of the client clock and never went backwards ([s002 › 3c](../spikes/s002-bicing-realtime-capture.md#3-freshness), 2026-10-05).
- **Timestamps:** RFC 3339 in UTC (`Z`) ([s002 › 1f](../spikes/s002-bicing-realtime-capture.md#1-schema), 2026-10-05).
- **`ttl` gives no cadence:** every feed declares `ttl` 0 ([d004 › D3](../designs/d004-bronze-data-capture.md#d3-feed-cadence), [spike-log-queries.sql › 6](../../spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql), 2026-10-14 to 2026-11-05).
- **Static feeds:** over 12.5 days of hourly captures, `station_information` changed 68 times, `system_pricing_plans` and `vehicle_types` once each, and the other static feeds never ([d004 › D3](../designs/d004-bronze-data-capture.md#d3-feed-cadence), [spike-log-queries.sql › 6](../../spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql), 2026-10-14 to 2026-10-26).
- **Stable index:** the `gbfs` index was 968 B in every hourly read ([d004 › D5](../designs/d004-bronze-data-capture.md#d5-hourly-index-refresh), [spike-log-queries.sql › 5](../../spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql), 2026-10-14 to 2026-11-05).
- **Latency shifts:** median response latency moved from about 158 ms to 37 ms on 2026-10-29 and to about 139 ms on 2026-11-03, with no change on the capture side ([d004 › D4](../designs/d004-bronze-data-capture.md#d4-static-feeds-spread-across-passes), [spike-log-queries.sql › 5](../../spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql), 2026-11-05).
- **No `content-length`:** the origin sends none, also when serving gzip, so a response's size is known only by reading its body ([s006 › F7](../spikes/s006-cloudflare-capture.md#findings), [d004 › Source fetch](../designs/d004-bronze-data-capture.md#source-fetch), 2026-10-12).
- **Volume:** about 19 MB per day as gzip, with static feeds every 15 min ([s002 › 7b](../spikes/s002-bicing-realtime-capture.md#7-volume), 2026-10-04).

### `station_status`

- **Content:** vehicles and docks per station, available and disabled, per-type counts, the status flags and `last_reported`.
- **Fields:**
  - Observed: `station_id`, `num_vehicles_available`, `num_vehicles_disabled`, `num_docks_available`, `num_docks_disabled`, `last_reported`, `is_installed`, `is_renting`, `is_returning`, `vehicle_docks_available`, `vehicle_types_available` ([s002 › 2a](../spikes/s002-bicing-realtime-capture.md#2-common-model), 2026-10-05).
  - `last_reported` is a real per-station time, about every 3 min, but counts often change without it (71,699 silent changes in two days): changes are detected by content ([s002 › 3b](../spikes/s002-bicing-realtime-capture.md#3-freshness), 2026-10-05).
  - No field has nulls ([profile › station_status](../../spikes/d005-data-model/profile/bicing/station_status.csv), 2026-10-14 to 2026-10-26).
  - `vehicle_types_available` always lists `FIT`, `EFIT`, `BOOST` and `ICONIC`, with count 0 when there are none, and no other type ([profile › station_status_vehicle_types](../../spikes/d005-data-model/profile/bicing/station_status_vehicle_types.csv), 2026-10-14 to 2026-10-26); `FIT` and `EFIT` showed no activity ([s002 › 4a](../spikes/s002-bicing-realtime-capture.md#4-sampling), 2026-10-05).
  - `num_vehicles_disabled` averages 2.9 per station, against 7.5 available, and reaches 50 ([profile › station_status](../../spikes/d005-data-model/profile/bicing/station_status.csv), 2026-10-14 to 2026-10-26).
  - `is_renting` and `is_returning` follow their GBFS meaning: false only while a station is out of service, about 5 stations per pass and 121 in all, and the two never disagree ([d005 › D7](../designs/d005-data-model.md#d7-station-status-flags), 2026-10-14 to 2026-10-26).
  - `is_renting` alone also marks a suspension of rentals: from 2026-10-03T18:14Z to 10-04T09:49Z it was false at 90–99% of stations while `is_returning` stayed true, and stations reopened gradually until 10-04T18:27Z; it matches the torrential rain episode in Catalonia of 3 and 4 October ([AEMET](https://aemetblog.es/2026/10/21/analisis-del-episodio-de-lluvias-torrenciales-en-cataluna-del-3-y-4-de-octubre-de-2026/)). Outside it, about 5 stations per pass were out of service, as later ([s002 › 8f, 8j](../spikes/s002-bicing-realtime-capture.md#8-quality), 2026-11-12).
  - `is_installed` is false at 1 station ([s002 › 8f](../spikes/s002-bicing-realtime-capture.md#8-quality), 2026-10-05).
- **Change:** content changes every 60 s; 14.7 MB per day as gzip ([s002 › 3a, 7b](../spikes/s002-bicing-realtime-capture.md#3-freshness), 2026-10-04).
- **Quality:**
  - Consistency: the per-type counts do not add up to `num_vehicles_available` in 2.7% of station items, at 521 stations ([s002 › 8c](../spikes/s002-bicing-realtime-capture.md#8-quality), 2026-10-05).
  - Consistency: available + disabled vehicles and docks exceed `capacity` in 5% of station items, at 52 stations ([s002 › 8a](../spikes/s002-bicing-realtime-capture.md#8-quality), 2026-10-05).
  - Consistency: a new station can appear in `station_status` before `station_information` (station `309`, in 11 status responses) ([s002 › 6b](../spikes/s002-bicing-realtime-capture.md#6-identity), 2026-10-05).
  - Timeliness: 15 installed stations had not reported for more than 24 h in every response ([s002 › 8d](../spikes/s002-bicing-realtime-capture.md#8-quality), 2026-10-05); the oldest `last_reported` is still 2025-06-12 ([profile › station_status](../../spikes/d005-data-model/profile/bicing/station_status.csv), 2026-10-14 to 2026-10-26).

### `station_information`

- **Content:** station name, coordinates, address, post code and capacity; 543 stations ([s002 › 6a](../spikes/s002-bicing-realtime-capture.md#6-identity), 2026-10-05).
- **Fields:**
  - `name` and `short_name` are localised in 5 languages ([s002 › 1d](../spikes/s002-bicing-realtime-capture.md#1-schema), 2026-10-05), always with the same text in all 5; 7 stations have a `name` with leading or trailing spaces ([`names_check.py`](../../spikes/d005-data-model/station-names/names_check.py), 2026-10-14 to 2026-10-26).
  - `capacity` equals the `count` of the single `vehicle_docks_capacity` group and can change: 13 changes in two days, and station `77` went from 24 to 0 ([s002 › 6c, 8a](../spikes/s002-bicing-realtime-capture.md#6-identity), 2026-10-05).
  - `cross_street` holds the district and neighbourhood, not a street, with the City Council's two-digit codes, e.g. `01-CiutatVella/01-el Raval` ([profile › station_information](../../spikes/d005-data-model/profile/bicing/station_information.csv), 2026-10-14 to 2026-10-26).
  - `is_charging_station` is always true, `is_virtual_station` always false, and `rental_methods` always `key`, `transitcard`, `creditcard` and `phone` ([profile › station_information](../../spikes/d005-data-model/profile/bicing/station_information.csv), 2026-10-14 to 2026-10-26).
  - `rental_uris` is always an empty object and `vehicle_types_capacity` an empty list ([profile › station_information](../../spikes/d005-data-model/profile/bicing/station_information.csv), [`keys_check.py`](../../spikes/d005-data-model/profile/keys_check.py), 2026-10-14 to 2026-10-26).
- **Change:** 68 changes in 12.5 days (see Service); 4.4 MB per day as gzip ([s002 › 7b](../spikes/s002-bicing-realtime-capture.md#7-volume), 2026-10-04).
- **Quality:**
  - Validity: `external_id` is not a GBFS 3.0 field ([s002 › 2a](../spikes/s002-bicing-realtime-capture.md#2-common-model), 2026-10-05).
  - Validity: `post_code` comes both with and without its leading zero (`08001`, `8001`) ([profile › station_information](../../spikes/d005-data-model/profile/bicing/station_information.csv), 2026-10-14 to 2026-10-26).
  - Completeness: `post_code` is missing in 0.37% of station items ([profile › station_information](../../spikes/d005-data-model/profile/bicing/station_information.csv), 2026-10-14 to 2026-10-26).
  - Validity: in 7 of 541 stations, `cross_street` pairs a neighbourhood with a district it does not belong to, e.g. `01/67`, where neighbourhood 67 is in district 10 ([neighbourhood.csv](../../spikes/d005-data-model/neighbourhood/neighbourhood.csv), stations of 2026-10-26, City Council boundaries of 2024-11-12).
  - Accuracy: the neighbourhood in `cross_street` is the one that contains the station in 522 of 541 stations; the other 19 name a neighbouring one, 0 to 82 m from the boundary, most on streets that form it, such as Gran Via or Paral·lel ([neighbourhood.csv](../../spikes/d005-data-model/neighbourhood/neighbourhood.csv), stations of 2026-10-26, City Council boundaries of 2024-11-12).
  - Validity: some `name` and `address` values start with a space ([profile › station_information](../../spikes/d005-data-model/profile/bicing/station_information.csv), 2026-10-14 to 2026-10-26).

### `vehicle_types`

- **Content:** 11 type IDs over the window, 9 or 10 per response: bicycles, a standing scooter (`CHLOE`) and a trailer (`TRAILER`), with 3 values of `form_factor` and 3 of `propulsion_type` ([profile › vehicle_types](../../spikes/d005-data-model/profile/bicing/vehicle_types.csv), 2026-10-14 to 2026-10-26); `METRO` became `METRO_BASE` on 2026-10-22 ([`vehicle_types_check.py`](../../spikes/d005-data-model/vehicle-types/vehicle_types_check.py)).
- **Fields:**
  - `max_range_meters` ranges from 0 to 70,000, and is 0 for most types ([profile › vehicle_types](../../spikes/d005-data-model/profile/bicing/vehicle_types.csv), 2026-10-14 to 2026-10-26).
- **Quality:**
  - Validity: `default_pricing_plan_id` is sometimes an empty string ([s002 › 2a](../spikes/s002-bicing-realtime-capture.md#2-common-model), 2026-10-05).
  - Completeness: `pricing_plan_ids` is missing in 14.89% of type items ([profile › vehicle_types](../../spikes/d005-data-model/profile/bicing/vehicle_types.csv), 2026-10-14 to 2026-10-26).

### `system_information`

- **Content:** `system_id` `bike_barcelona`, timezone `Europe/Madrid`, and the provider's contact.

### `system_pricing_plans`

- **Content:** prices.
- **Change:** 0.1 MB per day as gzip ([s002 › 7a](../spikes/s002-bicing-realtime-capture.md#7-volume), 2026-10-04).

### `system_regions`

- **Content:** empty: no region in any response ([`keys_check.py`](../../spikes/d005-data-model/profile/keys_check.py), 2026-10-14 to 2026-10-26).

### `geofencing_zones`

- **Content:** essentially empty, 152 B ([s002 › 7a](../spikes/s002-bicing-realtime-capture.md#7-volume), 2026-10-05).

## Open questions

- Whether the monthly archives are dumps of this feed, and whether they keep the GBFS 2.x fields (`num_bikes_available`, `num_bikes_available_types` with `mechanical` and `ebike`, `is_charging_station`, `status`) (T005).
- Content and schema changes inside the archives, 2019–2026 (T005).
- Whether the suspected wrong uploads are really wrong (T005).
