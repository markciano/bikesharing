<!--
Spike doc template. A spike is a time-boxed investigation of one task: it reaches the decisions a task needs, by analysis where possible and with evidence only where an unknown would change the choice. Its output is knowledge (decisions, answers, a verdict, inputs for designs and ADRs); its code is throwaway and lives in spikes/<name>/.
Blocks: Questions (what we need to know), Method (how we find out), Steps, Findings (filled during execution), Conclusion (filled after the last step).
Sections marked Optional are kept only when they apply.
-->

# Spike: dbt in the pipeline

- **Task:** T060.7
- **ADRs:** [ADR-0022](../decisions/0022-delta-lake-for-silver-and-gold.md), [ADR-0024](../decisions/0024-duckdb-as-processing-engine.md), [ADR-0025](../decisions/0025-sql-models-directed-by-python.md), [ADR-0042](../decisions/0042-data-quality-classes-and-severity.md), [ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md), [ADR-0046](../decisions/0046-functional-core-imperative-shell-for-the-pipeline.md)
- **Code:** `spikes/dbt-in-the-pipeline/`

## Status

<!-- State: Draft 📝 · Ready 🎬 · Running 🔄 · Concluded ✅.
Phase: the blocks and the review completed.
Started / Finished: UTC dates of the first step executed and of the Conclusion.
Current step: the step being executed, or —. -->

- State: Ready 🎬
- Phase: [x] Questions · [x] Method · [x] Steps · [x] Steps review · [ ] Conclusion
- Started: — · Finished: —
- Current step: —

## 1. Questions — what we need to know

### 1.1 Context

<!-- 2–4 sentences: the decisions this spike takes, which of them depend on evidence and why, and the spikes or designs it builds on. -->

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

<!-- In this order, so the reader finds what matters first:
1. The decision and why, in one short paragraph. If it depends on a Q, name it and what happens if its Gate fails.
2. What would change it, and what would not, each with the action to take. Only when a later event could reopen it.
3. The options rejected and how robust the result is.
4. The evaluation behind it: the table or weighted matrix (needs, cuts, anchors and scores) if one was used. A security decision lists its threats in a table: `| # | Threat (STRIDE) | Impact | Control | Requirement |`, with IDs `TH1`, `TH2`… per document. -->

### 1.3 Questions

<!-- The main question, answered by the Verdict. Then Q1..Qn, each answerable with evidence.
"Observe only": things to note during the run with no dedicated effort. -->

Main question: does dbt fit the pipeline as the layer that builds and audits its SQL (D1), with its glue below the thresholds of friction in Exit criteria?

- **Q1.** On DuckDB 2.0, do `dbt-core` 1.12 and `dbt-duckdb` 1.11 build a model that reads bronze JSON from R2 with the batch's window in its file path through `var()`, with an enforced contract, a runtime rule as a test with its severity, and a quarantine model for the rows that break the schema? Unblocks D1 and D2.
- **Q2.** Does the shell invoke that build through `dbtRunner` with the window in `--vars`, read each model's and test's result as values for the core, and hand the scratch table to `deltalake` as Arrow for a MERGE into a Delta table; and what does one invocation add to a run in time and peak memory? Unblocks D1.
- **Q3.** Do dbt unit tests run on `dbt-duckdb`, and how long does the dbt test suite take locally? Unblocks D3.
- **Q4.** Which dbt events reach a `dbtRunner` callback with a model's status, rows and duration and a test's failures? Unblocks D4.
- **Observe only:** how readable the compiled SQL and dbt's error messages are when a model fails.

### 1.4 Exit criteria

<!-- Fixed before the first run; a later change is recorded in the Decision log.
Derived from the standard that applies to this kind of question, named in the first line: e.g. DAMA data quality dimensions for a data source, a weighted decision matrix for a technology choice.
Each criterion is measurable and says whether it is a hard cut or a guide. The timebox says what ends the run. State whether one variant meeting the criteria is enough. -->

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

<!-- Optional. What someone could expect this spike to answer and it will not, each item pointing to the task that covers it. -->

- The move to dbt v2, when its DuckDB adapter covers what D2 needs — T070

## 2. Method — how we find out

### 2.1 Approach

<!-- The variants, options or probes compared, and what each one tells that the others do not. -->

