# Architecture

Solution architecture of the Barcelona bike sharing data platform, following the [arc42](https://arc42.org/overview) template. It states what holds today; each decision updates its section when it is taken.

## 1. Introduction and goals

A data platform on public bike sharing in the Barcelona area: it captures the AMBici and Bicing open data, unifies both providers in one model and serves it for analysis and visualization. It is a data engineering portfolio project.

Capture requirements, learned from the capture spikes ([s006](spikes/s006-cloudflare-capture.md)):

- Dynamic feeds are captured every minute; static feeds once a day, staggered.
- Responses are requested gzip-compressed from the origin and stored unchanged.
- A capture pass for all feeds needs a few milliseconds of CPU.

TODO: consumers, questions the data answers, freshness and whether Bicing history enters — D1 (T034).

## 2. Constraints

- **Cost:** €0 is the intent; a small cost may be approved once the execution target is evaluated.
- **Engine size:** single-node engines only. Distributed engines such as Spark are oversized for the volume (§3).

## 3. Context and scope

- **Sources:** AMBici and Bicing GBFS feeds ([ADR-0002](decisions/0002-data-sources-ambici-and-bicing.md)). AMBici publishes no history; Bicing does ([s004](spikes/s004-bicing-historical-data.md)).
- **Volume:** about 90 MB/day compressed and about 5,700 objects/day at a 1-minute interval, about 33 GB/year (measured 2026-10-14 to 2026-10-24).
- TODO: consumers — D1 (T034).

## 4. Solution strategy

- **Landing zone with an output contract:** every collector writes the same key layout, UTC capture time and origin bytes; the pipeline depends only on the files, so collectors can change tool or language ([ADR-0012](decisions/0012-collectors-decoupled-by-output-contract.md)).
- **Raw kept untouched:** source responses are stored as received, so everything downstream can be reprocessed from them, within the retention the storage decision sets ([ADR-0006](decisions/0006-raw-layer-keeps-source-responses-untouched.md)).
- **One common model:** both providers are unified on GBFS 3.0 and built together, since the model exists to join them ([ADR-0008](decisions/0008-common-model-on-gbfs-3-0.md)).
- **Decisions in dependency order:** each one is taken when the next step needs it (§9).

## 5. Building block view

| Block | Responsibility | State |
|---|---|---|
| Capture | Fetches the feeds and writes them to the landing zone | Built on Cloudflare Workers + R2 ([ADR-0011](decisions/0011-cloudflare-workers-r2-for-realtime-capture.md)); reassessed in D2 |
| Landing zone | Holds raw responses under the output contract | Contract set (ADR-0012); location in D2 |
| Processing | Turns raw responses into the common model and its tables | Engine in D3, execution in D4 |
| Consumption layer | Tables read by analysis and visualization | Storage and format in D2 |
| Visualization | Presents the data | D5 |

## 6. Runtime view

TODO: main flows (capture pass, pipeline run) — D4 (T037).

## 7. Deployment view

- **Capture:** Cloudflare Workers with Cron Triggers, writing to R2 (ADR-0011), until D2 confirms or replaces it.
- TODO: processing and visualization — D4 (T037), D5 (T038).

## 8. Cross-cutting concepts

- **Time:** every stored timestamp, file name and partition is in UTC; local time only when presenting ([ADR-0005](decisions/0005-utc-for-all-stored-timestamps.md)).
- **Test data:** real source responses trimmed by a committed script, plus hand-written edge cases ([ADR-0009](decisions/0009-trimmed-source-samples-as-test-fixtures.md)).
- **Versions and dependencies:** runtimes pinned in each component's native version file; dependencies locked per component ([ADR-0016](decisions/0016-runtime-versions-pinned-per-component.md), [ADR-0017](decisions/0017-dependencies-locked-per-component.md)).

## 9. Architecture decisions

Decisions in force are the ADRs in [decisions/](decisions/); retired ones are in `decisions/archive/`. Open decisions are tasks in [tasks.md](tasks.md), in dependency order.

TODO: ADR on separating processing logic from the platform it runs on, replacing ADR-0010 — after D4 (T037).

## 10. Quality requirements

TODO: freshness, availability and data quality targets — D1 (T034).

## 11. Risks and technical debt

- **R2 free tier:** 10 GB of storage against about 33 GB/year; exceeded in about 3.5 months if everything is kept. Addressed in D2.
- **Undocumented Worker behaviour:** capture relies on `encodeResponseBody: 'manual'` and on the Free plan's CPU enforcement, neither documented (ADR-0011).

## 12. Glossary

TODO: terms that need fixing as the design advances.
