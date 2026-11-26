<!--
Design doc template. A design doc is the working document of one task: Spec (what and why), Plan (how), Steps (implementation), Close (what was delivered).
It is detailed enough that Code can implement it without making design decisions.
Sections marked Optional are kept only when they apply.
Kind: a build task builds code or configuration and has every block. A document-only task delivers documents only, written during the Spec and the Plan, and has no Steps block. A parent is a document-only task with children (`TNNN.M`): it holds what its children share, and its Children section.
-->

# Design: Delta maintenance and access in the pipeline

- **Task:** T072
- **Kind:** build
- **ADRs:** [ADR-0021](../decisions/0021-retention-per-layer.md), [ADR-0052](../decisions/0052-delta-maintenance-and-access-pattern.md)
- **New ADRs from this doc:** `<ADRs created during this design, or "none">`

## Status

<!-- State: Draft 📝 · Ready for implementation 🎬 · In progress 🔄 · Complete ✅. A document-only task goes from Draft to Complete.
Phase: the blocks and reviews completed. A document-only task shows only Spec · Plan · Plan review.
Current: where work resumes (the step being implemented, or the block and section of the design; — when complete), plus only what the next session cannot derive from the document, such as an instruction from the owner. Nothing it can re-derive: options, recommendations, files to read, later sections. A document-only task names the section. -->

