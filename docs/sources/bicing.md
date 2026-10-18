# Source card — Bicing

Facts about this data source. Living document: update it when something new is confirmed.
Reviewed on 2026-10-03 — both Open Data BCN datasets (via the CKAN API) and the operator's GBFS feed.
Real-time facts confirmed by the realtime capture spike (T006, 2026-10-03 to 2026-10-05); evidence in [bicing-realtime-capture.md](../spikes/s002-bicing-realtime-capture.md) › Findings.

## Identity

Bicing — public bike sharing of the city of Barcelona. Two access routes:

### Real time — operator GBFS feed

| | |
|---|---|
| Coverage | Barcelona city |
| Standard | GBFS 3.0; `gbfs_versions` also lists 1.1 (`…/ube/gbfs/v1/`) and 2.3 (`…/customer/gbfs/v2/`), the 2.3 endpoint not verified |
| Index | `https://barcelona.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json` |
| Access | Public, no token |
| `system_id` | `bike_barcelona` |
| Timezone | `Europe/Madrid` |
| Languages | `ca`, `en`, `fr`, `nl`, `es` |
| Publisher | The technology provider, not the city: the feed contact is a Lyft address |
| Licence | No licence fields → CC0 by the GBFS 3.0 default; attribute anyway as good practice |
| Refresh | `ttl: 0` on every feed (no hint); measured: `station_status` content changes every 60 s, each station reports about every 3 min |

### History — Open Data BCN

| | |
|---|---|
| Publisher | Ajuntament de Barcelona, source B:SM |
| Licence | CC BY 4.0 — **attribution required** in any published output |
| Portal | Open Data BCN |
| Station status | `https://opendata-ajuntament.barcelona.cat/data/es/dataset/estat-estacions-bicing` |
| Station information | `https://opendata-ajuntament.barcelona.cat/data/es/dataset/informacio-estacions-bicing` |

## Resources

**Real time** — always read `gbfs.json` and follow its URLs instead of hard-coding feed URLs (the provider may change them).

| Feed | Change rate (measured) | Size per day (gzip) |
|---|---|---|
| `station_status` | Every 60 s | 14.7 MB |
| `station_information` | 7 changes in 2 days (capacity changes, one new station) | 4.4 MB |
| `system_pricing_plans` | No change in 2 days | 0.1 MB |
| `gbfs`, `gbfs_versions`, `system_information`, `vehicle_types`, `system_regions`, `geofencing_zones` | No change in 2 days | < 0.1 MB each |

Total about 19 MB per day compressed (4 October 2026, static feeds every 15 min).

**Open Data BCN secured JSON resources** (one per dataset) — token sent raw in the `Authorization` header, stored in `.env` as `TOKEN_BICING` (never committed). On 2026-10-03 both returned HTTP 500 with a valid token. Not needed while the operator feed works.

**Monthly history** — two series of `.7z` archives, no token, from March 2019:
- `..._ESTACIONS.7z` — status. ~16–26 MB compressed per month.
- `..._INFORMACIO.7z` — information. ~6–9 MB compressed per month.

Listable through the CKAN API (`/data/api/3/action/package_show?id=<dataset>`).

Months not listed on 2026-10-03:
- Status: November 2025, January 2026, July 2026.
- Information: November 2025, July 2026.

Suspected wrong uploads (same byte size as the other series):
- 2025-10 status and information (8,187,733 bytes).
- 2022-03 information equals 2022-03 status (25,816,125 bytes).

## Fields (station status, GBFS 3.0)

Observed in the operator feed: `station_id`, `num_vehicles_available`, `num_vehicles_disabled`, `num_docks_available`, `num_docks_disabled`, `last_reported`, `is_installed`, `is_renting`, `is_returning`, `vehicle_docks_available`, `vehicle_types_available`.

- Vehicle types: `vehicle_types` defines 9 (`ASTRO`, `BOOST`, `CHLOE`, `COSMO`, `EFIT`, `FIT`, `ICONIC`, `METRO`, `METRO_CONNECTED`); `station_status` uses only `FIT`, `EFIT`, `BOOST`, `ICONIC`, and `FIT` and `EFIT` showed no activity in the capture.
- Timestamps in RFC 3339 UTC (`Z`).
- `ttl: 0`.
- `last_updated` is the time the response was generated (equal to the request time), not data freshness; it can be up to 15 s ahead of the client clock.
- `last_reported` is a real per-station time (about every 3 min), but counts often change without it (71,699 silent changes in two days): detect changes by content.
- Station names and short names are localised in 5 languages.

The previous field list (`num_bikes_available`, `num_bikes_available_types` with `mechanical`/`ebike`, `is_charging_station`, `status`) was GBFS 2.x and may still apply to the historical archives.

Differences with AMBici: AMBici is GBFS 2.3, Bicing is GBFS 3.0; field-by-field mapping in [bicing-realtime-capture.md](../spikes/s002-bicing-realtime-capture.md) › Findings 2a.

## Data quality notes (real time)

- The per-type counts (`vehicle_types_available`) do not add up to `num_vehicles_available` in 2.7 % of station items (521 stations).
- `capacity` equals the `vehicle_docks_capacity` count and can change (13 changes in two days; station `77` went from 24 to 0).
- Available + disabled vehicles and docks exceed `capacity` in 5 % of station items (52 stations).
- `is_renting` is false in 38 % of station items, at 541 of 543 stations, mostly with vehicles available; its meaning is unknown.
- 15 installed stations had not reported for more than 24 h during the whole capture; 1 station has `is_installed` false.
- A new station can appear in `station_status` before `station_information` (station `309`, in 11 status responses).
- `geofencing_zones` and `system_regions` are essentially empty; `rental_uris` is always an empty object.
- `external_id` (station information) is not a GBFS 3.0 field; `default_pricing_plan_id` is sometimes an empty string.

## Documented gaps (published by the provider)

- 2019: 20 June 07:40–14:00; 26 July 13:30 → 29 July 10:40; 26 Nov 22:00 → 27 Nov 11:00 (possibly).
- 2020: 7 Aug 02:25 → 10 Aug 10:40; November: 4th 01:45–11:05, 20th 19:50 → 21st 10:50, 27th 02:50 → 30th 09:50. Service stopped during COVID-19 measures.
- 2023: 22–31 August and 1–5 September missing.
- 2024: 5 February 12:50–13:05.
- 2025: from 28 October 21:55 to end of month; November missing; December before the 9th missing, 9th–11th incomplete, normal from 11th 18:40.

These are useful to validate an automatic gap detector.

## Open questions

- Meaning of the four vehicle types (`vehicle_types` feed).
- Meaning of `is_renting` false in the operator feed.
- Whether the monthly archives are dumps of this feed (T005).
- Content and schema changes inside the archives, 2019–2026 (T005).
- Whether the suspected wrong uploads are really wrong (T005).
