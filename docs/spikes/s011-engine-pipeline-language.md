# Spike: Processing engine and pipeline language

- **Task:** T036
- **ADRs:** [ADR-0008](../decisions/0008-common-model-on-gbfs-3-0.md), [ADR-0018](../decisions/0018-medallion-architecture.md), [ADR-0019](../decisions/0019-own-lakehouse-on-cloudflare-r2.md), [ADR-0020](../decisions/0020-bronze-as-captured-objects.md), [ADR-0022](../decisions/0022-delta-lake-for-silver-and-gold.md), [ADR-0023](../decisions/0023-storage-security-baseline.md)
- **Code:** `spikes/engine-pipeline-language/`

## Status

- State: Draft 📝
- Phase: [ ] Questions · [ ] Method · [ ] Steps · [ ] Steps review
- Started: — · Finished: —
- Current step: —
- TODO(T036): decide the pipeline language (D3), then model the component's threats and add requirements to d002 (D4). If neither needs a run, propose closing the spike without Method and Steps.

## 1. Questions — what we need to know

### 1.1 Context

T036 decides the single-node processing engine, then the pipeline language, which depends on the engine, and models the component's threats to add requirements to [d002](../designs/d002-requirements.md#requirements). It builds on [s010](s010-storage-table-format.md), which set Delta Lake on Cloudflare R2 and showed that `deltalake` writes and MERGEs there and that Polars and DuckDB read the table. The engine is settled by documents and arithmetic, with no run. The pipeline language and the threat model are expected to be settled the same way.

### 1.2 Decided at framing

#### D1. Processing engine

**Decision: DuckDB, with Polars as the fallback.** DuckDB scores 8.1 out of 10 in the weighted matrix, against 6.8 for Polars. It leads on the two criteria that come directly from the workload: reading nested `json.gz` from R2 with window functions and as-of joins, and reading Delta natively with pruning. No run is needed, because the only unknown that could change the choice is settled by documents: DuckDB exports Arrow tables and `write_deltalake` accepts them (Sources).

What would change the engine:

