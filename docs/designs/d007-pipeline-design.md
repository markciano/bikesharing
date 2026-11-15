<!--
Design doc template. A design doc is the working document of one task: Spec (what and why), Plan (how), Steps (implementation), Close (what was delivered).
It is detailed enough that Code can implement it without making design decisions.
Sections marked Optional are kept only when they apply.
Kind: a build task builds code or configuration and has every block. A document-only task delivers documents only, written during the Spec and the Plan, and has no Steps block. A parent is a document-only task with children (`TNNN.M`): it holds what its children share, and its Children section.
-->

# Design: Processing pipeline

- **Task:** T060
- **Kind:** parent
- **ADRs:** [ADR-0025](../decisions/0025-sql-models-directed-by-python.md), [ADR-0026](../decisions/0026-budget-shares-per-component.md), [ADR-0027](../decisions/0027-modal-as-execution-platform.md), [ADR-0029](../decisions/0029-pipeline-code-architecture.md)
- **New ADRs from this doc:** none

## Status

<!-- State: Draft 📝 · Complete ✅.
Phase: the blocks and reviews completed. -->

- State: Draft 📝
- Phase: [ ] Spec · [ ] Plan · [ ] Plan review

## 1. Spec — what and why

<!-- What the result does seen from outside, not how it is built. The test: if whoever uses the result would notice a change, it belongs here; if not, it belongs to the Plan. External systems and their data (feeds, fields) may be named. -->

### 1.1 Context

<!-- 2–4 sentences for a reader with no prior context: the problem or need and why it matters now; who or what uses the result; where things stand today, including any design or spike this builds on. No solution here: it starts in Decided at framing. For a correction: current vs expected behaviour and how to reproduce it. -->

Capture writes the raw feeds of AMBici and Bicing to the bronze layer on R2 ([d004](d004-bronze-data-capture.md)), and [d005](d005-data-model.md) designs the data model that silver and gold hold. Nothing builds that model yet, so the questions of [d002](d002-requirements.md) have no answer and the public visualization (T041) has no data to show. This design decides how the pipeline builds silver and gold from bronze on the stack chosen by s010–s013, within the project's budget, and how the owner inspects the operation of capture and the pipeline, which today means downloading hundreds of capture log files.

### 1.2 Decided at framing

<!-- Optional. One heading per decision about what the result does. In this order, so the reader finds what matters first:
1. The decision and why, in one short paragraph.
2. What would change it, and what would not, each with the action to take. Only when a later event could reopen it.
3. The options rejected.
4. The artefact that fixes it, in whatever form the decision needs (e.g. a mapping table, a page map, a weighted matrix). An artefact that does not fit here or must outlive the design goes in its own file: the Plan decides where it lives and its format, File layout lists it, and this decision links to it.

A security decision lists its threats in this table, with IDs `TH1`, `TH2`… per document:

| # | Threat (STRIDE) | Impact | Control | Requirement |
|---|---|---|---|---|
| `TH1` | | | | |
-->

#### D1. Build by vertical slice

The pipeline is built one business process at a time, following Kimball's bus architecture: the model is designed once in [d005](d005-data-model.md), the concerns shared by every process (scheduling, lineage, data quality, the historical load, observability) are decided once in this design, and each child task of T060 builds one business process from bronze to silver and gold and runs it on Modal. Each child's design fixes that process's columns, gold tables and code, and moves its tables' column rules into their worksheets.

The build order:

1. T060.1, a walking skeleton on the station stock from real-time capture: the thinnest path from bronze to a published file, run on Modal. It builds the conformed dimensions that the other processes reuse, fixes the patterns the later children apply, and measures the real run time and memory that several carried-over inputs depend on.
2. T060.2, observability.
3. T060.3, the stock by vehicle type and then the stock movements, both from real-time capture.
4. T060.4, the historical archives, loaded into the station stock.

Observability comes right after T060.1, following the SRE practice of monitoring from the first production release: from T060.1 the pipeline runs 24/7, and a run that fails publishes nothing with no other sign (D4). It needs only what T060.1 and capture already emit, the log events of [ADR-0036](../decisions/0036-log-convention-across-components.md), so a later child's rules reach its alerts with no change, and a later indicator, such as RDM58, only adds its target.

