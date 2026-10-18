# Spike — AMBici historical data availability

**Status:** Concluded — 2026-10-03.

A spike is a short investigation to answer questions before building. Durable findings move to the source card (`docs/sources/ambici.md`) or to the decision log.

## Question

Is historical AMBici data publicly available?

## Findings

- The AMB open data catalogue entry "Servei AMBici" is DCAT metadata whose "Download" distribution is empty. Its only real distribution is the GBFS 2.3 feed `https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_bs/gbfs.json` (ttl 60 s).
- GBFS is real-time by design; the spec excludes historical/archival data.
- Citybikes (data.citybik.es) publishes monthly Parquet history only for Bicing. Its live API does track AMBici as 15 per-municipality networks (`ambici-amb`, `ambici-badalona`, …), all backed by the same `nextbike_bs` feed.
- MaxHalford/bike-sharing-history (git scraping every ~12 min) does not include AMBici among its current systems. Its Bicing archive has large gaps (nothing 2024-11 → 2026-05).

## Conclusion

No public AMBici history exists. It must be built by our own capture, starting as soon as possible (see `s001-ambici-realtime-capture.md`). A data request to AMB/TMB (open data participation form, or a public-information access request under Catalan Llei 19/2014) is a possible parallel path.

**Consequence for DL-004:** the per-station baseline for AMBici will not exist until several weeks of own capture have accumulated. Bicing is unaffected (official monthly history exists).

## Sources

- <https://github.com/MobilityData/gbfs>
- <https://data.citybik.es>
- <https://api.citybik.es/v2/networks>
- <https://github.com/MaxHalford/bike-sharing-history>
