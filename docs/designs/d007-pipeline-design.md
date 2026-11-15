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

1. T060.1, a walking skeleton on the station stock from real-time capture: the thinnest path from bronze to a published file, run on Modal. It builds the conformed dimensions that the other processes reuse, and measures the real run time and memory that several carried-over inputs depend on.
2. The historical archives, loaded into the station stock.
3. The stock by vehicle type and the stock movements, in the order OQ7 sets.
4. Observability, a child of its own.

What would change it: the measurements of T060.1 can reopen [ADR-0027](../decisions/0027-modal-as-execution-platform.md) (Carried-over inputs › Execution platform check); the later children are then built on the platform that review keeps.

Rejected: a split by layer (silver, then gold), since silver would be built with no consumer to validate it, and real runs would be measured late.

#### D2. Visualization after all slices

Each slice ends at a published file, not at a page. The public page (T041) is built once every business process publishes, so it is designed as a whole. Without a page, a slice is validated by data tests on its silver and gold tables, by reconciling its row counts from bronze to silver to gold, and by one acceptance query on gold per question it closes, checked on real data. Each published file has a fixed contract, a JSON Schema checked by a contract test ([ADR-0015](../decisions/0015-contract-tests-by-contract-kind.md)), which is what T041 builds on.

What would change it: if T041 needs a file shaped differently, the contract and its test change in T041.

Rejected: a minimal page after T060.1, to validate the file's shape and the page's deployment early, since the data validation above does not need a page and T060.1 already deploys the file.

#### D3. Continuous mode with a 15-minute cadence

The pipeline runs 24/7 on a schedule, every 15 minutes, so the visitor sees data about 17 minutes old (cadence plus a run of about 2 min, not measured). This refines [d002 › R3](d002-requirements.md#requirements). The cadence starts with margin because its cost estimate rests on a run time nobody has measured yet ([s012 › D1](../spikes/s012-execution-target.md#d1-execution-platform)); lowering it is a configuration change, not a redesign.

What would change it: when the runs measured in T060.1 show that a 10-minute cadence costs less per month than Modal's monthly credit of $30, the cadence lowers to 10 min. It does not go below 10 min, the shortest interval R2's Class B quota allows running 24/7 ([s010 › P5](../spikes/s010-storage-table-format.md#production-inputs)).

Rejected: on-demand runs, since the station status (d002's Q1) must stay current with no one asking for it; a 10-minute cadence from the start, since it would rest on the unmeasured run time.

#### D4. Data quality in four classes

The data quality catalog sorts every rule of [data-model.md › Data contract](../data-model.md#data-contract), every indicator and every new check into four classes, following the dimensions of DAMA-DMBOK and ISO/IEC 25012. A class sets how the item is verified:

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

Severity follows who causes a failure. A rule on the pipeline's own logic fails with severity error, following Write-Audit-Publish: the run publishes nothing, the page keeps the last file that passed, and the failure is logged in the run's events, so the visitor sees only an older data age. A rule on a provider's data fails with severity warn: the failure is logged and the run publishes. The owner learns of a failure of either severity through observability (OQ5).

A quality indicator is kept if it is actionable, when the owner acts on capture, on a provider or on the model's reference data as it moves, or if it measures a provider's quality, which answers [d002 › Q2](d002-requirements.md#guiding-questions). RDM58, RDM61, RDM64 and the counts above `capacity` form each provider's scorecard. [d002 › R14](d002-requirements.md#requirements) is an actionable indicator, built by the observability child since it reads capture's logs.

Frozen counts also reach the visitor: a published file that holds a station's latest count marks it when that count is frozen (RDM61), so a stale count is never shown as current. How the page shows the mark is decided by T041.

Rejected: severity warn for rules on the pipeline's logic, since the visitor could then see wrong data with no sign of it; severity error for rules on a provider's data, since the page would stop for what the project cannot fix; a rule that blocks counts above `capacity`, since GBFS defines no relation between the two and both are kept as published; frozen counts for the owner only, since the visitor could then trust a count hours old.

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
| `TNNN.1` | | | — | |

### 1.6 Open questions

<!-- Optional. The decisions still to take about the what, in dependency order. Each one closes as a decision in Decided at framing and leaves the table, so it is empty at Spec approval. Questions about the how are Plan decisions. -->

| OQ | Question | Depends on | Notes |
|---|---|---|---|
| OQ2 | How the historical archives reach R2 and are loaded, and how the Bicing archive is checked against the real-time capture | d005 | Bicing's archive is not on R2 yet. The check was handed to T040 by [d002 › Out of scope](d002-requirements.md) and is taken by T060. Decided by the child that loads the history, since no other child shares it; Children assigns it |
| OQ3 | The rest of the data quality catalog (D4): the published file's age as an indicator, where each item is queried, and what this task builds and what T042 builds | D4 | RDM60 measures service, not quality, and leaves the catalog. [ADR-0025](../decisions/0025-sql-models-directed-by-python.md) leaves where rules live and their format to T042 |
| OQ4 | How a silver or gold row is traced back to its bronze objects and to the run that wrote it | d005 | Column-level lineage and the source field dictionary are decided in d005 |
| OQ5 | How the owner queries the logs of capture, the pipeline and the web page together, and learns of a failed runtime rule of either severity (D4) | — | Today, querying capture's logs means downloading hundreds of files. Capture's logs do not enter the data model, which measures the feeds' timeliness and completeness on the data ([d005 › D26](d005-data-model.md#d26-timeliness-and-completeness-of-the-feeds)). Decided by the observability child (D1); Children assigns it |
| OQ6 | A script with the owner's common health queries, and whether it can run from a phone | OQ5 | [s013 › D5](../spikes/s013-visualization-tool.md#d5-no-separate-operations-panel). An option from [s013 › P9](../spikes/s013-visualization-tool.md#55-production-inputs), not verified: a manual GitHub Actions run, with no server, but its summary is public if the repository is, and GitHub holds one more read-only key. Decided by the observability child (D1); Children assigns it |
| OQ7 | The child tasks `T060.M`: one per business process, plus observability, in build order | D1, OQ1–OQ6 | Each child changes its tables' `TODO(T060)` markers in [data-model.md › Data contract](../data-model.md#data-contract) to its own ID |

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
