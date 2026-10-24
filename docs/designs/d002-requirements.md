# Design: Requirements

- **Task:** T034
- **ADRs:** [ADR-0005](../decisions/0005-utc-for-all-stored-timestamps.md), [ADR-0006](../decisions/0006-raw-layer-keeps-source-responses-untouched.md), [ADR-0008](../decisions/0008-common-model-on-gbfs-3-0.md)
- **New ADRs from this doc:** [ADR-0018](../decisions/0018-medallion-architecture.md)

## Status

- State: Draft 📝
- Phase: [x] Spec · [ ] Plan · [ ] Plan review · [ ] Steps · [ ] Steps review
- Current step: Plan, rule documents: owner approval of `docs/architecture.md` on its diff; then Plan approval and Plan review in a new session. No Implementation steps: the task closes after the Plan review.

## 1. Spec — what and why

### Context

The project is a portfolio piece that shows data engineering skills: near-real-time capture, a modern architecture, Python, medallion layers and a polished visualization. This design contains the requirements that storage, engine, execution target and visualization (T035–T038) are sized against. Bicing archives add past data the feeds cannot provide and show batch file loading alongside real-time capture. Criteria throughout: be pragmatic, data engineering skills rather than data science, and prefer free tiers when options tie.

### Guiding questions

Decisions T035–T038 are sized against Must, Should and Could; Must is the minimum, and the first vertical slice. Each question states what sizing needs (measures, grain, window, freshness); exact formulas and thresholds belong to the design of the slice that builds it. Every question can be compared across services (AMBici, Bicing). Bike IDs rotate after each trip, so every question relies on station or zone-level aggregates, never on tracking a bike ([ambici](../sources/ambici.md)).

The data fits Kimball's inventory case: stations are stores, available bikes are stock, each feed capture is a periodic stock count, and pick-ups and returns are stock movements derived from consecutive counts. Every measure derives from these two base facts: the stock snapshot (semi-additive) and the movements (additive); a measure that does not derive from them is not feasible.

| Priority | # | Question | Measures | Grain | Window | Freshness |
|---|---|---|---|---|---|---|
| Must | Q1 | How many bikes and free docks does each station have right now? | Bikes available by type, docks available | Snapshot | Latest | ≤ 5 min (R3) |
| Must | Q2 | Do the feeds arrive on time and complete? | Age of latest data, minutes without capture, % records breaking invariants, frozen stations | Minute | 30 days | ≤ 5 min |
| Must | Q3 | When is each station full or empty, and for how long? | Occupancy %, count and duration of empty and full episodes | Hour | 12 months | 1 hour |
| Should | Q4 | How many trips are made per day, by municipality and post code? | **KPI** estimated trips (lower bound), trips per dock | Day | 12 months | 1 hour |
| Should | Q5 | What share of the fleet is in use right now? | **KPI** % of fleet in use (estimated) | Snapshot | Latest | ≤ 5 min |
| Should | Q6 | Which stations are used most and least? | Changes per day, mean time between consecutive changes | Day | 12 months | 1 day |
| Could | Q7 | Which stations and zones act as sources or sinks by time band? | Net flow (arrivals − departures) | Hour | 12 months | 1 hour |
| Could | Q8 | How has the station network changed over time? | Capacity, location, name, stations added and removed | Change event | Since the earliest archive loaded | 1 day |

**Won't (now):** rebalancing, outages, trend since 2019, correlation at border stations, spatial clusters, 300 m coverage, anomalies, estimated origin-destination matrix.

### Done when

- Every item in File layout is delivered.
- Every TODO citing this task is resolved or re-pointed.
- The guiding questions that size the project are selected.
- `docs/architecture.md` states every requirement and the guiding questions, each in the arc42 section it belongs to.

### Requirements

