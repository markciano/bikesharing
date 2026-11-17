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

- State: Draft 📝
- Phase: [ ] Questions · [ ] Method · [ ] Steps · [ ] Steps review · [ ] Conclusion
- Started: — · Finished: —
- Current step: —

## 1. Questions — what we need to know

### 1.1 Context

<!-- 2–4 sentences: the decisions this spike takes, which of them depend on evidence and why, and the spikes or designs it builds on. -->

### 1.2 Decided at framing

#### D1. dbt builds and audits, Python plans and publishes

dbt runs every SQL model and runtime rule of the pipeline, for one batch at a time, in a scratch DuckDB database discarded at the end of the run. Python keeps what lies at the edges of the SQL: the core plans the batch ([ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md)) and turns dbt's results into a verdict; the shell invokes dbt with the batch's window as variables and, only if the audit passes, writes the batch to Delta on R2 with `deltalake`. This is Write-Audit-Publish: dbt writes to the scratch database and audits it, the shell publishes. dbt replaces what the pipeline would otherwise build itself: the ordered runner of [ADR-0025](../decisions/0025-sql-models-directed-by-python.md), the parameters in bronze file paths that ADR-0025 left unconfirmed, the column schema checks, the runner of runtime rules of [ADR-0046](../decisions/0046-functional-core-imperative-shell-for-the-pipeline.md) (rule 8), the scaffolding of SQL tests, and the table-level lineage written by hand ([ADR-0043](../decisions/0043-lineage-at-four-levels.md)). It depends on Q1: if its Gate fails, the pipeline has no dbt and ADR-0025 stands as it is.

What would change it:

- Q1's Gate fails: no dbt; ADR-0025 and ADR-0046 stand unchanged.
- A `dbt-duckdb` release writes Delta with MERGE or partition overwrite and tests before it publishes: dbt could write Delta itself; weigh option B again.

What would not: the lineage seam at the hand-off to Delta. dbt's lineage covers only the table level of ADR-0043, and exposures and sources can join the graph across the hand-off.

Options rejected:

- **B. dbt writes Delta itself,** through Python models or a custom materialization that calls `deltalake`: it writes to R2 while the batch is built, before its tests run, which is the opposite of Write-Audit-Publish; dbt's contracts do not apply to Python models, so the model that writes Delta has none; the writes, their credentials and retries move inside dbt, out of the shell of ADR-0046; no published example of such a materialization was found.
- **No dbt:** the simplest, and reversible from D1, since dbt models stay `SELECT` statements; it keeps the fallback role, and loses the pieces dbt replaces.
- **DuckLake instead of Delta,** which `dbt-duckdb` writes natively with MERGE: it reopens [ADR-0022](../decisions/0022-delta-lake-for-silver-and-gold.md) to gain a seamless lineage graph and incremental features that ADR-0045 already covers in its own way, adds a metadata database to run, and still neither tests before it publishes nor bounds batches in bytes.

The result is robust to the facts gathered: both gaps, Delta writes and Write-Audit-Publish, close with the same split, and the only unknown left is the friction of the glue, which Q1 measures.

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

Each tool tests its own side, following the standard of a dbt project and the test pyramid: dbt unit tests verify each SQL model's logic on its own, with input rows and expected rows written by hand and no real data read; pytest verifies the Python core and shell as today ([testing strategy › Python](../testing-strategy.md#python-srcbikesharing)), plus an integration test in which the shell runs dbt on bronze fixtures and writes Delta to a local folder. The testing strategy gains a section for SQL (dbt) with its five answers, and CI runs both. dbt unit tests are written before the model, as Python tests are before their code. The local budget of under 1 s ([s008 › F37](s008-testing-conventions.md#4-findings)) cannot hold for dbt, whose start-up alone takes longer: dbt tests get a budget of their own, measured in Q1, which also confirms that dbt unit tests run on `dbt-duckdb`.

What would change it: Q1 finds that dbt unit tests do not run on `dbt-duckdb`. Then model logic is tested from pytest on the scratch database, as option B.

Option rejected: **B. pytest only,** each test running `dbt build` on fixtures and asserting on the resulting tables. One tool, but every test pays dbt's start-up, and it tests several models together instead of one.

