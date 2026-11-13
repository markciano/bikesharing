<!--
Design doc template. A design doc is the working document of one task: Spec (what and why), Plan (how), Steps (implementation), Close (what was delivered).
It is detailed enough that Code can implement it without making design decisions.
Sections marked Optional are kept only when they apply.
-->

# Design: Processing pipeline

- **Task:** T060
- **ADRs:** [ADR-0025](../decisions/0025-sql-models-directed-by-python.md), [ADR-0026](../decisions/0026-budget-shares-per-component.md), [ADR-0027](../decisions/0027-modal-as-execution-platform.md), [ADR-0029](../decisions/0029-pipeline-code-architecture.md)
- **New ADRs from this doc:** none

## Status

<!-- State: Draft 📝 · Ready for implementation 🎬 · In progress 🔄 · Complete ✅.
Phase: the blocks and reviews completed.
Current step: the step being implemented, or —. -->

- State: Draft 📝
- Phase: [ ] Spec · [ ] Plan · [ ] Plan review · [ ] Steps · [ ] Steps review
- Current step: —

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

The pipeline is built one business process at a time, following Kimball's bus architecture: the model is designed once in [d005](d005-data-model.md), and each child task of T060 builds one of its business processes from bronze to silver and gold and runs it on Modal. Each child's design fixes that process's columns, gold tables and code. Observability is a child of its own. The first slice measures real run time and memory, which several carried-over inputs depend on.

Rejected: a split by layer (silver, then gold), since silver would be built with no consumer to validate it, and real runs would be measured late.

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

### 1.5 Open questions

<!-- Optional. The decisions still to take about the what, in dependency order. Each one closes as a decision in Decided at framing and leaves the table, so it is empty at Spec approval. Questions about the how are Plan decisions. -->

| OQ | Question | Depends on | Notes |
|---|---|---|---|
| OQ1 | The pipeline's mode (24/7 or on demand) and refresh cadence, against [d002 › R3](d002-requirements.md#requirements) and the freshness that d002's Q1, Q2 and Q5 need | d005 | The visitor sees the data's age as cadence plus run time (about 2 min, not measured): a 5–10 minute cadence gives about 7–12 minutes, above R3's 5 minutes ([s013 › D3](../spikes/s013-visualization-tool.md#d3-static-web-page-with-javascript)). Running 24/7, R2's Class B quota allows a commit every 10 minutes or more ([s010 › P5](../spikes/s010-storage-table-format.md#production-inputs)) |
| OQ2 | How the historical archives reach R2 and are loaded, and how the Bicing archive is checked against the real-time capture | d005 | Bicing's archive is not on R2 yet. The check was handed to T040 by [d002 › Out of scope](d002-requirements.md) and is taken here |
| OQ3 | Data quality: which rules and indicators this task builds and which T042 builds | d005 | [ADR-0025](../decisions/0025-sql-models-directed-by-python.md) leaves where rules live and their format to T042 |
| OQ4 | How a silver or gold row is traced back to its bronze objects and to the run that wrote it | d005 | Column-level lineage and the source field dictionary are decided in d005 |
| OQ5 | How the owner queries the logs of capture, the pipeline and the web page together | — | Today, querying capture's logs means downloading hundreds of files. Capture's logs do not enter the data model, which measures the feeds' timeliness and completeness on the data ([d005 › D26](d005-data-model.md#d26-timeliness-and-completeness-of-the-feeds)) |
| OQ6 | A script with the owner's common health queries, and whether it can run from a phone | OQ5 | [s013 › D5](../spikes/s013-visualization-tool.md#d5-no-separate-operations-panel). An option from [s013 › P9](../spikes/s013-visualization-tool.md#55-production-inputs), not verified: a manual GitHub Actions run, with no server, but its summary is public if the repository is, and GitHub holds one more read-only key |
| OQ7 | The child tasks `T060.M`: one per business process, plus observability, in build order | D1, OQ1–OQ6 | |

## 2. Plan — how

<!-- 2-3 sentences -->

### 2.1 Approach

<!-- Detailed plan organized by #### blocks.
Block `3. Steps` is written using this plan.
If some block contains `options considered`, include them with pros and cons.
-->

#### Carried-over inputs

Inputs about the how, left to this design by earlier spikes and designs; each becomes a Plan concern or part of one.

- **Execution platform check:** if the first slice measures runs of 1 minute or less, or normal runs of 2 GB or less, or OQ1 chooses the on-demand mode, the decision of [ADR-0027](../decisions/0027-modal-as-execution-platform.md) is reopened with Cloud Run and Fly.io as candidates. The run's final log event carries `duration_s` and `peak_memory_mb`, the latter from `ru_maxrss` ([s012 › D1, P1](../spikes/s012-execution-target.md#d1-execution-platform)).
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

## 3. Steps

<!-- Each step is one reviewable result and one commit, touching at most 2–3 files.
- Status: where the step is: 💤 todo · 🎬 ready · 🔄 in progress · ⛔ blocked · ✅ done
- Who: Owner (manual actions: dashboards, accounts, deploys, runs, checks) or Claude (code and documents).
- R: the requirements the step implements or tests, or —.
- Commit: the proposed message, following the Git conventions in CLAUDE.md.
- Model: the model and effort the step's session runs with (e.g. sonnet · medium), or — when Who is Owner. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

### Step 1 — `<Title>`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** following the Git conventions in CLAUDE.md, including `<dNNN.sN - >` at the begining of the message, for the design and the step number.
- **R:** R1, R3 (or —)
- **Model:** `<model · effort>` (or —)

#### Scope

<!-- The result of the step. List the components, the files created or changed (code, tests, docs), and the tests from the Test plan that cover it. A reviewer should know what the diff will contain from this section alone. -->

#### Reads

<!-- List of reads containing what to read (be specific with paragraph or line), what contains the read, and why it is interesting here.  -->

#### Do

<!-- Numbered actions in execution order, one verb each (write, implement, update, run). Every file named here must appear in Scope; add nothing Scope does not list. -->

#### Check

<!-- command/s or verification with a yes/no result. -->

## 4. Close

<!-- The record of what the task delivered, for whoever opens this design later. -->

### 4.1 Implemented

<!-- Component — what was delivered; tests passing. -->

### 4.2 Known gaps at close

<!-- What the task leaves undone or imperfect, each with the task that covers it: requirements not fully met, File layout items not delivered, TODOs citing this task. "None" is valid. -->

- `<gap>` — TNNN

### 4.3 Decisions taken during implementation

<!-- Decisions made after the Plan was approved, including deviations from Scope approved by the owner. Oldest first; "None" is valid.
- #: `DI1`, `DI2`… (decision during implementation).
- Applies to: anchor link(s) to the design section the decision changes, or the path of a file outside the design.
- Decision and Reason: one line each; the content goes where it applies.
- Decided at: the step where it was decided (`Step N`).
-->

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| | | | | |
