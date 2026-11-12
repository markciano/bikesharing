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

### History

None published: only the real-time feed exists ([s003](../spikes/s003-ambici-historical-data.md)).

## Facts

### Service

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
  - `last_reported` is the feed time, not the time of a station's last change: it equals the file's `last_updated` for 99.92% of station items, so changes are detected by comparing content ([s001 › 3b](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
  - `vehicle_types_available` omits types with count 0, and the list is empty when a station has no bikes ([s001 › 8c](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
  - Vehicle types `204` (e-bike) and `196` (classic) appear, `204` with almost all the activity; `420` never appears ([s001 › 4a](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
  - `is_renting` and `is_returning` are false at 8 stations in every response, while they hold bikes; an empty station keeps `is_renting` true ([s001 › 8f, 8j](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
- **Change:** content changes every 60 s; 3.3 MB per day as gzip ([s001 › 3a, 7b](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-04).
- **Quality:**
  - Consistency: available bikes + available docks exceed `capacity` in 3% of station items, at 43 stations ([s001 › 8a](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).

### `station_information`

- **Content:** station name, coordinates, capacity and region; 237 stations ([s001 › 6a](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05), capacities 12–28 docks.
- **Change:** 4 changes in 12.5 days (see Service); 1.0 MB per day as gzip ([s001 › 7b](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-04).

### `vehicle_types`

- **Content:** 3 bike types: `196`, `204` and `420` ([s001 › 2c](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
- **Quality:**
  - Validity: carries a non-standard `_description` field ([s001 › 10b](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).

### `system_regions`

- **Content:** 16 regions (municipalities), IDs 833–856.

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

## Open questions

- Whether nextbike publishes other cities with the same structure.