<!-- In this order, so the reader finds what matters first:
1. The decision and why, in one short paragraph. If it depends on a Q, name it and what happens if its Gate fails.
2. What would change it, and what would not, each with the action to take. Only when a later event could reopen it.
3. The options rejected and how robust the result is.
4. The evaluation behind it: the table or weighted matrix (needs, cuts, anchors and scores) if one was used. A security decision lists its threats in a table: `| # | Threat (STRIDE) | Impact | Control | Requirement |`, with IDs `TH1`, `TH2`… per document. -->

### 1.3 Questions

<!-- The main question, answered by the Verdict. Then Q1..Qn, each answerable with evidence.
"Observe only": things to note during the run with no dedicated effort. -->

Main question: `<one sentence>`

- **Q1.** `<question>`
- **Observe only:** `<item>`

### 1.4 Exit criteria

<!-- Fixed before the first run; a later change is recorded in the Decision log.
Derived from the standard that applies to this kind of question, named in the first line: e.g. DAMA data quality dimensions for a data source, a weighted decision matrix for a technology choice.
Each criterion is measurable and says whether it is a hard cut or a guide. The timebox says what ends the run. State whether one variant meeting the criteria is enough. -->

- **Standard:** fit-gap analysis of dbt against the decisions in force (ADRs and d007): each one is a fit, an adaptation (which decision changes, and its cost) or a gap; no ADR is fixed in advance, each is weighed by its impact.
- **Timebox:** `<window, and what ends it>`
- `<criterion>` — `<threshold>` — hard cut | guide

### 1.5 Out of scope

<!-- Optional. What someone could expect this spike to answer and it will not, each item pointing to the task that covers it. -->

- The move to dbt v2, when its DuckDB adapter covers what D2 needs — T070

## 2. Method — how we find out

### 2.1 Approach

<!-- The variants, options or probes compared, and what each one tells that the others do not. -->

| Variant | What it is | What it tells |
|---|---|---|
| | | |

#### 2.1.1 Shared behaviour

<!-- Optional. Rules every variant follows (schedules, formats, key layouts, logs), stated once so the steps can cite them. -->

-

#### `<A>`. `<Title of variant, option or probe A>`

<!-- Detailed description -->

### 2.3 Decision log

<!-- It logs decisions about the method, before and during the run, including changes of course. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Column Applies to: anchor link(s) to the section where the decision is applied, named in one or two words (e.g. Q1, Probe A, File layout).
- Column Decided at: the Status phase where it was decided (Method, Steps), `<phase> review` when decided while reviewing that phase, or `Running step N` when decided during the run.
-->

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| `<N>` |  |  |  |  |

### 2.4 File layout

<!-- Every file and folder the spike creates, as a tree with its purpose in one line. Captured data and outputs are marked as ignored by Git. The README is always included. -->

```text
spikes/dbt-in-the-pipeline/
├── README.md        Question, setup and commands, what each script does, link to the report
└── <file>           <purpose>
```

## 3. Steps
<!-- Each step is one reviewable result, touching at most 2–3 files.
- Status: where the step is: 💤 todo · 🎬 ready · 🔄 in progress · ⛔ blocked · ✅ done
- Who: Owner (manual actions: dashboards, accounts, deploys, runs, checks) or Claude (code and documents).
- Commit: only in a step that changes committed files: the proposed message, following the Git conventions in CLAUDE.md.
- Model: the model and effort the step's session runs with (e.g. sonnet · medium), or — when Who is Owner.
- Gate: optional. <condition> → <consequence if it fails: variants or steps dropped or re-decided>. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

### Step 1 — `<title>`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** following the Git conventions in CLAUDE.md.
- **Model:** `<model · effort>` (or —)
- **Gate:** `<condition>` → `<consequence>`

#### Scope

<!-- The result of the step. List the components and the files created or changed (code, tests, docs). A reviewer should know what the diff will contain from this section alone. -->

#### Reads

<!-- List of reads containing what to read (be specific with paragraph or line), what contains the read, and why it is interesting here.  -->

#### Do

<!-- Numbered actions in execution order, one verb each (write, implement, update, run). Every file named here must appear in Scope; add nothing Scope does not list. -->

#### Check

<!-- command/s or verification with a yes/no result. -->

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
