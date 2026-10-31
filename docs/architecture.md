# Architecture

Solution architecture of the Barcelona bike sharing data platform, following the [arc42](https://arc42.org/overview) template. It states what holds today; each decision updates its section when it is taken.

## 1. Introduction and goals

A data platform on public bike sharing in the Barcelona area: it captures the AMBici and Bicing open data, unifies both providers in one model and serves it for analysis and visualization. It is a data engineering portfolio project. [d002 › Context](designs/d002-requirements.md#context); [ADR-0002](decisions/0002-data-sources-ambici-and-bicing.md); [ADR-0008](decisions/0008-common-model-on-gbfs-3-0.md).

### 1.1 Requirements overview

The platform answers the guiding questions below, each comparable across services (AMBici, Bicing). Must is the minimum and the first vertical slice; storage, engine, execution target and visualization (T035–T038) are sized against Must, Should and Could. Window is the period gold must answer. [d002 › Guiding questions](designs/d002-requirements.md#guiding-questions).

| Priority | # | Question | Grain | Window | Freshness | Source |
|---|---|---|---|---|---|---|
| Must | Q1 | How many bikes and free docks does each station have right now? | Snapshot | Latest | ≤ 5 min | [d002 › Q1](designs/d002-requirements.md#guiding-questions) |
| Must | Q2 | Do the feeds arrive on time and complete? | Minute | 30 days | ≤ 5 min | [d002 › Q2](designs/d002-requirements.md#guiding-questions) |
| Must | Q3 | When is each station full or empty, and for how long? | Hour | 12 months | 1 hour | [d002 › Q3](designs/d002-requirements.md#guiding-questions) |
| Should | Q4 | How many trips are made per day, by municipality and post code? | Day | 12 months | 1 hour | [d002 › Q4](designs/d002-requirements.md#guiding-questions) |
| Should | Q5 | What share of the fleet is in use right now? | Snapshot | Latest | ≤ 5 min | [d002 › Q5](designs/d002-requirements.md#guiding-questions) |
| Should | Q6 | Which stations are used most and least? | Day | 12 months | 1 day | [d002 › Q6](designs/d002-requirements.md#guiding-questions) |
| Could | Q7 | Which stations and zones act as sources or sinks by time band? | Hour | 12 months | 1 hour | [d002 › Q7](designs/d002-requirements.md#guiding-questions) |
| Could | Q8 | How has the station network changed over time? | Change event | Since the earliest archive loaded | 1 day | [d002 › Q8](designs/d002-requirements.md#guiding-questions) |

**Won't (now):** rebalancing, outages, trend since 2019, correlation at border stations, spatial clusters, 300 m coverage, anomalies, estimated origin-destination matrix. [d002 › Guiding questions](designs/d002-requirements.md#guiding-questions).

Functional requirements:

- **Public visualization:** read-only and publicly accessible, without login. [d002 › R1](designs/d002-requirements.md#requirements).
- **Bicing history:** the monthly archives covering the 12 months before the first load are loaded once. [d002 › R5](designs/d002-requirements.md#requirements).
- **Capture:** dynamic feeds every minute, static feeds once a day, staggered; responses requested gzip-compressed from the origin and stored unchanged; a pass for all feeds needs a few milliseconds of CPU. [s006](spikes/s006-cloudflare-capture.md).

### 1.2 Quality goals

| Priority | Quality goal | Characteristic | Motivation | Source |
|---|---|---|---|---|
| 1 | Current station status is recent, and stale data is never shown as current | Currentness (ISO/IEC 25012) | Live station status (Q1) is the visualization's main view | [d002 › R3, R7](designs/d002-requirements.md#requirements) |
| 2 | Silver and gold can be caught up and rebuilt from bronze | Recoverability (ISO/IEC 25010) | Stops and model changes must not lose data | [d002 › R11, R13](designs/d002-requirements.md#requirements) |
| 3 | Each component and user reaches only the data and access its role needs, and data that cannot be rebuilt cannot be deleted or altered | Confidentiality, Integrity (ISO/IEC 25010) | Data and services run in the cloud, and the visualization is open to the public | [d002 › R1, R15–R18](designs/d002-requirements.md#requirements) |
| 4 | Every gap is recorded and attributed to its cause | Completeness (ISO/IEC 25012) | Measures derived from consecutive counts are only trustworthy when their gaps are known | [d002 › R9, R14](designs/d002-requirements.md#requirements) |

Each goal is made measurable by the scenarios in §10.

### 1.3 Stakeholders

| Role | Expectations | Source |
|---|---|---|
| Owner | Builds and operates the platform; is alerted when capture stops or cost is forecast over budget | [d002 › R8, R10](designs/d002-requirements.md#requirements) |
| Portfolio reviewers | Data engineering skills shown in practice: near-real-time capture, batch archive loading, medallion layers, industry standards | [d002 › Context](designs/d002-requirements.md#context) |
| Public visitors | Current and historical station data, without login | [d002 › R1](designs/d002-requirements.md#requirements) |
| Data publishers ([AMBici](sources/ambici.md), [Bicing](sources/bicing.md)) | Attribution as each licence requires | [d002 › R2](designs/d002-requirements.md#requirements) |

## 2. Constraints

| Constraint | Type | Background | Source |
|---|---|---|---|
| Running cost below €10 per month; free tiers preferred when options tie | Organisational | Portfolio project funded by the owner | [d002 › R4](designs/d002-requirements.md#requirements); [d002 › Context](designs/d002-requirements.md#context) |
| Licence attribution shown in the visualization | Legal | Required by each source's licence | [d002 › R2](designs/d002-requirements.md#requirements) |
| Single-node engines only | Technical | Distributed engines such as Spark are oversized for the volume (§3) | [tasks.md › T036](tasks.md) |
| Station or zone-level aggregates only | Technical | Bike IDs rotate after each trip, so a bike cannot be tracked | [d002 › Guiding questions](designs/d002-requirements.md#guiding-questions); [AMBici › Known characteristics](sources/ambici.md#known-characteristics) |

## 3. Context and scope

- **Sources:** AMBici and Bicing GBFS feeds. AMBici publishes no history; Bicing does. [ADR-0002](decisions/0002-data-sources-ambici-and-bicing.md); [s004](spikes/s004-bicing-historical-data.md).
- **Volume:** about 90 MB/day compressed and about 5,700 objects/day at a 1-minute interval, about 33 GB/year (measured 2026-10-14 to 2026-10-24). [AMBici › Feeds](sources/ambici.md#feeds); [Bicing › Resources](sources/bicing.md#resources).
- **Consumers:** public visitors read the visualization; the owner receives the operational alerts (§1.3). [d002 › R1, R8, R10](designs/d002-requirements.md#requirements).

## 4. Solution strategy

### 4.1 Technology

- **Own lakehouse on Cloudflare R2:** every layer is stored as open-format files in R2, with compute separate; R2 charges no egress, so the engine can run anywhere. Silver and gold are Delta Lake tables, whose commits are safe on R2 with no external lock. [ADR-0019](decisions/0019-own-lakehouse-on-cloudflare-r2.md); [ADR-0022](decisions/0022-delta-lake-for-silver-and-gold.md).

### 4.2 Structure

- **Landing zone with an output contract:** every collector writes the same key layout, UTC capture time and origin bytes; the pipeline depends only on the files, so collectors can change tool or language. [ADR-0012](decisions/0012-collectors-decoupled-by-output-contract.md).
- **Raw kept untouched:** source responses are stored as received, so everything downstream can be reprocessed from them, since bronze is kept indefinitely. [ADR-0006](decisions/0006-raw-layer-keeps-source-responses-untouched.md); [ADR-0021](decisions/0021-retention-per-layer.md).
- **Medallion layers:** bronze holds the captured objects and history archives as they arrive, with no table over them, silver the cleaned and conformed common model, gold the tables modelled for the guiding questions; silver and gold can be rebuilt from bronze. [d002 › R6, R13](designs/d002-requirements.md#requirements); [ADR-0018](decisions/0018-medallion-architecture.md); [ADR-0020](decisions/0020-bronze-as-captured-objects.md).

### 4.3 Data model

- **One common model:** both providers are unified on GBFS 3.0 and built together, since the model exists to join them. [ADR-0008](decisions/0008-common-model-on-gbfs-3-0.md).
- **Inventory model (Kimball):** stations are stores and bikes are stock; every measure derives from two base facts, the stock snapshot (semi-additive) and the movements derived from consecutive snapshots (additive). [d002 › Guiding questions](designs/d002-requirements.md#guiding-questions).

### 4.4 Organisation

- **Decisions in dependency order:** each one is taken when the next step needs it (§9). [tasks.md](tasks.md).

## 5. Building block view

| Block | Responsibility | State | Source |
|---|---|---|---|
| Capture | Fetches the feeds and writes them to the landing zone | Built on Cloudflare Workers + R2 | [ADR-0011](decisions/0011-cloudflare-workers-r2-for-realtime-capture.md); [ADR-0019](decisions/0019-own-lakehouse-on-cloudflare-r2.md) |
| Landing zone (bronze) | Holds raw responses under the output contract, and the history archives as downloaded | Bronze bucket in R2 | [ADR-0012](decisions/0012-collectors-decoupled-by-output-contract.md); [ADR-0020](decisions/0020-bronze-as-captured-objects.md); [ADR-0023](decisions/0023-storage-security-baseline.md) |
| Processing | Turns raw responses into the common model and its tables | Engine in T036, execution in T037 | [ADR-0008](decisions/0008-common-model-on-gbfs-3-0.md); [tasks.md › T036, T037](tasks.md) |
| Lakehouse | Silver and gold tables, read by analysis and visualization | Delta tables in the lakehouse bucket in R2; built by the pipeline (T040) | [ADR-0019](decisions/0019-own-lakehouse-on-cloudflare-r2.md); [ADR-0022](decisions/0022-delta-lake-for-silver-and-gold.md); [ADR-0023](decisions/0023-storage-security-baseline.md); [tasks.md › T040](tasks.md) |
| Visualization | Presents the data | T038 | [d002 › R1, R2](designs/d002-requirements.md#requirements); [tasks.md › T038](tasks.md) |

## 6. Runtime view

TODO(T037): main flows (capture pass, pipeline run).

## 7. Deployment view

- **Capture:** Cloudflare Workers with Cron Triggers, writing to the bronze bucket in R2. [ADR-0011](decisions/0011-cloudflare-workers-r2-for-realtime-capture.md); [ADR-0019](decisions/0019-own-lakehouse-on-cloudflare-r2.md).
- **Storage:** two R2 buckets: bronze, and lakehouse for silver and gold. [ADR-0019](decisions/0019-own-lakehouse-on-cloudflare-r2.md); [ADR-0023](decisions/0023-storage-security-baseline.md).
- TODO(T037): processing.
- TODO(T038): visualization.

## 8. Cross-cutting concepts

- **Time:** every stored timestamp, file name and partition is in UTC; hour and day boundaries are computed and shown in Europe/Madrid local time. [ADR-0005](decisions/0005-utc-for-all-stored-timestamps.md); [d002 › R12](designs/d002-requirements.md#requirements).
- **Test data:** real source responses trimmed by a committed script, plus hand-written edge cases. [ADR-0009](decisions/0009-trimmed-source-samples-as-test-fixtures.md).
- **Versions and dependencies:** runtimes pinned in each component's native version file; dependencies locked per component. [ADR-0016](decisions/0016-runtime-versions-pinned-per-component.md); [ADR-0017](decisions/0017-dependencies-locked-per-component.md).
- **Retention:** bronze and gold kept indefinitely; silver in a rolling window covering the longest gold window (§1.1); Delta tables keep 7 days of history. [ADR-0021](decisions/0021-retention-per-layer.md).
- **Storage security:** one token per component with least privilege; bronze in its own bucket, read-only for the pipeline; append-only bronze prefixes under a bucket lock; buckets private; the Admin token held by the owner. [ADR-0023](decisions/0023-storage-security-baseline.md); [d002 › R15–R18](designs/d002-requirements.md#requirements).

## 9. Architecture decisions

Decisions in force are the ADRs in [decisions/](decisions/); retired ones are in `decisions/archive/`. Open decisions are tasks in [tasks.md](tasks.md), in dependency order.

TODO(T037): ADR on separating processing logic from the platform it runs on, replacing ADR-0010.

## 10. Quality requirements

Quality scenarios that make the goals in §1.2 measurable:

| ID | Quality | Stimulus | Response | Source |
|---|---|---|---|---|
| QS1 | Currentness | Normal operation | Station status (Q1) is shown no more than 5 minutes after capture, and no more than 1 minute where the chosen tools allow it within the cost limit | [d002 › R3](designs/d002-requirements.md#requirements) |
| QS2 | Currentness | A feed stops updating | The visualization shows the age of the latest data instead of presenting it as current | [d002 › R7](designs/d002-requirements.md#requirements) |
| QS3 | Completeness | The capture is interrupted | The owner is alerted | [d002 › R8](designs/d002-requirements.md#requirements) |
| QS4 | Completeness | A monthly archive is missing or has gaps | The gap is recorded and the other months keep loading | [d002 › R9](designs/d002-requirements.md#requirements) |
| QS5 | Completeness | Data is missing for a period | The gap is attributed to the platform's own capture or to the provider's feed | [d002 › R14](designs/d002-requirements.md#requirements) |
| QS6 | Recoverability | Processing resumes after a stop | All data captured since the last run is processed, at each question's grain | [d002 › R11](designs/d002-requirements.md#requirements) |
| QS7 | Recoverability | Silver or gold must be rebuilt | They are rebuilt from bronze | [d002 › R13](designs/d002-requirements.md#requirements) |
| QS8 | Cost (§2) | The monthly cost is forecast to exceed €10 | The owner is alerted | [d002 › R10](designs/d002-requirements.md#requirements) |
| QS9 | Confidentiality | A component's token leaks | It reaches only that component's buckets and access | [d002 › R15](designs/d002-requirements.md#requirements) |
| QS10 | Integrity | A locked bronze object is deleted or overwritten | The store refuses it | [d002 › R16](designs/d002-requirements.md#requirements) |
| QS11 | Integrity | The pipeline writes to bronze | The store refuses it | [d002 › R17](designs/d002-requirements.md#requirements) |
| QS12 | Confidentiality | Data is requested without credentials | It is denied, except what the visualization publishes | [d002 › R18](designs/d002-requirements.md#requirements) |

- TODO(T037): capture completeness target.
- TODO(T042): data quality checks and targets.

## 11. Risks and technical debt

- **Unexpected R2 bill:** R2 bills storage and operations, and the cost model is estimated, not measured; how often the pipeline commits weighs on operations. Mitigated by the cost alert (QS8) and the recalibration with R2's metrics in production (T040). [ADR-0019](decisions/0019-own-lakehouse-on-cloudflare-r2.md); [s010 › Not verified](spikes/s010-storage-table-format.md#not-verified).
- **One vendor:** storage and capture both depend on Cloudflare. [ADR-0019](decisions/0019-own-lakehouse-on-cloudflare-r2.md).
- **Delta concurrency limits (low):** with no managed service coordinating commits, conflicting MERGEs are not resolved automatically, and concurrent table creation or schema merge can race; unlikely here, since tables are created and schemas changed rarely. The pipeline design handles them. [s010 › D4](spikes/s010-storage-table-format.md#decisions-to-record).
- **Undocumented Worker behaviour:** capture relies on `encodeResponseBody: 'manual'` and on the Free plan's CPU enforcement, neither documented. [ADR-0011](decisions/0011-cloudflare-workers-r2-for-realtime-capture.md).

## 12. Glossary

| Term | Meaning | Source |
|---|---|---|
| Service | One of the two bike sharing systems: AMBici or Bicing | [ADR-0002](decisions/0002-data-sources-ambici-and-bicing.md) |
| Guiding question | One of the questions Q1–Q8 the platform is sized to answer (§1.1) | [d002 › Guiding questions](designs/d002-requirements.md#guiding-questions) |
| Bronze, silver, gold | Medallion layers: data as captured; cleaned and conformed common model; tables modelled for the guiding questions | [ADR-0018](decisions/0018-medallion-architecture.md) |
| Snapshot | One capture of a station's status (bikes by type, docks available): a periodic stock count | [d002 › Guiding questions](designs/d002-requirements.md#guiding-questions) |
| Movement | A pick-up or return derived from two consecutive snapshots of a station | [d002 › Guiding questions](designs/d002-requirements.md#guiding-questions) |
| Empty or full episode | A continuous period in which a station has no bikes, or no free docks | [d002 › Q3](designs/d002-requirements.md#guiding-questions) |
| Frozen station | A station whose reported status stops changing while its feed keeps updating | [d002 › Q2](designs/d002-requirements.md#guiding-questions) |
| Estimated trips | Trips inferred from movements; a lower bound, since changes that cancel out between two snapshots are not seen | [d002 › Q4](designs/d002-requirements.md#guiding-questions) |
| Lakehouse | Silver and gold, stored as Delta tables in their own R2 bucket | [ADR-0019](decisions/0019-own-lakehouse-on-cloudflare-r2.md); [ADR-0022](decisions/0022-delta-lake-for-silver-and-gold.md) |
| Bucket lock | An R2 rule that blocks delete and overwrite of the objects under a prefix | [ADR-0023](decisions/0023-storage-security-baseline.md) |