- **R1** The visualization shall be publicly accessible, read-only, without login.
- **R2** The visualization shall show the attribution each data source's licence requires.
- **R3** The visualization shall show current station status (Q1) captured no more than 5 minutes earlier, and no more than 1 minute where the chosen tools allow it within R4.
- **R4** The solution shall cost less than €10 per month to run.
- **R5** The solution shall load the Bicing monthly archives covering the last 12 months.
- **R6** The solution shall organize data in medallion layers: bronze (raw as captured), silver (cleaned and conformed), gold (modelled for the guiding questions).
- **R7** If a feed stops updating, then the visualization shall show the age of the latest data instead of presenting it as current.
- **R8** If the capture is interrupted, then the solution shall alert the owner.
- **R9** If a monthly archive is missing or has gaps, then the solution shall record the gap and keep loading the other months.
- **R10** If the monthly cost is forecast to exceed €10, then the solution shall alert the owner.
- **R11** When processing resumes after a stop, the solution shall process all data captured since its last run, at each question's grain.
- **R12** The solution shall compute and show hour and day boundaries in Europe/Madrid local time.
- **R13** The solution shall be able to rebuild silver and gold from bronze.
- **R14** The solution shall distinguish gaps caused by its own capture from gaps in a provider's feed.

### Out of scope

- Retention and how much data stays visible in the model (owner's starting point: about 3 months) — T035
- Table format (Delta Lake or an alternative) — T035
- Whether the capture restarts on its own after an interruption — T037
- Capture completeness target — T037
- Data quality checks and targets beyond R14 and Q2 — T042
- Which Must question the first vertical slice builds — T040
- Checking the Bicing archive against the real-time capture, scope to be decided — T040

## 2. Plan — how

### Decision summary

| Concern | Decision | R |
|---|---|---|
| Traceability in architecture | Every section or table of `docs/architecture.md` ends with a `Source:` line naming the design requirements and ADRs it comes from (ISO/IEC/IEEE 29148 traceability). | — |
| Architecture style guide | A new path-scoped rule, `.claude/rules/architecture.md`, holds the arc42 style guide and the source rule; the Architecture bullet moves there from `.claude/rules/docs.md`. | — |
| ADRs from this task | Only the medallion layering becomes an ADR (ADR-0018); the other requirements turn into decisions in T035–T038. | R6 |
| Decision references | Decisions are referenced by task ID (T035, T036…); the D1–D5 labels are dropped, since design file numbers follow creation order. | — |
| Requirements in architecture | Each requirement goes to the arc42 section whose purpose it fits: functional ones and the guiding questions to §1.1, constraints to §2, solution decisions to §4, conventions to §8, quality scenarios to §10. §1 uses the arc42 subsections 1.1–1.3; quality goals are named after ISO/IEC 25010 and ISO/IEC 25012 characteristics; the terms this design introduces go to the glossary (§12). | R1–R14 |

### File layout

```text
.claude/rules/
├── architecture.md                      (new)       arc42 style guide and the Source rule, scoped to docs/architecture.md
└── docs.md                              (modified)  Architecture bullet moved to architecture.md
docs/
├── architecture.md                      (modified)  §1.1–1.3, §2, §4, §8, §10 and §12 with the requirements, each with Source lines; TODOs citing T034 resolved or re-pointed; D labels replaced by task IDs
├── tasks.md                             (modified)  T034 to 📝 with its doc; D labels dropped; T015 removed; T042, T043 added
├── decisions/
│   └── 0018-medallion-architecture.md   (new)       bronze, silver, gold layering (R6)
├── designs/
│   └── d002-requirements.md             (new)       this design
└── spikes/
    └── s004-bicing-historical-data.md   (modified)  T015 references re-pointed to T040
```

### What does not change

- `docs/architecture.md` §3, §5–7, §9 and §11, except for re-pointed TODOs, D labels and the §3 consumers line.
- ADR-0011: reassessed in T035, not here.

## 3. Implementation

### Prerequisites

### Steps

#### Step 1 — `<title>`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:**
- **R:** R1, R3 (or —)
- **Model:** `<model · effort>` (or —)

##### Scope

##### Reads

##### Do

##### Check

## 4. Close

### Implemented

### Known gaps at close

- `<gap>` — TNNN

### Decisions taken during implementation
