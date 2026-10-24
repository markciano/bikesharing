# Architecture

Solution architecture of the Barcelona bike sharing data platform, following the [arc42](https://arc42.org/overview) template. It states what holds today; each decision updates its section when it is taken.

## 1. Introduction and goals

A data platform on public bike sharing in the Barcelona area: it captures the AMBici and Bicing open data, unifies both providers in one model and serves it for analysis and visualization. It is a data engineering portfolio project.

### 1.1 Requirements overview

The platform answers the guiding questions below, each comparable across services (AMBici, Bicing). Must is the minimum and the first vertical slice; storage, engine, execution target and visualization (T035–T038) are sized against Must, Should and Could.

| Priority | # | Question | Grain | Window | Freshness |
|---|---|---|---|---|---|
| Must | Q1 | How many bikes and free docks does each station have right now? | Snapshot | Latest | ≤ 5 min |
| Must | Q2 | Do the feeds arrive on time and complete? | Minute | 30 days | ≤ 5 min |
| Must | Q3 | When is each station full or empty, and for how long? | Hour | 12 months | 1 hour |
| Should | Q4 | How many trips are made per day, by municipality and post code? | Day | 12 months | 1 hour |
| Should | Q5 | What share of the fleet is in use right now? | Snapshot | Latest | ≤ 5 min |
| Should | Q6 | Which stations are used most and least? | Day | 12 months | 1 day |
| Could | Q7 | Which stations and zones act as sources or sinks by time band? | Hour | 12 months | 1 hour |
| Could | Q8 | How has the station network changed over time? | Change event | Since the earliest archive loaded | 1 day |

**Won't (now):** rebalancing, outages, trend since 2019, correlation at border stations, spatial clusters, 300 m coverage, anomalies, estimated origin-destination matrix.

Source: [d002](designs/d002-requirements.md) Guiding questions.

Functional requirements:

- **Public visualization:** read-only and publicly accessible, without login (R1).
- **Bicing history:** the monthly archives covering the last 12 months are loaded (R5).
- **Capture:** dynamic feeds every minute, static feeds once a day, staggered; responses requested gzip-compressed from the origin and stored unchanged; a pass for all feeds needs a few milliseconds of CPU.

Source: [d002](designs/d002-requirements.md) R1, R5; [s006](spikes/s006-cloudflare-capture.md).

### 1.2 Quality goals

| Priority | Quality goal | Characteristic | Motivation |
|---|---|---|---|
| 1 | Current station status is recent, and stale data is never shown as current | Currentness (ISO/IEC 25012) | Live station status (Q1) is the visualization's main view |
| 2 | Silver and gold can be caught up and rebuilt from bronze | Recoverability (ISO/IEC 25010) | Stops and model changes must not lose data |
| 3 | Every gap is recorded and attributed to its cause | Completeness (ISO/IEC 25012) | Measures derived from consecutive counts are only trustworthy when their gaps are known |

Each goal is made measurable by the scenarios in §10.

Source: [d002](designs/d002-requirements.md) R3, R7, R9, R11, R13, R14.

### 1.3 Stakeholders

| Role | Expectations |
|---|---|
| Owner | Builds and operates the platform; is alerted when capture stops or cost is forecast over budget (R8, R10) |
| Portfolio reviewers | Data engineering skills shown in practice: near-real-time capture, batch archive loading, medallion layers, industry standards |
| Public visitors | Current and historical station data, without login (R1) |
| Data publishers ([AMBici](sources/ambici.md), [Bicing](sources/bicing.md)) | Attribution as each licence requires (R2) |

Source: [d002](designs/d002-requirements.md) Context, R1, R2, R8, R10.

## 2. Constraints

| Constraint | Type | Background |
|---|---|---|
| Running cost below €10 per month; free tiers preferred when options tie | Organisational | Portfolio project funded by the owner (R4) |
| Licence attribution shown in the visualization | Legal | Required by each source's licence (R2) |
| Single-node engines only | Technical | Distributed engines such as Spark are oversized for the volume (§3) |
| Station or zone-level aggregates only | Technical | Bike IDs rotate after each trip, so a bike cannot be tracked ([AMBici](sources/ambici.md)) |

Source: [d002](designs/d002-requirements.md) R2, R4, Guiding questions.

## 3. Context and scope

- **Sources:** AMBici and Bicing GBFS feeds ([ADR-0002](decisions/0002-data-sources-ambici-and-bicing.md)). AMBici publishes no history; Bicing does ([s004](spikes/s004-bicing-historical-data.md)).
- **Volume:** about 90 MB/day compressed and about 5,700 objects/day at a 1-minute interval, about 33 GB/year (measured 2026-10-14 to 2026-10-24).
- **Consumers:** public visitors read the visualization; the owner receives the operational alerts (§1.3).

## 4. Solution strategy

- **Landing zone with an output contract:** every collector writes the same key layout, UTC capture time and origin bytes; the pipeline depends only on the files, so collectors can change tool or language ([ADR-0012](decisions/0012-collectors-decoupled-by-output-contract.md)).
- **Raw kept untouched:** source responses are stored as received, so everything downstream can be reprocessed from them, within the retention the storage decision sets ([ADR-0006](decisions/0006-raw-layer-keeps-source-responses-untouched.md)).
- **Medallion layers:** bronze holds the data as captured, silver the cleaned and conformed common model, gold the tables modelled for the guiding questions; silver and gold can be rebuilt from bronze ([ADR-0018](decisions/0018-medallion-architecture.md)).
- **One common model:** both providers are unified on GBFS 3.0 and built together, since the model exists to join them ([ADR-0008](decisions/0008-common-model-on-gbfs-3-0.md)).
- **Inventory model (Kimball):** stations are stores and bikes are stock; every measure derives from two base facts, the stock snapshot (semi-additive) and the movements derived from consecutive snapshots (additive).
- **Decisions in dependency order:** each one is taken when the next step needs it (§9).

Source: [d002](designs/d002-requirements.md) R6, R13, Guiding questions; [ADR-0006](decisions/0006-raw-layer-keeps-source-responses-untouched.md); [ADR-0008](decisions/0008-common-model-on-gbfs-3-0.md); [ADR-0012](decisions/0012-collectors-decoupled-by-output-contract.md); [ADR-0018](decisions/0018-medallion-architecture.md).

## 5. Building block view

| Block | Responsibility | State |
|---|---|---|
| Capture | Fetches the feeds and writes them to the landing zone | Built on Cloudflare Workers + R2 ([ADR-0011](decisions/0011-cloudflare-workers-r2-for-realtime-capture.md)); reassessed in T035 |
| Landing zone | Holds raw responses under the output contract | Contract set (ADR-0012); location in T035 |
| Processing | Turns raw responses into the common model and its tables | Engine in T036, execution in T037 |
| Consumption layer | Tables read by analysis and visualization | Storage and format in T035 |
| Visualization | Presents the data | T038 |

## 6. Runtime view

TODO: main flows (capture pass, pipeline run) — T037.

## 7. Deployment view

- **Capture:** Cloudflare Workers with Cron Triggers, writing to R2 (ADR-0011), until T035 confirms or replaces it.
- TODO: processing and visualization — T037, T038.

## 8. Cross-cutting concepts

- **Time:** every stored timestamp, file name and partition is in UTC; hour and day boundaries are computed and shown in Europe/Madrid local time ([ADR-0005](decisions/0005-utc-for-all-stored-timestamps.md), R12).
- **Test data:** real source responses trimmed by a committed script, plus hand-written edge cases ([ADR-0009](decisions/0009-trimmed-source-samples-as-test-fixtures.md)).
- **Versions and dependencies:** runtimes pinned in each component's native version file; dependencies locked per component ([ADR-0016](decisions/0016-runtime-versions-pinned-per-component.md), [ADR-0017](decisions/0017-dependencies-locked-per-component.md)).

Source: [d002](designs/d002-requirements.md) R12; [ADR-0005](decisions/0005-utc-for-all-stored-timestamps.md); [ADR-0009](decisions/0009-trimmed-source-samples-as-test-fixtures.md); [ADR-0016](decisions/0016-runtime-versions-pinned-per-component.md); [ADR-0017](decisions/0017-dependencies-locked-per-component.md).

## 9. Architecture decisions

Decisions in force are the ADRs in [decisions/](decisions/); retired ones are in `decisions/archive/`. Open decisions are tasks in [tasks.md](tasks.md), in dependency order.

TODO: ADR on separating processing logic from the platform it runs on, replacing ADR-0010 — after T037.

## 10. Quality requirements

Quality scenarios that make the goals in §1.2 measurable:

| ID | Quality | Stimulus | Response | R |
|---|---|---|---|---|
| QS1 | Currentness | Normal operation | Station status (Q1) is shown no more than 5 minutes after capture, and no more than 1 minute where the chosen tools allow it within the cost limit | R3 |
| QS2 | Currentness | A feed stops updating | The visualization shows the age of the latest data instead of presenting it as current | R7 |
| QS3 | Completeness | The capture is interrupted | The owner is alerted | R8 |
| QS4 | Completeness | A monthly archive is missing or has gaps | The gap is recorded and the other months keep loading | R9 |
| QS5 | Completeness | Data is missing for a period | The gap is attributed to the platform's own capture or to the provider's feed | R14 |
| QS6 | Recoverability | Processing resumes after a stop | All data captured since the last run is processed, at each question's grain | R11 |
| QS7 | Recoverability | Silver or gold must be rebuilt | They are rebuilt from bronze | R13 |
| QS8 | Cost (§2) | The monthly cost is forecast to exceed €10 | The owner is alerted | R10 |

- TODO: capture completeness target — T037.
- TODO: data quality checks and targets — T042.

Source: [d002](designs/d002-requirements.md) R3, R7–R11, R13, R14.

## 11. Risks and technical debt

- **R2 free tier:** 10 GB of storage against about 33 GB/year; exceeded in about 3.5 months if everything is kept. Addressed in T035.
- **Undocumented Worker behaviour:** capture relies on `encodeResponseBody: 'manual'` and on the Free plan's CPU enforcement, neither documented (ADR-0011).

## 12. Glossary

| Term | Meaning |
|---|---|
| Service | One of the two bike sharing systems: AMBici or Bicing |
| Guiding question | One of the questions Q1–Q8 the platform is sized to answer (§1.1) |
| Bronze, silver, gold | Medallion layers: data as captured; cleaned and conformed common model; tables modelled for the guiding questions |
| Snapshot | One capture of a station's status (bikes by type, docks available): a periodic stock count |
| Movement | A pick-up or return derived from two consecutive snapshots of a station |
| Empty or full episode | A continuous period in which a station has no bikes, or no free docks |
| Frozen station | A station whose reported status stops changing while its feed keeps updating |
| Estimated trips | Trips inferred from movements; a lower bound, since changes that cancel out between two snapshots are not seen |

Source: [d002](designs/d002-requirements.md) R6, Guiding questions; [ADR-0018](decisions/0018-medallion-architecture.md).
