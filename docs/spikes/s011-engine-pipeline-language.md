# Spike: Processing engine and pipeline language

- **Task:** T036
- **ADRs:** [ADR-0008](../decisions/0008-common-model-on-gbfs-3-0.md), [ADR-0018](../decisions/0018-medallion-architecture.md), [ADR-0019](../decisions/0019-own-lakehouse-on-cloudflare-r2.md), [ADR-0020](../decisions/0020-bronze-as-captured-objects.md), [ADR-0022](../decisions/0022-delta-lake-for-silver-and-gold.md), [ADR-0023](../decisions/0023-storage-security-baseline.md)
- **Code:** `spikes/engine-pipeline-language/`

## Status

- State: Draft 📝
- Phase: [ ] Questions · [ ] Method · [ ] Steps · [ ] Steps review
- Started: — · Finished: —
- Current step: —

## 1. Questions — what we need to know

### 1.1 Context

T036 decides the single-node processing engine, then the pipeline language, which depends on the engine, and models the component's threats to add requirements to [d002](../designs/d002-requirements.md#requirements). It builds on [s010](s010-storage-table-format.md), which set Delta Lake on Cloudflare R2 and showed that `deltalake` writes and MERGEs there and that Polars and DuckDB read the table. All three decisions are expected to be settled by documents and arithmetic; a run is added only if the winning engine rests on an unknown that they cannot settle.

### 1.2 Decided at framing

#### D1. Processing engine

Workload the engine must cover. It traces criteria to requirements and is not a pipeline design:

