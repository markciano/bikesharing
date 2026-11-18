<!--
Design doc template. A design doc is the working document of one task: Spec (what and why), Plan (how), Steps (implementation), Close (what was delivered).
It is detailed enough that Code can implement it without making design decisions.
Sections marked Optional are kept only when they apply.
Kind: a build task builds code or configuration and has every block. A document-only task delivers documents only, written during the Spec and the Plan, and has no Steps block. A parent is a document-only task with children (`TNNN.M`): it holds what its children share, and its Children section.
-->

# Design: Pipeline platform and walking skeleton

- **Task:** T060.1
- **Kind:** build
- **ADRs:** `<ADRs this design must respect, or "none">`
- **New ADRs from this doc:** `<ADRs created during this design, or "none">`

## Status

<!-- State: Draft 📝 · Ready for implementation 🎬 · In progress 🔄 · Complete ✅. A document-only task goes from Draft to Complete.
Phase: the blocks and reviews completed. A document-only task shows only Spec · Plan · Plan review.
Current step: the step being implemented, or —. A document-only task has no Current step. -->

- State: Draft 📝
- Phase: [ ] Spec · [ ] Plan · [ ] Plan review · [ ] Steps · [ ] Steps review
- Current step: —
- Next: Spec › Failure cases, FC1 closed as D9; left: DQR12 with less than 24 h of previous captures (D4), a deployment from uncommitted changes or a commit outside `main` (D5), the end instant left set after the first load (D8)

## 1. Spec — what and why

<!-- What the result does seen from outside, not how it is built. The test: if whoever uses the result would notice a change, it belongs here; if not, it belongs to the Plan. External systems and their data (feeds, fields) may be named. -->

### 1.1 Context

<!-- 2–4 sentences for a reader with no prior context: the problem or need and why it matters now; who or what uses the result; where things stand today, including any design or spike this builds on. No solution here: it starts in Decided at framing. For a correction: current vs expected behaviour and how to reproduce it. -->

