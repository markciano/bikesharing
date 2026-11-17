# Spike: dbt in the pipeline

- **Task:** T060.7
- **ADRs:** [ADR-0022](../decisions/0022-delta-lake-for-silver-and-gold.md), [ADR-0024](../decisions/0024-duckdb-as-processing-engine.md), [ADR-0025](../decisions/0025-sql-models-directed-by-python.md), [ADR-0042](../decisions/0042-data-quality-classes-and-severity.md), [ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md), [ADR-0046](../decisions/0046-functional-core-imperative-shell-for-the-pipeline.md)
- **Code:** `spikes/dbt-in-the-pipeline/`

## Status

- State: Concluded ✅
- Phase: [x] Questions · [x] Method · [x] Steps · [x] Steps review · [x] Conclusion
- Started: 2026-11-17 · Finished: 2026-11-17
- Current step: —

## 1. Questions — what we need to know

### 1.1 Context

This spike decides where dbt applies in the pipeline and which tool runs its runtime rules, as [d007 › Children](../designs/d007-pipeline-design.md#16-children) asks of T060.7, by a fit-gap analysis of dbt against the decisions in force: the engine and language of [s011](s011-engine-pipeline-language.md), the code architecture of [s015](s015-pipeline-code-architecture.md) and the catch-up and quality rules of [d007](../designs/d007-pipeline-design.md). Analysis and the documentation settle the shape (D1), the release line (D2), how SQL is tested (D3) and how dbt's events are logged (D4). What only a run can settle is the friction of the glue between dbt and the rest: whether `dbt-duckdb` works on DuckDB 2.0, how the shell invokes dbt and hands its result to `deltalake`, whether dbt unit tests run on DuckDB, and which events dbt emits. The owner wants to adopt dbt, for what it brings and for learning; the thresholds of friction are fixed before the run, so that this wish does not decide the result.

### 1.2 Decided at framing

#### D1. dbt builds and audits, Python plans and publishes

dbt runs every SQL model and runtime rule of the pipeline, for one batch at a time, in a scratch DuckDB database discarded at the end of the run. Python keeps what lies at the edges of the SQL: the core plans the batch ([ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md)) and turns dbt's results into a verdict; the shell invokes dbt with the batch's window as variables and, only if the audit passes, writes the batch to Delta on R2 with `deltalake`. This is Write-Audit-Publish: dbt writes to the scratch database and audits it, the shell publishes. dbt replaces what the pipeline would otherwise build itself: the ordered runner of [ADR-0025](../decisions/0025-sql-models-directed-by-python.md), the parameters in bronze file paths that ADR-0025 left unconfirmed, the column schema checks, the runner of runtime rules of [ADR-0046](../decisions/0046-functional-core-imperative-shell-for-the-pipeline.md) (rule 8), the scaffolding of SQL tests, and the table-level lineage written by hand ([ADR-0043](../decisions/0043-lineage-at-four-levels.md)). It depends on Q1 and Q2: if either Gate fails, the pipeline has no dbt and ADR-0025 stands as it is.

What would change it:

- Q1's or Q2's Gate fails: no dbt; ADR-0025 and ADR-0046 stand unchanged.
- A `dbt-duckdb` release writes Delta with MERGE or partition overwrite and tests before it publishes: dbt could write Delta itself; weigh option B again.

What would not: the lineage seam at the hand-off to Delta. dbt's lineage covers only the table level of ADR-0043, and exposures and sources can join the graph across the hand-off.

Options rejected:

- **B. dbt writes Delta itself,** through Python models or a custom materialization that calls `deltalake`: it writes to R2 while the batch is built, before its tests run, which is the opposite of Write-Audit-Publish; dbt's contracts do not apply to Python models, so the model that writes Delta has none; the writes, their credentials and retries move inside dbt, out of the shell of ADR-0046; no published example of such a materialization was found.
- **No dbt:** the simplest, and reversible from D1, since dbt models stay `SELECT` statements; it keeps the fallback role, and loses the pieces dbt replaces.
- **DuckLake instead of Delta,** which `dbt-duckdb` writes natively with MERGE: it reopens [ADR-0022](../decisions/0022-delta-lake-for-silver-and-gold.md) to gain a seamless lineage graph and incremental features that ADR-0045 already covers in its own way, adds a metadata database to run, and still neither tests before it publishes nor bounds batches in bytes.

The result is robust to the facts gathered: both gaps, Delta writes and Write-Audit-Publish, close with the same split, and the only unknown left is the friction of the glue, which Q1 and Q2 measure.

Fit-gap of dbt against the decisions in force (facts as of 2026-11-17, sources in [Sources](#6-sources)):

| # | Decision in force | Result | Fact |
|---|---|---|---|
| G1 | DuckDB 2.0 ([ADR-0024](../decisions/0024-duckdb-as-processing-engine.md)) | Unknown, Q1 | `dbt-duckdb` 1.11.1 does not cap DuckDB, but tests DuckDB 2.0 only in nightly CI, with no support statement |
| G2 | Delta on R2 ([ADR-0022](../decisions/0022-delta-lake-for-silver-and-gold.md)) | Gap in dbt; fit with the shell writing | The `delta` plugin only reads; external models write parquet, csv or json, with no incremental; DuckDB's `delta` extension only appends |
| G3 | Python directs ([ADR-0025](../decisions/0025-sql-models-directed-by-python.md), [ADR-0046](../decisions/0046-functional-core-imperative-shell-for-the-pipeline.md)) | Fit | `dbtRunner` is a supported entry point, safe for sequential invocations in one process; its result objects are not a stable contract |
| G4 | Bounded batches ([ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md)) | Adaptation | Microbatch splits by time only and needs tables dbt manages; the core keeps planning batches and passes their capture range to dbt |
| G5 | Write-Audit-Publish and quarantine ([ADR-0042](../decisions/0042-data-quality-classes-and-severity.md), d007 #1, #9) | Gap in dbt; fit with the shell publishing | dbt tests a model after materializing it and has no native WAP or quarantine; a quarantine model in SQL holds the failing rows |
| G6 | Lineage ([ADR-0043](../decisions/0043-lineage-at-four-levels.md)) | Fit, table level only | dbt Core generates table-level lineage; column-level lineage is a paid feature |
| G7 | SQL tests ([testing strategy](../testing-strategy.md)) | Adaptation | dbt unit tests exist since dbt-core 1.8; their behaviour on `dbt-duckdb` is unconfirmed |
| G8 | Logs ([ADR-0036](../decisions/0036-log-convention-across-components.md)) | Adaptation | A `dbtRunner` callback receives every event and can forward it to Python's logging |

#### D2. dbt v1: `dbt-core` 1.12 with `dbt-duckdb`

The pipeline uses dbt's v1 line, `dbt-core` 1.12 (Apache 2.0, supported until 2027-07-15) with the `dbt-duckdb` adapter, following the practice of running the stable, supported release line rather than a beta. It is the only line that covers today what D1 needs: a stable DuckDB adapter, extensions to read bronze on R2, `read_json` in staging models, and `dbtRunner` with callbacks for the shell.

What would change it: v2's DuckDB adapter leaving beta with extensions and a Python API. Then the pipeline moves to v2 before v1.12's end of support; the move is bounded, since models are SQL with Jinja, though v2 parses them more strictly. T070 checks it, starting three months before that date.

Option rejected: **v2** (Rust engine, released 2026-09-14, as the proprietary `dbt` or the Apache 2.0 `dbt-oss`), where new features land from now on. Its DuckDB adapter is in beta; its bundled driver loads no extensions without a system driver installed apart; its static analysis can fail on `read_json`; it has no callbacks and no manifest injection, and its Python API is in development. It fails three of D1's four needs, and no run could change that today.

| Need (D1) | v1 | v2 |
|---|---|---|
| DuckDB adapter | `dbt-duckdb` 1.11.1, stable | Built in, beta |
| Extensions (`httpfs`) to read bronze on R2 | Yes | Only with a system driver installed apart |
| `read_json` in staging models | Yes | Static analysis can fail |
| Invoked from the shell, with results and a log callback | `dbtRunner` with callbacks | No callbacks or manifest injection; Python API in development |

#### D3. SQL tested with dbt unit tests, Python with pytest

Each tool tests its own side, following the standard of a dbt project and the test pyramid: dbt unit tests verify each SQL model's logic on its own, with input rows and expected rows written by hand and no real data read; pytest verifies the Python core and shell as today ([testing strategy › Python](../testing-strategy.md#python-srcbikesharing)), plus an integration test in which the shell runs dbt on bronze fixtures and writes Delta to a local folder. The testing strategy gains a section for SQL (dbt) with its five answers, and CI runs both. dbt unit tests are written before the model, as Python tests are before their code. The local budget of under 1 s ([s008 › F37](s008-testing-conventions.md#4-findings)) cannot hold for dbt, whose start-up alone takes longer: dbt tests get a budget of their own, measured in Q3, which also confirms that dbt unit tests run on `dbt-duckdb`.

What would change it: Q3 finds that dbt unit tests do not run on `dbt-duckdb`. Then model logic is tested from pytest on the scratch database, as option B.

Option rejected: **B. pytest only,** each test running `dbt build` on fixtures and asserting on the resulting tables. One tool, but every test pays dbt's start-up, and it tests several models together instead of one.

#### D4. dbt's events translated into the log convention

The shell registers a callback on `dbtRunner` that receives each dbt event as it happens and forwards the relevant ones to Python's logging, which writes them in the convention of [ADR-0036](../decisions/0036-log-convention-across-components.md), with its common fields and an event name of the pipeline's own (such as `model_built` or `rule_checked`); dbt's `invocation_id` travels as a field of each event, and dbt writes no log of its own. The relevant events are a model started, a model finished with its status, rows and duration, a test finished with its failures, and errors. This follows the adapter pattern into one structured log stream, and keeps rule 7 of [ADR-0046](../decisions/0046-functional-core-imperative-shell-for-the-pipeline.md): the callback lives in the shell and only logs. A run that hangs or is killed in the middle of dbt still shows in its log the model it had reached. Which dbt event types carry these data is unconfirmed; Q4 confirms it.

What would change it: Q4 finds that the callback does not receive per-model and per-test results. Then the shell logs them from dbt's results once the invocation ends, and the log of a run killed inside dbt shows only that dbt started.

Option rejected: **B. dbt's own JSON log kept apart,** uploaded as a second file per run. No glue, but its events carry neither `component`, `version` nor `run_id`, so the query across components of ADR-0036 does not see them, and they could be joined only by time.

### 1.3 Questions

Main question: does dbt fit the pipeline as the layer that builds and audits its SQL (D1), with its glue below the thresholds of friction in Exit criteria?

- **Q1.** On DuckDB 2.0, do `dbt-core` 1.12 and `dbt-duckdb` 1.11 build a model that reads bronze JSON from R2 with the batch's window in its file path through `var()`, with an enforced contract, a runtime rule as a test with its severity, and a quarantine model for the rows that break the schema? Unblocks D1 and D2.
- **Q2.** Does the shell invoke that build through `dbtRunner` with the window in `--vars`, read each model's and test's result as values for the core, and hand the scratch table to `deltalake` as Arrow for a MERGE into a Delta table; and what does one invocation add to a run in time and peak memory? Unblocks D1.
- **Q3.** Do dbt unit tests run on `dbt-duckdb`, and how long does the dbt test suite take locally? Unblocks D3.
- **Q4.** Which dbt events reach a `dbtRunner` callback with a model's status, rows and duration and a test's failures? Unblocks D4.
- **Observe only:** how readable the compiled SQL and dbt's error messages are when a model fails.

### 1.4 Exit criteria

- **Standard:** fit-gap analysis of dbt against the decisions in force (ADRs and d007): each one is a fit, an adaptation (which decision changes, and its cost) or a gap; no ADR is fixed in advance, each is weighed by its impact.
- **Timebox:** one day of work (T060.7 is ef3). The run ends when Q1–Q4 are answered, or at the first hard cut that fails: Q1 or Q2 failing ends it with no dbt (D1).
- **Variants:** one, the shape of D1; meeting the hard cuts is enough, and the guides weigh how much glue it costs.
- **Guides:** with every hard cut met, one or two guides missed keep D1, with the extra cost recorded in the Conclusion; three or more reopen D1 with the owner, on the measured figures.
- **Q1 · Works on DuckDB 2.0:** the probe model builds on DuckDB 2.0 with its contract, its runtime rule as a test with its severity, and its quarantine model, with no patch to dbt or `dbt-duckdb` and no DuckDB pinned below 2.0 — hard cut.
- **Q1 · Window in the file path:** the model reads only the bronze objects of the window passed through `var()`, from R2 — hard cut.
- **Q2 · Results as values:** each model's and test's status and failures reach the shell from `dbtRunner`'s result or `run_results.json`, without parsing logs — hard cut.
- **Q2 · Hand-off to Delta:** the scratch table reaches `deltalake` as Arrow and its MERGE into a Delta table gives the expected rows — hard cut.
- **Q1–Q2 · No dbt internals:** the glue uses only `dbtRunner`, its documented result fields and dbt's documented artifacts; any other import from dbt is a failure — hard cut.
- **Q2 · Glue size:** at most 150 lines of Python, without tests or comments, for invocation, results, hand-off and callback, about the size of the runner of ADR-0025 that dbt replaces — guide.
- **Q2 · Time per invocation:** dbt adds at most 15 s to a run, under 2% of the 15-minute cadence — guide.
- **Q2 · Peak memory:** dbt adds at most 500 MB to a run's peak memory, a quarter of the 2 GB line by which d007 judges [ADR-0027](../decisions/0027-modal-as-execution-platform.md), so that dbt alone does not move a run across it — guide.
- **Q3 · Unit tests run:** a dbt unit test passes and fails as expected on `dbt-duckdb` — hard cut for D3, whose fallback is option B.
- **Q3 · Test suite time:** the probe's dbt tests run locally in at most 30 s — guide; it becomes dbt's local budget (D3).
- **Q4 · Results in the callback:** the callback receives each model's status, rows and duration and each test's failures — guide; D4 names the fallback.

### 1.5 Out of scope

- The move to dbt v2, when its DuckDB adapter covers what D2 needs — T070

## 2. Method — how we find out

### 2.1 Approach

One variant, the shape of D1, probed in three parts; A runs first, since it tests the riskiest assumption at the lowest cost and its Gate ends the run with no dbt if it fails.

| Probe | What it is | What it tells | Q |
|---|---|---|---|
| [A](#a-build-on-duckdb-20) | A minimal dbt project built with `dbt build` from the CLI | Whether dbt and `dbt-duckdb` work on DuckDB 2.0 with no patch | Q1 |
| [B](#b-shell-glue) | A Python script that runs A's build through `dbtRunner` and publishes to Delta | The friction of the glue: results, hand-off, callback, lines, time and memory | Q2, Q4 |
| [C](#c-unit-tests) | dbt unit tests on A's model | Whether dbt unit tests run on `dbt-duckdb`, and the suite's time | Q3 |

Q4 is part of B: the callback is registered on the same `dbtRunner` invocation that Q2 measures, so a probe of its own would repeat that run and tell nothing more.

A rough worst-case estimate settles none of the guides, so each is measured within B: dbt-core starts and parses a small project in about 2–5 s, which may approach 15 s in a cold container; its Python process adds about 150–300 MB, close enough to 500 MB to need a figure; the glue is expected at 80–120 lines, counted on B's code.

#### 2.1.1 Shared behaviour

- **One dbt project** serves the three probes, on DuckDB 2.0 with `dbt-core` 1.12 and `dbt-duckdb` 1.11 (D2).
- **Bronze is read from the real R2 bucket** with an R2 token scoped to read only, created for the spike and revoked at tear-down. **#1**
- **Nothing is written to R2:** the Delta table of B is a local folder. **#1**

#### A. Build on DuckDB 2.0

A dbt project with a base model that reads bronze JSON with the batch's window in its file path through `var()`, and two models on it: a staging model with an enforced contract and one runtime rule as a test with its severity, and a quarantine model for the rows that break the schema. It is built with `dbt build` from the CLI on DuckDB 2.0, with `dbt-core` 1.12 and `dbt-duckdb` 1.11 (D2). **#3**

#### B. Shell glue

A Python script that invokes A's build through `dbtRunner` with the window in `--vars`, reads each model's and test's result as values, hands the scratch table to `deltalake` as Arrow for a MERGE into a Delta table, and registers a callback that records every event it receives.

It measures what dbt adds to a run against a baseline: the same batch runs once as the SQL dbt compiled, executed directly on DuckDB and written to Delta, and once through `dbtRunner`. Each mode runs three times locally under `/usr/bin/time -l`; the median wall time and maximum resident set size of each mode are compared, and their difference is dbt's cost. The work DuckDB does is the same in both modes, so a small batch measures it. A local machine may be faster than a cold container on Modal; the Conclusion records this under Not verified. **#2**

#### C. Unit tests

dbt unit tests on A's staging and quarantine models, with the base model's rows mocked and expected rows written by hand, two written to pass and one to fail; the suite is timed locally. **#3**

### 2.3 Decision log

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| 1 | [Shared behaviour](#211-shared-behaviour) | Probes read the real bronze bucket with a read-only R2 token and write Delta locally (least privilege) | Tests the real path layout the window relies on, with no write access to production data | Method |
| 2 | [Probe B](#b-shell-glue) | dbt's time and memory measured against a baseline without dbt, locally, median of three runs (A/B benchmark with a baseline) | Isolates dbt's own cost from DuckDB's and `deltalake`'s work, which the guides do not count | Method |
| 3 | [Probe A](#a-build-on-duckdb-20), [Probe C](#c-unit-tests) | Bronze is read in a base model that the staging and quarantine models `ref()` (dbt base model, dbt style guide) | dbt unit tests mock only `ref()` and `source()` inputs; a `source` with `external_location` would add a `dbt-duckdb` unknown to Q1 | Steps review |
| 4 | [Step 8](#step-8--run-b-in-both-modes) | The owner runs Step 8's commands from one wrapper script that writes their output, `/usr/bin/time` included, to `out/step8.log` (adaptation of the Step protocol: how the result is reported, not what runs) | Seven runs with long outputs; the commands and the measurement stay as planned, and the credentials stay with the owner | Running step 8 |
| 5 | [Step 8](#step-8--run-b-in-both-modes) | Step 8 is done with rows missing from the events recorded as a result ([F9](#f9-dbt-duckdb-reports-no-rows-affected)), not as a failed run; Q4's guide is missed on rows (negative result as evidence) | dbt-duckdb returns no row count anywhere, so a rerun would not change it; D4's fallback covers it | Running step 8 |

### 2.4 File layout

```text
spikes/dbt-in-the-pipeline/
├── README.md                 Question, setup and commands per check, link to s017
├── pyproject.toml            Pins Python, dbt-core 1.12, dbt-duckdb 1.11, DuckDB 2.0, deltalake
├── uv.lock                   Locked dependencies
├── .env.example              R2 read-only token variables, empty values
├── .gitignore                Ignores .env, out/ and dbt's target/ and logs/
├── dbt_project/              The one dbt project shared by A, B and C
│   ├── dbt_project.yml
│   ├── profiles.yml          DuckDB scratch database, httpfs to R2 from env vars
│   └── models/staging/
│       ├── base_probe_read.sql       Probe A: reads bronze for the var() window, uncast
│       ├── stg_probe.sql             Probe A: typed rows that meet the schema
│       ├── stg_probe_quarantine.sql  Probe A: rows that break the schema
│       ├── stg_probe.yml             Probe A: contract and runtime rule with severity
│       └── stg_probe_unit.yml        Probe C: unit tests, two passing, one failing on purpose
├── shell_glue/
│   └── run_batch.py          Probe B: --mode dbt|baseline; dbtRunner, callback, MERGE to Delta
└── out/                      Ignored by Git: scratch databases, local Delta table, events, timings
```

The dbt project is shared by the three probes ([Shared behaviour](#211-shared-behaviour)), so it is not split into one subfolder per check; `shell_glue/` holds Probe B's script.

## 3. Steps

### 3.1 Prerequisites

- **uv 0.13.5** on the local machine; it installs Python 3.13 for the spike. Verify: `uv --version`.
- **R2 token for the spike,** in the Cloudflare dashboard: an R2 API token with Object Read only, scoped to the bronze bucket. Its access key ID, secret and the account's S3 endpoint go into `spikes/dbt-in-the-pipeline/.env`, once Step 1 has created `.env.example`. It is revoked at tear-down (#1).
- **One hour of bronze:** the bucket name, and the `<source>`, `<feed>`, date and UTC hour of one complete hour of one system's station status, under the key layout of [d004](../designs/d004-bronze-data-capture.md) (`raw/<source>/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz`), with the number of objects in that hour, read in the dashboard; reported back as the window of Probe A.
  - Window: bucket `bikesharing-bronze`, source `bicing`, feed `station_status`, date `2026-11-16`, hour `10` UTC, 60 objects.

Owner commands run from `spikes/dbt-in-the-pipeline/`; `<vars>` stands for the window reported in Prerequisites, as `--vars '{"source": "…", "feed": "…", "date": "YYYY-MM-DD", "hour": "HH"}'`, and `<dbt>` for `uv run --env-file .env dbt` with `--project-dir dbt_project --profiles-dir dbt_project` after the subcommand.

### Step 1 — Spike environment

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `chore: set up the environment of spike s017`
- **Model:** sonnet · medium

#### Scope

The spike's Python environment, unlocked: `pyproject.toml`, `.env.example`, `.gitignore` under `spikes/dbt-in-the-pipeline/`. Nothing outside that folder.

#### Reads

- [D2](#d2-dbt-v1-dbt-core-112-with-dbt-duckdb): the release lines to pin.
- [Shared behaviour](#211-shared-behaviour) and [File layout](#24-file-layout): what the folder holds and what Git ignores.
- `spikes/execution-target/pyproject.toml`: the shape of an earlier spike's `pyproject.toml`, to follow it.

#### Do

1. Write `pyproject.toml`: `requires-python = ">=3.13,<3.14"`; dependencies `dbt-core~=1.12.0`, `dbt-duckdb~=1.11.0`, `duckdb~=2.0.0`, `deltalake` and `pyarrow` at their latest releases. No pin is relaxed to make resolution pass: a failure to resolve is Step 2's evidence.
2. Write `.env.example` with empty `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT` and `R2_BUCKET`.
3. Write `.gitignore` with `.env`, `out/`, `dbt_project/target/`, `dbt_project/logs/` and `.venv/`.

#### Check

The three files exist, and `git status` shows no other change.

### Step 2 — Install and resolve versions

- **Status:** ✅ done
- **Who:** Owner
- **Commit:** `chore: lock the dependencies of spike s017` (`uv.lock`)
- **Model:** —
- **Gate:** `uv sync` resolves DuckDB 2.0 with `dbt-core` 1.12 and `dbt-duckdb` 1.11 → if not, Q1 fails and the run ends with no dbt (D1).

#### Scope

`uv.lock`, created by uv; `.env`, filled from Prerequisites and ignored by Git.

#### Do

1. Run `uv sync`.
2. Copy `.env.example` to `.env` and fill it with the token of Prerequisites.
3. Run `uv run python -c "import duckdb, deltalake; print(duckdb.__version__, deltalake.__version__)"` and `uv run dbt --version`.
4. Report back: the output of the three commands, or the resolution error in full.

#### Check

`uv run dbt --version` lists `dbt-core` 1.12.x and `duckdb` plugin 1.11.x, and DuckDB prints 2.0.x.

### Step 3 — Model reading the window

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `chore: add the dbt project of spike s017 with a model reading one bronze hour`
- **Model:** sonnet · medium

#### Scope

`dbt_project/dbt_project.yml`, `dbt_project/profiles.yml` and `dbt_project/models/staging/base_probe_read.sql`. No staging model, contract, tests or quarantine yet (Step 5).

#### Reads

- [Probe A](#a-build-on-duckdb-20) and [Shared behaviour](#211-shared-behaviour).
- [d004](../designs/d004-bronze-data-capture.md), the bronze tree at the top of its file layout: the key layout the window builds its glob from.
- The station status feed's section of the source card of the reported system (`docs/sources/ambici.md` or `docs/sources/bicing.md`): the JSON document's shape and fields.

#### Do

1. Write `dbt_project.yml`: project `dbt_in_the_pipeline`, models materialized as tables, the vars `source`, `feed`, `date` and `hour` with no defaults.
2. Write `profiles.yml`: `dbt-duckdb` on the file `out/scratch.duckdb`, relative to the spike root, where every command runs; the `httpfs` extension, and an S3 secret for R2 from `env_var()` of the four variables of `.env.example`.
3. Write `base_probe_read.sql`: read with `read_json` the objects matching `s3://{{ env_var('R2_BUCKET') }}/raw/{{ var('source') }}/{{ var('feed') }}/{{ var('date') }}/{{ var('date') | replace('-', '') }}T{{ var('hour') }}*.json.gz`, with `filename = true`; unnest the stations; select, uncast, a station key, the counts and a categorical field of the feed; then the capture time of the object, and the object's key as `source_key`.

#### Check

`<dbt> parse <vars>` ends with no error.

### Step 4 — Build the window from R2

- **Status:** ✅ done
- **Who:** Owner
- **Commit:** —
- **Model:** —
- **Gate:** the model reads from R2 only the objects of the window passed through `var()` → if not, Q1 fails and the run ends with no dbt (D1).

#### Do

1. Run `<dbt> build <vars>`.
2. Run `<dbt> show <vars> --inline "select count(*) as rows, count(distinct source_key) as objects, min(source_key) as first_key, max(source_key) as last_key from {{ ref('base_probe_read') }}"`.
3. Report back: the output of both commands, in full if the build fails.

#### Check

The build passes; `objects` equals the number of objects of the hour reported in Prerequisites, and `first_key` and `last_key` both lie in that hour; `out/scratch.duckdb` exists at the spike root.

### Step 5 — Contract, rule and quarantine

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `chore: add the contract, a runtime rule and a quarantine model to spike s017`
- **Model:** sonnet · medium

#### Scope

`dbt_project/models/staging/stg_probe.sql`, `stg_probe_quarantine.sql` and `stg_probe.yml`, all new; both models are built on `base_probe_read`, which does not change.

#### Reads

- [Probe A](#a-build-on-duckdb-20) and Q1.
- [ADR-0042](../decisions/0042-data-quality-classes-and-severity.md): the classes and severities that the rule's test and the quarantine follow.
- The model written in Step 3, `base_probe_read.sql`.
- The station status feed's section of the source card of the reported system: the values of the categorical field.

#### Do

1. Write `stg_probe.sql` on `ref('base_probe_read')`: cast each field with `try_cast` and keep only the rows whose required fields cast to a non-null value.
2. Write `stg_probe_quarantine.sql` on `ref('base_probe_read')`: the rows that fail those casts, with `source_key` and the failed field.
3. Write `stg_probe.yml`: an enforced contract on `stg_probe` with each column's type and `not_null` constraints on its required fields; `not_null` on the station key with severity `error`; `accepted_values` on the categorical field with severity `warn`, its values taken from a var `accepted` that defaults to the feed's values in its source card.

#### Check

`<dbt> parse <vars>` ends with no error.

### Step 6 — Build the full probe A

- **Status:** ✅ done
- **Who:** Owner
- **Commit:** —
- **Model:** —
- **Gate:** the build passes on DuckDB 2.0 with the contract enforced, both tests run with their severities and the quarantine model built, with no patch to dbt or `dbt-duckdb` → if not, Q1 fails and the run ends with no dbt (D1).

#### Do

1. Run `<dbt> build <vars>`.
2. Run it again with `accepted` reduced to one value: `<vars>` with `"accepted": ["<one value of the feed>"]` added.
3. Run `<dbt> show <vars> --inline "select (select count(*) from {{ ref('stg_probe') }}) as rows, (select count(*) from {{ ref('stg_probe_quarantine') }}) as quarantined"`.
4. Open `dbt_project/target/run/dbt_in_the_pipeline/models/staging/stg_probe.sql`, the DDL dbt ran for the model.
5. Report back: the output of the three commands; the `create table` statement of that file; and how readable the compiled SQL in `dbt_project/target/compiled/` and any error message are (Observe only, recorded as a Finding).

#### Check

Run 1 passes every test, and the `create table` of `stg_probe` lists each column with its type and `not null` on the required fields; run 2 ends with `accepted_values` as a warning and the build still succeeds; the quarantine model exists, with any row count.

### Step 7 — Shell glue

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `chore: add the shell glue of spike s017 between dbt and Delta`
- **Model:** sonnet · medium

#### Scope

`shell_glue/run_batch.py` (new). No change to the dbt project.

#### Reads

- [Probe B](#b-shell-glue), Q2, Q4 and the Q2 exit criteria, including No dbt internals.
- [D4](#d4-dbts-events-translated-into-the-log-convention): which events matter.
- dbt's documentation on programmatic invocations (`dbtRunner`, `dbtRunnerResult`, callbacks), through the `web-researcher`: the only dbt API the script may import.

#### Do

1. Write `run_batch.py` with `argparse`: `--mode dbt|baseline` and the four window arguments plus an optional `--accepted`.
2. Implement `--mode dbt`: invoke `dbtRunner(callbacks=[…]).invoke(["build", …, "--vars", …])`; the callback appends each event's name, level and data fields to `out/events.jsonl`; from `dbtRunnerResult`, print as JSON per node its `unique_id`, status, failures, rows affected and execution time.
3. Implement `--mode baseline`: in a fresh database `out/baseline.duckdb`, with the same `httpfs` extension and R2 secret as `profiles.yml`, execute with no dbt the compiled SQL from `dbt_project/target/compiled/` of `base_probe_read`, `stg_probe` and `stg_probe_quarantine`, in that order, each as `CREATE TABLE <model> AS`, then the compiled query of each data test, so that DuckDB does the same work as in `--mode dbt`.
4. Implement the hand-off shared by both modes: read `stg_probe` from its mode's database (`out/scratch.duckdb` or `out/baseline.duckdb`) as Arrow and MERGE it into the Delta table `out/delta/stg_probe` with `deltalake`, on the station key and capture time, creating the table on the first run; print the Delta table's row count.
5. Import from dbt only `dbt.cli.main` (`dbtRunner`, `dbtRunnerResult`).

#### Check

`uv run python shell_glue/run_batch.py --help` lists both modes.

### Step 8 — Run B in both modes

- **Status:** ✅ done **#5**
- **Who:** Owner **#4**
- **Commit:** —
- **Model:** —
- **Gate:** each model's and test's status and failures reach the shell as values, the MERGE gives the expected rows, and the glue imports no dbt internals → if not, Q2 fails and the run ends with no dbt (D1).

Below, `<run>` stands for `uv run --env-file .env /usr/bin/time -l python shell_glue/run_batch.py` followed by the window arguments.

#### Do

1. Run `<dbt> compile <vars>`, so the baseline has its SQL.
2. Run `<run> --mode dbt` three times.
3. Run `<run> --mode baseline` three times.
4. Run `<run> --mode dbt --accepted <one value of the feed>` once.
5. Run `grep -nE "^(from|import) dbt" shell_glue/run_batch.py`.
6. Report back: for each of the seven runs, the JSON printed, the Delta row count, and `/usr/bin/time`'s real time and maximum resident set size; the output of the `grep`; and `out/events.jsonl` (or its distinct event names, if large).

#### Check

- Every node of the build appears in the JSON with its status; run 4 shows `accepted_values` with failures above 0.
- The Delta row count equals the row count of `stg_probe` reported in Step 6, and stays the same across the seven runs.
- The `grep` shows only an import from `dbt.cli.main`.
- For each model and test of the build, an event in `out/events.jsonl` carries its status, rows and duration, or its failures; the names of those events are noted.
- The median of `--mode dbt` minus the median of `--mode baseline` is at most 15 s of real time and at most 500 MB of maximum resident set size, which macOS reports in bytes; each guide is met or missed.

### Step 9 — Unit tests

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `chore: add dbt unit tests to spike s017`
- **Model:** sonnet · medium

#### Scope

`dbt_project/models/staging/stg_probe_unit.yml` (new). No change to the models.

#### Reads

- [Probe C](#c-unit-tests), Q3 and [D3](#d3-sql-tested-with-dbt-unit-tests-python-with-pytest).
- The models and their YAML from Steps 3 and 5.

#### Do

1. Write a unit test on `stg_probe`: two hand-written input rows given for `ref('base_probe_read')`, expected rows written by hand; it passes.
2. Write a unit test on `stg_probe_quarantine`: one malformed row given for `ref('base_probe_read')`, expected in quarantine with its failed field; it passes.
3. Write a unit test on `stg_probe` whose expected rows are wrong on purpose, named so that its failure reads as intended; it fails.

#### Check

`<dbt> parse <vars>` ends with no error.

### Step 10 — Run and time unit tests

- **Status:** ✅ done
- **Who:** Owner
- **Commit:** —
- **Model:** —
- **Gate:** the two tests pass and the third fails, as written → if not, D3 moves to its option B, and the run continues.

#### Do

1. Run `uv run --env-file .env /usr/bin/time -l dbt test --select test_type:unit --project-dir dbt_project --profiles-dir dbt_project <vars>` three times.
2. Report back: the output of each run and its real time.

#### Check

Each run shows two passes and one failure; the median real time is set against the Q3 guide.

### Step 11 — README

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `docs: add the README of spike s017`
- **Model:** sonnet · medium

#### Scope

`README.md` (new). It also reports the glue's size for the Q2 guide.

#### Reads

- `.claude/rules/code/spikes.md`: the README's procedure shape.
- Steps 1–10 of this document for each check's command, and its Findings for each output and run time.

#### Do

1. Write `README.md` as a procedure: the question and a link to s017, the prerequisites, then one section per probe (A, B, C) in run order, each citing the decision it is evidence for (D1, D2, D3, D4).
2. Count the lines of `shell_glue/run_batch.py` without blank lines, comments, docstrings and the code of `--mode baseline`, which the guide does not count, and report it for the Q2 guide.

#### Check

The README covers A, B and C in run order, and the line count is reported.

## 4. Findings

### F1. DuckDB 2.0 resolves with dbt-core 1.12 and dbt-duckdb 1.11

Step 2 · 2026-11-17 · `uv sync`, `uv run dbt --version` and the import of `duckdb` and `deltalake`, run by the owner

- Locked versions: `dbt-core` 1.12.7, `dbt-duckdb` plugin 1.11.1, DuckDB 2.0.0, `deltalake` 1.6.6. dbt reports 1.12.7 and 1.11.1 as the latest releases of their lines.
- Consequence: the Gate of Step 2 passes; Probes A, B and C run on these versions.

### F2. dbt-duckdb does not create the folder of its database file

Step 4 · 2026-11-17 · `dbt build`, run by the owner

- With `path: out/scratch.duckdb` and no `out/` folder, the first query fails: `IO Error: Cannot open file ".../out/scratch.duckdb": No such file or directory`. Neither DuckDB nor `dbt-duckdb` creates the parent folder.
- Consequence: the folder is created before the first build (`mkdir out`), and the README lists it as a setup command. In the pipeline, the shell creates the database's folder before invoking dbt.

### F3. dbt-duckdb reads from R2 only the objects of the window passed through var()

Step 4 · 2026-11-17 · `dbt build` and `dbt show` on `base_probe_read`, run by the owner, window `bicing` / `station_status` / 2026-11-16 / 10 UTC

- `dbt build` passes on DuckDB 2.0 with no patch: `PASS=1 WARN=0 ERROR=0`; the model builds in 2.85 s, the whole run in 3.07 s.
- The model reads 60 objects, as many as the hour holds in the bucket, and 32,700 rows (545 stations per object). The first key is `…/20261116T100039Z.json.gz` and the last `…/20261116T105939Z.json.gz`, both in the hour.
- Consequence: the Gate of Step 4 passes; Probe A continues with the contract, the rule and the quarantine (Step 5).

### F4. dbt-duckdb enforces the model contract on DuckDB 2.0

Step 6 · 2026-11-17 · `dbt build`, `dbt show` and the DDL in `target/run/`, run by the owner, window `bicing` / `station_status` / 2026-11-16 / 10 UTC

- `dbt build` passes with no patch: `PASS=5 WARN=0 ERROR=0` (3 models, 2 data tests), the whole run in 1.78 s.
- The DDL dbt runs for `stg_probe` is a `create table` with an explicit column list: each of the six columns with its contract type (`varchar`, `integer`, `boolean`, `timestamp`) and `not null`.
- `stg_probe` holds 32,700 rows, as many as `base_probe_read` (F3); `stg_probe_quarantine` is built and holds 0 rows.

### F5. A test with severity warn reports and does not fail the build

Step 6 · 2026-11-17 · second `dbt build`, run by the owner, with `accepted` set to `[true]`

- `accepted_values` on `is_renting` ends as `WARN 1` and the build ends `Completed with 1 warning`, `PASS=4 WARN=1 ERROR=0`; `not_null` on `station_id`, severity `error`, passes.
- Consequence: the Gate of Step 6 passes; Q1 holds for Probe A, and the run continues with probe B (Step 7).

### F6. Compiled SQL is readable; the test name keeps the raw var expression

Step 6 · 2026-11-17 · `target/compiled/` and the build output, read by the owner (Observe)

- The compiled SQL in `target/compiled/` is plain SQL with the `ref()` calls resolved to `"scratch"."main"."…"`, e.g. the inline query of `dbt show`.
- The warning names the test and the path of its compiled SQL, which is enough to find the failing rows.
- The generated test name embeds the unrendered default, `accepted_values_stg_probe_is_renting__False___var_accepted_true_false_`, and stays the same when the var changes, so it does not show the values tested.
- No error message came up in this step, so how readable dbt errors are is not observed here.

### F7. dbtRunner returns each node's status and failures as values

Step 8 · 2026-11-17 · `shell_glue/run_batch.py --mode dbt`, four runs, run by the owner (`out/step8.log`, #4)

- `dbtRunnerResult.result.results` holds one `RunResult` per node, the three models and the two tests, with `node.unique_id`, `status` (`success`, `pass`, `warn`), `failures` (`null` for models, a count for tests) and `execution_time`.
- With `accepted` set to `[true]`, `accepted_values` returns `status: warn` and `failures: 1`, and `success` stays `true`.
- The script imports from dbt only `dbt.cli.main` (`dbtRunner`, `dbtRunnerResult`).

### F8. dbt-duckdb keeps its database open in the process after dbtRunner returns

Step 8 · 2026-11-17 · first `--mode dbt` run, run by the owner

- Opening `out/scratch.duckdb` again in the same process with `read_only=True` fails: `Can't open a connection to same database file with a different configuration than existing connections`.
- dbt-duckdb opens the file with `read_only=False` and an empty config (`dbt/adapters/duckdb/environments/__init__.py`); a `duckdb.connect()` with the default config reuses that instance and reads `stg_probe`.
- Consequence: the shell reads dbt's scratch table in the same process only with dbt-duckdb's connection config.

### F9. dbt-duckdb reports no rows affected

Step 8 · 2026-11-17 · `--mode dbt` runs and `out/events.jsonl`, run by the owner

- `adapter_response` holds only `{"_message": "OK"}` for every model, so `rows_affected` is empty both in `RunResult` and in the `run_result` of `NodeFinished`.
- Consequence: a model's row count does not reach the shell from dbt; the shell would count it on the scratch table.

### F10. The callback receives each node's start, status, duration and failures

Step 8 · 2026-11-17 · `out/events.jsonl` of the run with `accepted` set to `[true]`, run by the owner

- `NodeStart` (5) marks each node's start, with `node_info`.
- `NodeFinished` (5) carries, for models and tests alike, `node_info.unique_id`, `run_result.status`, `run_result.execution_time` and, when above 0, `run_result.num_failures`.
- `LogTestResult` (2) carries a test's `status`, `execution_time` and `num_failures`; `LogModelResult` (3) a model's `status` and `execution_time`.
- `MessageToDict` leaves out `num_failures` when it is 0, the protobuf default, so a passing test's event has no failures field.
- No error event came up in these runs.

### F11. The MERGE into Delta gives the expected rows in both modes

Step 8 · 2026-11-17 · three runs per mode and one with `accepted` set to `[true]`, run by the owner

- The Delta table `out/delta/stg_probe` holds 32,700 rows after each of the seven runs, the row count of `stg_probe` in F4; the MERGE on station key and capture time adds no duplicates.

### F12. dbt adds about 1 s and 36 MB to a run

Step 8 · 2026-11-17 · `/usr/bin/time -l`, three runs per mode on the owner's machine

| Mode | Real time (median) | Maximum resident set size (median) |
|---|---|---|
| dbt | 2.70 s | 400.5 MB |
| baseline | 1.75 s | 364.1 MB |
| Difference | +0.95 s | +36.4 MB |

- Both guides are met: at most 15 s and at most 500 MB.
- Consequence: the Gate of Step 8 passes; Q2 holds, and the run continues with Probe C (Step 9).

### F13. dbt unit tests pass and fail as written on dbt-duckdb

Step 10 · 2026-11-17 · `dbt test --select test_type:unit`, three runs, run by the owner

- Each run ends with `PASS=2 WARN=0 ERROR=1 SKIP=0 NO-OP=0 REUSED=0 TOTAL=3`: `stg_probe_keeps_valid_rows_typed` and `stg_probe_quarantine_keeps_malformed_row_with_failed_field` pass; `stg_probe_fails_on_purpose_wrong_vehicle_count` fails with `FAIL 1`.
- The unit tests run against the scratch database left by the earlier steps, from which dbt reads the column types of the mocked `base_probe_read`; no bronze is read.
- The run's summary names the failing unit test and its YAML file, then shows the diff of actual against expected rows, with the failing value as expected→actual (`6→5` under `num_vehicles_available`), later columns elided as `...`, and the path of the test's compiled SQL.
- Consequence: the Gate of Step 10 passes; D3 holds with dbt unit tests.

### F14. The dbt unit test suite runs locally in about 1.5 s

Step 10 · 2026-11-17 · `/usr/bin/time -l`, three runs on the owner's machine

- Real time 1.84 s, 1.52 s and 1.50 s: median 1.52 s, dbt's start-up included; dbt reports 0.21 s for the three tests themselves.
- The guide of at most 30 s is met.

### F15. The shell glue is 71 lines of Python

Step 11 · 2026-11-17 · code lines of `shell_glue/run_batch.py`, counted with Python's `tokenize`

- 98 code lines in all, without blank lines, comments and docstrings; 27 of them are `--mode baseline`'s (`run_baseline` and the names only it uses: `os`, `COMPILED`, `MODELS`), which the guide does not count. 71 remain for invocation, results, hand-off and callback.
- The guide of at most 150 lines is met.

## 5. Conclusion

Observed window: bronze of `bicing` / `station_status` from 2026-11-16 10:00 to 10:59 UTC (60 objects, 32,700 rows), processed on the owner's machine on 2026-11-17. It does not cover AMBici, other feeds, batches longer than one hour or a container on Modal.

### 5.1 Answers

- **Q1. Works on DuckDB 2.0:** yes. `dbt-core` 1.12.7 and `dbt-duckdb` 1.11.1 resolve with DuckDB 2.0.0 and build, with no patch, the base model reading from R2 only the objects of the window passed through `var()`, the enforced contract, a rule with severity `warn` that reports without failing the build, and the quarantine model. (F1, F3, F4, F5)
- **Q2. Shell glue:** yes. `dbtRunner` returns each node's status, failures and execution time as values; the scratch table reaches `deltalake` as Arrow in the same process, opened only with `dbt-duckdb`'s connection config; the MERGE gives 32,700 rows in all seven runs. dbt adds 0.95 s and 36.4 MB to a run, and the glue is 71 lines. (F7, F8, F11, F12, F15)
- **Q3. Unit tests:** yes. They pass and fail as written, with a readable diff on failure, and the suite runs locally in 1.52 s (median). dbt reads the column types of the mocked input from its relation in the scratch database, which must exist beforehand. (F13, F14)
- **Q4. Events in the callback:** partly. `NodeStart` and `NodeFinished` carry each node's start, status, duration and failures; rows are missing, since `dbt-duckdb` reports none, and `num_failures` is left out when it is 0. No error event came up. (F9, F10)
- **Observe only:** the compiled SQL is readable; a test's name keeps the raw var expression; the only error message observed, a failing unit test's diff, is readable. (F6, F13)

### 5.2 Exit criteria

| Criterion | Kind | Result | Findings |
|---|---|---|---|
| Q1 · Works on DuckDB 2.0 | Hard cut | Met | F1, F4, F5 |
| Q1 · Window in the file path | Hard cut | Met: 60 of 60 objects, all in the hour | F3 |
| Q2 · Results as values | Hard cut | Met, from `dbtRunnerResult` | F7 |
| Q2 · Hand-off to Delta | Hard cut | Met: 32,700 rows in each of seven runs | F8, F11 |
| Q1–Q2 · No dbt internals | Hard cut | Met: only `dbt.cli.main` | F7 |
| Q2 · Glue size | Guide | Met: 71 of 150 lines | F15 |
| Q2 · Time per invocation | Guide | Met: 0.95 s of 15 s | F12 |
| Q2 · Peak memory | Guide | Met: 36.4 MB of 500 MB | F12 |
| Q3 · Unit tests run | Hard cut (D3) | Met | F13 |
| Q3 · Test suite time | Guide | Met: 1.52 s of 30 s | F14 |
| Q4 · Results in the callback | Guide | Missed on rows; status, duration and failures met | F9, F10 |

Every hard cut is met and one guide is missed, so D1 stands; the extra cost is D4's fallback for rows: the shell counts them on the scratch table.

### 5.3 Verdict

Yes: dbt fits the pipeline as the layer that builds and audits its SQL (D1), on DuckDB 2.0 with `dbt-core` 1.12 and `dbt-duckdb` 1.11 (D2), with every hard cut met and the glue well below its guides of size, time and memory. D3 holds with dbt unit tests. D4 holds with the callback for status, duration and failures, while the shell counts each model's rows on the scratch table, since `dbt-duckdb` reports none.

### 5.4 Not verified

- **A cold container on Modal** — time and memory were measured locally; dbt may start more slowly on Modal — the margin is wide (0.95 s of 15 s), and each production run logs its duration.
- **Several batches in one process** — each run here was a fresh process, and `dbt-duckdb` keeps its database open (F8), so a second `dbtRunner` invocation on a new scratch database in the same process, as a catch-up of several batches (ADR-0045) needs, is untested — the shell's integration test runs two batches in one process.
- **Errors** — no error event or contract violation came up, so their events and how readable their messages are remain unknown — the integration test makes a model fail and a contract break, and checks the result and the log.
- **Quarantine with real rows** — the quarantine held 0 rows on real data and is covered only by a unit test — the integration test's bronze fixtures include a malformed row.
- **Batches longer than one hour, other systems and feeds** — only one hour of Bicing's `station_status` was read — dbt's own cost does not grow with the batch, whose work DuckDB does, and the glob follows the key layout of d004, shared by every system.

### 5.5 Production inputs

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | Pins: `dbt-core` 1.12.7, `dbt-duckdb` 1.11.1 and DuckDB 2.0.x resolve together | D2, F1 | [d008 › Carried-over inputs](../designs/d008-pipeline-platform-and-walking-skeleton.md#carried-over-inputs) |
| P2 | The shell creates the scratch database's folder before it invokes dbt | F2 | [d008 › Carried-over inputs](../designs/d008-pipeline-platform-and-walking-skeleton.md#carried-over-inputs) |
| P3 | The shell reads dbt's scratch table in the same process only with `dbt-duckdb`'s connection config (`read_only=False`, empty config) | F8 | [d008 › Carried-over inputs](../designs/d008-pipeline-platform-and-walking-skeleton.md#carried-over-inputs) |
| P4 | The callback turns `NodeStart` and `NodeFinished` into the pipeline's events (such as `model_started`, `model_built`, `rule_checked`); a missing `num_failures` means 0; the shell counts each model's rows on the scratch table | D4, F9, F10 | [d008 › Carried-over inputs](../designs/d008-pipeline-platform-and-walking-skeleton.md#carried-over-inputs) |
| P5 | Each data test takes an explicit `name`, its `DQR` ID, since the generated name keeps the raw var expression; it answers [d007 › Rule names in code](../designs/d007-pipeline-design.md#carried-over-inputs) | F6 | [d008 › Carried-over inputs](../designs/d008-pipeline-platform-and-walking-skeleton.md#carried-over-inputs) |
| P6 | dbt unit tests need their upstream relations to exist: CI builds them first with `dbt run --empty`, dbt's documented pattern, and the testing strategy gains its SQL (dbt) section | D3, F13 | [d008 › Carried-over inputs](../designs/d008-pipeline-platform-and-walking-skeleton.md#carried-over-inputs) |
| P7 | The shell's integration test runs two batches in one process, a failing model and a contract violation, and checks the result and the log | [Not verified](#54-not-verified) | [d008 › Carried-over inputs](../designs/d008-pipeline-platform-and-walking-skeleton.md#carried-over-inputs) |
| P8 | The bronze fixtures of the quarantine's integration test include a malformed row | [Not verified](#54-not-verified) | T060.5's design. TODO(T060.5) |

### 5.6 Records

| Output | From | Destination | Commit |
|---|---|---|---|
| ADR-0047: dbt builds and audits the pipeline's SQL, extending ADR-0025 and ADR-0046 | D1, D2, D4 | [ADR-0047](../decisions/0047-dbt-builds-and-audits-the-pipeline-sql.md) | Done |
| dbt as the layer that builds and audits the SQL, citing ADR-0047 | D1 | [architecture.md](../architecture.md) › 4.1 Technology, 5. Building block view, 6.2 Pipeline run, 8. Cross-cutting concepts (Data quality), 12. Glossary (SQL model) | Done |
| The runtime rules' runner is dbt, and the data-test tool is decided, citing ADR-0047 | D1 | [d007](../designs/d007-pipeline-design.md) › Carried-over inputs (Platform separation, dbt) | Done |

## 6. Sources

Read on 2026-11-17.

- dbt versions and support: <https://docs.getdbt.com/docs/dbt-versions/core>; licensing of v1 and v2: <https://docs.getdbt.com/docs/dbt-licensing.md>
- `dbt-duckdb`: <https://github.com/duckdb/dbt-duckdb>, its releases <https://github.com/duckdb/dbt-duckdb/releases>, its `delta` plugin <https://github.com/duckdb/dbt-duckdb/blob/master/dbt/adapters/duckdb/plugins/delta.py>, its configs <https://docs.getdbt.com/reference/resource-configs/duckdb-configs>
- DuckDB `delta` extension: <https://duckdb.org/docs/2.0/core_extensions/delta>
- delta-rs on S3-like storage: <https://delta-io.github.io/delta-rs/integrations/object-storage/s3-like>
- Programmatic invocations: <https://docs.getdbt.com/reference/programmatic-invocations>
- Microbatch: <https://docs.getdbt.com/docs/build/incremental-microbatch>
- `dbt build`: <https://docs.getdbt.com/reference/commands/build>; WAP with dbt: <https://www.getdbt.com/blog/testing-is-not-enough-transforming-data-quality-with-write-audit-publish>
- Model contracts: <https://docs.getdbt.com/docs/mesh/govern/model-contracts>
- Logs and events: <https://docs.getdbt.com/reference/global-configs/logs>, <https://docs.getdbt.com/reference/events-logging>
- Column-level lineage: <https://docs.getdbt.com/docs/explore/column-level-lineage.md>
