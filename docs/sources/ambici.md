# Source card — AMBici (GBFS)

Facts about the AMBici data source, confirmed against captured data.

## Source

| | |
|---|---|
| System | AMBici — public e-bike sharing of the Àrea Metropolitana de Barcelona (AMB) |
| Coverage | Metropolitan municipalities around Barcelona (not the city itself) |
| Operator | TIER Mobility SE (nextbike platform) |
| Standard | GBFS 2.3 only: no `gbfs_versions` feed, no 3.0 endpoint found ([s001 › 1c](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05) |
| Licence | CC0-1.0 (no attribution required) |

## Access

### Real time

| | |
|---|---|
| Index | `https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_bs/gbfs.json` |
| Format | JSON, GBFS 2.3 |
| Auth | Public, no token |
| Languages | `en`, `ca`, `es`: same structure; only vehicle type names and descriptions differ, and `ca` is identical to `es` (Spanish). One language (`en`) is enough ([s001 › 10](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05) |
| Declared refresh | `ttl` 60 s on every feed, 86,400 s on `geofencing_zones` and `system_pricing_plans` |

### nextbike live

| | |
|---|---|
| Endpoint | `https://maps.nextbike.net/maps/nextbike-live.json?domains=bs`, the data behind the map at `https://www.ambici.cat/ca/mapa/` |
| Format | JSON, nextbike's own schema, not GBFS: country → cities (one per municipality) → places (stations) → bikes |
| Auth | Public, no token |
| Licence | Not stated in the feed |

### History

None published: only the real-time feed exists ([s003](../spikes/s003-ambici-historical-data.md)).

## Facts

### Service

- **Stable schema:** every key path appears in every file of `station_status`, `station_information`, `vehicle_types` and `system_regions` ([`keys_check.py`](../../spikes/d005-data-model/profile/keys_check.py), 2026-10-14 to 2026-10-26).
- **Snapshots, not events:** no trips are published; rentals, returns and rebalancing are inferred from changes between consecutive snapshots ([s001 › 3a](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
- **`ttl` does not reflect changes:** the static feeds keep their declared `ttl` however often they change ([d004 › D3](../designs/d004-bronze-data-capture.md#d3-feed-cadence), [spike-log-queries.sql › 6](../../spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql), 2026-11-05).
- **Static feeds rarely change:** over 12.5 days of hourly captures, `station_information` changed 4 times and the other static feeds never did ([d004 › D3](../designs/d004-bronze-data-capture.md#d3-feed-cadence), [spike-log-queries.sql › 6](../../spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql), 2026-10-14 to 2026-10-26).
- **`last_updated`:** when the server generated the file; at most 64 s old at request time, median 31 s ([s001 › 3c](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
- **Timeliness:** `last_updated` occasionally steps back by 1–3 s, 12 times in two days across `station_status` and `free_bike_status` ([s001 › 3c](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
- **Stable index:** the `gbfs` index was 3,124 B in every hourly read ([d004 › D5](../designs/d004-bronze-data-capture.md#d5-hourly-index-refresh), [spike-log-queries.sql › 5](../../spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql), 2026-10-14 to 2026-11-05).
- **Latency shifts:** median response latency moved from about 760 ms to 39 ms on 2026-10-29 and to about 317 ms on 2026-11-03, with no change on the capture side ([d004 › D4](../designs/d004-bronze-data-capture.md#d4-static-feeds-spread-across-passes), [spike-log-queries.sql › 5](../../spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql), 2026-11-05).
- **Volume:** about 75 MB per day as gzip, with static feeds every 15 min; `free_bike_status` is 94% of it ([s001 › 7b](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-04).

### `station_status`

- **Content:** bikes and free docks per station, the status flags and `last_reported`.
- **Fields:**
  - No field has nulls, and `is_installed` is always true ([profile › station_status](../../spikes/d005-data-model/profile/ambici/station_status.csv), 2026-10-14 to 2026-10-26).
  - `last_reported` is the feed time, not the time of a station's last change: it equals the file's `last_updated` for 99.92% of station items, so changes are detected by comparing content ([s001 › 3b](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
  - `vehicle_types_available` omits types with count 0, and the list is empty when a station has no bikes ([s001 › 8c](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05; [profile › station_status_vehicle_types](../../spikes/d005-data-model/profile/ambici/station_status_vehicle_types.csv), 2026-10-14 to 2026-10-26).
  - `num_bikes_available` also counts bikes parked outside the docks in +P spaces: when all docks are taken, a bike may be left in the orange-marked +P spaces, and only there, so it can exceed `capacity`. +P had 280 places at 14 stations in July 2024 ([AMB](https://www.amb.cat/es/web/amb/actualitat/sala-de-premsa/notes-de-premsa/detall/-/notapremsa/entren-en-funcionament-280-aparcaments--p-a-les-estacions-d-ambici-per/18364152/11696), 2024-07-10) and 1,146 places at 57 stations later ([AMBici FAQ](https://www.ambici.cat/es/faq/), undated, read 2026-11-12). The feed does not say which bikes are in +P.
  - Only vehicle types `204` (e-bike) and `196` (classic) appear; `420` never does ([profile › station_status_vehicle_types](../../spikes/d005-data-model/profile/ambici/station_status_vehicle_types.csv), 2026-10-14 to 2026-10-26). `204` has almost all the activity ([s001 › 4a](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
  - `is_renting` and `is_returning` are false at 8 stations in every response, while they hold bikes; an empty station keeps `is_renting` true ([s001 › 8f, 8j](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
- **Change:** content changes every 60 s; 3.3 MB per day as gzip ([s001 › 3a, 7b](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-04).
- **Quality:**
  - Consistency: available bikes + available docks exceed `capacity` in 3% of station items, at 43 stations ([s001 › 8a](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
  - Consistency: `num_bikes_available` exceeds `capacity` at 141 of 237 stations, at some for more than half the passes, and reaches 70 at station `135340017` (capacity 24); at each station's peak there are no free docks. It happens at 51 of the 57 stations with +P ([`nextbike-live.json`](#nextbike-livejson)), and at 90 of the 180 without, less often: a median of 886 and 1,978 passes over at the two +P place types, against 258 and 310 at the others ([over_capacity.csv](../../spikes/d005-data-model/over-capacity/over_capacity.csv), 2026-10-14 to 2026-10-26; [plus_p.csv](../../spikes/d005-data-model/plus-p/plus_p.csv), 2026-11-12).

### `station_information`

- **Content:** station name, coordinates, capacity and region; 237 stations ([s001 › 6a](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
- **Fields:**
  - No field has nulls; `capacity` ranges from 12 to 28 docks, `region_id` from 833 to 856, and `is_virtual_station` is always false ([profile › station_information](../../spikes/d005-data-model/profile/ambici/station_information.csv), 2026-10-14 to 2026-10-26).
- **Change:** 4 changes in 12.5 days (see Service); 1.0 MB per day as gzip ([s001 › 7b](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-04).

### `vehicle_types`

- **Content:** 3 bike types, all `form_factor` `bicycle` with `rider_capacity` 1: `196` "Classic Bike" (`human`), and `204` and `420`, both "E-Bike" (`electric_assist`) ([profile › vehicle_types](../../spikes/d005-data-model/profile/ambici/vehicle_types.csv), 2026-10-14 to 2026-10-26).
- **Fields:**
  - `max_range_meters` is 60,000 for the electric types and absent for the human one ([profile › vehicle_types](../../spikes/d005-data-model/profile/ambici/vehicle_types.csv), 2026-10-14 to 2026-10-26; [s002 › 2a](../spikes/s002-bicing-realtime-capture.md#2-common-model)).
- **Quality:**
  - Validity: carries a non-standard `_description` field ([s001 › 10b](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).

### `system_regions`

- **Content:** 16 regions, IDs 833–856, named after municipalities except "AMB" ([profile › system_regions](../../spikes/d005-data-model/profile/ambici/system_regions.csv), 2026-10-14 to 2026-10-26).
  - "AMB" holds the 10 stations in or at the edge of Barcelona: 8 inside it, 150 to 1,067 m from its boundary, at university campuses, metro stations and a shopping centre; 1 in Sant Adrià de Besòs, 37 m from it, and 1 in L'Hospitalet de Llobregat, 8 m from it ([municipality.csv](../../spikes/d005-data-model/municipality/municipality.csv), stations of 2026-10-26, ICGC boundaries v2r2).
  - Region names drop the leading article ICGC's municipality names keep, e.g. "Hospitalet de Llobregat" ([municipality.csv](../../spikes/d005-data-model/municipality/municipality.csv), 2026-10-26).
- **Quality:**
  - Accuracy: the region of 226 of the 227 stations outside "AMB" is the municipality that contains them; the exception, `135349994` (TRAM Sant Feliu - Consell Comarcal, region Sant Feliu de Llobregat), falls in Sant Just Desvern, 4 m from the boundary ([municipality.csv](../../spikes/d005-data-model/municipality/municipality.csv), stations of 2026-10-26, ICGC boundaries v2r2).

### `free_bike_status`

- **Content:** one record per bike, with its station, battery and range; about 2,100 bikes per response, all docked: every bike has a `station_id` ([s001 › 9a, 9b](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
- **Fields:**
  - `bike_id` rotates after each trip, as GBFS 2.x requires for privacy: 12,065 distinct IDs in two days, so bikes cannot be followed across trips ([s001 › 9a](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
  - `current_fuel_percent` comes as an integer or a decimal number ([s001 › 1d](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
- **Change:** content changes every 60 s; 70.8 MB per day as gzip ([s001 › 3a, 7b](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-04); the largest response of both sources, up to 56,711 B as gzip ([d004 › D12](../designs/d004-bronze-data-capture.md#d12-capture-security), [spike-log-queries.sql › 5](../../spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql), 2026-11-05).
- **Quality:**
  - Completeness: 466 distinct bikes have no `current_fuel_percent` while reporting `current_range_meters: 0`, in every response ([s001 › 8i](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).

### `system_information`

- **Content:** operator, timezone, licence and contact.
- **Quality:**
  - Accuracy: `timezone` is `Europe/Berlin` although the system operates in Barcelona (same UTC offset), in every response ([s001 › 8i](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).

### `system_hours`

- **Content:** service hours.
- **Change:** changed twice from 2026-10-03 to 10-05 ([s001 › 3a](../spikes/s001-ambici-realtime-capture.md#capture-findings)), and never from 2026-10-14 to 10-26 (see Service).

### `system_pricing_plans`

- **Content:** prices.

### `geofencing_zones`

- **Content:** polygons where riding or parking is allowed; empty ([d005 › D3](../designs/d005-data-model.md#d3-feeds-that-enter-the-model)).

### `nextbike-live.json`

- **Content:** the same 237 stations as GBFS, with their bikes one by one ([fields.txt](../../spikes/d005-data-model/plus-p/fields.txt), 2026-11-12).
- **Fields:**
  - A place's `uid` is the GBFS `station_id`, with the same name, at all 237 stations ([plus_p.csv](../../spikes/d005-data-model/plus-p/plus_p.csv), 2026-11-12).
  - `place_type` 27 or 33 marks a station with +P parking, blue on the map; 14 and 16 are regular stations, red. 21 and 36 stations, 57 in all, as the [AMBici FAQ](https://www.ambici.cat/es/faq/) states; checked by eye on 4 stations of each type ([plus_p.csv](../../spikes/d005-data-model/plus-p/plus_p.csv), 2026-11-12).
  - `bike_racks` equals the GBFS `capacity` at every station, so it counts docks only; `special_racks` and `free_special_racks` are 0 everywhere, so no field gives a station's +P places ([fields.txt](../../spikes/d005-data-model/plus-p/fields.txt), [plus_p.csv](../../spikes/d005-data-model/plus-p/plus_p.csv), 2026-11-12).

## Open questions

- Whether nextbike publishes other cities with the same structure.
- Why available bikes exceed `capacity` at 90 stations without +P parking.
