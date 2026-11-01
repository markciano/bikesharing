# Spike: Processing engine and pipeline language

- **Task:** T036
- **ADRs:** [ADR-0008](../decisions/0008-common-model-on-gbfs-3-0.md), [ADR-0018](../decisions/0018-medallion-architecture.md), [ADR-0019](../decisions/0019-own-lakehouse-on-cloudflare-r2.md), [ADR-0020](../decisions/0020-bronze-as-captured-objects.md), [ADR-0022](../decisions/0022-delta-lake-for-silver-and-gold.md), [ADR-0023](../decisions/0023-storage-security-baseline.md)

## Status

- State: Concluded ✅
- Phase: [x] Questions · Method, Steps and Steps review do not apply: triage leaves no run
- Started: 2026-11-01 · Finished: 2026-11-01
- Current step: —
- TODO(T036): record the engine, the pipeline language and the budget split in one commit each: the ADR together with its lines in `docs/architecture.md`. Propose a line in the `/spike` skill that fixes this order, after reading `spike.md` in `/implement`: what cites only requirements goes with its decision; what cites an ADR goes after the spike closes and the ADR exists. Then take the task to ✅.

## 1. Questions — what we need to know

### 1.1 Context

T036 decides the single-node processing engine, then the pipeline language, which depends on the engine, and models the component's threats to add requirements to [d002](../designs/d002-requirements.md#requirements). It builds on [s010](s010-storage-table-format.md), which set Delta Lake on Cloudflare R2 and showed that `deltalake` writes and MERGEs there and that Polars and DuckDB read the table. The engine, the pipeline language and the threat model are settled by documents and arithmetic, with no run.

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

**Transformations: SQL.** Models in `.sql` files, which DuckDB executes. Python only directs: it runs the models in order, extracts the `.7z` archives if DuckDB cannot read them directly, and hands results to `deltalake`. SQL scores 9.1 out of 10 in the weighted matrix, against 8.7 for Mixed and 6.0 for DuckDB's Python API. No operation in O1–O7 was found that SQL does not cover, and without one Mixed is the same as SQL. No run is needed, because no result would change the choice: if parameters do not work in file paths, SQL and Mixed drop equally on Reuse and SQL still leads.

What would change the form:

| Event | Where it shows | Action |
|---|---|---|
| A transformation cannot be written in SQL | T040 | Only that step goes to Python, with the reason documented |

Robustness: without Team practice, SQL leads Mixed and the Python API 84 to 79 and 62, and without Learning curve 99 to 96 and 68. With Team practice inverted (SQL at 1, Python API at 5), SQL still leads the Python API 89 to 87. Team practice is a reasoned judgement, since no job-ad data exists per form and the survey figure measures SQL use in general, not in data teams. Learning curve reflects the owner's skills: very strong SQL, basic Python. Ibis, even if fixed, would score 86 against SQL's 109, so it is not worth waiting for. Rejected: Mixed (second; same as SQL unless an operation falls short), DuckDB's Python API (lower score; windows and joins still need SQL strings) and Ibis (fails C4).

Inputs for T040:

- Check whether `con.sql()` accepts parameters: D1 reads batches through `con.sql()`, but the documentation read confirms parameters only for `execute()`.
- Check whether parameters work in `read_json` file paths; the documentation read shows them only as values.
- Check that `dbt-duckdb` is compatible with DuckDB 2.0, which requires Python 3.11 or newer.

Evaluation behind the decision follows.

Needs the form must cover:

