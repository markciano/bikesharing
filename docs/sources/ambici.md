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

## General facts

Facts that hold for the whole source, not for one feed: how it publishes its data and how the system runs.

- **Stable schema:** every key path appears in every file of `station_status`, `station_information`, `vehicle_types` and `system_regions` ([`keys_check.py`](../../spikes/d005-data-model/profile/keys_check.py), 2026-10-14 to 2026-10-26).
- **Snapshots, not events:** no trips are published; rentals, returns and rebalancing are inferred from changes between consecutive snapshots ([s001 › 3a](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
- **`ttl` does not reflect changes:** the static feeds keep their declared `ttl` however often they change ([d004 › D3](../designs/d004-bronze-data-capture.md#d3-feed-cadence), [spike-log-queries.sql › 6](../../spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql), 2026-11-05).
- **Static feeds rarely change:** over 12.5 days of hourly captures, `station_information` changed 4 times and the other static feeds never did ([d004 › D3](../designs/d004-bronze-data-capture.md#d3-feed-cadence), [spike-log-queries.sql › 6](../../spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql), 2026-10-14 to 2026-10-26).
- **`last_updated`:** when the server generated the file; at most 64 s old at request time, median 31 s ([s001 › 3c](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
- **Timeliness:** `last_updated` occasionally steps back by 1–3 s, 12 times in two days across `station_status` and `free_bike_status` ([s001 › 3c](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
- **Stable index:** the `gbfs` index was 3,124 B in every hourly read ([d004 › D5](../designs/d004-bronze-data-capture.md#d5-hourly-index-refresh), [spike-log-queries.sql › 5](../../spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql), 2026-10-14 to 2026-11-05).
- **Latency shifts:** median response latency moved from about 760 ms to 39 ms on 2026-10-29 and to about 317 ms on 2026-11-03, with no change on the capture side ([d004 › D4](../designs/d004-bronze-data-capture.md#d4-static-feeds-spread-across-passes), [spike-log-queries.sql › 5](../../spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql), 2026-11-05).
- **Volume:** about 75 MB per day as gzip, with static feeds every 15 min; `free_bike_status` is 94% of it ([s001 › 7b](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-04).
- **Frame lock:** each bike has a lock on its rear wheel. It pauses a rental anywhere, and ends one outside the docks only at a +P station with no free dock; a return at a dock needs both the dock and the lock ([AMBici FAQ](https://www.ambici.cat/ca/faq/), undated, read 2026-11-13).
- **Reservations:** the app reserves a bike at a given station up to 10 min before picking it up (AMBici app, 2026-11-13).

## Feeds

One section per feed: what it holds, how often it changes and its quality issues; a feed the data model reads adds its field dictionary.

### `station_status`

- **Content:** bikes and free docks per station, the status flags and `last_reported`.
- **Change:** content changes every 60 s; 3.3 MB per day as gzip ([s001 › 3a, 7b](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-04).
- **Quality:**
  - Consistency: available bikes + available docks exceed `capacity` in 3% of station items, at 43 stations ([s001 › 8a](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
  - Consistency: `num_bikes_available` exceeds `capacity` at 141 of 237 stations, at some for more than half the passes, and reaches 70 at station `135340017` (capacity 24); at each station's peak there are no free docks. It happens at 51 of the 57 stations with +P ([`nextbike-live.json`](#nextbike-livejson)), and at 90 of the 180 without, less often: a median of 886 and 1,978 passes over at the two +P place types, against 258 and 310 at the others ([over_capacity.csv](../../spikes/d005-data-model/over-capacity/over_capacity.csv), 2026-10-14 to 2026-10-26; [plus_p.csv](../../spikes/d005-data-model/plus-p/plus_p.csv), 2026-11-12).
  - Accuracy: `capacity` matches the docks on Google Street View at 5 stations without +P that exceed it (Bellamar, Montmar, Riera de Sant Llorenç - Can Guardiola, Plaça de la Vila - Av. de Catalunya, Podium - Torre-roja; imagery of July 2024 to March 2026), so a stale `capacity` does not explain the excess (checked 2026-11-13).

#### Field dictionary

Every field of `station_status` as AMBici publishes it: its meaning, its definition in GBFS 2.3 and the values profiled from 2026-10-14 to 2026-10-26.

| Field | Description | Type | Required | Unit or format | Domain | Observed | Example | Notes |
|---|---|---|---|---|---|---|---|---|
| `last_updated` | [When the server generated the file][gbfs-output] | integer | required | POSIX time | — | No nulls | `1794011276` | Timeliness: steps back by 1–3 s at times (see [General facts](#general-facts)) |
| `ttl` | [Declared seconds until the file is refreshed][gbfs-output] | integer | required | seconds | — | Always 60 | `60` | — |
| `version` | [GBFS version of the file][gbfs-output] | string | required | — | — | Always `2.3` | `2.3` | — |
| `data.stations[].station_id` | [The station's identifier, the same as in `station_information`][gbfs-ss] | string | required | — | — | No nulls; ≈238 distinct | `189004148` | — |
| `data.stations[].num_bikes_available` | [Bikes available for rental at the station, at its docks or in its +P spaces][gbfs-ss] | integer | required | bikes | — | 0 to 70, median 8 | `7` | Consistency: exceeds `capacity` (see Quality and Field notes) |
| `data.stations[].vehicle_types_available` | [Available bikes by vehicle type][gbfs-ss] | array | conditionally required: when `vehicle_types` is published | — | — | Never null; empty at times | `[{"vehicle_type_id": "204", "count": 7}]` | See Field notes |
| `data.stations[].vehicle_types_available[].vehicle_type_id` | [The vehicle type, by its ID in `vehicle_types`][gbfs-ss] | string | conditionally required: as its array | — | — | `196`, `204`; `420` never appears | `204` | — |
| `data.stations[].vehicle_types_available[].count` | [Available bikes of that type][gbfs-ss] | integer | conditionally required: as its array | bikes | — | 1 to 70, median 8; never 0 | `7` | — |
| `data.stations[].num_docks_available` | [Free docks at the station][gbfs-ss] | integer | conditionally required: except at a station with unlimited docks | docks | — | 0 to 28, median 11 | `13` | — |
| `data.stations[].is_installed` | [Whether the station is installed on the street][gbfs-ss] | boolean | required | — | — | Always true | `true` | — |
| `data.stations[].is_renting` | [Whether the station lets bikes be rented][gbfs-ss] | boolean | required | — | — | True and false | `true` | See Field notes |
| `data.stations[].is_returning` | [Whether the station accepts returned bikes][gbfs-ss] | boolean | required | — | — | True and false | `true` | See Field notes |
| `data.stations[].last_reported` | [The file's time, not the station's last report][gbfs-ss] | integer | required | POSIX time | — | No nulls; the range of `last_updated` | `1794011276` | Differs from GBFS: the file's time, where GBFS has the station's last report to the operator's backend (see Field notes) |

- **Field notes:**
  - `num_bikes_available` also counts bikes parked outside the docks in +P spaces: when all docks are taken, a bike may be left in the orange-marked +P spaces, and only there, so it can exceed `capacity`. +P had 280 places at 14 stations in July 2024 ([AMB](https://www.amb.cat/es/web/amb/actualitat/sala-de-premsa/notes-de-premsa/detall/-/notapremsa/entren-en-funcionament-280-aparcaments--p-a-les-estacions-d-ambici-per/18364152/11696), 2024-07-10) and 1,146 places at 57 stations later ([AMBici FAQ](https://www.ambici.cat/es/faq/), undated, read 2026-11-12). The feed does not say which bikes are in +P.
  - `vehicle_types_available` omits types with count 0, and the list is empty when a station has no bikes ([s001 › 8c](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05; [profile › station_status_vehicle_types](../../spikes/d005-data-model/profile/ambici/station_status_vehicle_types.csv), 2026-10-14 to 2026-10-26).
  - `vehicle_type_id`: `204` (e-bike) has almost all the activity, `196` (classic) little ([s001 › 4a](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
  - `is_renting` and `is_returning` are false at 8 stations in every response, while they hold bikes; an empty station keeps `is_renting` true ([s001 › 8f, 8j](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
  - `last_reported` is the feed time, not the time of a station's last change: it equals the file's `last_updated` for 99.92% of station items, so changes are detected by comparing content ([s001 › 3b](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
- **Evidence:** [profile › station_status](../../spikes/d005-data-model/profile/ambici/station_status.csv) and [station_status_vehicle_types](../../spikes/d005-data-model/profile/ambici/station_status_vehicle_types.csv), 4,233,604 station items from [profile.sql](../../spikes/d005-data-model/profile/ambici/profile.sql), 2026-10-14 to 2026-10-26; examples from the capture fixture [station_status.json](../../capture/test/fixtures/ambici/station_status.json), 2026-11-07.

### `station_information`

- **Content:** station name, coordinates, capacity and region; 237 stations ([s001 › 6a](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05).
- **Change:** 4 changes in 12.5 days (see [General facts](#general-facts)); 1.0 MB per day as gzip ([s001 › 7b](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-04).

#### Field dictionary

Every field of `station_information` as AMBici publishes it: its meaning, its definition in GBFS 2.3 and the values profiled from 2026-10-14 to 2026-10-26.

| Field | Description | Type | Required | Unit or format | Domain | Observed | Example | Notes |
|---|---|---|---|---|---|---|---|---|
| `last_updated` | [When the server generated the file][gbfs-output] | integer | required | POSIX time | — | No nulls | `1794011276` | — |
| `ttl` | [Declared seconds until the file is refreshed][gbfs-output] | integer | required | seconds | — | Always 60 | `60` | — |
| `version` | [GBFS version of the file][gbfs-output] | string | required | — | — | Always `2.3` | `2.3` | — |
| `data.stations[].station_id` | [The station's identifier][gbfs-si] | string | required | — | — | No nulls; ≈238 distinct | `189004148` | — |
| `data.stations[].name` | [The station's public name][gbfs-si] | string | required | — | — | No nulls; ≈241 distinct | `AMB - METRO La Pau` | Validity: at least one name starts with a space, `" FGC Cornellà - Riera"` |
| `data.stations[].short_name` | [A five-digit station code][gbfs-si] | string | optional | — | — | `34701` to `34948`, ≈239 distinct | `34872` | — |
| `data.stations[].lat` | [The station's latitude][gbfs-si] | number | required | WGS 84 degrees | — | 41.265438 to 41.482205 | `41.423345` | — |
| `data.stations[].lon` | [The station's longitude][gbfs-si] | number | required | WGS 84 degrees | — | 1.943849 to 2.267271 | `2.205672` | — |
| `data.stations[].region_id` | [The station's region, by its ID in `system_regions`][gbfs-si] | string | optional | — | — | `833` to `856`, 16 distinct | `833` | Accuracy: see [`system_regions`](#system_regions) |
| `data.stations[].rental_uris.android` | [Link to the station in the Android app][gbfs-si] | string | optional | URI | — | No nulls | `https://ambici.nextbike.app/station?id=189004148` | — |
| `data.stations[].rental_uris.ios` | [Link to the station in the iOS app][gbfs-si] | string | optional | URI | — | No nulls | `https://ambici.nextbike.app/station?id=189004148` | — |
| `data.stations[].rental_uris.web` | [Short web link to the station][gbfs-si] | string | optional | URL | — | No nulls | `https://nxtb.it/p/189004148` | — |
| `data.stations[].is_virtual_station` | [Whether the station has no physical docks][gbfs-si] | boolean | optional | — | — | Always false | `false` | — |
| `data.stations[].capacity` | [Docks at the station, not counting its +P spaces][gbfs-si] | integer | optional | docks | — | 12 to 28, median 20 | `20` | Accuracy: available bikes exceed it, though it matches the docks seen on the street (see [`station_status`](#station_status) › Quality) |

- **Evidence:** [profile › station_information](../../spikes/d005-data-model/profile/ambici/station_information.csv), 71,291 station items from [profile.sql](../../spikes/d005-data-model/profile/ambici/profile.sql), 2026-10-14 to 2026-10-26; examples from the capture fixture [station_information.json](../../capture/test/fixtures/ambici/station_information.json), 2026-11-07.

### `vehicle_types`

- **Content:** 3 bike types, all `form_factor` `bicycle` with `rider_capacity` 1: `196` "Classic Bike" (`human`), and `204` and `420`, both "E-Bike" (`electric_assist`) ([profile › vehicle_types](../../spikes/d005-data-model/profile/ambici/vehicle_types.csv), 2026-10-14 to 2026-10-26; per type, [vehicle_types.json](../../capture/test/fixtures/ambici/vehicle_types.json), 2026-11-07).

#### Field dictionary

Every field of `vehicle_types` as AMBici publishes it: its meaning, its definition in GBFS 2.3 and the values profiled from 2026-10-14 to 2026-10-26.

| Field | Description | Type | Required | Unit or format | Domain | Observed | Example | Notes |
|---|---|---|---|---|---|---|---|---|
| `last_updated` | [When the server generated the file][gbfs-output] | integer | required | POSIX time | — | No nulls | `1794011276` | — |
| `ttl` | [Declared seconds until the file is refreshed][gbfs-output] | integer | required | seconds | — | Always 60 | `60` | — |
| `version` | [GBFS version of the file][gbfs-output] | string | required | — | — | Always `2.3` | `2.3` | — |
| `data.vehicle_types[].vehicle_type_id` | [The type's identifier, the one `station_status` cites][gbfs-vt] | string | required | — | — | `196`, `204`, `420` | `204` | — |
| `data.vehicle_types[].vehicle_image` | [Link to a picture of the type][gbfs-vt] | string | optional | URL | — | One per type | `https://static.nextbike.net/app/biketypes-v5/type/bs/196/h500.png` | — |
| `data.vehicle_types[].name` | [The type's name, in the feed's language][gbfs-vt] | string | optional | — | — | `Classic Bike` (`196`); `E-Bike` (`204`, `420`) | `E-Bike` | Per type: [vehicle_types.json](../../capture/test/fixtures/ambici/vehicle_types.json), 2026-11-07 |
| `data.vehicle_types[]._description` | [A free-text list of the bike's components][gbfs-ext] | string | — | — | — | One per type | `SMARTbike 2.0 with labeling` (first line) | An extension outside GBFS, named with the leading underscore GBFS asks of extensions ([s001 › 10b](../spikes/s001-ambici-realtime-capture.md#capture-findings), 2026-10-05) |
| `data.vehicle_types[].form_factor` | [The vehicle's form][gbfs-vt] | string | required | — | `bicycle`, `cargo_bicycle`, `car`, `moped`, `scooter`, `scooter_standing`, `scooter_seated`, `other` | Always `bicycle` | `bicycle` | — |
| `data.vehicle_types[].rider_capacity` | [Riders the vehicle carries][gbfs-vt] | integer | optional | persons | — | Always 1 | `1` | — |
| `data.vehicle_types[].propulsion_type` | [How the vehicle is propelled][gbfs-vt] | string | required | — | `human`, `electric_assist`, `electric`, `combustion`, `combustion_diesel`, `hybrid`, `plug_in_hybrid`, `hydrogen_fuel_cell` | `human` (`196`); `electric_assist` (`204`, `420`) | `electric_assist` | Per type: [vehicle_types.json](../../capture/test/fixtures/ambici/vehicle_types.json), 2026-11-07 |
| `data.vehicle_types[].max_range_meters` | [Distance a fully charged bike can travel][gbfs-vt] | integer | conditionally required: when `propulsion_type` is not `human` | metres | — | 60,000 for `204` and `420`; absent for `196` | `60000` | Per type: [vehicle_types.json](../../capture/test/fixtures/ambici/vehicle_types.json), 2026-11-07 |

- **Evidence:** [profile › vehicle_types](../../spikes/d005-data-model/profile/ambici/vehicle_types.csv), 903 type items from [profile.sql](../../spikes/d005-data-model/profile/ambici/profile.sql), 2026-10-14 to 2026-10-26; examples from the capture fixture [vehicle_types.json](../../capture/test/fixtures/ambici/vehicle_types.json), 2026-11-07.

### `system_regions`

- **Content:** 16 regions, IDs 833–856, named after municipalities except "AMB" ([profile › system_regions](../../spikes/d005-data-model/profile/ambici/system_regions.csv), 2026-10-14 to 2026-10-26).
  - "AMB" holds the 10 stations in or at the edge of Barcelona: 8 inside it, 150 to 1,067 m from its boundary, at university campuses, metro stations and a shopping centre; 1 in Sant Adrià de Besòs, 37 m from it, and 1 in L'Hospitalet de Llobregat, 8 m from it ([municipality.csv](../../spikes/d005-data-model/municipality/municipality.csv), stations of 2026-10-26, ICGC boundaries v2r2).
  - Region names drop the leading article ICGC's municipality names keep, e.g. "Hospitalet de Llobregat" ([municipality.csv](../../spikes/d005-data-model/municipality/municipality.csv), 2026-10-26).
- **Quality:**
  - Accuracy: the region of 226 of the 227 stations outside "AMB" is the municipality that contains them; the exception, `135349994` (TRAM Sant Feliu - Consell Comarcal, region Sant Feliu de Llobregat), falls in Sant Just Desvern, 4 m from the boundary ([municipality.csv](../../spikes/d005-data-model/municipality/municipality.csv), stations of 2026-10-26, ICGC boundaries v2r2).

#### Field dictionary

Every field of `system_regions` as AMBici publishes it: its meaning, its definition in GBFS 2.3 and the values profiled from 2026-10-14 to 2026-10-26.

| Field | Description | Type | Required | Unit or format | Domain | Observed | Example | Notes |
|---|---|---|---|---|---|---|---|---|
| `last_updated` | [When the server generated the file][gbfs-output] | integer | required | POSIX time | — | No nulls | `1794011276` | — |
| `ttl` | [Declared seconds until the file is refreshed][gbfs-output] | integer | required | seconds | — | Always 60 | `60` | — |
| `version` | [GBFS version of the file][gbfs-output] | string | required | — | — | Always `2.3` | `2.3` | — |
| `data.regions[].region_id` | [The region's identifier, the one `station_information` cites][gbfs-sr] | string | required | — | — | `833` to `856`, 16 distinct | `833` | — |
| `data.regions[].name` | [The region's name: a municipality, or `AMB`][gbfs-sr] | string | required | — | — | 16 distinct, `AMB` to `Viladecans` | `Badalona` | See Content |

- **Evidence:** [profile › system_regions](../../spikes/d005-data-model/profile/ambici/system_regions.csv), 4,816 region items from [profile.sql](../../spikes/d005-data-model/profile/ambici/profile.sql), 2026-10-14 to 2026-10-26; examples from the capture fixture [system_regions.json](../../capture/test/fixtures/ambici/system_regions.json), 2026-11-07.

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
- **Change:** changed twice from 2026-10-03 to 10-05 ([s001 › 3a](../spikes/s001-ambici-realtime-capture.md#capture-findings)), and never from 2026-10-14 to 10-26 (see [General facts](#general-facts)).

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
- Whether a reserved bike still counts in `num_bikes_available`: `station_status` has no count of reserved bikes, and only `free_bike_status` flags `is_reserved`, per bike.

[gbfs-output]: https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md#output-format
[gbfs-ss]: https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md#station_statusjson
[gbfs-si]: https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md#station_informationjson
[gbfs-vt]: https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md#vehicle_typesjson
[gbfs-sr]: https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md#system_regionsjson
[gbfs-ext]: https://github.com/MobilityData/gbfs/blob/v2.3/gbfs.md#extensions-outside-of-the-specification
