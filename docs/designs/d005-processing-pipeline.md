<!--
Design doc template. A design doc is the working document of one task: Spec (what and why), Plan (how), Steps (implementation), Close (what was delivered).
It is detailed enough that Code can implement it without making design decisions.
Sections marked Optional are kept only when they apply.
-->

# Design: Processing pipeline

- **Task:** T040
- **ADRs:** `<ADRs this design must respect, or "none">`
- **New ADRs from this doc:** `<ADRs created during this design, or "none">`

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

Capture runs in production and writes the raw feeds of AMBici and Bicing to the bronze layer on R2 ([d004](d004-bronze-data-capture.md)). Nothing reads bronze yet: the silver and gold layers do not exist, so the questions of [d002](d002-requirements.md) have no answer and the public visualization (T041) has no data to show. This task builds the processing pipeline from bronze to silver and gold on the stack chosen by s010–s013, within the project's budget. It also covers how the owner inspects the operation of capture and the pipeline, which today means downloading hundreds of capture log files.

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

#### D1. Vertical slices over one bus matrix

T040 is split into child tasks by vertical slice, following Kimball's bus architecture: the whole model is designed once and built one business process at a time. This design fixes what crosses slices: the feeds that enter, the bus matrix (business processes, the grain of each fact, the conformed dimensions) and the cross-cutting concerns. Each child builds one business process from bronze to silver and gold, runs it on Modal, and its own design fixes the columns, its gold tables and the code. Observability is a child of its own. The first slice measures real run time and memory, which several carried-over inputs depend on.

Rejected: a split by layer (silver, then gold), since silver would be built with no consumer to validate it, and real runs would be measured late.

#### D2. Capture's fixtures as the feed sample

The sample for inspecting each feed is capture's fixtures, `capture/test/fixtures/<source>/<feed>.json`: pretty-printed, uncompressed JSON with the whole index and the first 3 entries of every other feed, and their provenance in `manifest.json` ([d004 › Fixtures](d004-bronze-data-capture.md#fixtures)). They show the full structure of each feed, enough to judge what it contributes to the model. Bronze objects are gzip (`.json.gz`), which is why an editor shows them as binary; DuckDB reads them directly.

What would change it: a feed whose value cannot be judged from 3 entries; that feed's latest bronze object is then downloaded and decompressed for inspection, outside Git.

Rejected: a new sample from R2 in a folder ignored by Git, since it shows the same structure and adds local R2 credentials and a script to maintain.

#### D3. Feeds that enter the model