| # | Operation | Source | Separates engines |
|---|---|---|---|
| O1 | Read nested `json.gz` from R2 and flatten it | Bronze, [ADR-0008](../decisions/0008-common-model-on-gbfs-3-0.md) | Yes |
| O2 | Read Bicing monthly archives | [d002 › R5, R9](../designs/d002-requirements.md#requirements) | Little |
| O3 | Clean, type, deduplicate and validate invariants | [d002 › R6, Q2](../designs/d002-requirements.md#guiding-questions) | No |
| O4 | Compare each reading with the station's previous one (window functions): movements and frozen stations | [d002 › Q2, Q4, Q6, Q7](../designs/d002-requirements.md#guiding-questions) | Somewhat |
| O5 | Detect full and empty episodes and their duration, including those that span two batches | [d002 › Q3](../designs/d002-requirements.md#guiding-questions) | Yes |
| O6 | Detect capture gaps against a time grid | [d002 › Q2, R14](../designs/d002-requirements.md#guiding-questions) | Somewhat |
| O7 | Aggregate by hour and day in local time, across clock changes | [d002 › R12](../designs/d002-requirements.md#requirements) | Little |
| O8 | Read Delta filtered by partition without downloading all of it | [d002 › R11](../designs/d002-requirements.md#requirements), R2 read costs | Yes |
| O9 | Write by partition overwrite or MERGE | [d002 › R13](../designs/d002-requirements.md#requirements) | No |
| O10 | Rebuild silver and gold from bronze | [d002 › R13](../designs/d002-requirements.md#requirements) | Little |

Reference data, the most demanding case of each operation ([s010 › F7, F12, F13](s010-storage-table-format.md#4-findings)):

| Operation | Reference data | Volume |
|---|---|---|
| O1, O8, memory criterion | AMBici `free_bike_status` (live feed) | 73.2 MB a day as `json.gz` |
| O4, O5, O6 on live data | Bicing `station_status` (live feed) | 17.0 MB a day as `json.gz`; deduplication keeps 33% of rows |
| O4, O5 on history | `ESTACIONS` (Bicing history, `.7z` archives) | About 0.29 GB and 4.4M rows a month uncompressed; deduplication keeps 98.5% |
| O2 | `INFORMACIO` (Bicing history, `.7z` archives), once uncompressed | About 0.9 GB a month uncompressed |

Hard cuts:

| # | Cut | Source |
|---|---|---|
| C1 | Runs on a single node, with no cluster | [architecture.md › Constraints](../architecture.md) |
| C2 | Reads and writes Delta on R2, MERGE included, by itself or by handing data to `deltalake` | [ADR-0022](../decisions/0022-delta-lake-for-silver-and-gold.md) |
| C3 | Open source, with no per-use cost and with stable, maintained releases | [d002 › R4](../designs/d002-requirements.md#requirements) |

Cut results (checked on 2026-11-01):

| Candidate | Result | Fact |
|---|---|---|
| Polars | Passes | Hands MERGE to `deltalake`; spills to disk by default since 2.0. Not confirmed whether joins spill |
| DuckDB | Passes | No Delta MERGE in 2.0 (INSERT only), so it hands MERGE to `deltalake`; spills to disk |
| Apache DataFusion | Passes | Hands writes and MERGE to `deltalake`; spills to disk |
| ClickHouse (`clickhouse-local`) | Passes, conditional | Delta writes are Beta with no MERGE, so it hands MERGE to `deltalake`; spilling not confirmed in the docs |
| ClickHouse server | Removed | Same engine as `clickhouse-local`, plus a service to keep running |
| chDB | Removed | Its 25.8 build predates ClickHouse's Delta writes, and its docs do not mention Delta |
| pandas | Passes | Hands Delta reads, writes and MERGE to `deltalake`; eager and in-memory |
| Daft | Fails C3 | Below 1.0 (0.7.26) |
| Spark in local mode | Fails C1 | Ruled out by the architecture constraint on single-node engines |

Anchors (2 and 4 are in between):

| Criterion (weight) | 1 | 3 | 5 |
|---|---|---|---|
| Portfolio value (5) | Niche, almost absent from data engineering job ads | Recognised and growing, appears in some job ads | Widely requested standard |
| Workload fit (4) | Lacks window functions, or they must be hand-written | Covers O4–O6, but O1 needs custom Python code | Reads nested `json.gz` from R2, with native window functions and as-of join |
| Delta integration on R2 (4) | Cannot filter: downloads the whole table | Filters by partition, but only through `deltalake` or custom code | Reads Delta natively, filters by partition and file statistics, and works with S3-compatible endpoints |
| Maturity (3) | ≥ 1.0, but something needed is experimental | ≥ 1.0, with what is needed stable but recent (under 6 months) | Over 2 years since 1.0, with what is needed stable and well documented |
| Operational simplicity (3) | Needs a running service | A separate binary, or needs extra setup | An in-process library, installed with the dependencies and testable locally with no infrastructure |
| Memory behaviour (3) | In memory only | Spills to disk for some operations, or not by default | Spills to disk across O1–O8, with a configurable limit |
| dbt fit (3) | No maintained adapter | Maintained adapter, but writing Delta needs custom code | Maintained adapter and incremental Delta writes on S3-compatible storage |
| Learning value (2) | No new concepts | One new core concept | Several, such as a query optimizer, vectorized execution or out-of-core processing |

- TODO(T036): scores and winner.
- **MERGE on real volumes needs no run.** All surviving candidates hand it to `deltalake`, so it does not separate them. Silver averages about 80 MB of Parquet per day ([s010 › Q1](s010-storage-table-format.md#answers)), and about 300 MB at the ×3.8 break-even of vehicles' estimated bytes per row ([s010 › F24](s010-storage-table-format.md#4-findings)), so a MERGE bounded to one day stays near 3 GB in memory, assuming ×10 over Parquet. The choice between partition overwrite and a bounded MERGE belongs to T040, which also confirms predicate overwrite on R2.
- **DuckDB's reads are not counted before choosing.** This replaces the mitigation in [s010 › Not verified](s010-storage-table-format.md#not-verified), because no count would change the choice. On demand, the pipeline uses 3.7% of R2's free Class B quota. The risk appears only at 24/7 every 10 minutes, which reaches €2 at ×2.1 reads per file ([s010 › F24](s010-storage-table-format.md#4-findings)), and a lower commit cadence reverses it. If DuckDB wins, its reads are measured in production through R2's per-bucket metrics.

#### D2. Budget shares

The [d002 › R4](../designs/d002-requirements.md#requirements) limit of €10 per month covers the whole solution. It is shared as follows:

| Component | Share per month | Basis |
|---|---|---|
| Capture | €0 | €0 billed within free tiers ([ADR-0011](../decisions/0011-cloudflare-workers-r2-for-realtime-capture.md)) |
| Storage (R2) | €2 | [s010 › Exit criteria](s010-storage-table-format.md#exit-criteria); its worst month up to month 12 is €0.83 |
| Pipeline (engine and execution) | €4 | The engine is free under C3, so the share pays for where it runs (T037) |
| Visualization | €2 | Validated by T038 |
| Reserve | €2 | USD/EUR rate, since R2 bills in USD, and deviations |

- The pipeline gets the largest share because it is the only component that may need an always-on machine.
- Rejected: 6 / 2 / 0 (pipeline, visualization, reserve), because with no reserve any deviation breaks R4.
- The shares are reversible: if T037 or T038 find real prices above their share, they reopen the split against the reserve.
- TODO(T036): when the spike closes, record the split in an ADR and in `docs/architecture.md` § Constraints.

### 1.3 Questions

Main question: `<one sentence>`

- **Q1.** `<question>`
- **Observe only:** `<item>`

### 1.4 Exit criteria

- **Standard:** `<standard or pattern applied>`
- **Timebox:** `<window, and what ends it>`
- `<criterion>` — `<threshold>` — hard cut | guide

### 1.5 Out of scope

- Partition overwrite or MERGE, batch size, commit cadence and state between batches (T040).
- Where dbt applies, if anywhere: T040 decides it, and the owner wants to use it where it can be justified.
- Where the pipeline runs and what schedules it (T037).
- Data quality checks beyond the basics (T042).

### 1.6 Open questions

| Question | Notes |
|---|---|
| | |

## 2. Method — how we find out

### 2.1 Approach

| Variant | What it is | What it tells |
|---|---|---|
| | | |

#### 2.1.1 Shared behaviour

-

#### `<A>`. `<Title of variant, option or probe A>`

### 2.3 Decision log

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| `<N>` |  |  |  |  |

### 2.4 File layout

```text
spikes/engine-pipeline-language/
├── README.md        Setup, commands, what each script does; How we got here (written at Conclusion)
└── <file>           <purpose>
```

## 3. Steps

### 3.1 Prerequisites

### Step 1 — `<title>`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** following the Git conventions in CLAUDE.md.
- **R:** R1, R3 (or —)
- **Model:** `<model · effort>` (or —)
- **Gate:** `<condition>` → `<consequence>`

#### Scope

#### Reads

#### Do

#### Check

### Step N — Conclusion

## 4. Findings

### F1. `<one-line statement>`

Step N · YYYY-MM-DD · `<source of evidence>`

- `<evidence>`
- Consequence: `<for variants, steps or questions>`

### 4.1 Production inputs

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | | Step N · FN | |

## 5. Conclusion

Observed window: `<from–to, UTC; what it does not cover>`

### 5.1 Answers

- **Q1. Title** `<answer>` (FN)

### 5.2 Exit criteria

| Criterion | Kind | Result | Findings |
|---|---|---|---|

### 5.3 Verdict

### 5.4 Decisions to record

| D | Outcome | Why |
|---|---|---|

### 5.5 Not verified

- `<item>` — `<risk>` — `<mitigation>`

### 5.6 Follow-ups

- `<ADR or task>`

## 6. Sources

-