- State: Draft 📝
- Phase: [ ] Spec · [ ] Plan · [ ] Plan review · [ ] Steps · [ ] Steps review
- Current: Spec › Decisions, from OQ3. Parked for the Plan: how the common table access is enforced (module, and a possible rule in `.claude/rules/`); rewriting [d008 › Delta writes](d008-pipeline-platform-and-walking-skeleton.md#delta-writes), whose #6 makes maintenance a separate job; the owner leans to partitioning `processed_objects` like bronze's keys (system, feed, date)

## 1. Spec — what and why

<!-- What the result does seen from outside, not how it is built. The test: if whoever uses the result would notice a change, it belongs here; if not, it belongs to the Plan. External systems and their data (feeds, fields) may be named. -->

### 1.1 Context

<!-- 2–4 sentences for a reader with no prior context: the problem or need and why it matters now; who or what uses the result; where things stand today, including any design or spike this builds on. No solution here: it starts in Decided at framing. For a correction: current vs expected behaviour and how to reproduce it. -->

The pipeline's first slice (T060.1) manages its Delta tables on R2 poorly: a run opens its tables several times and reads them with no bounds, so its lakehouse reads and its run time grow every day; a run counted 12,369 GetObject, most of them in full reads of the control table `processed_objects` ([s019 › Verdict](../spikes/s019-pipeline-run-time-r2-reads.md#53-verdict)). [ADR-0052](../decisions/0052-delta-maintenance-and-access-pattern.md) sets how every pipeline table is accessed and maintained, and this task applies it to the slice's tables before the next slices build on them, together with silver's rolling 12-month retention ([ADR-0021](../decisions/0021-retention-per-layer.md)). The result is the scheduled pipeline itself, and the owner who operates it: its reads and run time per run should stop growing with the data held.

### 1.2 Decided at framing

<!-- Optional. One heading per decision about what the result does. In this order, so the reader finds what matters first:
1. The decision and why, in one short paragraph. A decision with several parts (rules, cases, steps) follows it with them as a list, or a numbered list for steps in order, each with its reason.
2. What would change it, and what would not, each with the action to take. Only when a later event could reopen it.
3. The options rejected that a later reader could propose again, each with why it lost: it meets the requirements and the ADRs in force, and lost on a trade-off this project weighed. An option that breaks an ADR or a requirement, only varies a parameter of the chosen one, or merely shapes the choice is left out; with none such, this item is omitted.
4. The artefact that fixes it, in whatever form the decision needs (e.g. a mapping table, a page map, a weighted matrix). An artefact that does not fit here or must outlive the design goes in its own file: the Plan decides where it lives and its format, File layout lists it, and this decision links to it.

A security decision lists its threats in this table, with IDs `TH1`, `TH2`… per document:

| # | Threat (STRIDE) | Impact | Control | Requirement |
|---|---|---|---|---|
| `TH1` | | | | |
-->

#### D1. Same outputs, and one control table for every feed

The task changes how the tables are read and maintained, not what they hold, following a behaviour-preserving refactoring: what the pipeline produces stays fixed, and later slices build on the control table's contract.

- **Unchanged:**
  - for the same bronze, the rows of `station_stock` and the published file are identical;
  - each batch stays idempotent, with an insert-only MERGE;
  - catch-up stays in bounded batches ([ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md));
  - the run's events and its heartbeat keep their names and fields; events or fields may be added, none removed or renamed.
- **May change:** the tables' physical layout (partitions, files, checkpoints), `processed_objects`' layout, how discovery lists bronze, and each run's reads and run time.
- **Contract for later slices:**
  - `processed_objects` is one table for every system and feed, with one row per processed bronze object;
  - its layout lets each feed read only its own rows, so a new feed registers its objects with no change to it;
  - a slice may add columns, such as T060.5's statuses, but not change its partitioning;
  - slices reach it through the pipeline's common table access, not by reading it on their own.

Options rejected:

- **One control table per feed:** each feed's state stays apart, but a run opens one table per feed and replays each log, so its reads grow with every feed added, and each table needs its own maintenance.

#### D2. Existing data moves to the new layout in a one-off migration

A table whose partitioning changes, such as `processed_objects`, is rewritten with all its current rows in the new layout, following Delta's way of changing a table's partitioning (an overwrite with the new partition columns). Every row keeps its run ID and code version, the lineage of [ADR-0043](../decisions/0043-lineage-at-four-levels.md). A table that keeps its partitioning, such as `station_stock`, is not rewritten.

The owner runs the change once, in this order, so that no run overlaps the migration ([ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md)) and the deployed code never meets a table in the other layout:

1. Pause the schedule.
2. Run the migration and its verification.
3. Deploy the new code, which resumes the schedule; catch-up then processes what bronze received during the pause.

The verification follows source-to-target reconciliation: the rewritten table and the version before it hold

- the same number of rows;
- the same set of bronze object keys in their rows;
- the same run ID and code version on each row.

Their data files differ by design. If a check fails, the migration reports which one, and the schedule stays paused while the owner:

1. Restores the version before the migration with Delta's time travel.
2. Fixes the cause.
3. Runs the migration again.

Options rejected:

- **A layout check in the new code:** the run would fail before writing if `processed_objects` lacked the new partitioning, but it adds code to every run for a one-off change that the order above already covers.

#### D3. Discovery keeps a watermark per system and feed

Each feed lists bronze from its own latest processed capture minus the lookback, following a watermark with allowed lateness kept per stream, and the daily full sweep is removed.

- **New feed:** a feed with nothing processed lists bronze from its start and enters by catch-up in bounded batches ([ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md)), so a new slice's feed starts with no change to the others.
- **Lookback:** 15 min, the maximum wall time of a Cloudflare cron invocation ([Workers › Limits](https://developers.cloudflare.com/workers/platform/limits/)). Capture writes each object within the pass its key names, so no object arrives later than that, whether passes overlap or not. The keys it lists again fall in the same list page, so it adds no requests.
- **Pipeline pause,** such as a Modal outage: no recovery is needed. The watermarks do not move while no run happens, and the next run catches up from them.
- **Older keys:** nothing writes them to bronze. Capture is its only writer and never overwrites, and the bucket lock prevents deletions that a restore would refill, so no on-demand rediscovery of a window is built.

- **What would change it:**
  - a source that delivers its data later than a capture pass → a completeness check that compares bronze with `processed_objects` per closed day;
  - an operation that writes older keys to bronze, such as a recapture or an import → a task that adds on-demand rediscovery of a window.

Options rejected:

- **Watermark per system:** a feed added to a system that already holds processed objects would never list its history older than the system's watermark.
- **Daily completeness check:** it would catch causes not seen today, at the cost of reads every day for a case capture does not produce.

#### D4. Silver keeps the current local month and the 12 whole months before it

`station_stock` keeps the current local calendar month and the 12 whole local months before it, following partition-based retention aligned to the calendar, the rolling window of [ADR-0021](../decisions/0021-retention-per-layer.md).

- **Calendar:** its partitions are local dates ([ADR-0041](../decisions/0041-utc-timestamps-local-calendar-keys.md)), the calendar gold cuts by, so the window removes whole partitions and its edge is the first day gold can ask for.
- **Coverage:** it always holds at least 365 days, so it covers a 12-month gold window whether counted in calendar months or in days.
- **When a month leaves:** on the first local day of each month, the oldest month leaves the window; e.g. on 2026-12-01 November 2025 leaves.
- **On state, not on the date,** following idempotent reconciliation to a desired state: each daily maintenance deletes every partition outside the window, so a day it fails is caught up by the next one that runs, and a day with nothing outside the window deletes nothing and writes no commit.
- **`processed_objects` is kept whole:** it is control state, not a layer's data. Without its rows, a feed that stopped capturing more than 12 months ago would have nothing processed and list bronze from its start (D3), bringing back into silver what retention removed. Its rows are small, and their reads stay bounded by partition (D1).

Options rejected:

- **365 rolling days:** it holds up to a month less, but a gold window of the last 12 calendar months would lack the first days of its oldest month.

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

Checked on production after the deploy, over a window of at least 3 h that starts with the first scheduled run with no catch-up (one batch), and includes a checkpoint of each table and the run of the daily maintenance ([s019 › P7](../spikes/s019-pipeline-run-time-r2-reads.md#55-production-inputs)):

- GetObject per run on `bikesharing-lakehouse` (`r2_metrics.py`) averages about 400 and stays at or below 700;
- p95 run time (`run_stats.py`) is at most 2 min, the estimate [ADR-0027](../decisions/0027-modal-as-execution-platform.md) rests on.

If either fails, `capture_history`'s pruning is checked first.

### 1.5 Out of scope

<!-- Optional. What someone could expect and will not be done, each item pointing to the task that covers it. -->

- Moving Modal's region ([s019 › P8](../spikes/s019-pipeline-run-time-r2-reads.md#55-production-inputs)): its steps are written in this design and not run in it — T080

### 1.6 Open questions

<!-- Optional. The decisions still to take about the what, in dependency order. Each one closes as a decision in Decided at framing and leaves the table, so it is empty at Spec approval. Questions about the how are Plan decisions. -->

| OQ | Question | Depends on | Notes |
|---|---|---|---|

## 2. Plan — how

<!-- 2-3 sentences -->

### 2.1 Approach

<!-- Detailed plan organized by #### blocks.
Block `3. Steps` is written using this plan. In a document-only task, Approach lists the main and supporting deliverables instead, each already written.
A block may end with `Options considered`, with pros and cons, only for a decision asked of the owner, and listing only the alternatives that Decided at framing's item 3 keeps; a decision with none such has no Options considered.
-->

#### Carried-over inputs

The how this plan builds, from [s019 › Production inputs](../spikes/s019-pipeline-run-time-r2-reads.md#55-production-inputs):

| P | Input |
|---|---|
| P1 | Apply the Delta pattern to every pipeline table |
| P2 | Partition `processed_objects` by system and date, bound its MERGE, compact by threshold |
| P3 | Prune `station_stock` by capture range, compact closed partitions |
| P4 | Bound discovery's reads, take the latest capture from the log, set the lookback from lateness |
| P5 | Rediscover a window through the one-off run; not built (D3) |
| P6 | Vacuum and set a checkpoint interval per table |

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

<!-- Build tasks only; a document-only task removes this block.
Each step is one reviewable result and one commit, touching at most 2–3 files.
- Status: where the step is: 💤 todo · 🎬 ready · 🔄 in progress · ⛔ blocked · ✅ done
- Who: Owner (manual actions: dashboards, accounts, deploys, runs, checks) or Claude (code and documents).
- R: the requirements the step implements or tests, or —.
- Commit: the proposed message, following the Git conventions in CLAUDE.md.
- Model: the model and effort the step's session runs with, fitted to the step: the lightest that does it well, never more than it needs nor less (e.g. sonnet · medium). For an Owner step, those of the session that guides the owner, or — when the owner works alone.
- Review: `code`, `security`, `code and security`, or `no`. A review goes on the step that completes a reviewable unit (a flow or action, usually built over several steps); the last code step has at least `code`. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

### Step 1 — `<Title>`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** following the Git conventions in CLAUDE.md, with the design and step ID first in the description: `<type>: dNNN.sN <description>`.
- **R:** R1, R3 (or —)
- **Model:** `<model · effort>` (or —)
- **Review:** `<code | security | code and security | no>`

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

<!-- Component — what was delivered; tests passing. In a document-only task: Deliverable — what it holds. A parent also names the children's issues created at its close; this block is not updated as they progress, since their state lives in their issues and their own working documents. -->

### 4.2 Known gaps at close

<!-- What the task leaves undone or imperfect, each with the task that covers it and its `TODO(TNNN)` marker (CLAUDE.md › Pending items): requirements not fully met, File layout items not delivered, TODOs citing this task. "None" is valid. -->

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