One variant, the shape of D1, probed in three parts; A runs first, since it tests the riskiest assumption at the lowest cost and its Gate ends the run with no dbt if it fails.

| Probe | What it is | What it tells | Q |
|---|---|---|---|
| [A](#a-build-on-duckdb-20) | A minimal dbt project built with `dbt build` from the CLI | Whether dbt and `dbt-duckdb` work on DuckDB 2.0 with no patch | Q1 |
| [B](#b-shell-glue) | A Python script that runs A's build through `dbtRunner` and publishes to Delta | The friction of the glue: results, hand-off, callback, lines, time and memory | Q2, Q4 |
| [C](#c-unit-tests) | dbt unit tests on A's model | Whether dbt unit tests run on `dbt-duckdb`, and the suite's time | Q3 |

Q4 is part of B: the callback is registered on the same `dbtRunner` invocation that Q2 measures, so a probe of its own would repeat that run and tell nothing more.

A rough worst-case estimate settles none of the guides, so each is measured within B: dbt-core starts and parses a small project in about 2–5 s, which may approach 15 s in a cold container; its Python process adds about 150–300 MB, close enough to 500 MB to need a figure; the glue is expected at 80–120 lines, counted on B's code.

#### 2.1.1 Shared behaviour

<!-- Optional. Rules every variant follows (schedules, formats, key layouts, logs), stated once so the steps can cite them. -->

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

<!-- It logs decisions about the method, before and during the run, including changes of course. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Column Applies to: anchor link(s) to the section where the decision is applied, named in one or two words (e.g. Q1, Probe A, File layout).
- Column Decided at: the Status phase where it was decided (Method, Steps), `<phase> review` when decided while reviewing that phase, or `Running step N` when decided during the run.
-->

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| 1 | [Shared behaviour](#211-shared-behaviour) | Probes read the real bronze bucket with a read-only R2 token and write Delta locally (least privilege) | Tests the real path layout the window relies on, with no write access to production data | Method |
| 2 | [Probe B](#b-shell-glue) | dbt's time and memory measured against a baseline without dbt, locally, median of three runs (A/B benchmark with a baseline) | Isolates dbt's own cost from DuckDB's and `deltalake`'s work, which the guides do not count | Method |
| 3 | [Probe A](#a-build-on-duckdb-20), [Probe C](#c-unit-tests) | Bronze is read in a base model that the staging and quarantine models `ref()` (dbt base model, dbt style guide) | dbt unit tests mock only `ref()` and `source()` inputs; a `source` with `external_location` would add a `dbt-duckdb` unknown to Q1 | Steps review |

### 2.4 File layout

<!-- Every file and folder the spike creates, as a tree with its purpose in one line. Captured data and outputs are marked as ignored by Git. The README is always included. -->

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
<!-- Each step is one reviewable result, touching at most 2–3 files.
- Status: where the step is: 💤 todo · 🎬 ready · 🔄 in progress · ⛔ blocked · ✅ done
- Who: Owner (manual actions: dashboards, accounts, deploys, runs, checks) or Claude (code and documents).
- Commit: only in a step that changes committed files: the proposed message, following the Git conventions in CLAUDE.md.
- Model: the model and effort the step's session runs with (e.g. sonnet · medium), or — when Who is Owner.
- Gate: optional. <condition> → <consequence if it fails: variants or steps dropped or re-decided>. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

- **uv 0.13.5** on the local machine; it installs Python 3.13 for the spike. Verify: `uv --version`.
- **R2 token for the spike,** in the Cloudflare dashboard: an R2 API token with Object Read only, scoped to the bronze bucket. Its access key ID, secret and the account's S3 endpoint go into `spikes/dbt-in-the-pipeline/.env`, once Step 1 has created `.env.example`. It is revoked at tear-down (#1).
- **One hour of bronze:** the bucket name, and the `<source>`, `<feed>`, date and UTC hour of one complete hour of one system's station status, under the key layout of [d004](../designs/d004-bronze-data-capture.md) (`raw/<source>/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz`), with the number of objects in that hour, read in the dashboard; reported back as the window of Probe A.

Owner commands run from `spikes/dbt-in-the-pipeline/`; `<vars>` stands for the window reported in Prerequisites, as `--vars '{"source": "…", "feed": "…", "date": "YYYY-MM-DD", "hour": "HH"}'`, and `<dbt>` for `uv run --env-file .env dbt` with `--project-dir dbt_project --profiles-dir dbt_project` after the subcommand.

### Step 1 — Spike environment

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `chore: set up the environment of spike s017`
- **Model:** sonnet · medium

#### Scope

<!-- The result of the step. List the components and the files created or changed (code, tests, docs). A reviewer should know what the diff will contain from this section alone. -->

The spike's Python environment, unlocked: `pyproject.toml`, `.env.example`, `.gitignore` under `spikes/dbt-in-the-pipeline/`. Nothing outside that folder.

#### Reads

<!-- List of reads containing what to read (be specific with paragraph or line), what contains the read, and why it is interesting here.  -->

- [D2](#d2-dbt-v1-dbt-core-112-with-dbt-duckdb): the release lines to pin.
- [Shared behaviour](#211-shared-behaviour) and [File layout](#24-file-layout): what the folder holds and what Git ignores.
- `spikes/execution-target/pyproject.toml`: the shape of an earlier spike's `pyproject.toml`, to follow it.

#### Do

<!-- Numbered actions in execution order, one verb each (write, implement, update, run). Every file named here must appear in Scope; add nothing Scope does not list. -->

1. Write `pyproject.toml`: `requires-python = ">=3.13,<3.14"`; dependencies `dbt-core~=1.12.0`, `dbt-duckdb~=1.11.0`, `duckdb~=2.0.0`, `deltalake` and `pyarrow` at their latest releases. No pin is relaxed to make resolution pass: a failure to resolve is Step 2's evidence.
2. Write `.env.example` with empty `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT` and `R2_BUCKET`.
3. Write `.gitignore` with `.env`, `out/`, `dbt_project/target/`, `dbt_project/logs/` and `.venv/`.

#### Check

<!-- command/s or verification with a yes/no result. -->

The three files exist, and `git status` shows no other change.

### Step 2 — Install and resolve versions

- **Status:** 💤 todo
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

- **Status:** 💤 todo
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

- **Status:** 💤 todo
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

- **Status:** 💤 todo
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

- **Status:** 💤 todo
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

- **Status:** 💤 todo
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

- **Status:** 💤 todo
- **Who:** Owner
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

- **Status:** 💤 todo
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

- **Status:** 💤 todo
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

- **Status:** 💤 todo
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

<!-- Filled during the run, in the step that produces the evidence. One fact per finding: what was observed, the evidence (figures, tables) and its consequence for the spike. Numbering is never reused. An earlier finding is not rewritten to fit a later result; the later one says which finding it corrects. -->

### F1. `<one-line statement>`

Step N · YYYY-MM-DD · `<source of evidence>`

- `<evidence>`
- Consequence: `<for variants, steps or questions>`

## 5. Conclusion

<!-- Filled after the last step. Covers only the observed window. -->

Observed window: `<from–to, UTC; what it does not cover>`

### 5.1 Answers

- **Q1. Title** `<answer>` (FN)

### 5.2 Exit criteria

<!-- One result per criterion and variant. -->

| Criterion | Kind | Result | Findings |
|---|---|---|---|

### 5.3 Verdict

<!-- The answer to the main question in 2–3 sentences. -->

### 5.4 Not verified

<!-- What the evidence does not cover, each with its risk and mitigation. "None" is valid. -->

- `<item>` — `<risk>` — `<mitigation>`

### 5.5 Production inputs

<!-- Optional. What a later task must take into account when it builds, from any part of the spike: done when that task runs. Each one has a Destination: a design (with its task) or discarded with a reason. -->

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | | `<e.g. D1, #2, F3>` | |

### 5.6 Records

<!-- Documents this spike updates before it closes: ADRs from Decided at framing (each in its own commit), architecture, requirements, source cards and new tasks agreed with the owner. A decision that updates no document has no row. Commit: "Done", or "Pending" until delivered; the spike closes when every row is Done. Production inputs are not repeated here. -->

| Output | From | Destination | Commit |
|---|---|---|---|
| `<ADR, requirement, source card or task>` | `<e.g. D1, F3>` | `<document and section>` | `<Done, or Pending>` |

## 6. Sources

<!-- Optional. Earlier spikes, benchmarks and documentation used. -->

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
