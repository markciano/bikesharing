# Source card — AMBici (GBFS)

Facts about this data source. Living document: update it when something new is confirmed.
Facts confirmed or corrected by the realtime capture spike (T006, 2026-10-03 to 2026-10-05); evidence in [ambici-realtime-capture.md](../spikes/s001-ambici-realtime-capture.md) › Findings.

## Identity

| | |
|---|---|
| System | AMBici — public e-bike sharing of the Àrea Metropolitana de Barcelona (AMB) |
| Coverage | Metropolitan municipalities around Barcelona (not the city itself) |
| Operator | TIER Mobility SE (nextbike platform) |
| Standard | GBFS 2.3 only: no `gbfs_versions` feed, no 3.0 endpoint found (checked 2026-10-05) |
| Licence | CC0-1.0 (no attribution required) |
| Access | Public, no token |
| Index | `https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_bs/gbfs.json` |
| Languages | `en`, `ca`, `es`: same structure; only vehicle type names and descriptions differ, and `ca` is identical to `es` (Spanish). One language (`en`) is enough |
| Refresh | `ttl: 60` s; measured content change every 60 s in the dynamic feeds |

## Feeds

| Feed | Content | Change rate (measured) | Size per day (gzip) |
|---|---|---|---|
| `station_status` | Bikes and free docks per station; renting/returning flags; `last_reported` | Every 60 s | 3.3 MB |
| `free_bike_status` | One record per bike: station, battery %, range | Every 60 s | 70.8 MB |
| `station_information` | Station name, coordinates, capacity, region | No change in 2 days | 1.0 MB |
| `system_information` | Operator, timezone, licence, contact | No change in 2 days | < 0.1 MB |
| `vehicle_types` | Bike types | No change in 2 days | < 0.1 MB |
| `system_regions` | Regions (municipalities) | No change in 2 days | < 0.1 MB |
| `system_hours` | Service hours | Changed twice in 2 days | < 0.1 MB |
| `system_pricing_plans` | Prices | No change in 2 days | < 0.1 MB |
| `geofencing_zones` | Polygons where riding/parking is allowed | No change in 2 days | < 0.1 MB |

Total about 75 MB per day compressed (4 October 2026, static feeds every 15 min); `free_bike_status` is 94 % of it.

## Known characteristics

- **Snapshots, not events.** No trips are published. Rentals, returns and rebalancing must be inferred from changes between consecutive snapshots.
- **Bike IDs rotate.** GBFS 2.x rotates `bike_id` after each trip for privacy; consistent with the capture (12,065 distinct IDs in two days, about 2,100 bikes per response). Individual bikes cannot be followed across trips: analysis is per station.
- **`last_reported` is the feed time.** `last_updated` is when the server generated the file. In AMBici, `last_reported` equals the file's `last_updated` for 99.92 % of station items, so it is not the time of a station's last change. Changes must be detected by comparing content.
- **Not strictly monotonic.** `last_updated` occasionally steps back by 1–3 s (12 times in two days).
- **No public history.** Only the real-time GBFS feed exists. See `docs/spikes/s003-ambici-historical-data.md`.
- **Size:** 237 stations, capacities 12–28 docks, 16 regions (IDs 833–856); about 2,100 bikes. Vehicle types `204` (e-bike) and `196` (classic) are in use, `204` with almost all the activity; `420` is defined but never seen in `station_status`.
- **All bikes are docked.** Every bike in `free_bike_status` has a `station_id`.
- **Field mapping to GBFS 3.0:** see [bicing-realtime-capture.md](../spikes/s002-bicing-realtime-capture.md) › Findings 2a.

## Data quality notes

- `system_information.timezone` is `Europe/Berlin` although the system operates in Barcelona (same UTC offset, semantically wrong); in every response.
- Some bikes have no `current_fuel_percent` while reporting `current_range_meters: 0` (466 distinct bikes, in every response).
- `current_fuel_percent` comes as an integer or a decimal number.
- `vehicle_types_available` omits types with count 0; the list is empty when a station has no bikes.
- Available bikes + available docks exceed `capacity` in 3 % of station items (43 stations).
- 8 stations have `is_renting` and `is_returning` false in every response while holding bikes. An empty station is not flagged as not renting.
- `vehicle_types` carries a non-standard `_description` field.
- The stale `last_updated` (hours or days old) seen in one early read was not reproduced: during the capture it was at most 64 s old.

## Open questions

- Whether nextbike publishes other cities with the same structure.