| Event | Where it shows | Action |
|---|---|---|
| The hand-off from DuckDB to `deltalake` fails on real data and a `CAST` does not fix it | First slice of T040 | Move to Polars |
| A reference batch runs out of memory, even with smaller batches and spilling | First slice of T040, or the history load | Move to Polars, once confirmed that it copes |
| DuckDB's reads break R2's quota and a lower cadence no longer meets [d002 › R3](../designs/d002-requirements.md#requirements) | R2 metrics in production | Re-evaluate, measuring Polars too |

What would not change it:

| Event | Why not | Action |
|---|---|---|
| Type mismatches | Fixed in the query | `CAST` |
| Predicate overwrite fails | It belongs to `deltalake`, under any engine | Bounded MERGE |
| The Delta extension cannot read something in our tables | There is a second read path | Read with `deltalake` and hand over through Arrow |
| A DuckDB 2.0 bug | It belongs to the version, not the engine | Pin 1.5, supported until March 2027 |

A later change migrates no data, since Delta is an open format; only the transformations are rewritten.

Robustness: without portfolio value DuckDB leads 95 to 77, and without dbt fit 101 to 86. With Polars at 5 and DuckDB at 1 on portfolio value, Polars leads 102 to 100, the only case tested that reverses the result. Portfolio value is a reasoned judgement, since no job-ad data exists per engine, and pandas's scores rest mostly on general knowledge. Rejected: Polars (second; O1 likely needs custom code and it has no solid dbt adapter), `clickhouse-local`, pandas and DataFusion (lower scores).

Decisions taken on the way:

- **MERGE on real volumes needs no run.** All surviving candidates hand it to `deltalake`, so it does not separate them. Silver averages about 80 MB of Parquet per day ([s010 › Q1](s010-storage-table-format.md#answers)), and about 300 MB at the ×3.8 break-even of vehicles' estimated bytes per row ([s010 › F24](s010-storage-table-format.md#4-findings)), so a MERGE bounded to one day stays near 3 GB in memory, assuming ×10 over Parquet.
- **DuckDB's reads are not counted before choosing.** This replaces the mitigation in [s010 › Not verified](s010-storage-table-format.md#not-verified), because no count would change the choice. On demand, the pipeline uses 3.7% of R2's free Class B quota. The risk appears only at 24/7 every 10 minutes, which reaches €2 at ×2.1 reads per file ([s010 › F24](s010-storage-table-format.md#4-findings)), and a lower commit cadence reverses it. Its reads are measured in production through R2's per-bucket metrics.

Inputs for T040:

- Choose between partition overwrite and a bounded MERGE, and confirm predicate overwrite on R2.
- Use `to_arrow_table` or `to_arrow_reader`: DuckDB 2.0 removed `fetch_arrow_table` and similar methods after `con.execute()`.
- Read in batches through `con.sql()`, since after `con.execute()` the whole query runs before the first batch.
- Check whether the installed `deltalake` expects `aws_conditional_put` or `conditional_put`, since sources differ.
- Pin DuckDB after the November 2.0 patch ([ADR-0016](../decisions/0016-runtime-versions-pinned-per-component.md)).

Evaluation behind the decision follows.

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
| Delta read on R2 (4) | Cannot filter: downloads the whole table | Filters by partition, but only through `deltalake` or custom code | Reads Delta natively, filters by partition and file statistics, and works with S3-compatible endpoints |
| Maturity (3) | ≥ 1.0, but something needed is experimental | ≥ 1.0, with what is needed stable but recent (under 6 months) | Over 2 years since 1.0, with what is needed stable and well documented |
| Operational simplicity (3) | Needs a running service | A separate binary, or needs extra setup | An in-process library, installed with the dependencies and testable locally with no infrastructure |
| Memory behaviour (3) | In memory only | Spills to disk for some operations, or not by default | Spills to disk across O1–O8, with a configurable limit |
| dbt fit (3) | No maintained adapter | Maintained adapter, but writing Delta needs custom code | Maintained adapter and incremental Delta writes on S3-compatible storage |
| Learning value (2) | No new concepts | One new core concept | Several, such as a query optimizer, vectorized execution or out-of-core processing |

Scores (total = Σ score × weight, maximum 135, normalised to 0–10), with facts checked on 2026-11-01:

| Criterion (weight) | DuckDB | Polars | `clickhouse-local` | pandas | DataFusion |
|---|---|---|---|---|---|
| Portfolio value (5) | 3: recognised, 3.3% in Stack Overflow 2025 | 3: recognised; no comparable survey figure | 3: recognised, 2.4% in Stack Overflow 2025 | 4: widely known | 1: not in the survey |
| Workload fit (4) | 5: `read_json` on `json.gz` from R2, `UNNEST`, windows, `ASOF JOIN` | 3: windows and `join_asof`; gzip not documented, so O1 likely needs custom Python | 4: `s3()` detects gzip, `ASOF JOIN`, `lagInFrame`; nested files likely need `JSONExtract` | 3: `shift`, `merge_asof`; JSON handled in Python | 2: windows, no as-of join in a release; nested single objects not confirmed |
| Delta read on R2 (4) | 5: native, partition and statistics pruning; read the table on R2 ([s010 › F18](s010-storage-table-format.md#4-findings)) | 4: `scan_delta` read the table on R2 (F18); open issue on file skipping | 3: native, but pruning not documented and R2 not officially documented | 3: only through `deltalake` | 3: through `deltalake` providers; not confirmed on R2 |
| Maturity (3) | 3: 1.0 in 2024, but 2.0 is 11 days old and its notes advise waiting for the November patch for critical workloads | 3: 1.0 in 2024, but 2.0 and out-of-core work are under a month old | 4: long-standing, stable engine; calendar versions | 5: stable for years | 3: no 1.0 line; spill work is recent |
| Operational simplicity (3) | 5: in-process library | 5: in-process library | 3: separate binary, called as a subprocess | 5: in-process library | 5: in-process library |
| Memory behaviour (3) | 4: sort, group by, join and windows spill, with exceptions such as `string_agg` | 3: on by default; joins not confirmed | 3: opt-in per operator; windows not confirmed | 1: in memory only | 2: sort and some joins; windows buffer in memory |
| dbt fit (3) | 3: `dbt-duckdb` is maintained; writing Delta needs custom code | 2: `dbt-polars` is Beta, with one maintainer | 1: `dbt-clickhouse` needs a server and does not mention Delta | 1: no adapter | 1: `dbt-datafusion` is an abandoned scaffold |
| Learning value (2) | 5: optimizer, vectorized execution, out-of-core | 5: optimizer, lazy evaluation, out-of-core | 4: optimizer, vectorized execution | 1: no new concepts | 5: logical and physical plans, vectorized execution |
| **Total** | **110 → 8.1** | **92 → 6.8** | **84 → 6.2** | **82 → 6.1** | **68 → 5.0** |

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

#### D3. Pipeline language

The pipeline language covers two things: the host language, which reads from R2, calls DuckDB and hands results to `deltalake`, and the form in which transformations are written, which DuckDB executes.

**Host language: Python.** [d002 › Context](../designs/d002-requirements.md#context) names Python as part of what the portfolio shows, and MERGE depends on `deltalake` (D1), whose bindings are Python and Rust. Rust is not scored, because no result would change the choice.

TODO(T036): decide the form of the transformations with a weighted decision matrix.

Needs the form must cover:

| # | Need | Source |
|---|---|---|
| N1 | Express O3–O7: cleaning, comparison with the previous reading, episodes that span batches, gaps against a time grid, aggregates in local time | D1 workload, [d002 › Q2–Q7, R12](../designs/d002-requirements.md#guiding-questions) |
| N2 | Flatten bronze's nested JSON (O1) and read the Bicing archives (O2) | [ADR-0008](../decisions/0008-common-model-on-gbfs-3-0.md), [d002 › R5, R9](../designs/d002-requirements.md#requirements) |
| N3 | Use the same logic for the incremental batch and for a rebuild from bronze, changing only the data range | [d002 › R11, R13](../designs/d002-requirements.md#requirements) |
| N4 | Be tested before the code is written, locally and with no infrastructure | [Testing strategy](../testing-strategy.md) |
| N5 | Follow the practice of a company data team and show data engineering skills | [d002 › Context](../designs/d002-requirements.md#context) |
| N6 | Leave T040 free to decide where dbt applies | 1.5 Out of scope |
| N7 | Let T042 add data quality rules at any layer and record their results as measures, without rewriting transformations; T042 decides where the rules live and their format | [d002 › Q2](../designs/d002-requirements.md#guiding-questions), [task T042](../tasks.md) |

Candidates:

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

Checked on 2026-11-01. Further facts in D1 come from each project's current documentation and release notes.

- DuckDB: [2.0 announcement](https://duckdb.org/2026/10/21/announcing-duckdb-200), [Delta extension](https://duckdb.org/docs/2.0/core_extensions/delta.html), [export to Arrow](https://duckdb.org/docs/2.0/guides/python/export_arrow.html), [loading JSON](https://duckdb.org/docs/2.0/data/json/loading_json.html), [S3 API](https://duckdb.org/docs/2.0/core_extensions/httpfs/s3api.html), [tuning workloads](https://duckdb.org/docs/2.0/guides/performance/how_to_tune_workloads.html).
- `deltalake`: [writing](https://delta-io.github.io/delta-rs/latest/usage/writing/), [`DeltaTable`](https://delta-io.github.io/delta-rs/latest/api/delta_table/), [S3-like stores](https://delta-io.github.io/delta-rs/latest/integrations/object-storage/s3-like/), [issue #4614](https://github.com/delta-io/delta-rs/issues/4614).
- Polars: [2.0.0](https://github.com/pola-rs/polars/releases/tag/py-2.0.0) and [2.1.0](https://github.com/pola-rs/polars/releases/tag/py-2.1.0) release notes.
- ClickHouse: [`deltaLake` table function](https://clickhouse.com/docs/sql-reference/table-functions/deltalake), [spill settings](https://clickhouse.com/docs/reference/settings/session-settings/max-bytes.md).
- DataFusion: [configuration](https://datafusion.apache.org/user-guide/configs.html), [window spill discussion](https://github.com/apache/datafusion/discussions/26425).
- dbt: [`dbt-duckdb`](https://github.com/duckdb/dbt-duckdb), [`dbt-polars`](https://pypi.org/project/dbt-polars/), [`dbt-clickhouse`](https://github.com/ClickHouse/dbt-clickhouse), [`dbt-datafusion`](https://libraries.io/pypi/dbt-datafusion), [licensing](https://docs.getdbt.com/docs/dbt-licensing).
- Market: [Stack Overflow Developer Survey 2025](https://survey.stackoverflow.co/2025/technology).