Capture writes the raw feeds of AMBici and Bicing to the bronze layer on R2 ([d004](d004-bronze-data-capture.md)), and [d007](d007-pipeline-design.md) decides how the pipeline builds silver and gold from it, one business process per child of T060 ([d007 › D1](d007-pipeline-design.md#d1-build-by-vertical-slice)). Nothing of the pipeline runs yet: it has no code base, no run on Modal, and the run time and memory on which the cadence, the batch bounds and [ADR-0027](../decisions/0027-modal-as-execution-platform.md) depend have never been measured. This task builds the walking skeleton, the thinnest path from the real-time `station_status` feed to a published file, run on Modal, and the platform and patterns that T060.2, T060.5, T060.8 and the later children build on. Its scope, the requirements of d007 it closes and its closing condition are set in [d007 › Children](d007-pipeline-design.md#16-children).

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

#### D1. First version of the station stock

The skeleton writes the station stock of both systems, AMBici and Bicing, at its grain of one row per station and capture ([data-model.md › Grain](../data-model.md#grain), TR1), so that the run is measured on the real volume of both feeds and handles their differences from the first run. Each row holds its natural key (system, `station_id` and capture instant in UTC), the measures and flags kept as each source publishes them (TR5–TR8, TR10, TR53), with TR9's null for a Bicing station out of service, its local calendar keys ([ADR-0041](../decisions/0041-utc-timestamps-local-calendar-keys.md)) and its lineage, the run's ID and code version ([d007 › D5](d007-pipeline-design.md#d5-lineage-at-four-levels)). The TR rules are those of [data-model.md › Data contract › Station stock](../data-model.md#station-stock). Every row is written with its final meaning, following Kimball's practice that a fact row gains columns but does not change what it states: T060.8 adds the dimension keys and the rest of the columns without rewriting what the skeleton wrote.

Left to later children: the keys of the Station and System dimensions and the tables of Date and Time of day (T060.8); TR3, whether a row comes from the archive, and TR2 and TR4 on the archive (T060.4).

Rejected: TR9 left to T060.8, taking "as published" literally, since the published file would show vehicles at closed stations and T060.8 would rewrite those rows from bronze; one system only, since the run would not be measured on the real volume.

#### D2. Published file: the latest count of each station

The skeleton publishes one file with the latest count of each station of both systems, the answer to [d002 › Q1](d002-requirements.md#guiding-questions) without its split by vehicle type: per station, its system, `station_id`, vehicles and docks available, `is_renting`, `is_returning`, `last_reported` and capture instant; per file, the capture instant of its most recent data, so that its age can be measured ([d007 › D4](d007-pipeline-design.md#d4-data-quality-in-four-classes)) and the page can show it. Its JSON Schema is the contract of [d007 › D2](d007-pipeline-design.md#d2-visualization-after-all-slices). Following the walking skeleton, the file has its final shape from the first run, and later children only add fields to it, a backward-compatible change of the contract: T060.8 adds the station's attributes and the mark of a frozen count (DQM5), T060.3 the split by vehicle type.

Rejected: totals per system, since its contract would be far from the one T041 consumes and T060.8 would change it in a breaking way.

#### D3. Runtime rules checked by the skeleton

The skeleton checks every runtime rule of [data-quality.md](../data-quality.md) that applies to what it builds, as [d007](d007-pipeline-design.md#13-requirements)'s R4 requires: DQR1 (one row per station and capture), DQR2 (no row updated or deleted), DQR13 (reconciliation) and DQR14 (the file's JSON Schema), of severity error; DQR11 (schema drift) and DQR12 (volume drop), of severity warn. The rules on the other facts (DQR3–DQR6) and on the dimensions (DQR7–DQR10) are checked by the child that builds their table.

#### D4. Volume drop against a rolling median

DQR12 flags a capture of a system that lists fewer than 90% of the median number of stations of that system's captures in the 24 h before its capture instant, following the volume monitors of data observability: a relative threshold over a rolling baseline. The window is set by the capture instant, not by the run, so that the stages of D8 compare each capture with its own past. With fewer than 60 captures of the system in the window, 1 h at one per minute, the rule is not evaluated for that capture and the run logs it as such, following the minimum baseline of those monitors; this happens only on the first day of captures or after a gap of more than 23 h, and a baseline of 1 h suffices since the daily variation stays inside the margin. The margin covers the variation seen in Bicing's archive, 513 to 546 stations per snapshot, 5.5% below its usual 543 ([bicing › Content](../sources/bicing.md)), while AMBici holds 237 stations steadily ([ambici › Content](../sources/ambici.md)); 24 h covers one daily cycle. The three values are provisional, set before any production run; the rule, with its values, lives in [data-quality.md › Runs and published files](../data-quality.md#runs-and-published-files).

What would change it: weeks of production runs that show legitimate drops above 10%, or real losses below it, change the threshold or the window, reviewed by T060.2.

Rejected: a fixed minimum per system, since it needs an edit whenever a network changes and misses a drop that stays above it.

#### D5. Code version: the deployed commit's SHA

The pipeline's code version, written in every row and log event ([d007 › D5](d007-pipeline-design.md#d5-lineage-at-four-levels)) and as the tag of each page deployment ([d007 › D6](d007-pipeline-design.md#d6-deployments-tagged-with-their-commit)), is the full SHA of the Git commit its deployment was made from, the same SHA the deploy script tags the deployment with. A row then leads to its commit with no lookup, following Twelve-Factor's unique ID for each release; the full SHA avoids the ambiguity of a short one.

The deploy script refuses to deploy from a working tree with uncommitted changes or from a commit that is not on the remote `main`, following GitHub Flow, where `main` is always deployable and what is deployed has passed its PR's checks. A row's SHA then always leads to reviewed code that stays in the history.

Rejected: refusing only uncommitted changes, since it lets unreviewed code reach production and its commit is lost if its branch is rebased.

#### D6. Provisional run bounds

Until T060.5 sets them from measured runs ([d007 › D7](d007-pipeline-design.md#d7-catch-up-in-bounded-batches)), a run has these bounds, following a timeout as a generous backstop below the cadence, with a graceful shutdown before it:

| Bound | Value | Why |
|---|---|---|
| Timeout | 10 min | Below the 15-minute cadence; a run that hangs costs at most two thirds of the time |
| Time budget | 7 min | The timeout less 3 min for one batch and the run's close, neither measured yet |
| Batch bound | 360 objects | 3 h of `station_status` captures of both systems, one per minute each: a normal run of about 30 objects fits in one batch, and the first backlog advances 3 h per batch; far below the thousands of files at which `read_json` runs out of memory (Carried-over inputs › Reading many JSON files) |

The batch bound is confirmed, or lowered, by the memory of a reference batch on real data, measured before the first deployment (Carried-over inputs › DuckDB use), so that a batch fits in the container's memory with margin.

Rejected: a 14-minute timeout with an 11-minute time budget, since it drains the first backlog sooner but doubles the worst-case cost before any run is measured.

#### D7. Heartbeat with no platform retries

The heartbeat of [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md) sends the failure signal on the first failed run: the platform does not retry a run, since the next scheduled run is its retry, as a failed batch stays pending ([d007 › D7](d007-pipeline-design.md#d7-catch-up-in-bounded-batches)), following the scheduled cycle as the retry of an idempotent pipeline. The monitor expects a signal every 15 min, the cadence, with 15 min of grace, which covers a run up to its 10-minute timeout (D6). The owner then learns of a failed run at once, of a run that hangs when it reaches its timeout, and of a run that never starts about 30 min after it was due.

What would change it: alerts from transient failures that the next run resolves, frequent enough to be ignored, change the retries.

Rejected: one platform retry 1 min after a failure, since it can overlap the next scheduled run, which then waits, and delays the alert of a real failure.

#### D8. First load in chronological stages

The first load of the bronze captured before the first deployment drains in three stages, following an incremental backfill with a check between stages: first the oldest day of captures, then the first week, then everything. The pipeline processes only the bronze objects captured up to a configured end instant, oldest first as in [d007 › D7](d007-pipeline-design.md#d7-catch-up-in-bounded-batches); the owner checks each stage's runtime rules, reconciliation, run time and memory, and moves the end instant forward for the next one. Once the last stage drains, the end instant is removed and the pipeline processes every object, as d007 › D7 sets. Each stage then exercises a larger volume only after the smaller one passed, in the same order and with the same code as any backlog.

While an end instant is set, a run that finds no pending object captured up to it logs an event of severity warn, which alerts the owner like any warn rule ([d007](d007-pipeline-design.md#13-requirements)'s R10), following the completion notice of a backfill: the owner learns that a stage has drained when it is time to check it and move the end instant, and an end instant left set after the last stage cannot halt the pipeline unnoticed.

Rejected: draining each stage in one-off runs that take the end instant as an argument, with no end instant in the scheduled run, since a large stage would need many runs launched by hand within D6's time budget; draining the first load as any backlog, since a problem that only shows at volume would be found in the middle of it; stages from the most recent captures backwards, since the current file it gives earlier has no visitors until T041 ([d007 › D2](d007-pipeline-design.md#d2-visualization-after-all-slices)), the first backlog drains in under a day, and it reverses d007 › D7's order.

#### D9. A failed batch halts the pipeline until T060.5

Until T060.5 builds the set-aside with redrive and the quarantine table ([d007 › D7](d007-pipeline-design.md#d7-catch-up-in-bounded-batches)), a batch that fails a runtime rule of severity error, holds a row that fails its column's schema, or holds a bronze object that cannot be read fails the run and stays pending, following fail-fast: nothing of the batch is committed, the next run retries it, and the heartbeat sends the failure signal on every run until a new code version fixes it (D7). The pipeline then never commits a row a rule rejected, and while it halts the published file only grows older, with no visitors until T041 ([d007 › D2](d007-pipeline-design.md#d2-visualization-after-all-slices)). A rule of severity warn (DQR11, DQR12) does not halt it.

Rejected: building the set-aside and the quarantine in T060.1, since it brings T060.5's scope forward into the skeleton.

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

### 1.5 Out of scope

<!-- Optional. What someone could expect and will not be done, each item pointing to the task that covers it. -->

- `<item>` — TNNN

### 1.6 Children

<!-- Parent only. The child map, in build order: each child's scope (e.g. the business process it builds), the questions or requirements it closes, the children it depends on, and the condition that closes it. Each child has its own working document, which cites the parent's decisions instead of repeating them. Every open question and requirement of the parent is closed by the parent or by one child. The parent's Done when: its Open questions closed and its children created. -->

| Child | Scope | Closes | Depends on | Done when |
|---|---|---|---|---|
| `TNNN.1` | | | — | |

### 1.7 Open questions

<!-- Optional. The decisions still to take about the what, in dependency order. Each one closes as a decision in Decided at framing and leaves the table, so it is empty at Spec approval. Questions about the how are Plan decisions. -->

| OQ | Question | Depends on | Notes |
|---|---|---|---|

## 2. Plan — how

<!-- 2-3 sentences -->

### 2.1 Approach

<!-- Detailed plan organized by #### blocks.
Block `3. Steps` is written using this plan. In a document-only task, Approach lists the main and supporting deliverables instead, each already written.
If some block contains `options considered`, include them with pros and cons.
-->

#### Carried-over inputs

Inputs about the how, left to this task by earlier spikes, designs and its issue; each links to its origin, which holds the detail.

- **Execution platform check:** `duration_s` and `peak_memory_mb` in the run's final event, and the thresholds that reopen ADR-0027 ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)).
- **Memory:** DuckDB's limit below the container's, a hard container limit, a cap per run, no retry of memory errors, Modal's handling of a memory kill ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)).
- **Reading many JSON files:** `read_json` running out of memory over thousands of files in DuckDB 2.0.0, duckdb#27806 ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)).
- **Platform separation:** CI checks for ADR-0046's rules 1–5, module names, idempotent runs over a window, runtime rules as dbt data tests, `include_external_packages` or PyTestArch ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)).
- **Code workflow:** `pyproject.toml` with its linters, `scripts/check-pipeline.sh`, the `PostToolUse` hook, the Review field, SQL file conventions, `/code-review` and `/security-review` at first use ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)).
- **Run operation:** logged events, no overlapping runs, region, safe re-runs, Modal's usage and spend limits, batch size and time budget, smoke tests ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)).
- **Publishing:** prepared files from an explicit list, deployed at the end of a run with a token limited to one Worker; a failed deployment does not fail the run's data ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)).
- **R2 operation classes:** the class of conditional PutObject, ListObjectsV2 and DeleteObjects, confirmed with R2's per-operation metrics ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)).
- **Rule names in code:** each data test takes an explicit `name`, its `DQR` ID ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs), [s017 › P5](../spikes/s017-dbt-in-the-pipeline.md#55-production-inputs)).
- **Deployment tags:** where `wrangler deploy --tag` and `modal deploy --tag` show, their limits, and whether Modal's tag is redundant ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)).
- **Delta writes on R2:** partition overwrite or bounded MERGE, retry on conflict, table creation, checkpoint interval, the conditional put option's name ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)).
- **DuckDB use:** the pinned patch, batches read through `con.sql()` into Arrow, parameters, the hand-off to `deltalake` and its memory, Polars as fallback ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)).
- **DuckDB hardening:** `enable_external_access`, extensions installed ahead and autoinstall off, temporary secrets, the time limit with `interrupt()` ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)).
- **Cost model recalibration:** R2's metrics per bucket against the cost model, with the Cloudflare alerts ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)).
- **Heartbeat retries:** the number of retries and the time limit before the failure signal ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)).
- **Pipeline version:** the value of `version` in the pipeline's logs and rows ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)).
- **Log upload:** a failed upload of a run's logs does not hide the run's real outcome ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)).
- **Fixtures and contracts:** fixture entries chosen for variety, consumer tests of the shared contract vectors with their `invalid` cases, the pipeline's component folder ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)).
- **dbt pins:** `dbt-core` 1.12.7, `dbt-duckdb` 1.11.1 and DuckDB 2.0.x resolve together ([s017 › P1](../spikes/s017-dbt-in-the-pipeline.md#55-production-inputs)).
- **dbt scratch database:** the shell creates its folder before invoking dbt, and reads its table in the same process only with `dbt-duckdb`'s connection config ([s017 › P2, P3](../spikes/s017-dbt-in-the-pipeline.md#55-production-inputs)).
- **dbt events:** the callback turns `NodeStart` and `NodeFinished` into the pipeline's events; a missing `num_failures` means 0; the shell counts each model's rows ([s017 › P4](../spikes/s017-dbt-in-the-pipeline.md#55-production-inputs)).
- **dbt unit tests:** CI builds upstream relations first with `dbt run --empty`; the testing strategy gains its SQL (dbt) section ([s017 › P6](../spikes/s017-dbt-in-the-pipeline.md#55-production-inputs)).
- **Shell integration test:** two batches in one process, a failing model and a contract violation, checking the result and the log ([s017 › P7](../spikes/s017-dbt-in-the-pipeline.md#55-production-inputs)).
- **Python version:** 3.14, with its latest patch in `uv`, in `.python-version` and `requires-python = ">=3.14,<3.15"`; if `uv sync --locked` and the tests fail on 3.14, 3.13.17 with the cause as a finding (T060.1's issue, comment of 2026-11-17).
- **Python patch on Modal:** `debian_slim(python_version="3.14")` takes only the minor version, so production may run another patch than local and CI (T060.1's issue, comment of 2026-11-17).
- **mashumaro floor:** dbt-core 1.12.7 accepts `mashumaro>=3.9,<3.18`, and below 3.15 it truncates float model versions, dbt-labs/dbt-core#16284 (T060.1's issue, comment of 2026-11-17).

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
- Model: the model and effort the step's session runs with (e.g. sonnet · medium), or — when Who is Owner.
- Review: `code`, `security`, `code and security`, or `no`. A review goes on the step that completes a reviewable unit (a flow or action, usually built over several steps); the last code step has at least `code`. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

### Step 1 — `<Title>`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** following the Git conventions in CLAUDE.md, including `<dNNN.sN - >` at the begining of the message, for the design and the step number.
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