A feed enters silver only if it answers a question of [d002 › Guiding questions](d002-requirements.md#guiding-questions). The rest stay in bronze untouched ([ADR-0006](../decisions/0006-raw-layer-keeps-source-responses-untouched.md)) and the model does not read them. Prices and opening hours answer no question, and no feed ties a trip to a pricing plan, since trips are estimated from stock changes; if a measure ever needs them, they enter as parameters.

What would change it: a new question that needs a discarded feed; the feed then enters, and its history is already in bronze.

| Feed | AMBici | Bicing | Use in the model |
|---|---|---|---|
| `station_status` | Enters | Enters | The stock snapshot, base fact of Q1 and Q3–Q7 |
| `station_information` | Enters | Enters | Station dimension; Q8, and Bicing's `post_code` for Q4 |
| `vehicle_types` | Enters | Enters | Bikes by type in Q1, through `vehicle_type_id` in `vehicle_types_available` |
| `system_regions` | Enters | Discarded: empty | AMBici's regions are municipalities, linked by `region_id` in `station_information`: the municipality of Q4 |
| `free_bike_status` | Discarded: adds nothing to `station_status` | Not published | Over 17,870 passes (2026-10-14 to 10-26), every bike has a `station_id`, none is disabled, a mean of 0.6 are reserved, and 99.1% of the station counts match `num_bikes_available`, with the rest off by about one bike. Its battery fields (`current_fuel_percent`, `current_range_meters`) answer no question yet |
| `geofencing_zones` | Discarded: empty | Discarded: empty | — |
| `system_pricing_plans` | Discarded | Discarded | No question uses prices |
| `system_hours` | Discarded | Not published | No question uses opening hours |
| `system_information` | Discarded | Discarded | One row per system with nothing to measure; the system dimension's few static attributes are fixed in OQ3 |
| `gbfs.json`, `gbfs_versions` | Discarded | Discarded | Discovery index, used only by capture |

#### D4. Business processes and the grain of the stock

The model follows Kimball's inventory case, as framed in [d002 › Guiding questions](d002-requirements.md#guiding-questions): each capture is a stock count per station, and trips are stock movements derived from consecutive counts. Four business processes answer Q1–Q7; Q8 is answered by the history of the station dimension, not by a fact. The model, with how each question maps to a process, lives in [data-model.md](../data-model.md).

- **Station stock:** one row per station and capture, a periodic snapshot. Semi-additive: it is not summed over time.
- **Stock by vehicle type:** one row per station, capture and vehicle type, from the real-time feeds only, since the Bicing archive has no per-type counts.
- **Stock movements:** one row per station and pair of consecutive captures with a change, derived from the stock. Additive: departures and arrivals are summed over time.
- **Capture passes:** one row per source, feed and capture pass, from capture's logs.

Every capture is kept as a row, even when the station has not changed: rows are only appended, a gap in capture is visible as missing rows, and the Bicing archive's 5-minute snapshots fit the same grain. Rows that repeat values compress well in columnar storage, and small files are compacted by the pipeline.

What would change it: silver's storage cost approaching its share of the budget ([ADR-0026](../decisions/0026-budget-shares-per-component.md)); rows older than a set age are then reduced to intervals or a coarser resolution.

Rejected: one row per station state with `valid_from` and `valid_to` (a timespan tracking fact). It stores far fewer rows, but every change rewrites the open row with a MERGE, with more R2 operations and more conflicts, and a gap in capture reads as an unchanged state.

#### D5. Conformed dimensions

Each dimension answers what describes a fact row: when, where, whose and what. The bus matrix and the reasons for each dimension live in [data-model.md › Dimensions](../data-model.md#dimensions).

- **Date** and **time of day**, apart, since questions group by day and by hour or time band; the exact UTC instant stays in the fact.
- **System**, its own dimension, since capture passes have no station and every question compares AMBici with Bicing.
- **Station**, with its history (SCD type 2), since Q8 asks for it and past occupancy needs the capacity of its time; post code and municipality flattened into it.
- **Vehicle type**, with its propulsion as the level that compares across systems and with the Bicing archive, whose only split is mechanical and electric.
- **Feed**, for capture passes.

The status flags `is_installed`, `is_renting` and `is_returning` stay in the stock fact, not in a dimension.

Rejected: system as an attribute of the station, since capture passes could not be compared by system; municipality as a dimension of its own linked to the station (a snowflake), since it adds a join for a small hierarchy.

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

- Capturing less often, or no longer capturing, the feeds that do not enter the model ([D3](#d3-feeds-that-enter-the-model)), except `free_bike_status`, kept for future questions on AMBici's battery levels — task assigned at the end of this design

### 1.6 Open questions

<!-- Optional. The decisions still to take about the what, in dependency order. Each one closes as a decision in Decided at framing and leaves the table, so it is empty at Spec approval. Questions about the how are Plan decisions. -->

| OQ | Question | Depends on | Notes |
|---|---|---|---|
| OQ4 | Normalization of terms and values across AMBici and Bicing | D5 | [ADR-0008](../decisions/0008-common-model-on-gbfs-3-0.md) reviewed critically: GBFS 3.0 as vocabulary rather than shape. To find out: what `is_installed`, `is_renting` and `is_returning` mean in each system; what Bicing's four vehicle types (`ICONIC`, `BOOST`, `FIT`, `EFIT`) are, against its two known kinds, mechanical and electric; AMBici's post code, which it does not publish, and its region "AMB", which is not a municipality |
| OQ5 | Which d002 questions gold answers, and which Must question the first slice builds | D5 | Handed to T040 by [d002 › Out of scope](d002-requirements.md) |
| OQ6 | The pipeline's mode (24/7 or on demand) and refresh cadence, reviewed together with [d002 › R3](d002-requirements.md#requirements) and the freshness of d002's Q1, Q2 and Q5 | OQ5 | The visitor sees cadence plus run time (about 2 min, not measured): a 5–10 minute cadence gives about 7–12 minutes of age, above R3's 5 minutes ([s013 › D3](../spikes/s013-visualization-tool.md#d3-static-web-page-with-javascript)). Running 24/7, R2's Class B quota allows commits every 10 minutes or more ([s010 › P5](../spikes/s010-storage-table-format.md#production-inputs)) |
| OQ7 | How the historical archives reach R2 and are loaded, and the check of the Bicing archive against the real-time capture | D5 | Bicing's archive is not on R2 yet. The check is handed to T040 by [d002 › Out of scope](d002-requirements.md) |
| OQ8 | Data quality rules and indicators: what T040 does and what T042 does | D5 | [ADR-0025](../decisions/0025-sql-models-directed-by-python.md) leaves where rules live and their format to T042 |
| OQ9 | Metadata and lineage: how a silver or gold row is traced back to bronze and to its run | D5 | |
| OQ10 | How the owner queries the logs of capture, the pipeline and the web page, together | — | Today, querying capture's logs means downloading hundreds of files. The capture passes fact ([D4](#d4-business-processes-and-the-grain-of-the-stock)) already turns capture's logs into a table |
| OQ11 | A script with the common health queries for the owner, and whether it can run from a phone | OQ10 | [s013 › D5](../spikes/s013-visualization-tool.md#d5-no-separate-operations-panel). Option from [s013 › P9](../spikes/s013-visualization-tool.md#55-production-inputs): a manual GitHub Actions run, with no server, but its summary is public if the repository is, and GitHub holds one more read-only key; not verified |
| OQ12 | The child tasks `T040.M`: one per business process, plus observability, in build order | OQ4–OQ11 | [D1](#d1-vertical-slices-over-one-bus-matrix) |

## 2. Plan — how

<!-- 2-3 sentences -->

### 2.1 Approach

<!-- Detailed plan organized by #### blocks.
Block `3. Steps` is written using this plan.
If some block contains `options considered`, include them with pros and cons.
-->

#### Carried-over inputs

Inputs about the how, left to this design by earlier spikes; each becomes a Plan concern or part of one.

- **Execution platform check:** if the first slice measures runs of 1 minute or less, or normal runs of 2 GB or less, or OQ6 chooses the on-demand mode, the decision of [ADR-0027](../decisions/0027-modal-as-execution-platform.md) is reopened with Cloud Run and Fly.io as candidates. The run's final log event carries `duration_s` and `peak_memory_mb`, the latter from `ru_maxrss` ([s012 › D1, P1](../spikes/s012-execution-target.md#d1-execution-platform)).
- **Memory:** set DuckDB's memory limit below the container's; decide on a hard container limit (`memory=(request, limit)`; without one, usage above the request is billed, as Modal charges the higher of the two); cap what one run processes and leave the rest to the next; do not retry memory errors, since they are permanent; check in the first slice how Modal treats a memory kill of a scheduled function ([s012 › D3, TH12](../spikes/s012-execution-target.md#d3-pipeline-security), [d002 › R23](d002-requirements.md#requirements)).
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