After T060.2, no child depends on another, so they follow increasing difficulty: each adds one new kind of work to what the previous ones built. The stock by vehicle type repeats T060.1's pattern with one more dimension; the stock movements compare each count with the previous one of its station, across runs; the historical load brings a new source, a bulk load that can be rerun and its check against real-time capture. The two real-time processes share one child, since neither takes an architecture decision.

What would change it: the measurements of T060.1 can reopen [ADR-0027](../decisions/0027-modal-as-execution-platform.md) (Carried-over inputs › Execution platform check); the later children are then built on the platform that review keeps. If T060.3's steps exceed ten, its design splits it into one child per process.

Rejected: a split by layer (silver, then gold), since silver would be built with no consumer to validate it, and real runs would be measured late; observability as the last child, since two children would be built with the pipeline in production and no alert of a failed run; one child per business process, since the stock by vehicle type would take a full design and pull request for little to decide; the historical load right after T060.1, since nothing depends on it and the archives are already held by the owner.

#### D2. Visualization after all slices

Each slice ends at a published file, not at a page. The public page (T041) is built once every business process publishes, so it is designed as a whole. Without a page, a slice is validated by data tests on its silver and gold tables, by reconciling its row counts from bronze to silver to gold, and by one acceptance query on gold per question it closes, checked on real data. Each published file has a fixed contract, a JSON Schema checked by a contract test ([ADR-0015](../decisions/0015-contract-tests-by-contract-kind.md)), which is what T041 builds on.

What would change it: if T041 needs a file shaped differently, the contract and its test change in T041.

Rejected: a minimal page after T060.1, to validate the file's shape and the page's deployment early, since the data validation above does not need a page and T060.1 already deploys the file.

#### D3. Continuous mode with a 15-minute cadence