| # | Need | Source |
|---|---|---|
| N1 | Express O3–O7: cleaning, comparison with the previous reading, episodes that span batches, gaps against a time grid, aggregates in local time | D1 workload, [d002 › Q2–Q7, R12](../designs/d002-requirements.md#guiding-questions) |
| N2 | Flatten bronze's nested JSON (O1) and read the Bicing archives (O2) | [ADR-0008](../decisions/0008-common-model-on-gbfs-3-0.md), [d002 › R5, R9](../designs/d002-requirements.md#requirements) |
| N3 | Use the same logic for the incremental batch and for a rebuild from bronze, changing only the data range | [d002 › R11, R13](../designs/d002-requirements.md#requirements) |
| N4 | Be tested before the code is written, locally and with no infrastructure | [Testing strategy](../testing-strategy.md) |
| N5 | Follow the practice of a company data team and show data engineering skills | [d002 › Context](../designs/d002-requirements.md#context) |
| N6 | Leave T040 free to decide where dbt applies | 1.3 Out of scope |
| N7 | Let T042 add data quality rules at any layer and record their results as measures, without rewriting transformations; T042 decides where the rules live and their format | [d002 › Q2](../designs/d002-requirements.md#guiding-questions), [task T042](../tasks.md) |

Candidates:

| # | Candidate | What it is |
|---|---|---|
| A | SQL | Models in `.sql` files that Python runs in order |
| B | DuckDB's Python API | Chained operations on DuckDB relations |
| C | Ibis | Python library that writes transformations as DataFrames and translates them for the engine |
| D | Mixed | SQL by default, Python only where SQL falls short |

dbt is not a candidate: it manages SQL or Python rather than being a form of writing them, and T040 decides where it applies.

Hard cuts:

| # | Cut | Source |
|---|---|---|
| C4 | Runs on DuckDB and hands its result to `deltalake` through Arrow | D1 |
| C5 | Open source, with no per-use cost and with stable, maintained releases | [d002 › R4](../designs/d002-requirements.md#requirements), as in C3 |

Anchors (2 and 4 are in between):

| Criterion (weight) | Need | 1 | 3 | 5 |
|---|---|---|---|---|
| Team practice (5) | N5 | Rare in data teams and job ads | Recognised, used by some teams | Common standard in data teams |
| Workload fit (4) | N1, N2 | Some operation in O1–O7 cannot be expressed without leaving this form | All can be expressed, some with workarounds or fragments of another language | All are expressed directly with the form's own constructs |
| Testing (3) | N4 | Tested only by running the whole pipeline | Each transformation is tested locally, with substantial custom scaffolding | Each transformation is tested in isolation with sample data in `pytest`, with little scaffolding and the test written first |
| Reuse (3) | N3 | Changing the data range requires duplicating logic | The range is injected through templates or text, with care | The range is a parameter of the tool itself, with no duplicated logic |
| Path to dbt (3) | N6 | Full rewrite | Part is rewritten or converted | Existing work becomes dbt models with minor changes |
| Data quality (3) | N7 | Rules go inside the transformations | Rules are separate, but storing their results needs custom code | Rules are separate pieces over any result, and their results are stored by the same mechanism as the data |
| Learning curve (2) | — | Requires mastering programming abstractions before being productive | The essentials are learned in weeks from official documentation | Well-documented concepts that map to those of a visual tool |
| Portability to Polars (1) | D1 | Full rewrite | Part is rewritten | Works unchanged |

Cut results (checked on 2026-11-01):

| Candidate | Result | Fact |
|---|---|---|
| A. SQL | Passes | DuckDB's native interface; `to_arrow_reader` hands the result to `deltalake` |
| B. DuckDB's Python API | Passes | Documented with no stability warning in 2.0, though with breaking changes |
| D. Mixed | Passes | Same as A and B |
| C. Ibis | Fails C4 | No release supports DuckDB 2.0: `to_pyarrow_batches` fails (issue 12196, open), with 35 of 51 export tests failing as reported there; the latest release is from February 2026 |

Scores (total = Σ score × weight, maximum 120, normalised to 0–10), with facts checked on 2026-11-01. Ibis is scored only to test whether a fix would be worth waiting for:

| Criterion (weight) | A. SQL | D. Mixed | B. Python API | C. Ibis (hypothetical) |
|---|---|---|---|---|
| Team practice (5) | 5: SQL at 58.6% in Stack Overflow 2025, and the basis of dbt | 5: same as A | 2: no usage data | 3: 3.3M downloads a month, users named by the project itself |
| Workload fit (4) | 5: `read_json`, `UNNEST`, windows, `ASOF JOIN`, `AT TIME ZONE` | 5: same as A | 3: windows and join conditions need SQL strings | 4: native `lag` and `asof_join`; time zones not confirmed |
| Testing (3) | 4: in-memory database and `pytest`, with no official guide | 4: same as A | 4: same as A | 5: native `ibis.memtable` |
| Reuse (3) | 4: `$name` parameters work for values; file paths not confirmed | 4: same as A | 5: function parameters | 5: function parameters |
| Path to dbt (3) | 5: a `SELECT` is a model; `ref()` replaces table names | 4: Python parts become Python models | 3: Python models, or a manual rewrite | 3: community `dbt-ibis`, status not confirmed |
| Data quality (3) | 4: a rule is a `SELECT`; storing results needs a small runner | 4: same as A | 3: tools consume mostly SQL | 3: Pandera, described as less mature |
| Learning curve (2) | 5: very strong SQL | 4: Python parts rely on basic Python | 2: Python, with only a method reference | 2: a tutorial for SQL users, but still Python |
| Portability to Polars (1) | 3: Polars SQL has `LAG` and `UNNEST`; `ASOF` uses another syntax | 3: same as A | 1: no path | 3: own backend, with 9 of 22 queries failing in a 2024 benchmark |
| **Total** | **109 → 9.1** | **104 → 8.7** | **72 → 6.0** | **86 → 7.2** |

#### D4. Pipeline security

**Decision: five new requirements, [d002 › R19–R23](../designs/d002-requirements.md#requirements), and the other threats documented without a requirement.** Threats are listed with STRIDE and controls follow least privilege, as in [s010 › D7](s010-storage-table-format.md#d7-storage-security-baseline). The scope is the engine and the pipeline code. [ADR-0023](../decisions/0023-storage-security-baseline.md) and R15–R18 cover tokens, buckets and the bronze lock, and T037 covers where the pipeline runs, how it receives secrets and its network.

| # | Threat (STRIDE) | Impact | Control | Requirement |
|---|---|---|---|---|
| A1 | A value from a feed or archive ends up inside a query (Tampering) | Unplanned SQL runs with the pipeline's token; `sql()` accepts several statements in one string | Run only SQL versioned in the repository; captured values never enter the query text | R19 |
| A2 | Unplanned SQL reads or writes beyond what the pipeline needs (Elevation of privilege) | DuckDB can reach local and remote files | Prevented by R19 and bounded by R15 and R17; restricting DuckDB's paths is hardening to try in T040 | None |
| A3 | An altered extension or dependency, since DuckDB can download extensions at run time (Tampering) | Third-party code runs with the pipeline's credentials | Pinned versions ([ADR-0017](../decisions/0017-dependencies-locked-per-component.md)), installed ahead of the run; no downloads at run time | R20 |
| A4 | A malicious or corrupt `.7z`: decompression bomb or paths outside the folder (Denial of service, Tampering) | Full disk or overwritten files | Size limit and a bounded folder; the archive is rejected and recorded as a gap (R9) | R21 |
| A5 | Credentials end up in logs, queries or engine files (Information disclosure) | Same as a leaked credential in [ADR-0023](../decisions/0023-storage-security-baseline.md) | Credentials held only in memory, never in logs or query text | R22 |
| A6 | A failure or loop repeats reads and writes with no end (Denial of service) | R2 cost breaks R4 (denial of wallet) | Limited retries and a time limit, with an alert to the owner | R23 |
| A7 | A bug or a leak corrupts silver or gold (Tampering) | Wrong data published | Rebuilt from bronze (R13); damage bounded by R15 and R17 | None |
| A8 | No way to tell which run changed what (Repudiation) | Low: there is one operator | Accepted: Delta's commit log gives a basic trace | None |
| A9 | Data leaks through DuckDB's temporary files (Information disclosure) | Low: the data comes from public feeds | Accepted; reviewed in T037 once it is known where the pipeline runs | None |
| A10 | Something impersonates a party the pipeline deals with (Spoofing) | Considered, with no threat specific to this component | The pipeline exposes no entry point; spoofed feeds belong to capture and the pipeline's identity on its machine to T037 | None |

Restricting DuckDB's paths (A2) is not a requirement, because it may not be achievable with R2 and Delta today, and a DuckDB maintainer commented that these settings do not replace real sandboxing against untrusted SQL (issue 24695):

- The allow-lists grant write as well as read (issue 28083, reproduced on 2.0.0).
- Allowing `s3://` prefixes depends on a fix merged in October 2026 that is not confirmed in the released package; `r2://` and the `delta` extension are not confirmed either.
- HTTPS under the lock requires allow-listing the CA bundle path, which SQL can then write to.

Risk kept: unplanned SQL could still touch local files if R19 were ever broken.

No run is needed: the open checks go to T040, and none changes what is required.

Inputs for T040:

- Try restricting DuckDB's paths with `enable_external_access` on R2 and Delta, as hardening.
- Disable `autoinstall_known_extensions` and `allow_community_extensions`, which are on by default. List the extensions the installed package already includes with `duckdb_extensions()`, and install the others ahead of the run.
- Use `py7zr` 1.1.4 or newer if it extracts the archives, and set `max_extract_size` explicitly, since its default is not confirmed.
- Use temporary secrets, since persistent ones are stored unencrypted. Check that credentials do not reach logs, since their redaction in logs is not confirmed and `deltalake` logs store details at debug level.
- Set the time limit with `interrupt()` or in T037's execution target, since DuckDB documents no query timeout.

Requirements transferred to [d002 › Requirements](../designs/d002-requirements.md#requirements):

| R | Threat | Evidence |
|---|---|---|
| R19 | A1 | [DuckDB Python DB API](https://duckdb.org/docs/2.0/clients/python/dbapi.html) passes values separately from the SQL text |
| R20 | A3 | [DuckDB securing guide](https://duckdb.org/docs/2.0/operations_manual/securing_duckdb/overview.html): extensions run with the process's privileges, and automatic installation can be disabled |
| R21 | A4 | [`py7zr` changelog](https://py7zr.readthedocs.io/en/latest/Changelog.html): recent fixes for path traversal and decompression bombs |
| R22 | A5 | [DuckDB secrets manager](https://duckdb.org/docs/2.0/configuration/secrets_manager.html): temporary secrets stay in memory, persistent ones are unencrypted files |
| R23 | A6 | [DuckDB configuration](https://duckdb.org/docs/2.0/configuration/overview.html): no query timeout among the settings read; the gap in R8, which alerts only on capture |

### 1.3 Out of scope

- Partition overwrite or MERGE, batch size, commit cadence and state between batches (T040).
- Where dbt applies, if anywhere: T040 decides it, and the owner wants to use it where it can be justified.
- Where the pipeline runs and what schedules it (T037).
- Data quality checks beyond the basics (T042).

## 2. Conclusion

### 2.1 Verdict

The single-node engine is DuckDB, with Polars as the fallback. The pipeline is SQL models directed by Python, with `deltalake` writing the Delta tables. Documents and arithmetic settled every decision, so nothing was run; this spike has no Method, Steps or Findings.

### 2.2 Decisions to record

| D | Outcome | Why |
|---|---|---|
| D1 | DuckDB, with Polars as the fallback | 8.1 against 6.8 in the weighted matrix; it leads on the two criteria that come directly from the workload |
| D2 | €10 per month: capture €0, storage €2, pipeline €4, visualization €2, reserve €2 | The pipeline may need an always-on machine; the reserve absorbs the exchange rate and deviations |
| D3 | Python as host, transformations as SQL models | 9.1 against 8.7 for Mixed and 6.0 for DuckDB's Python API; no operation in O1–O7 needs anything else |
| D4 | R19–R23, with the other threats documented without a requirement | Threats listed with STRIDE; controls follow least privilege |

### 2.3 Not verified

- The hand-off from DuckDB to `deltalake` on real data — a type mismatch, or a failure that a `CAST` does not fix — the first slice of T040 tries it; D1 moves to Polars if it fails.
- Memory on a reference batch — running out of memory even with smaller batches and spilling — the first slice of T040 or the history load measures it; D1 moves to Polars once confirmed that it copes.
- `$name` parameters in `con.sql()` and in `read_json` file paths — less reuse across models — T040 checks them; D3 holds either way.
- Restricting DuckDB's paths on R2 and Delta — unplanned SQL could touch local files if R19 were ever broken — T040 tries it as hardening.

### 2.4 Follow-ups

- ADRs to write, each in its own commit with its lines in `docs/architecture.md`: processing engine (D1), pipeline language (D3) and budget shares (D2).
- T040 picks up the inputs listed in D1, D3 and D4.
- T037 works within the pipeline share and reviews A9; T038 validates the visualization share.

## 3. Sources

Checked on 2026-11-01. Further facts in D1 come from each project's current documentation and release notes.

- DuckDB: [2.0 announcement](https://duckdb.org/2026/10/21/announcing-duckdb-200), [Delta extension](https://duckdb.org/docs/2.0/core_extensions/delta.html), [export to Arrow](https://duckdb.org/docs/2.0/guides/python/export_arrow.html), [loading JSON](https://duckdb.org/docs/2.0/data/json/loading_json.html), [S3 API](https://duckdb.org/docs/2.0/core_extensions/httpfs/s3api.html), [tuning workloads](https://duckdb.org/docs/2.0/guides/performance/how_to_tune_workloads.html).
- `deltalake`: [writing](https://delta-io.github.io/delta-rs/latest/usage/writing/), [`DeltaTable`](https://delta-io.github.io/delta-rs/latest/api/delta_table/), [S3-like stores](https://delta-io.github.io/delta-rs/latest/integrations/object-storage/s3-like/), [issue #4614](https://github.com/delta-io/delta-rs/issues/4614).
- Polars: [2.0.0](https://github.com/pola-rs/polars/releases/tag/py-2.0.0) and [2.1.0](https://github.com/pola-rs/polars/releases/tag/py-2.1.0) release notes.
- ClickHouse: [`deltaLake` table function](https://clickhouse.com/docs/sql-reference/table-functions/deltalake), [spill settings](https://clickhouse.com/docs/reference/settings/session-settings/max-bytes.md).
- DataFusion: [configuration](https://datafusion.apache.org/user-guide/configs.html), [window spill discussion](https://github.com/apache/datafusion/discussions/26425).
- dbt: [`dbt-duckdb`](https://github.com/duckdb/dbt-duckdb), [`dbt-polars`](https://pypi.org/project/dbt-polars/), [`dbt-clickhouse`](https://github.com/ClickHouse/dbt-clickhouse), [`dbt-datafusion`](https://libraries.io/pypi/dbt-datafusion), [licensing](https://docs.getdbt.com/docs/dbt-licensing).
- Market: [Stack Overflow Developer Survey 2025](https://survey.stackoverflow.co/2025/technology).
- DuckDB, for D3: [Python migration to 2.0](https://duckdb.org/docs/2.0/clients/python/migration.html), [relational API](https://duckdb.org/docs/2.0/clients/python/relational_api.html), [prepared statements](https://duckdb.org/docs/2.0/sql/query_syntax/prepared_statements.html), [Python DB API](https://duckdb.org/docs/2.0/clients/python/dbapi.html), [`ASOF JOIN`](https://duckdb.org/docs/2.0/guides/sql_features/asof_join.html), [time zones](https://duckdb.org/docs/2.0/sql/functions/timestamptz.html).
- Ibis: [release notes](https://ibis-project.org/release_notes), [issue 12196](https://github.com/ibis-project/ibis/issues/12196), [DuckDB backend](https://ibis-project.org/backends/duckdb), [2024 benchmark](https://ibis-project.org/posts/ibis-bench/), [download statistics](https://pypistats.org/packages/ibis-framework), [`dbt-ibis`](https://pypi.org/project/dbt-ibis/0.7.0/).
- Polars SQL: [functions](https://docs.pola.rs/api/python/stable/reference/sql/functions/index.html), [clauses](https://docs.pola.rs/api/python/stable/reference/sql/clauses.html).
- Data quality: [dbt data tests](https://docs.getdbt.com/docs/build/data-tests), [Pandera with Ibis](https://pandera.readthedocs.io/en/stable/ibis.html).
- Security, for D4: [DuckDB issue 28083](https://github.com/duckdb/duckdb/issues/28083), [DuckDB PR 27412](https://github.com/duckdb/duckdb/pull/27412), [DuckDB issue 24695](https://github.com/duckdb/duckdb/issues/24695), [DuckDB extensions](https://duckdb.org/docs/2.0/extensions/installing_extensions.html).