The pipeline runs 24/7 on a schedule, every 15 minutes, so the visitor sees data about 17 minutes old (cadence plus a run of about 2 min, not measured). This refines [d002 › R3](d002-requirements.md#requirements). The cadence starts with margin because its cost estimate rests on a run time nobody has measured yet ([s012 › D1](../spikes/s012-execution-target.md#d1-execution-platform)).

What would change it: when the runs measured in T060.1 show that a 10-minute cadence costs less per month than Modal's monthly credit of $30, the cadence lowers to 10 min. It does not go below 10 min, the shortest interval R2's Class B quota allows running 24/7 ([s010 › P5](../spikes/s010-storage-table-format.md#production-inputs)).

Rejected: on-demand runs, since the station status (d002's Q1) must stay current with no one asking for it; a 10-minute cadence from the start, since it would rest on the unmeasured run time.

#### D4. Data quality in four classes

The data quality catalog sorts every rule of [data-model.md › Data contract](../data-model.md#data-contract), every indicator and every new check into four classes, following the dimensions of DAMA-DMBOK and ISO/IEC 25012. The runtime rules and the quality indicators form the catalog, in a document of their own apart from the model, as the Open Data Contract Standard keeps quality apart from the schema; the Plan fixes its file and format. A class sets how the item is verified:

| Class | What it is | Verified by | Items of the Data contract |
|---|---|---|---|
| Transformation spec | How a value is built | Unit or integration test in CI, on fixtures | RDM4–RDM14, RDM16–RDM21, RDM23–RDM28, RDM30, RDM31, RDM37–RDM55, RDM57, RDM63, RDM70–RDM72, RDM74, RDM76 |
| Runtime rule | What must always hold on real data | Data test in every run | RDM1, RDM3, RDM15, RDM22, RDM29, RDM32–RDM36, RDM52, RDM56 |
| Quality indicator | A measure tracked over time | Gold table, queried by the owner | RDM58, RDM61, RDM62, RDM64, RDM75; the review table of RDM43, RDM46 and RDM73 |
| Documentation | Worksheets, source cards and the feeds read | Inspection | RDM65–RDM69 |

Besides the Data contract, these checks join the catalog:

| Check | Class | Dimension | Severity |
|---|---|---|---|
| Schema drift: a bronze feed adds or drops a field of those the model reads (RDM65, RDM69) | Runtime rule | Validity | warn |
| Volume: a capture lists fewer stations than the recent median, by more than the threshold the slice building it fixes | Runtime rule | Completeness | warn |
| Reconciliation: the rows a run adds to silver and gold match the items it reads from bronze, by count, or by total in a gold table that aggregates | Runtime rule | Completeness | error |
| Counts above `capacity`: the share of station items whose vehicles and docks exceed the station's `capacity`, leaving out AMBici's +P stations (RDM52), whose bikes in +P spaces exceed it by design | Quality indicator | Consistency | — |
| Published file age: the time since the capture of the data in each file the page serves, which alerts the owner when it exceeds one cadence plus one run ([d002 › R3](d002-requirements.md#requirements)) | Quality indicator | Timeliness | — |

Severity follows who causes a failure. A rule on the pipeline's own logic fails with severity error, following Write-Audit-Publish: the run publishes nothing, the page keeps the last file that passed, and the failure is logged in the run's events, so the visitor sees only an older data age. A rule on a provider's data fails with severity warn: the failure is logged and the run publishes. The owner learns of a failure of either severity through observability (OQ5).

A quality indicator is kept if it is actionable, when the owner acts on capture, on a provider or on the model's reference data as it moves, or if it measures a provider's quality, which answers [d002 › Q2](d002-requirements.md#guiding-questions). RDM58, RDM61, RDM64 and the counts above `capacity` form each provider's scorecard. [d002 › R14](d002-requirements.md#requirements) is an actionable indicator, built by the observability child since it reads capture's logs. RDM60, a station's service, measures the business, not its data, and stays in the model outside the catalog.

Each quality indicator has a target, such as a minimum monthly completeness. Capture's completeness target of [d004 › D6](d004-bronze-data-capture.md) joins the catalog. An initial value comes from what the source cards measured on real captures, and the child that builds the alerts reviews it against weeks of production indicators before it closes, following the SRE practice of setting an objective from a measured baseline. This task builds the whole catalog; T042 is absorbed by it.

Frozen counts also reach the visitor: a published file that holds a station's latest count marks it when that count is frozen (RDM61), so a stale count is never shown as current. How the page shows the mark is decided by T041.

Rejected: severity warn for rules on the pipeline's logic, since the visitor could then see wrong data with no sign of it; severity error for rules on a provider's data, since the page would stop for what the project cannot fix; a rule that blocks counts above `capacity`, since GBFS defines no relation between the two and both are kept as published; frozen counts for the owner only, since the visitor could then trust a count hours old.

#### D5. Lineage at four levels

Lineage is covered at the four levels that OpenLineage and Kimball's audit dimension name, adding as little as each level needs:

| Level | Question | Where it is answered |
|---|---|---|
| Table | Which tables feed which | The bus matrix and the table worksheets ([d005](d005-data-model.md)) |
| Column | Which source field a column comes from | The source field dictionary (RDM68, RDM69) |
| Run | What a run read and wrote, and its outcome | The run's log events, kept 30 days ([ADR-0036](../decisions/0036-log-convention-across-components.md)) |
| Row | Which run and code version wrote a row, and which bronze object it comes from | Every silver and gold row carries the ID of the run that wrote it and the code version of that run, kept as long as the row; a silver row's bronze object follows from its system, feed and capture instant, since bronze is kept indefinitely ([ADR-0021](../decisions/0021-retention-per-layer.md)) |

Rejected: a table of runs, with the bronze object's key in every silver row and the configuration version of each run, since this project does not need more than the levels above; the run's ID alone in each row, since the code version would be lost with the logs and the Delta history after 30 days at most.

#### D6. No release tracking

Nothing is built to show which code each platform runs. Each component already reports its own version in what it produces: capture as its Worker's version ID ([ADR-0036](../decisions/0036-log-convention-across-components.md)), the pipeline in its rows and logs (D5). Since every deployment is made by hand from `main` right after a merge, the commit behind a deployment is the last merge to `main` before the deployment's time on its platform.

What would change it: deployments made by GitHub Actions, which could then record each one with its commit (GitHub Deployments).

Rejected: tagging each deployment with its commit on its platform, and reading every component's latest version in one health query, since an occasional lookup by time is enough for this project.

### 1.3 Requirements

<!-- Optional. The acceptance criteria, cited by number in the Test plan and the steps. They translate Decided at framing and cite the decision they come from; nothing is decided here.
One behaviour per requirement, verifiable, with a measurable threshold where one applies. Written in EARS:
- Ubiquitous: The <system> shall <response>.
- Event: When <trigger>, the <system> shall <response>.
- State: While <state>, the <system> shall <response>.
- Unwanted: If <condition>, then the <system> shall <response>.
- Optional: Where <feature is included>, the <system> shall <response>.
Only requirements specific to this task; project-wide rules (CLAUDE.md, ADRs) are not repeated. -->

- **R1** `<EARS statement>` (D`<N>`)

### 1.4 Done when

<!-- Optional. Only what closes this task and Requirements cannot express: operational actions, checks on real data, understanding. The general closing rule is checked in `.claude/skills/implement/review.md`. -->

- `<extra condition>`

### 1.5 Children

<!-- Parent only. The child map, in build order: each child's scope (e.g. the business process it builds), the questions or requirements it closes, the children it depends on, and the condition that closes it. Each child has its own working document, which cites the parent's decisions instead of repeating them. Every open question and requirement of the parent is closed by the parent or by one child. The parent's Done when: its Open questions closed and its children created. -->

| Child | Scope | Closes | Depends on | Done when |
|---|---|---|---|---|
| T060.1 | The station stock from real-time capture as a walking skeleton (D1), with the conformed dimensions Date, Time of day, System and Station, up to its published file | [d002 › Q1](d002-requirements.md#guiding-questions) without the split by type, Q2, Q3, Q5, Q8; the cadence review (D3) and the execution platform check (Carried-over inputs) | — | It runs on Modal every 15 min in production; one acceptance query per question passes on real data (D2); its run time and memory are measured, and the cadence and [ADR-0027](../decisions/0027-modal-as-execution-platform.md) are reviewed against them |
| T060.2 | Observability of capture and the pipeline: their logs queried together, and alerts on failed runtime rules and on quality indicators off target (D4) | How the owner queries the logs of capture, the pipeline and the page together, and learns of a failed runtime rule of either severity; a script with the owner's common health queries, and whether it runs from a phone ([s013 › D5](../spikes/s013-visualization-tool.md#d5-no-separate-operations-panel), [P9](../spikes/s013-visualization-tool.md#55-production-inputs)); [d002 › R14](d002-requirements.md#requirements) | T060.1 | A failed rule of each severity reaches the owner; the indicator targets are reviewed against weeks of production indicators (D4) |
| T060.3 | The stock by vehicle type, then the stock movements, from real-time capture, with the Vehicle type dimension | [d002 › Q1](d002-requirements.md#guiding-questions)'s split by type, Q4, Q6, Q7; RDM58's target in T060.2's alerts | T060.1, T060.2 | One acceptance query per question passes on real data (D2) |
| T060.4 | The historical archives, loaded into the station stock | How the archives reach R2 and are loaded, and how Bicing's archive is checked against real-time capture, the check handed over by [d002 › Out of scope](d002-requirements.md) | T060.1 | The archives the model takes ([data-model.md › Grain](../data-model.md#grain)) are in the station stock and pass their check against real-time capture |

Each child changes its tables' `TODO(T060)` markers in [data-model.md › Data contract](../data-model.md#data-contract) to its own ID.

## 2. Plan — how

<!-- 2-3 sentences -->

### 2.1 Approach

<!-- Detailed plan organized by #### blocks.
Approach lists the main and supporting deliverables, each already written.
If some block contains `options considered`, include them with pros and cons.
-->

#### Carried-over inputs

Inputs about the how, left to this design by earlier spikes and designs; each becomes a Plan concern or part of one.

- **Execution platform check:** if the first slice measures runs of 1 minute or less, or normal runs of 2 GB or less, the decision of [ADR-0027](../decisions/0027-modal-as-execution-platform.md) is reopened with Cloud Run and Fly.io as candidates. The run's final log event carries `duration_s` and `peak_memory_mb`, the latter from `ru_maxrss` ([s012 › D1, P1](../spikes/s012-execution-target.md#d1-execution-platform)).
- **Memory:** set DuckDB's memory limit below the container's; decide on a hard container limit (`memory=(request, limit)`; without one, usage above the request is billed, as Modal charges the higher of the two); cap what one run processes and leave the rest to the next; do not retry memory errors, since they are permanent; check in the first slice how Modal treats a memory kill of a scheduled function ([s012 › D3, TH12](../spikes/s012-execution-target.md#d3-pipeline-security), [d002 › R23](d002-requirements.md#requirements)).
- **Reading many JSON files:** in DuckDB 2.0.0, `read_json` over thousands of files runs out of memory when it binds each file's schema, with `union_by_name` or a schema sample over every file ([duckdb#27806](https://github.com/duckdb/duckdb/issues/27806)). The fix is merged upstream, but no release carrying it was confirmed. The d005 profile met it ([spikes/d005-data-model › profile](../../spikes/d005-data-model/README.md#profile)).
- **Platform separation:** CI checks for rules 1, 2 and 4 of [ADR-0029](../decisions/0029-pipeline-code-architecture.md), and where the platform module lives in the repository ([s012 › D4](../spikes/s012-execution-target.md#d4-processing-logic-separated-from-the-platform)).
- **Run operation** ([s012 › Out of scope](../spikes/s012-execution-target.md#15-out-of-scope)): which events the pipeline logs; preventing two runs from overlapping; the region (`eu` costs 1.15x); runs safe to run again after an interruption; Modal's usage and spend limits; the size of catch-up batches and where the one-off history load runs; the end-to-end and post-deploy smoke tests.
- **Publishing:** the pipeline generates the prepared files from an explicit list and deploys them at the end of a run, with the token from the secret store; a failed deployment does not fail the run's data ([s013 › P8](../spikes/s013-visualization-tool.md#55-production-inputs)). Before building it, try a few deployments with the token limited to one Worker and read Cloudflare's terms ([s013 › Not verified](../spikes/s013-visualization-tool.md#54-not-verified)).
- **R2 operation classes:** confirm with R2's per-operation metrics (GraphQL Analytics) the class of conditional PutObject, ListObjectsV2 and DeleteObjects, which the pricing page does not name; s010 confirmed only class totals ([s010 › F14](../spikes/s010-storage-table-format.md#4-findings)).

### 2.2 Decision summary

<!-- It logs decisions about the plan, including changes. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Applies to: anchor link(s) to the section where the decision is applied, named in one or two words.
- Decided at: the Status phase where it was decided (Plan, Steps), or `<phase> review` when decided while reviewing that phase.
- R: Requirement affected.
-->

| # | Applies to | Decision | Reason | R | Decided at |
|---|---|---|---|---|---|
| | | | | | |

### 2.3 Architecture

<!-- Optional. One diagram and 2–3 sentences. -->

### 2.4 File layout

<!-- Every file and folder the task creates or modifies, documents included, as a tree: (new) or (modified), and its purpose or change in one line. A task that adds a component also lists its CI job in `.github/workflows/ci.yml` (recipe in `.claude/rules/code/ci.md`), and its version files, manifest and lockfile (`.claude/rules/code/dependencies.md`). -->

```text
<path>/
└── <file>      (new)        <purpose>
```

### 2.5 Components

<!-- Optional. One subsection per component. The contract is exact, in the component's own language, never pseudocode. -->

#### `<ComponentName>`

- **Responsibility:** `<one sentence>`
- **Location:** `path/to/file`
- **Contract:**

```python
```

### 2.6 Test plan

<!-- Optional. Every requirement has at least one verification method (IADT: Inspection, Analysis, Demonstration, Test). Test is the default, at the lowest level that can verify the requirement. Another method only when no test can: Inspection for configuration or documents, Analysis for production data or measurements, Demonstration for behaviour observed end to end, such as a third-party service. -->

| R | Method | What is verified | Level |
|---|---|---|---|
| R1 | Test / Inspection / Analysis / Demonstration | | unit / integration / e2e; — for other methods |

### 2.7 Breaking changes

<!-- Optional. Shared models or interfaces this design changes, and how their dependants are handled. -->

| File | Why it breaks | Strategy |
|---|---|---|
| | | |

### 2.8 What does not change

<!-- Optional. Code or documents that must not be modified. Out of scope limits the what; this section limits the how. -->

-

## 3. Close

<!-- The record of what the task delivered, for whoever opens this design later. -->

### 3.1 Implemented

<!-- Deliverable — what it holds. A parent also names the children's issues created at its close; this block is not updated as they progress, since their state lives in their issues and their own working documents. -->

### 3.2 Known gaps at close

<!-- What the task leaves undone or imperfect, each with the task that covers it: requirements not fully met, File layout items not delivered, TODOs citing this task. "None" is valid. -->

- `<gap>` — TNNN

### 3.3 Decisions taken during implementation

<!-- Decisions made after the Plan was approved, including deviations from Scope approved by the owner. Oldest first; "None" is valid.
- #: `DI1`, `DI2`… (decision during implementation).
- Applies to: anchor link(s) to the design section the decision changes, or the path of a file outside the design.
- Decision and Reason: one line each; the content goes where it applies.
- Decided at: the step where it was decided (`Step N`).
-->

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| | | | | |
