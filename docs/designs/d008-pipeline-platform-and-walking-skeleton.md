<!--
Design doc template. A design doc is the working document of one task: Spec (what and why), Plan (how), Steps (implementation), Close (what was delivered).
It is detailed enough that Code can implement it without making design decisions.
Sections marked Optional are kept only when they apply.
Kind: a build task builds code or configuration and has every block. A document-only task delivers documents only, written during the Spec and the Plan, and has no Steps block. A parent is a document-only task with children (`TNNN.M`): it holds what its children share, and its Children section.
-->

# Design: Pipeline platform and walking skeleton

- **Task:** T060.1
- **Kind:** build
- **ADRs:** [ADR-0016](../decisions/0016-runtime-versions-pinned-per-component.md), [ADR-0017](../decisions/0017-dependencies-locked-per-component.md), [ADR-0018](../decisions/0018-medallion-architecture.md), [ADR-0023](../decisions/0023-storage-security-baseline.md), [ADR-0027](../decisions/0027-modal-as-execution-platform.md), [ADR-0028](../decisions/0028-modal-cron-as-pipeline-scheduler.md), [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md), [ADR-0033](../decisions/0033-data-published-by-redeploying-static-assets.md), [ADR-0035](../decisions/0035-cloud-resource-naming.md), [ADR-0036](../decisions/0036-log-convention-across-components.md), [ADR-0037](../decisions/0037-test-fixtures-per-component.md), [ADR-0038](../decisions/0038-account-wide-workers-editor-deploy-token.md), [ADR-0041](../decisions/0041-utc-timestamps-local-calendar-keys.md), [ADR-0043](../decisions/0043-lineage-at-four-levels.md), [ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md), [ADR-0046](../decisions/0046-functional-core-imperative-shell-for-the-pipeline.md), [ADR-0047](../decisions/0047-dbt-builds-and-audits-the-pipeline-sql.md), [ADR-0049](../decisions/0049-log-events-copied-to-monitoring-over-otlp.md)
- **New ADRs from this doc:** [ADR-0050](../decisions/0050-contract-tests-by-contract-kind-with-native-schemas.md)

## Status

<!-- State: Draft 📝 · Ready for implementation 🎬 · In progress 🔄 · Complete ✅. A document-only task goes from Draft to Complete.
Phase: the blocks and reviews completed. A document-only task shows only Spec · Plan · Plan review.
Current: where work resumes (the step being implemented, or the block and section of the design; — when complete), plus only what the next session cannot derive from the document, such as an instruction from the owner. Nothing it can re-derive: options, recommendations, files to read, later sections. A document-only task names the section. -->

- State: In progress 🔄
- Phase: [x] Spec · [x] Plan · [x] Plan review · [x] Steps · [x] Steps review
- Current: DI12's code (the three platform modules, `test_platform_separation.py` and `check-pipeline.sh`) as a one-step change, then a one-off run from the new module to confirm the image; then Step 29, run by the owner.

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

The skeleton writes the station stock of both systems, AMBici and Bicing, at its grain of one row per station and capture ([data-model.md › Grain](../data-model.md#grain), TR1), so that the run is measured on the real volume of both feeds and handles their differences from the first run. Each row holds its natural key (system, `station_id` and capture instant in UTC), the measures and flags kept as each source publishes them (TR5–TR8, TR10, TR53), with TR9's null for a Bicing station out of service, its local calendar keys ([ADR-0041](../decisions/0041-utc-timestamps-local-calendar-keys.md)) and its lineage, the run's ID and code version ([d007 › D5](d007-pipeline-design.md#d5-lineage-at-four-levels)). The TR rules are those of [data-model.md › Data contract › Station stock](../data-model.md#station-stock). Every row is written with its final meaning, following Kimball's practice that a fact row gains columns but does not change what it states: T060.8 adds the dimension keys and the rest of the columns without rewriting what the skeleton wrote; how it fills its new columns on the rows already written is decided by T060.8.

Left to later children: the keys of the Station and System dimensions and the tables of Date and Time of day (T060.8); TR3, whether a row comes from the archive, and TR2 and TR4 on the archive (T060.4).

Rejected: TR9 left to T060.8, taking "as published" literally, since the published file would show vehicles at closed stations and T060.8 would rewrite those rows from bronze; one system only, since the run would not be measured on the real volume.

#### D2. Published file: the latest count of each station

The skeleton publishes one file with the latest count of each station of both systems, the answer to [d002 › Q1](d002-requirements.md#guiding-questions) without its split by vehicle type: per station, its system, `station_id`, vehicles and docks available, `is_renting`, `is_returning`, `last_reported` and capture instant; per file, the capture instant of its most recent data, so that its age can be measured ([d007 › D4](d007-pipeline-design.md#d4-data-quality-in-four-classes)) and the page can show it. Its JSON Schema is the contract of [d007 › D2](d007-pipeline-design.md#d2-visualization-after-all-slices). Following the walking skeleton, the file has its final shape from the first run, and later children only add fields to it, a backward-compatible change of the contract: T060.8 adds the station's attributes and the mark of a frozen count (DQM5), T060.3 the split by vehicle type.

Rejected: totals per system, since its contract would be far from the one T041 consumes and T060.8 would change it in a breaking way.

#### D3. Runtime rules checked by the skeleton

The skeleton checks every runtime rule of [data-quality.md](../data-quality.md) that applies to what it builds, as [d007 › R4](d007-pipeline-design.md#13-requirements) requires: DQR1 (one row per station and capture), DQR2 (no row updated or deleted), DQR13 (reconciliation) and DQR14 (the file's JSON Schema), of severity error; DQR11 (schema drift) and DQR12 (volume drop), of severity warn, whose failures are only logged until T060.2 builds their alerts. The rules on the other facts (DQR3–DQR6) and on the dimensions (DQR7–DQR10) are checked by the child that builds their table.

#### D4. Volume drop against a rolling median

DQR12 flags a capture of a system that lists fewer than 90% of the median number of stations of that system's captures in the 24 h before its capture instant, following the volume monitors of data observability: a relative threshold over a rolling baseline. The window is set by the capture instant, not by the run, so that the stages of D8 compare each capture with its own past. With fewer than 60 captures of the system in the window, 1 h at one per minute, the rule is not evaluated for that capture and the run logs it as such, following the minimum baseline of those monitors; this happens only on the first day of captures or after a gap of more than 23 h, and a baseline of 1 h suffices since the daily variation stays inside the margin. The margin covers the variation seen in Bicing's archive, 513 to 546 stations per snapshot, 5.5% below its usual 543 ([bicing › Content](../sources/bicing.md)), while AMBici holds 237 stations steadily ([ambici › Content](../sources/ambici.md)); 24 h covers one daily cycle. The three values are provisional, set before any production run; the rule, with its values, lives in [data-quality.md › Runs and published files](../data-quality.md#runs-and-published-files).

What would change it: weeks of production runs that show legitimate drops above 10%, or real losses below it, change the threshold or the window, reviewed by T060.2.

Rejected: a fixed minimum per system, since it needs an edit whenever a network changes and misses a drop that stays above it.

#### D5. Code version: the deployed commit's SHA

The pipeline's code version, written in every row and log event ([d007 › D5](d007-pipeline-design.md#d5-lineage-at-four-levels)) and as the tag of each page deployment ([d007 › D6](d007-pipeline-design.md#d6-deployments-tagged-with-their-commit)), is the full SHA of the Git commit its deployment was made from, the same SHA the deploy script tags the deployment with. A row then leads to its commit with no lookup, following Twelve-Factor's unique ID for each release; the full SHA avoids the ambiguity of a short one.

The deploy script refuses to deploy from a working tree with uncommitted changes or from a commit that is not the latest of the remote `main`, as [d007 › D6](d007-pipeline-design.md#d6-deployments-tagged-with-their-commit) sets, following GitHub Flow, where `main` is always deployable and what is deployed has passed its PR's checks. A row's SHA then always leads to reviewed code that stays in the history.

Rejected: refusing only uncommitted changes, since it lets unreviewed code reach production and its commit is lost if its branch is rebased.

#### D6. Provisional run bounds

Until T060.5 sets them from measured runs ([d007 › D7](d007-pipeline-design.md#d7-catch-up-in-bounded-batches)), a run has these bounds, following a timeout as a generous backstop below the cadence, with a graceful shutdown before it:

| Bound | Value | Why |
|---|---|---|
| Timeout | 10 min | Below the 15-minute cadence; a run that hangs costs at most two thirds of the time |
| Time budget | 7 min | The timeout less 3 min for one batch and the run's close, neither measured yet |
| Batch bound | 360 objects | 3 h of `station_status` captures of both systems, one per minute each: a normal run of about 30 objects fits in one batch, and the first backlog advances 3 h per batch; far below the thousands of files at which `read_json` runs out of memory ([Carried-over inputs › Reading many JSON files](#carried-over-inputs)) |

The batch bound is confirmed, or lowered, by the memory of a reference batch on real data, measured before the first deployment ([Carried-over inputs › DuckDB use](#carried-over-inputs)), so that a batch fits in the container's memory with margin.

Rejected: a 14-minute timeout with an 11-minute time budget, since it drains the first backlog sooner but doubles the worst-case cost before any run is measured.

#### D7. Heartbeat with no platform retries

The heartbeat of [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md) sends the failure signal on the first failed run: the platform does not retry a run, since the next scheduled run is its retry, as a failed batch stays pending ([d007 › D7](d007-pipeline-design.md#d7-catch-up-in-bounded-batches)), following the scheduled cycle as the retry of an idempotent pipeline. The monitor expects a signal every 15 min, the cadence, with 15 min of grace, which covers a run up to its 10-minute timeout (D6). The owner then learns of a failed run at once, of a run that hangs, and is killed by its timeout with no failure signal, when the grace runs out about 15 min after its start, and of a run that never starts about 30 min after the last signal.

What would change it: alerts from transient failures that the next run resolves, frequent enough to be ignored, change the retries.

Rejected: one platform retry 1 min after a failure, since it can overlap the next scheduled run, which then waits, and delays the alert of a real failure.

#### D8. First load in chronological stages

The first load of the bronze captured before the first deployment drains in three stages, following an incremental backfill with a check between stages: first the oldest day of captures, then the first week, then everything. The pipeline processes only the bronze objects captured up to a configured end instant, oldest first as in [d007 › D7](d007-pipeline-design.md#d7-catch-up-in-bounded-batches); the owner checks each stage's runtime rules, reconciliation, run time and memory, and moves the end instant forward for the next one. Once the last stage drains, the end instant is removed and the pipeline processes every object, as d007 › D7 sets. Each stage then exercises a larger volume only after the smaller one passed, in the same order and with the same code as any backlog.

While an end instant is set, a run that finds no pending object captured up to it logs an event of severity warn, following the completion notice of a backfill: it tells the owner that a stage has drained and that it is time to check it and move the end instant. Until T060.2 builds the alerts on warn events ([d007 › R10](d007-pipeline-design.md#13-requirements)), the owner reads it in the run's logs on Modal, and in the run's events on R2 when those are not enough; the end instant's removal after the last stage is checked in Done when.

Rejected: draining each stage in one-off runs that take the end instant as an argument, with no end instant in the scheduled run, since a large stage would need many runs launched by hand within D6's time budget; draining the first load as any backlog, since a problem that only shows at volume would be found in the middle of it; stages from the most recent captures backwards, since the current file it gives earlier has no visitors until T041 ([d007 › D2](d007-pipeline-design.md#d2-visualization-after-all-slices)), the first backlog is estimated to drain in under a day, and it reverses d007 › D7's order.

#### D9. A failed batch halts the pipeline until T060.5

Until T060.5 builds the set-aside with redrive and the quarantine table ([d007 › D7](d007-pipeline-design.md#d7-catch-up-in-bounded-batches)), a batch that fails a runtime rule of severity error on its rows (DQR1, DQR13), holds a row that fails its column's schema, or holds a bronze object that cannot be read fails the run and stays pending, following fail-fast: nothing of the batch is committed, the next run retries it, and the heartbeat sends the failure signal on every run until a new code version fixes it (D7). The pipeline then never commits a row a rule rejected, and while it halts the published file only grows older, with no visitors until T041 ([d007 › D2](d007-pipeline-design.md#d2-visualization-after-all-slices)). This is a provisional state of [d007 › D7](d007-pipeline-design.md#d7-catch-up-in-bounded-batches), not a change to it: D7 rejects this halt since one faulty object would freeze the page, which cannot happen before T041, and T041 comes after T060.5. A rule of severity warn (DQR11, DQR12) does not halt it, and a file that fails DQR14 follows [d007 › R2](d007-pipeline-design.md#13-requirements): it is not deployed, the last file that passed is kept, and the run fails, so the heartbeat sends the failure signal. DQR2 is checked after each write instead, and fails the run (R30). **#13**

Rejected: building the set-aside and the quarantine in T060.1, since it brings T060.5's scope forward into the skeleton.

#### D10. Security of the skeleton

The skeleton adds a run on Modal that holds secrets, a public file, a deployment of the page from the run and one-off runs from a branch. Its threats, from one STRIDE pass over D1–D9, are those below; the storage baseline of [ADR-0023](../decisions/0023-storage-security-baseline.md) (a token per component, bronze read-only for the pipeline, bucket lock, private buckets) applies as it stands and is not repeated. The pipeline holds its own Cloudflare token, with the Workers Editor role and an expiry, following ADR-0023's token per component: a leak on Modal is revoked without touching the token of local deployments. Its reach over every Worker of the account is accepted as residual risk until Cloudflare scopes a token to one Worker, as [ADR-0038](../decisions/0038-account-wide-workers-editor-deploy-token.md) accepts it.

Rejected: reusing ADR-0038's token on Modal, since one leak would force revoking both.

| # | Threat (STRIDE) | Impact | Control | Requirement |
|---|---|---|---|---|
| `TH1` | Spoofing: someone sends a forged success signal to the heartbeat | A failed run does not alert the owner | The heartbeat's URL is a secret, never in the repository or the logs | R24 |
| `TH2` | Tampering: a feed publishes values that act as code, SQL text or markup in the file | Corrupted tables, or a script in the page | Feed values are never interpolated into SQL; the file holds only D2's typed fields and passes its JSON Schema (DQR14); escaping its values in the page belongs to T041 | R7, R8, R25 |
| `TH3` | Tampering: unreviewed code writes to production | Rows with an unreviewed SHA in silver and gold, or in the page | D5 for deployments; a one-off run from a branch, such as D6's reference batch, neither writes to the production lakehouse nor deploys the page | R10, R26, R27 |
| `TH4` | Repudiation: a row or a deployment cannot be traced to its code | The code behind a wrong value cannot be found | The run's ID and the code version in every row and event, and the deployment's tag (D5) | R5, R9 |
| `TH5` | Information disclosure: a secret shows in the run's events, copied to the monitoring tool, or in an error message | Credentials leak outside Modal | The run's events and errors never hold a secret's value; secrets reach the run only as Modal Secrets | R23, R24 |
| `TH6` | Information disclosure: the public file exposes internal fields, such as lineage or bronze keys | The internal structure is revealed | The file is built only from D2's explicit list of fields | R7 |
| `TH7` | Denial of service: runaway runs or unbounded R2 requests drive up cost (denial of wallet) | The bill | D6's timeout, no platform retries (D7), no overlapping runs, and Modal's spend limit set by the owner | R11, R16, [d007 › R15](d007-pipeline-design.md#13-requirements); the spend limit in Done when |
| `TH8` | Elevation of privilege: the run's Cloudflare token leaks | It reaches every Worker of the account, capture's included | The pipeline's own token, Workers Editor with an expiry; the account-wide reach is residual risk | Done when |
| `TH9` | Elevation of privilege: a DuckDB query reads local files or loads extensions as the data directs | The engine leaves the perimeter of R2 | DuckDB reaches only the pipeline's buckets and loads no extension at run time | R28, R29 |

### 1.3 Requirements

<!-- Optional. The acceptance criteria, cited by number in the Test plan and the steps. They translate Decided at framing and cite the decision they come from; nothing is decided here.
One behaviour per requirement, verifiable, with a measurable threshold where one applies. Written in EARS:
- Ubiquitous: The <system> shall <response>.
- Event: When <trigger>, the <system> shall <response>.
- State: While <state>, the <system> shall <response>.
- Unwanted: If <condition>, then the <system> shall <response>.
- Optional: Where <feature is included>, the <system> shall <response>.
Only requirements specific to this task; project-wide rules (CLAUDE.md, ADRs) are not repeated. -->

- **R1** The pipeline shall write one row of station stock per station and capture of AMBici and Bicing, keyed by system, `station_id` and capture instant in UTC. (D1)
- **R2** The pipeline shall write each row's measures and flags as its source publishes them, following TR5–TR8, TR10 and TR53. (D1)
- **R3** While a Bicing station is out of service, with `is_renting` and `is_returning` false, the pipeline shall write null as its `num_vehicles_available`, following TR9. (D1)
- **R4** The pipeline shall write in each row its local calendar keys. (D1)
- **R5** The pipeline shall write in each row the run's ID and the code version. (D1, TH4)
- **R6** The pipeline shall publish one file with the latest count of each station of both systems, holding the fields D2 lists per station and per file. (D2)
- **R7** The pipeline shall build the published file only from the fields D2 lists. (D2, TH2, TH6)
- **R8** The pipeline shall check, in every run, DQR1, DQR2, DQR13 and DQR14 with severity error, and DQR11 and DQR12 with severity warn, as [data-quality.md](../data-quality.md) states them. (D3, D4)
- **R9** The pipeline shall use as its code version the full SHA of the Git commit its deployment was made from. (D5, TH4)
- **R10** If the working tree has uncommitted changes, or its commit is not the latest of the remote `main`, then the deploy script shall refuse to deploy. (D5, TH3)
- **R11** The timeout of [d007 › R21](d007-pipeline-design.md#13-requirements) shall be 10 min. (D6, TH7)
- **R12** The time budget of [d007 › R25](d007-pipeline-design.md#13-requirements) shall be 7 min. (D6)
- **R13** The pipeline shall process at most 360 bronze objects per batch. (D6)
- **R14** When a run ends without failing, the pipeline shall send the heartbeat's success signal. (D7)
- **R15** If a run fails, then the pipeline shall send the heartbeat's failure signal. (D7)
- **R16** If a run fails, then the platform shall not retry it. (D7, TH7)
- **R17** The heartbeat monitor shall expect a signal every 15 min, with 15 min of grace. (D7)
- **R18** While an end instant is set, the pipeline shall process only the bronze objects captured up to it, oldest first. (D8)
- **R19** While an end instant is set, when a run finds no pending object captured up to it, the pipeline shall log an event of severity warn. (D8)
- **R20** If a batch fails a runtime rule of severity error on its rows (DQR1, DQR13), then the pipeline shall commit nothing of the batch, leave it pending and fail the run. (D9, #13)
- **R21** If a batch holds a row that fails its column's schema, then the pipeline shall commit nothing of the batch, leave it pending and fail the run. (D9)
- **R22** If a batch holds a bronze object that cannot be read, then the pipeline shall commit nothing of the batch, leave it pending and fail the run. (D9)
- **R23** The pipeline shall receive its secrets only as Modal Secrets. (TH5)
- **R24** The pipeline shall not write a secret's value, the heartbeat's URL included, to its events or error messages. (TH1, TH5)
- **R25** The pipeline shall pass feed values to SQL only as data or parameters, never as SQL text. (TH2)
- **R26** While a run is a one-off run of code that is not deployed, the pipeline shall not write to the production lakehouse. (TH3)
- **R27** While a run is a one-off run of code that is not deployed, the pipeline shall not deploy the page. (TH3)
- **R28** The pipeline shall let DuckDB reach only the pipeline's buckets. (TH9)
- **R29** The pipeline shall load no DuckDB extension at run time. (TH9)
- **R30** If a write to the station stock reports a row updated or deleted, then the pipeline shall log DQR2's failure and fail the run. (D3, #13)
- **R31** If the page's deployment fails, then the pipeline shall keep the batches committed in the run, log the failure and fail the run. (#19)

### 1.4 Done when

<!-- Optional. Only what closes this task and Requirements cannot express: operational actions, checks on real data, understanding. The general closing rule is checked in `.claude/skills/implement/review.md`. -->

- Before the first deployment, the memory of a reference batch on real data confirms or lowers the batch bound (D6).
- The owner has set Modal's spend limit (TH7).
- The owner has created the pipeline's own Cloudflare token, with the Workers Editor role and an expiry, and the run deploys the page with it (D10, TH8).
- The first load has drained through D8's three stages, each with its runtime rules, reconciliation, run time and memory checked before the next, and the end instant removed after the last (D8).
- The pipeline runs on Modal every 15 min in production; its run time and memory are measured on the feeds' real volume, and the cadence and [ADR-0027](../decisions/0027-modal-as-execution-platform.md) are reviewed against them ([d007 › Children](d007-pipeline-design.md#16-children)).
- R2's operations and storage per bucket over 14 days of scheduled runs are compared with the cost model, the model is recalibrated, the classes of conditional PutObject, ListObjectsV2 and DeleteObjects are confirmed, and the owner has set Cloudflare's R2 alerts from the recalibrated figures ([Cost recalibration](#cost-recalibration)).
- The `pull_request` run's wall-clock is measured again with the `pipeline` job and updated in [testing-strategy.md › Moving tests](../testing-strategy.md#moving-tests); if it passes 10 min, the slowest group moves as that section sets.

### 1.5 Out of scope

<!-- Optional. What someone could expect and will not be done, each item pointing to the task that covers it. -->

- The keys of the Station and System dimensions, the station's attributes in the file and the tables of Date and Time of day — T060.8
- TR3, whether a row comes from the archive, and TR2 and TR4 on the archive — T060.4
- The set-aside of failed batches with redrive, and the quarantine table — T060.5
- The split by vehicle type, in the station stock and in the file — T060.3
- The review of DQR12's threshold, window and minimum of captures against production runs — T060.2
- The page that shows the published file, and the escaping of its values in the page — T041
- The compaction, VACUUM and retention of the pipeline's Delta tables — T072

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

#### Component structure

The pipeline is a component with its own folder, `pipeline/`, beside `capture/`: it holds its runtime pin, manifest and lockfile (`.python-version`, `pyproject.toml`, `uv.lock`), its package under `src/bikesharing/`, its `tests/` and its `scripts/`. The repository root keeps only what every component shares, such as the documentation tooling. **#1**

The package `bikesharing` has the two subpackages of [ADR-0046](../decisions/0046-functional-core-imperative-shell-for-the-pipeline.md), `bikesharing.core` and `bikesharing.shell`. The platform modules are `pipeline/modal_image.py`, `pipeline/modal_app.py` and `pipeline/modal_one_off.py`, at the component's root and outside `src/`, so they are never installed with the package; they are the only files that import `modal`, and `modal_image.py` adds the package to the image with `add_local_python_source`. **#2, DI12**

ADR-0046's rules 1–3 are import-linter contracts in `pyproject.toml`, with `bikesharing` as its root package: rule 1 forbids `modal` in `bikesharing`, rule 2 forbids `duckdb`, `dbt` and HTTP clients in `bikesharing.core`, and rule 3 is a layers contract of `shell` above `core`. A forbidden contract on an external package needs `include_external_packages = true`; the step that writes the contracts confirms it with a contract that must fail, and falls back to PyTestArch if import-linter cannot express it. Rules 4 and 5 are CI tests in `pipeline/tests/integration/test_platform_separation.py`. Rule 4 reads the imports of each platform module from its syntax tree and fails on `duckdb`, since import-linter takes only packages as root packages and the platform modules are single modules. Rule 5 imports the package and builds its configuration in an environment synced without Modal's SDK, which sits in its own dependency group. **DI11, DI12**

Options considered for the component folder:

- `pipeline/` as the component folder (chosen): pros, the runtime and lockfile stay in the component's own files ([ADR-0016](../decisions/0016-runtime-versions-pinned-per-component.md), [ADR-0017](../decisions/0017-dependencies-locked-per-component.md)) and its CI job targets one folder, as with `capture/`; cons, longer paths and an edit to CLAUDE.md › Project structure.
- The repository root, the layout of a single-project Python repository: pros, shorter paths; cons, the Python project shares the root with the documentation's Node project, and `scripts/` and `tests/` mix the pipeline with the rest.

Options considered for the platform modules:

- `pipeline/modal_*.py`, outside `src/` (chosen): pros, PyPA's `src/` layout keeps them out of the installed package, so rule 5 holds by construction, and their names state the platform; cons, import-linter takes only packages as root packages, so rule 4 is a test of the modules' imports instead of a contract.
- `pipeline/src/bikesharing_modal/`, a second top-level package: pros, import-linter sees it as one more package; cons, two packages declared in `pyproject.toml`, and rule 5 depends on keeping one of them out of the installation.

#### Runtime and dependencies

- **Python:** `pipeline/.python-version` holds the exact patch of 3.14, with `requires-python = ">=3.14,<3.15"`; if `uv sync --locked` or the tests fail on 3.14, both move to 3.13.18 and the cause is recorded as a finding; since `uuid.uuid7()` is new in 3.14, the shell then generates the run ID with a function of its own that follows RFC 9562's UUIDv7 layout.
- **Python on Modal:** the image is built from the official `python:<patch>-slim-bookworm` image, whose patch `modal_image.py` reads from `.python-version` at deploy time, so production runs the patch that passed CI. **#3**
- **Manifest and lockfile:** `pyproject.toml` declares the runtime dependencies (DuckDB on its pinned 2.0.x patch, `dbt-core` 1.12.7, `dbt-duckdb` 1.11.1, `deltalake` with its Arrow library `arro3-core` (DI7), `obstore` and `jsonschema`) and two dependency groups: `dev` (pytest, ruff, mypy, import-linter, SQLFluff with its dbt templater) and `platform` (Modal's SDK). `uv.lock` locks them all. `mashumaro>=3.15` is a constraint on a transitive dependency of dbt, set in `[tool.uv] constraint-dependencies`, against the truncation of float model versions below 3.15.
- **S3 client:** the shell reaches R2's S3 API with `obstore`, through an `S3Store` with the account's endpoint and the credentials passed explicitly, never read from the environment or a profile; it lists, downloads each batch's objects concurrently and uploads the run's log object. Tests use its `LocalStore` over local folders, through the same code. On R2, `list`'s `offset` returns exactly the keys after it and not the key itself, as `start-after` does (#7): listing a day of AMBici's `station_status` (1,431 keys) after the key in the middle of the day returned the 715 keys that follow it; the core sorts the keys it receives, since `obstore` does not guarantee their order. **#25**
- **Image dependencies:** the image installs only the runtime dependencies, at the versions locked in `uv.lock`; Modal provides its own client inside the container.
- **Checks:** `pipeline/scripts/check-pipeline.sh` runs the checks of [Tests and CI](#tests-and-ci); it is the Check of every code step and the command of the pipeline's CI job.

Options considered for the Python patch on Modal:

- The official image with the exact patch (chosen): pros, one line in `modal_app.py`, and the patch matches local and CI; cons, a new patch waits for its official image, published within hours of the release.
- Modal's `debian_slim` with the exact patch installed by `uv python install`: pros, the same build of Python as local and CI; cons, two or three more image steps for the same patch.
- Modal's `debian_slim(python_version="3.14")`: pros, the simplest image; cons, Modal picks the patch, so production can run one CI never tested.

Options considered for the S3 client:

- `obstore` (chosen), following a minimal dependency footprint where secrets are held and tests against a real local implementation rather than a mock: pros, one wheel with no Python dependencies, concurrent downloads, and `LocalStore` runs the integration tests through the production code; cons, pre-1.0 with breaking minor releases, held by `uv.lock` and reviewed at each update.
- `boto3`, AWS's SDK, the client of Cloudflare's R2 examples: pros, the most used and documented client; cons, botocore and four more packages in the image, `moto` to simulate R2 in tests, and its checksum settings pinned after the incompatibility R2 had with them.

#### Delta writes

- **Table paths:** the Delta tables live in `bikesharing-lakehouse` under one prefix per layer, as [ADR-0035](../decisions/0035-cloud-resource-naming.md) sets for a bucket that holds more than one layer: `station_stock` at `silver/station_stock/`. The pipeline's control tables, which hold the state of its loads and no data of any layer, live under `control/`: `processed_objects` at `control/processed_objects/`. This slice writes no gold table, since `latest_station_count` lives only in the run's scratch database and leaves it as the published file (#24).
- **Fact rows:** a batch's station stock is written with an insert-only MERGE on the natural key (system, `station_id`, capture instant), bounded by the batch's range of capture instants, so that processing an object again adds only the rows the table does not hold ([ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md)) and no row is updated or deleted (DQR2).
- **Partitioning:** the station stock is partitioned by the row's local calendar date ([ADR-0041](../decisions/0041-utc-timestamps-local-calendar-keys.md)), so that a normal run's MERGE and the read of the latest counts touch one partition, and retention drops whole partitions. The MERGE's partition predicate is the set of local dates the batch's own rows carry. **#5**
- **Processing state:** a Delta table, `processed_objects`, holds one row per bronze object a run has processed: its key, system, feed, capture instant, the number of stations it lists (`station_count`, the history of DQR12), status, run ID and code version. A bronze object is pending while it has no row there. Each batch commits its fact rows first and its rows in `processed_objects` second, with an insert-only MERGE on `key` so that no object is recorded twice, following an idempotent sink with a progress log written after it: a run that stops between the two commits leaves the batch pending, and processing it again adds no fact row. In T060.1 the only status is `processed`; T060.5 adds the status of a batch set aside and of an object with rows in quarantine. The table can be rebuilt from the fact rows, since each row's bronze object follows from its system, feed and capture instant ([ADR-0043](../decisions/0043-lineage-at-four-levels.md)). **#4**
- **Conflicts:** a MERGE that conflicts with a concurrent commit is retried on a fresh table handle. Scheduled runs never overlap and one-off runs write only to local disk (#20), so a conflict means another writer, such as T072's maintenance job, committed at the same time.
- **Table creation:** the shell creates each missing table with its explicit schema at the start of a run, before any write; no write uses `schema_mode="merge"`, so a column change takes a new code version.
- **Table maintenance:** the run neither compacts nor vacuums its tables; their maintenance, with silver's retention, is a scheduled job of its own, T072. Until then each partition keeps the small files of its commits, which only reads of past days touch. **#6**
- **Conditional put:** `deltalake` writes to R2 with conditional put, with no locking provider: the storage options set `aws_conditional_put` to `etag` and `AWS_REGION` to `auto`, as `deltalake`'s documentation gives them for R2.

Options considered for the processing state:

- A control table of processed objects (chosen): pros, it records objects that produce no rows, T060.5 extends it with one status, and pending objects are read from a small table; cons, one more table, and a second commit per batch.
- Derived from the fact rows, as the distinct pairs of system and capture instant: pros, no extra table; cons, an object with no rows looks pending for ever, each fact table of later children needs its own derivation, and T060.5 needs a table for batches set aside anyway.

Options considered for the partitioning:

- By local date, one partition per day (chosen): pros, each run reads one day, the table is read by local day, and the column already exists; cons, about 96 small files a day per partition until they are compacted.
- By UTC date, one partition per day: pros, the same reach per run; cons, a query for one local day touches two partitions, and the table carries a column used only to partition it.
- By week or by month: pros, fewer partitions; cons, the same number of files a day, and each run's MERGE and read scan up to a week or a month.

#### Bronze reading

- **Discovery of pending objects:** the shell lists each system's `station_status` prefix through R2's S3 API, and the pending objects are the listed keys with no row in `processed_objects`. A run lists from 1 h before the most recent processed object, with `start-after`, which covers the delay between a capture's instant and the write of its object; the first run after local midnight lists the whole prefix, so that an object written later than that is processed too ([ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md)); with no processed object, as on the first load, a run lists the whole prefix. Whether a run sweeps the whole prefix, and from which key it lists otherwise, is decided by the core. **#7**
- **Batch reading:** each run has one work folder on the container's local disk, created at its start and removed at its end, which holds the scratch database, DuckDB's spill folder, the Parquet inputs of dbt and one subfolder per batch. The shell downloads each batch's objects, by their explicit keys, to the batch's subfolder, and DuckDB reads that batch's files with `read_json` from their explicit list, never from a glob. The subfolder is removed when the batch ends, whatever its outcome. DuckDB runs with `enable_external_access = false`, `allowed_directories` set to the run's work folder and `lock_configuration = true`; the folder is the same for every batch, since the process shares one DuckDB instance of the scratch database and its configuration is locked. DuckDB then reaches no network and no other file, loads no extension and holds no R2 credential (R28, R29). Files on the container's local disk do not count against its memory: a probe in a container of 4096 MiB wrote a 5 GiB file to its overlay disk, of 512 GiB, and finished. The container exposes no cgroup counters, so that is the evidence. A batch's files are then bounded by the disk, not by the memory. **#9**
- **Memory:** the Modal function sets its memory reservation equal to a hard limit, and the shell sets DuckDB's `memory_limit` to 60% of that limit, a value it receives as configuration from `modal_image.py`; the rest is left to Python, the Arrow hand-off to `deltalake` and dbt. DuckDB spills to a folder in the run's work folder (#9), set with `temp_directory`; the step that writes DuckDB's configuration confirms that spilling and dbt's scratch database work with external access off. In a container of `one_off_run`'s size, with `cpu=1.0`, DuckDB detects 17 threads and a default `memory_limit` of 3.1 GiB, measured by a probe. `threads` stays at that default, which the `peak_memory_mb` of the reference batch checks. A memory error is not retried. Both values change only when `peak_memory_mb` nears the container's limit, or DuckDB raises memory errors while the container has room left. **#10, #30**
- **Read schema:** `read_json` reads each batch with an explicit `columns` schema and without `union_by_name`, so that DuckDB infers no schema file by file, which is what exhausts its memory over thousands of files in duckdb#27806; a row that does not fit the schema fails its batch (R21). There is one schema per system and feed, a constant of `bikesharing.core` declared from that feed's field dictionary in its system's source card ([AMBici](../sources/ambici.md), [Bicing](../sources/bicing.md)), since each provider publishes its own GBFS version and departs from it in its own way; a child that reads another feed adds that feed's schemas. A test reads each system's bronze fixtures with its schema. If a 2.0.x patch carrying the upstream fix is released, the pin moves to it, but the reading does not depend on it. **#11**
- **Unreadable objects:** until T060.5, an unreadable bronze object fails its batch (D9) and is excluded only by a versioned list in the repository, `pipeline/config/excluded_objects.txt`, one key per line with its reason; the core removes the listed keys from the pending objects. An exclusion is then a reviewed change deployed as a new code version, as D9 sets. The list is provisional: T060.5 replaces it with the set-aside and removes it, and the file carries a `TODO(T060.5):` marker saying so. **#8**

Options considered for the discovery of pending objects:

- Incremental listing with a daily full sweep (chosen), following incremental directory listing with a periodic backfill (e.g. Auto Loader's `cloudFiles.backfillInterval`): pros, a normal run lists one page per system, about 30,000 list requests a month after a year of bronze; cons, an object later than 1 h waits for the daily sweep.
- A full listing in every run: pros, the simplest and exact in every run; cons, about 1,000 requests per run after a year, some 3 million a month, above R2's free Class A operations and growing with bronze.
- R2 event notifications to a queue: pros, no listing; cons, a queue, its consumer on Modal and one more point of failure, out of proportion for this volume.

Options considered for the exclusion of unreadable objects:

- A versioned exclusion list in the repository (chosen), following a deny list in a fail-fast pipeline: pros, each exclusion is reviewed and traced by the deployed SHA; cons, a PR and a deployment to unblock the pipeline.
- A manual `excluded` status in `processed_objects`, set by a script: pros, immediate; cons, a manual write to a production table outside review, and one more status for T060.5 to inherit.

Options considered for how bronze reaches DuckDB:

- The shell downloads each batch to a local folder, the only path DuckDB may read (chosen), following least privilege with DuckDB's file sandbox: pros, DuckDB keeps its JSON reader, reaches no network and holds no credential, and tests read local fixtures through the same code path; cons, the batch takes local disk, and the download is code of the shell.
- The shell reads the objects into memory and hands DuckDB an Arrow table: pros, DuckDB touches no file; cons, the JSON parsing and its schema move to Python, and the batch is held in memory as bytes, Python objects and Arrow at once.
- DuckDB reads R2 with `httpfs`, installed in the image and loaded explicitly, with a secret scoped to bronze: pros, no download and no local folder; cons, it breaks R29, and DuckDB gets network access and an R2 credential, and tests need a simulated R2.

Options considered for memory:

- Explicit limits on both sides, DuckDB's a fraction of the container's (chosen), following engine memory set below the container's limit with headroom: pros, a batch too large spills or fails with DuckDB's own error, which the log records; cons, one more configuration value.
- The container's limit only, with DuckDB's default of 80% of the memory it detects: pros, no configuration; cons, DuckDB may detect the host's memory instead of the container's, and the container is then killed with no final event.

#### Transformation in dbt

- **Project:** the dbt project is `pipeline/dbt/`, with its `dbt_project.yml` and a `profiles.yml` whose database is the run's scratch database: a DuckDB file in the run's work folder (#9), created at the start of the run and removed at its end ([ADR-0047](../decisions/0047-dbt-builds-and-audits-the-pipeline-sql.md)).
- **Bronze as external sources:** each system's bronze is a source of its own, `ambici.station_status` and `bicing.station_status`, since AMBici publishes GBFS 2.3 and Bicing GBFS 3.0. Each is declared with `dbt-duckdb`'s `external_location` as a `read_json` over the batch's local files of its system, with its system's read schema of #11 and `filename = true`, so that the staging models take each row's system and capture instant from its file's path, which ends with its bronze key ([`bikesharing.shell.r2`](#bikesharingshellr2)), parsed as `contracts/bronze-keys.json` sets. The shell passes the files and the read schemas as dbt variables keyed by system, together with the run's ID and code version. Models read bronze only through `source()`, so that dbt's lineage starts at bronze and unit tests replace the sources with hand-written rows. The step that writes the sources confirms that `external_location` renders dbt variables; if it does not, each staging model calls `read_json` with the variables and declares its source with dbt's `depends_on` comment, so that lineage still starts at bronze, and unit tests start at the next model. **#12**
- **Models:** the models are grouped in one folder per layer of [ADR-0018](../decisions/0018-medallion-architecture.md), `models/silver/` and `models/gold/`. In silver, following dbt Labs' project structure, one staging model per source, `stg_ambici__station_status` and `stg_bicing__station_status`, casts its source's fields, converts its instants to UTC timestamps, renames its measures as GBFS 3.0 names them (TR5) and applies D1's rules on measures and flags: TR8's nulls in AMBici's, TR9's null in Bicing's. `station_stock` unions both, in the columns of its contract, and adds the local calendar keys and the lineage columns, at D1's grain; `capture_volume` and `schema_drift` audit the batch (#14, #15). In gold, `latest_station_count` holds D2's fields in the shape of the published file, under a dbt model contract ([Publishing](#publishing)). The published file is a dbt exposure of type `application` in `models/exposures.yml`, which depends on `latest_station_count`, so that dbt's lineage ends at the file. **#24**
- **SQL conventions:** the SQL files follow dbt Labs' SQL style guide, and `.claude/rules/code/sql.md`, on `pipeline/dbt/**`, states it with what is the project's own: one model per file, sources read only through `source()` and models through `ref()`, each data test's `name` as its DQR ID, and a model contract on every model the shell or a consumer reads. SQLFluff checks them with the `duckdb` dialect and its default rules, s016 › D2's policy, configured in `[tool.sqlfluff]` of `pyproject.toml`, with the dbt templater; the step that configures it confirms the templater supports `dbt-core` 1.12.7, and falls back to the Jinja templater otherwise. A `PostToolUse` hook on `.sql` edits under `pipeline/dbt/` runs `sqlfluff fix` and `sqlfluff lint` on the edited file and reports what remains on stderr with exit 2, as the Python hook does (s016 › P3). **#27**
- **Rule traceability:** each runtime rule's data test takes its catalog ID as `name` and, in `meta`, the link to its entry in [data-quality.md](../data-quality.md), so that dbt's documentation shows the rule beside its model.
- **Runtime rules:** DQR1 is a project generic test of `station_stock` that fails on each natural key with more than one row, since dbt's built-in `unique` takes one column and the project adds no dbt package, and DQR13 a data test that compares the stations the source lists with the rows of `station_stock`; together with the insert-only MERGE (#4), they hold the grain across batches. DQR2 is the one rule of D3 that is not a dbt data test, since it concerns the Delta table's history, which dbt does not see: it holds by construction, as the MERGE has only an insert clause, and after each MERGE the shell checks that the metrics it returns report no row updated or deleted, logs DQR2's result and fails the run otherwise. The retention of T072 drops partitions in its own job, never in a run. **#13**
- **Volume drop:** DQR12 is a data test of severity warn on the model `capture_volume`, with one row per capture of the batch: its system, capture instant and number of stations, the median number of stations of its system's captures in the 24 h before its capture instant, and its status, `ok`, `drop`, or `not_evaluated` with fewer than 60 captures in that window. The median takes the history and the batch's own earlier captures, so that the stages of D8 compare each capture with its own past. The test fails on `drop`, and the shell logs each `not_evaluated` capture. The history is the source `lakehouse.capture_history`: the rows of `processed_objects` captured in the 24 h before the batch's first capture, which the shell reads with `deltalake` and writes as a Parquet file to the batch's subfolder (#9). A capture that lists no station is counted as 0. **#14**
- **Schema drift:** DQR11 is a data test of severity warn on the model `schema_drift`, which compares the fields each bronze object carries with the read schema of #11, since a read with explicit `columns` ignores a new field and turns a missing one into nulls. The sources `ambici.station_status_raw` and `bicing.station_status_raw` read each system's same local files with `read_json_objects`, with no schema; per object, `schema_drift` takes the union of the stations' keys with `json_keys`, so that GBFS's optional fields, present in some stations only, raise no drift, and compares it with its system's declared fields. A declared field missing from every station of an object is dropped, and a field present in any station but not declared is added. The test fails when any field is added or dropped, and the shell logs each field with its system. **#15**
- **Severity and verdict:** each data test declares in its own configuration the severity its rule has in the catalog, `error` or `warn`. The shell collects the status of every node of `dbt build` as values, and the core commits the batch only if no node ends in `fail` or `error`, which includes a model that fails its contract (R21); each `warn` is logged as an event and stops nothing. dbt runs without fail-fast, so that one run logs every failing rule of the batch. **#16**
- **Materialization:** the staging models, `capture_volume` and `schema_drift` are views, read once by their tests; `station_stock` is a table of the scratch database, read by its tests and then by the hand-off, so that it is computed once.
- **Hand-off to Delta:** once the core's verdict lets the batch commit, the shell opens the scratch database with the configuration of #9 and #10, reads `station_stock` whole as an Arrow table with `con.sql()`, counts its rows from it, and passes it to the MERGE of `deltalake`. The Arrow table sits outside DuckDB's `memory_limit`, in the headroom #10 leaves: under 2 MB in a normal run, about 35 MB for a full batch of 360 objects (D6). If `peak_memory_mb` shows the hand-off as the run's peak, it moves to a stream of record batches. **#17**

Options considered for how a batch enters dbt:

- One external source per system over the batch's local files (chosen), following `dbt-duckdb`'s external sources: pros, reading bronze is part of dbt's graph, as ADR-0047 sets, and the shell keeps only I/O; cons, it depends on the adapter rendering variables in `external_location`.
- The shell loads the batch into a table of the scratch database, which dbt reads as a source: pros, no dependency on the adapter's external sources; cons, the reading and its schema become Python code of the shell, dbt's lineage starts at an intermediate table, and the batch is held as a table before it is transformed.

Options considered for DQR12's history:

- Each capture's station count kept in `processed_objects` (chosen), following per-load metrics in the control table: pros, about 2,900 counts read per run, from a table the discovery reads anyway, and a capture with no rows is in the history; cons, one more column in the control table.
- Rows of `station_stock` counted per capture: pros, no new column; cons, each run reads about 1.1 million fact rows for the same counts, and a capture with no rows is missing from the history.

Options considered for DQR11:

- The keys of each object, read with no schema, compared with the read schema (chosen), following the schema monitors of data observability: pros, it detects added and dropped fields and names them, in milliseconds over files already on local disk; cons, the batch's files are read twice.
- The read schema with `not_null` tests on required fields: pros, no second read; cons, it misses added fields, half of DQR11, and a dropped optional field.
- One read with the stations as JSON, typed in the staging model: pros, a single read; cons, the typing of #11 moves to hand-written SQL to save milliseconds.

Options considered for the models' folders:

- One folder per layer, with the published file as an exposure of a gold model (chosen), following ADR-0018 and dbt's exposures for downstream consumers: pros, the project shows the medallion at a glance, the file reads only gold, and the lineage ends at the file with no model that copies another; cons, a fixed shape a future file cannot take from one gold table goes into gold or into its serialization.
- dbt's `staging/`, `intermediate/` and `marts/`, with a table that maps each folder to its layer: pros, the layout every dbt user knows; cons, the medallion lives outside the code, and the published file has no place of its own.
- One folder per layer plus `serving/`, a model with the file's shape: pros, room to shape files that combine gold tables; cons, in this slice a copy of the gold model.

Options considered for the SQL conventions:

- A rule on dbt Labs' style guide, checked by SQLFluff (chosen), following the style guide and the linter it recommends, as s016 › D2 does for Python: pros, a tool checks the style, not the review; cons, one more dependency, and the dbt templater's support of `dbt-core` 1.12.7 is still to be confirmed.
- The rule alone, checked in review: pros, no new dependency; cons, the style rests on the review, unlike Python's.

#### Publishing

- **Source of the file:** the file is built from the lakehouse's committed state, not from the run's batches. After the run's last commit, the shell finds in `processed_objects` the most recent capture of each system, reads from `station_stock` only that capture's rows, pruned by local calendar date, and writes them as a Parquet file to the run's work folder (#9). The dbt model `latest_station_count` reads it as the source `lakehouse.latest_captures` and builds D2's fields. The file's stations are those listed by the latest capture of their system, so a system with no capture in the run keeps its earlier count, and a station the feed stops listing leaves the file.
- **Contract:** the file is published as `latest-station-count.json`, a fixed name across runs ([s013 › P1](../spikes/s013-visualization-tool.md#55-production-inputs)). Its JSON Schema, named after it, is `contracts/latest-station-count.schema.json`, in draft 2020-12, shared by the pipeline, which produces the file, and the page, which consumes it. It declares D2's fields with their types and nullability, and `additionalProperties: false` at every level, so that DQR14 also rejects a field outside D2's list (R7). Its shared vectors, `contracts/latest-station-count.json`, follow [testing.md](../../.claude/rules/code/testing.md)'s contract format: one `valid` file and one `invalid` file per kind of violation (a missing field, a wrong type, a field outside D2's list), each with its `reason`, read by the pipeline now and by the page from T041. A child that adds a field to the file adds it to the schema and to the vectors in the same commit. **#29**
- **Runtime check:** the core validates the built file against the schema with the `jsonschema` library before the shell deploys it. A file that fails DQR14 follows [d007 › R2](d007-pipeline-design.md#13-requirements): it is not deployed, the last file that passed stays published, the run logs each violation with its path in the file, and the run fails (D9).
- **CI check:** the pipeline's contract test builds the file from the fixtures through the same models and validates it against the schema, together with the vectors' cases: the `valid` file must pass and each `invalid` file must fail.
- **Deployment tool:** the run deploys the page with `wrangler deploy`, passing the run's code version as `--tag` (D5). Modal's image installs Node and `wrangler` at build time, at the versions `web/` pins and locks ([ADR-0016](../decisions/0016-runtime-versions-pinned-per-component.md), [ADR-0017](../decisions/0017-dependencies-locked-per-component.md)), so a run installs nothing. The shell runs `wrangler` as a subprocess with the pipeline's Cloudflare token in its environment only, and reads its exit code and output. **#18**
- **Worker configuration:** the page's Worker belongs to the page's component, `web/`, created in this slice with only what the deployment needs: `wrangler.jsonc`, a Worker of static assets only, with its name, compatibility date and assets directory, and the pins of Node and `wrangler`. T041 adds the page, its tests and its CI job. Modal's image copies `web/`; the run writes the published file to the assets directory and deploys with `wrangler deploy --config`. Until T041 the Worker serves only `latest-station-count.json`. **#26**

Options considered for the deployment tool:

- `wrangler` in Modal's image (chosen), following deployment with the provider's official tool: pros, no deployment code of the project's own, and the same tool and behaviour as capture; cons, a second runtime in the image, with its updates and npm dependencies in a container that holds secrets.
- The direct upload API called from Python: pros, a single runtime in the image; cons, the project maintains code against an API whose hash format and version tag are not confirmed ([Cloudflare source card](../sources/cloudflare.md)), and its failures differ from capture's.

Options considered for the Worker's configuration:

- The page's component, `web/`, created now with the Worker's configuration and the pins of `wrangler` (chosen), following one folder per component in a monorepo, as #1, since the Worker deploys the page and its data together ([ADR-0033](../decisions/0033-data-published-by-redeploying-static-assets.md)): pros, each file is in its final place and T041 only adds; cons, an almost empty folder until T041, and `modal_image.py` reads files outside `pipeline/`.
- `pipeline/publish/wrangler.jsonc`, with `wrangler` pinned in `pipeline/`: pros, the pipeline depends on nothing outside its folder; cons, T041 moves the file and the pins to the page's component.

- **Failed deployment:** the deployment runs after the run's last commit, so a failed deployment leaves the committed batches in place. The run logs the failure with `wrangler`'s exit code and output, ends as failed, and the heartbeat sends the failure signal (R15). The next run builds the file again from the lakehouse and deploys it, so the scheduled cycle is the retry (D7). Every run deploys, with or without new batches, so a run after a failed deployment recovers the page even when it has nothing to process; at the 15-minute cadence that is about 2,900 deployments a month, below the 4,300–8,600 that [ADR-0033](../decisions/0033-data-published-by-redeploying-static-assets.md) assessed. **#19**

Options considered for a failed deployment:

- The run ends as failed (chosen), following a heartbeat that reports the whole job's outcome, publishing included: pros, the owner learns of it at once, an expired token included; cons, an outage of Cloudflare alerts on every run while it lasts.
- The run ends with no failure, the error logged as an event: pros, no alerts from Cloudflare's outages; cons, until T060.2 builds the alert on the file's age, a broken deployment shows only in the logs and the page can stay frozen unnoticed.

#### Environments and configuration

- **One environment:** the pipeline runs only in production, as [ADR-0035](../decisions/0035-cloud-resource-naming.md) sets; there are no development buckets or Modal environments.
- **One-off runs:** the two functions live in two Modal apps, the scheduled one in `modal_app.py` and the one-off one in `modal_one_off.py`, which share the image of `modal_image.py`. `modal run` creates every function of the app it starts, so a run from a branch starts only the one-off app and never creates the scheduled function. The scheduled function is the only one with the lakehouse's read-write token and the pipeline's Cloudflare token attached, and it refuses to start unless the code version that the deploy script sets in the image is present (D5). The one-off function, used for runs from a branch such as D6's reference batch, has only bronze's read-only token attached: it writes its Delta tables to the container's local disk, removed at its end, and never deploys the page. R26 and R27 then hold because no function of the one-off app has a credential to break them, whatever the owner's shell holds. **#20, DI12**
- **End instant:** D8's end instant is a constant of the core, an instant in UTC or none, changed by a PR and a deployment at each stage and removed after the last one; the code version in each row then traces the end instant it was processed under. **#21**
- **Secrets and settings:** secrets reach the run only as Modal Secrets (R23), one per credential so that each function attaches only its own: bronze's read-only R2 token, the lakehouse's read-write R2 token, the pipeline's Cloudflare token and the heartbeat's URL. Every other setting, such as the account ID and the bucket names of ADR-0035, is a constant of the code, reviewed and traced like the end instant; the page's Worker name is in its `wrangler.jsonc` ([Publishing](#publishing)).

Options considered for one-off runs:

- A one-off function with no write credentials, in an app of its own (chosen), following least privilege per app: pros, R26 and R27 hold by construction, within ADR-0035's single environment; cons, one more module and one more app, and a one-off run does not exercise writes to R2.
- The two functions in one app, the scheduled one refusing to start without a code version: pros, one module; cons, `modal run` creates every function of the app, so the scheduled function, with production's credentials, was part of Step 28's one-off run, and only the owner's shell kept it from writing.
- A development environment, with a Modal environment and buckets of its own: pros, a one-off run writes to R2 as production does; cons, it changes ADR-0035, and adds buckets, tokens and a second set of configuration to create and pay for.

Options considered for the end instant:

- A constant in the repository (chosen), following configuration as code: pros, each change is reviewed and traced by the deployed SHA, as #8's deny list is; cons, a PR and a deployment per stage, about four in all.
- An environment variable in a Modal Secret, following Twelve-Factor's configuration in the environment: pros, a change applies at the next run with no deployment; cons, it is neither reviewed nor traced, and a secret holds a value that is not secret.

#### Run operation on Modal

- **Schedule:** the scheduled function runs on `modal.Cron("*/15 * * * *")`, in UTC, the 15-minute cadence of D7 at fixed clock times that do not move on redeploy ([ADR-0028](../decisions/0028-modal-cron-as-pipeline-scheduler.md)).
- **Container size:** both functions declare `cpu=1.0` and `memory=(4096, 4096)`, in MiB: a reservation equal to its hard limit (#10), at the 1 vCPU and 4 GiB on which [s012 › D1](../spikes/s012-execution-target.md#d1-execution-platform) estimates the monthly credit, and which [s012 › F1](../spikes/s012-execution-target.md#f1-modals-starter-plan-accepts-a-4-gib-function-and-lets-it-occupy-3822-gb) showed Starter accepts. DuckDB's `memory_limit` is then about 2.4 GiB. The size is raised only when the reference batch or `peak_memory_mb` calls for it, and a request above 4 GiB is first tried in a one-off run, since the plan's maximum is unknown.
- **Timeout and retries:** the scheduled function declares `timeout=600` (R11) and no `retries`, Modal's default of none (R16). A memory kill of a deployed function is the exception ([s012 › TH12](../spikes/s012-execution-target.md#d3-pipeline-security)): a probe with a 512 MiB function that exceeded its hard limit, deployed and invoked once, started 8 times in 52 s, each attempt ending with `Runner killed (SIGKILL), exit code: 137`, before the call failed with `modal.exception.InternalFailure` (`Server has lost track of input`). Modal retries a container killed for memory by itself, outside `retries`, so R16 holds for what the function declares and not for this failure. The residual risk stays bounded as TH12 accepts it, by DuckDB's limit, the heartbeat's failure signal and the spend limit.
- **No overlapping runs:** the scheduled function declares `max_containers=1`. Its timeout, below the cadence, already keeps a tick from finding a run still active; the limit is the backstop that makes such a tick wait instead of running beside it (TH7).
- **Region:** the functions run in Modal's default region, on global capacity, not in `eu`, which costs 1.15x and lowers the credit's 540 hours to about 470. The region is revisited only if `duration_s` shows the run's time dominated by its requests to R2.
- **Usage and spend limits:** the owner sets Modal's usage limit to the $30 monthly credit and its spend limit to $1 on the billing page, so that usage above the credit is bounded at $1 ([s012 › R28](../spikes/s012-execution-target.md#d3-pipeline-security)); the spend limit is checked in Done when (TH7).

#### Observability

- **Event convention:** the pipeline's events follow [ADR-0036](../decisions/0036-log-convention-across-components.md): JSON Lines with `ts`, `level`, `component`, `version`, `run_id` and `event` first. `component` is `pipeline`, `version` is the code version of D5, and `run_id` is a UUIDv7 that the shell generates with Python's standard library at the start of the run, so that the core and the rows' lineage do not depend on Modal (ADR-0046's rule 5) and run IDs sort by time. A one-off run carries the version `unreleased`.
- **Events:** the core builds each event as a value with its own fields, and the shell writes it. The events are:

  | Event | Level | Own fields |
  |---|---|---|
  | `run_started` | info | `end_instant`, `excluded_objects` |
  | `objects_discovered` | info | per system: `listed`, `pending`, `full_sweep` |
  | `stage_drained` | warn | `end_instant` (R19) |
  | `batch_started` | info | `batch`, `objects`, `first_capture`, `last_capture` |
  | `node_finished` | info | dbt's `node`, `status`, `duration_s`, `rows`, `num_failures` ([s017 › P4](../spikes/s017-dbt-in-the-pipeline.md#55-production-inputs)) |
  | `rule_checked` | info, warn or error by outcome | `rule` (its DQR ID), `severity`, `status`, `failures` |
  | `volume_not_evaluated` | info | `system`, `captured_at`, `captures_in_window` (DQR12) |
  | `schema_drift_field` | warn | `system`, `field`, `change` (`added` or `dropped`) (DQR11) |
  | `batch_committed` | info | `batch`, `rows_inserted`, `objects` |
  | `batch_failed` | error | `batch`, `reason`, `error_type`, `error` (R20–R22) |
  | `file_built` | info | `stations`, `data_instant` |
  | `file_invalid` | error | `violations`, each with its path in the file (DQR14) |
  | `page_deployed` | info | `tag`, `deploy_peak_memory_mb` |
  | `page_deploy_failed` | error | `exit_code`, `output` (R31) |
  | `heartbeat_failed` | warn | `signal`, `attempts`, `error_type` |
  | `log_upload_failed` | warn | `error_type` (stdout only) |
  | `run_finished` | info or error | `outcome`, `batches`, `rows_inserted`, `duration_s`, `peak_memory_mb`, `error_type`, `error` (an exception outside a batch, DI8) |

- **Run measures:** `duration_s` is the run's wall-clock time, and `peak_memory_mb` the Python process's `ru_maxrss` from `RUSAGE_SELF`, in decimal MB ([s012 › D1](../spikes/s012-execution-target.md#d1-execution-platform)); `wrangler`'s own peak, from `RUSAGE_CHILDREN` once it exits, goes in `page_deployed`, since the container's limit counts both.
- **Log object:** every event goes to stdout as it happens, which Modal keeps for its own retention, and is kept in memory for the run's object. At the run's end, whatever its outcome, the shell writes that object to `bikesharing-lakehouse` as `logs/pipeline/date=YYYY-MM-DD/<run_id>.jsonl` ([ADR-0035](../decisions/0035-cloud-resource-naming.md)); a lifecycle rule on `logs/pipeline/`, set by the owner, deletes it after 30 days. A failed upload is logged to stdout and does not change the run's outcome or its heartbeat signal. A run killed by its timeout or its memory limit writes no object, and its events stay only in Modal's logs; the heartbeat reports it.
- **Heartbeat:** the run pings the Healthchecks.io check of [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md) with `/start` when it starts, so that the service measures its duration, then once with success (R14) or `/fail` (R15) as its last action, after the log upload. A failure ping carries the `run_finished` event and the failing event as its body. Each ping has a 10 s timeout and up to 3 attempts, 1 s and 2 s apart, following Healthchecks.io's advice to retry pings; a ping that still fails is logged as `heartbeat_failed` and does not change the outcome, since a missing signal alerts the owner anyway. The platform does not retry a run (D7), so the time limit before the failure signal is the 10-minute timeout. The check, with its period of 15 min and grace of 15 min (R17), is created by the owner.
- **Secrets in events:** events are built only from their declared fields. An error's message passes through a redaction step that replaces the value of each secret the function holds with `***` before it is logged or sent in a ping, following log redaction at the sink, so that an exception that quotes a URL or a token leaks nothing (R24). The heartbeat's URL is never a field of an event.
- **Copy to the monitoring tool:** T060.1 writes its events only to stdout and R2; the copy over OTLP of [ADR-0049](../decisions/0049-log-events-copied-to-monitoring-over-otlp.md) is sent from T060.2, which also maps the common fields to OTLP attributes and builds the alerts that read them. **#22**
  - TODO(T060.2): send each run's events over OTLP after the log upload, as ADR-0049 sets, with the monitoring tool's token as a Modal Secret of the scheduled function only.

#### Deploy script

- **Script:** `pipeline/scripts/deploy.sh` deploys the Modal app `bikesharing-pipeline` ([ADR-0035](../decisions/0035-cloud-resource-naming.md)) and is the only way to deploy it, as [d007 › D6](d007-pipeline-design.md#d6-deployments-tagged-with-their-commit) sets. The owner runs it from the local machine until T066 runs it from CI on merge to `main`; it takes no arguments, so both run it the same way.
- **Checks before deploying:** the script fetches `origin/main` and refuses to deploy, with a message naming the cause, if `git status --porcelain` lists any change, untracked files included, or `HEAD` is not `origin/main` (R10). It does not run the checks again: the commit is on `main`, so its PR's checks passed (GitHub Flow).
  - `git status` does not list ignored files, and the image copies folders from the disk, so an ignored file in them would reach the image without being in the commit.
  - TODO(T066): deploy from a clean checkout of the commit, which CI gives, so that the image holds only what the SHA names.
- **Code version:** the script reads the full SHA with `git rev-parse HEAD` and passes it to `modal_app.py` in an environment variable, which the image stores as an environment variable of the container; the scheduled function reads it as the code version and refuses to start without it (#20). Every row and event of the deployment then carries that SHA (R9).
- **Tag:** the script runs `modal deploy --tag <SHA> modal_app.py` through the `platform` dependency group. A probe on a temporary app, `bikesharing-t0601-tag-probe`, showed that the tag is the `tag` field of `modal app history --json`; that Modal accepts tags of up to 50 characters, of alphanumerics, dashes, periods and underscores, so the 40-character SHA fits; and that Modal records the Git commit itself in the `commit` field, as a short SHA, so the full SHA is held only by the tag. A second probe, on a temporary Worker with static assets of the same name, showed that `wrangler deploy --tag` accepts the 40-character SHA and shows it as the `Tag` of the version in `wrangler versions list`, for the page's deployment (#18). Both tools hold the full SHA, as D5 sets, so no deployment is tagged with a short one. Both temporary resources are deleted when the task closes.
- **Post-deploy smoke test:** once deployed, the script invokes the deployed scheduled function once and waits for it, following a smoke test of the deployed release in production. It runs `pipeline/scripts/smoke_test.py` with `uv run --group platform`, which looks the function up with `modal.Function.from_name("bikesharing-pipeline", "scheduled_run")`, starts it with `spawn()`, prints the call's ID and waits on it with `get()`. It passes when the run ends without failing, which a normal run reaches in well under its 10-minute timeout, and fails the script otherwise, since the function raises on a failed run; the printed call ID finds the run's events in Modal's logs. The run is a normal production run: it is idempotent (#4), waits for a scheduled run in progress (`max_containers=1`) and sends its heartbeat signal like any other.
- **Going back:** a faulty deployment is undone by a PR that reverts its commit, merged and deployed like any other, following GitHub Flow's roll forward; the script never deploys an older commit, so a row's SHA always names what `main` held when it ran.

#### Tests and CI

The pipeline follows [testing-strategy.md](../testing-strategy.md), whose Python section moves to `pipeline/` and which gains a section for SQL in dbt ([s017 › P6](../spikes/s017-dbt-in-the-pipeline.md#55-production-inputs)). The levels are:

- **Unit, core:** `pipeline/tests/unit/`, pytest, no I/O. They cover the core's decisions as values: which prefix a run lists and from which key (#7), the pending objects after the exclusion list (#8), the batches and the time budget (R12, R13), the end instant and `stage_drained` (R18, R19), the verdict over dbt's node statuses (#16), DQR2's check on a MERGE's metrics (R30), the events and their redaction (R24), and the file's validation against its schema (DQR14).
- **Unit, dbt:** dbt unit tests in `pipeline/dbt/`, on hand-written rows that replace the sources, for each model's logic: the casts, conversions and renames of each staging model, with TR8's nulls in AMBici's and TR9's null in Bicing's, the union of both in `station_stock`, the calendar keys and lineage of `station_stock`, the median, `drop` and `not_evaluated` of `capture_volume`, the fields added and dropped of `schema_drift`, and D2's fields of `latest_station_count`. dbt builds the upstream relations first with `dbt run --empty` ([s017 › P6](../spikes/s017-dbt-in-the-pipeline.md#55-production-inputs)).
- **Integration, shell:** `pipeline/tests/integration/`, on bronze fixtures in a local folder and Delta tables on a local path, with no network. They cover the read schema over the fixtures (#11), the shell's run of two batches in one process with a failing model and a contract violation, checking the tables and the log ([s017 › P7](../spikes/s017-dbt-in-the-pipeline.md#55-production-inputs)), a batch processed twice that adds no row (#4), a run that stops between its two commits, a batch with an unreadable bronze object (R22), DuckDB refusing a file outside its folder and an extension load (R28, R29), the published file built from the tables, a failed page deployment with a stand-in for `wrangler` that exits with an error (R31), the deploy script's refusals in a temporary Git repository with a stand-in for `uv` first on the `PATH`, which records its calls (R10), and the heartbeat's pings for each outcome, with their retries, against a local stub of the check (R14, R15).
- **Contract:** consumer of `contracts/bronze-keys.json`, the keys the discovery parses; producer of `contracts/latest-station-count.schema.json`, tested with its vectors, `contracts/latest-station-count.json` ([Publishing](#publishing)). The content of a bronze object has no contract file: the read schema (#11), DQR11 and the failure of an unreadable object (R22) check it in every run, and capture's own tests check that it stores the response body unchanged ([d004](d004-bronze-data-capture.md)).
- **End to end:** none in CI. The one-off run of D6's reference batch on Modal, on real bronze, is the end-to-end check before the first deployment, and the deploy script's smoke test the one after each deployment ([Deploy script](#deploy-script)).
- **Platform separation:** import-linter's contracts run in `check-pipeline.sh` ([Component structure](#component-structure)), and so do the test of rule 4, which fails if a platform module imports `duckdb`, and the test of R26 and R27, which fails if `modal_one_off.py` names a Secret other than bronze's read-only one or the deployment. Rule 5 holds by the environment: the `platform` group is left out of `[tool.uv] default-groups`, so `uv sync --locked` installs no Modal SDK, locally and in CI, and a test asserts that `modal` cannot be imported and that the package and its configuration load without it. The deploy script adds the group with `uv run --group platform`. mypy checks the platform modules and the deploy script's smoke test with a `[[tool.mypy.overrides]]` that sets `ignore_missing_imports` for the module `modal` only, so the rest of each file is type-checked without the group installed.
- **Fixtures:** `pipeline/tests/fixtures/`, bronze `station_status` objects of both systems kept as captured, gzip-compressed, trimmed to a few stations each and chosen for variety: a Bicing station out of service, a station without GBFS's optional fields, a capture with a station added or removed, and an object with a field outside the read schema ([ADR-0037](../decisions/0037-test-fixtures-per-component.md)).
- **dbt documentation:** not generated in CI, since nothing publishes it; `check-pipeline.sh` runs `dbt parse`, which fails on the same errors in the project's YAML, and the owner generates the documentation locally when needed.
- **Check script:** `pipeline/scripts/check-pipeline.sh` runs ruff, mypy, import-linter, SQLFluff (#27), `dbt parse`, `dbt run --empty` with dbt's unit tests, and pytest, in that order, so that the fastest checks fail first. The dbt commands take their variables from `pipeline/scripts/dbt_check_vars.py`, run with `uv run`: it writes empty Parquet files of `capture_history` and `latest_captures` to the script's temporary folder and prints, as JSON, the variables of [`bikesharing.shell.dbt_runner`](#bikesharingshelldbt_runner) for the bronze fixtures, with `read_columns` and `station_fields` taken from `bikesharing.core.read_schema`, so that the read schema lives in one place; `check-pipeline.sh` passes them with `--vars`.
- **CI job:** `pipeline` in `.github/workflows/ci.yml`, following [ci.md](../../.claude/rules/code/ci.md): `working-directory: pipeline`, `astral-sh/setup-uv` with its cache, `uv sync --locked`, and `bash scripts/check-pipeline.sh`. Its path filter holds `pipeline/**`, `.github/workflows/ci.yml` and the three contract files it reads. `ci-passed` needs the new job.

#### Cost recalibration

- **Window:** the first 14 days of scheduled runs after D8's last stage, so that the first load's backlog does not inflate the figures and two weekly cycles are covered.
- **Measures:** per bucket, `bikesharing-bronze` and `bikesharing-lakehouse`, the Class A and Class B operations and the storage over the window, from R2's GraphQL Analytics API, with the query of [s010 › Step 5](../spikes/s010-storage-table-format.md#step-5--run-probe-a-and-verify-the-analysis). Operation metrics are sampled, so only totals per class and bucket are compared ([s010 › F14](../spikes/s010-storage-table-format.md#4-findings)).
- **Operation classes:** the same query, grouped by `actionType`, confirms the class of conditional PutObject, ListObjectsV2 and DeleteObjects, which R2's pricing page does not name; a sampled count is enough to tell the class of an operation type.
- **Comparison:** the measured totals, scaled to a month, are compared with the prediction of s010's cost model for 24/7 at 15 min; `params.toml` is adjusted where they differ and the model is run again, in `spikes/storage-table-format/`, the code it was built with ([s010 › P4](../spikes/s010-storage-table-format.md#production-inputs)). The prediction, the measure and the new monthly cost go in Close.
- **Alerts:** the owner sets Cloudflare's alerts on the total monthly R2 bill (€2, the review trigger of [s010 › D5](../spikes/s010-storage-table-format.md#d5-bronze-is-kept-indefinitely-reviewed-only-above-a-cost-threshold)), Class A operations and storage from the recalibrated model's figures.

### 2.2 Decision summary

<!-- It logs decisions about the plan, including changes. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Applies to: anchor link(s) to the section where the decision is applied, named in one or two words.
- Decided at: the Status phase where it was decided (Plan, Steps), or `<phase> review` when decided while reviewing that phase.
- R: Requirement affected.
-->

| # | Applies to | Decision | Reason | R | Decided at |
|---|---|---|---|---|---|
| 1 | [Component structure](#component-structure) | The pipeline lives in its own component folder, `pipeline/`, following one folder per component in a monorepo | Its runtime and lockfile stay in its own files (ADR-0016, ADR-0017), as with `capture/` | — | Plan |
| 2 | [Component structure](#component-structure) | The platform module is `pipeline/modal_app.py`, outside the `src/` layout's package, following ADR-0046 and PyPA's `src/` layout | The package never ships the platform module, so rule 5 holds by construction | — | Plan |
| 3 | [Runtime and dependencies](#runtime-and-dependencies) | Modal's image starts from the official Python image at the exact patch of `.python-version`, following Twelve-Factor's dev/prod parity and ADR-0016 | Production runs the patch that passed CI | — | Plan |
| 4 | [Delta writes](#delta-writes) | A Delta control table records each processed bronze object, written after the batch's fact rows, following an idempotent sink with a progress log | It records objects with no rows and is what T060.5's set-aside extends | R20–R22 | Plan |
| 5 | [Delta writes](#delta-writes) | The station stock is partitioned by local calendar date, following date partitioning of time-series facts on the column they are filtered by | Each run reads one day, and the table is read by local day | — | Plan |
| 6 | [Delta writes](#delta-writes) | Compaction, VACUUM and retention are left to a scheduled maintenance job of their own, T072, following table maintenance apart from ingestion | Nothing reads past days before T041, and its frequency is set from production files | — | Plan |
| 7 | [Bronze reading](#bronze-reading) | A run lists bronze from 1 h before its most recent processed object, and the whole prefix once a day, following incremental directory listing with a periodic backfill | The cost of listing stays flat as bronze grows, and no late object is left behind | R18 | Plan |
| 8 | [Bronze reading](#bronze-reading) | Until T060.5, an unreadable bronze object is excluded only by a versioned list in the repository, following a deny list in a fail-fast pipeline | Each exclusion is reviewed and traced by the deployed SHA, with no manual write to production | R22 | Plan |
| 9 | [Bronze reading](#bronze-reading) | The shell downloads each batch to a temporary local folder, the only path DuckDB may read, following least privilege with DuckDB's file sandbox (`enable_external_access`, `allowed_directories`) | DuckDB reaches no network, loads no extension and holds no R2 credential | R28, R29 | Plan |
| 10 | [Bronze reading](#bronze-reading) | DuckDB's `memory_limit` is 60% of the container's hard limit, revised only when `peak_memory_mb` or a memory error calls for it, following engine memory set below the container's limit with headroom **→ #30** | A batch too large fails with an error the log records, not a container kill | — | Plan |
| 11 | [Bronze reading](#bronze-reading) | Bronze is read with a declared schema per system and feed, a constant of the core taken from its source card and checked against the fixtures, following schema on read with an explicit schema rather than an inferred one | It avoids duckdb#27806, a change in the source fails a batch instead of changing the schema unnoticed, and DQR11 compares each object with what its own system publishes | R21 | Plan |
| 12 | [Transformation in dbt](#transformation-in-dbt) | A batch enters dbt as one external source per system over its local files, each with its own staging model, unioned in silver, following `dbt-duckdb`'s external sources, dbt Labs' staging model per source, and ADR-0047 | dbt's lineage starts at bronze, each system's GBFS version is read and cast in its own model, unit tests replace the sources with rows, and the shell keeps only I/O | — | Plan |
| 13 | [Transformation in dbt](#transformation-in-dbt) | DQR2 holds by the insert-only MERGE and is checked after each MERGE on the metrics it returns, following a guarantee by construction checked at runtime | The run checks it as D3 requires, and a code change that updates or deletes rows fails at its first run | R20, R30 | Plan |
| 14 | [Transformation in dbt](#transformation-in-dbt) | DQR12's history is each capture's station count, kept in `processed_objects` and read by dbt as a second external source, following per-load metrics in the control table, as data observability's volume monitors keep them | Each run reads about 2,900 counts instead of a day of fact rows, and a capture with no rows counts as a drop | R8 | Plan |
| 15 | [Transformation in dbt](#transformation-in-dbt) | DQR11 compares the keys of each bronze object, read with no schema, with the read schema, following the schema monitors of data observability | It detects added and dropped fields, which the typed read ignores, at a cost of milliseconds | R8 | Plan |
| 16 | [Transformation in dbt](#transformation-in-dbt) | Each rule's severity is the data test's own dbt configuration, and the core commits a batch only if no node fails or errors, following dbt's native test severity, as ADR-0047 sets | One source of severity per rule, and the core keeps a single rule over the statuses | R8, R20, R21 | Plan |
| 17 | [Transformation in dbt](#transformation-in-dbt) | The audited table passes to `deltalake` whole as Arrow, following the DuckDB to Arrow to `deltalake` hand-off | The simplest hand-off fits the headroom of #10 with bounded batches; streaming waits for a measured need | — | Plan |
| 18 | [Publishing](#publishing) | The run deploys the page with `wrangler`, installed in Modal's image at build time, following deployment with the provider's official tool **→ #26** | No deployment code of the project's own, and the same tool as capture; the second runtime costs only a pinned version | R6 | Plan |
| 19 | [Publishing](#publishing) | A failed deployment keeps the committed batches and fails the run, following a heartbeat that reports the whole job's outcome | Until T060.2's alert on the file's age, the heartbeat is the only signal of a page that stops refreshing | R15, R31 | Plan |
| 20 | [Environments and configuration](#environments-and-configuration) | One-off runs use a function of their own with only bronze's read-only token, writing to local disk, and the scheduled function requires the deployed code version, following least privilege per function | R26 and R27 hold by construction, within ADR-0035's single environment | R26, R27 | Plan |
| 21 | [Environments and configuration](#environments-and-configuration) | D8's end instant is a constant in the repository, changed by a PR and a deployment per stage, following configuration as code | Each change is reviewed and traced by the SHA, as #8's deny list; about four changes in all | R18, R19 | Plan |
| 22 | [Observability](#observability) | The copy of the events over OTLP (ADR-0049) is left to T060.2, following a walking skeleton that builds only the thinnest path | Nothing reads the copy before T060.2's alerts, and its field mapping is decided once, where ADR-0049 places it | — | Plan |
| 23 | [Tests and CI](#tests-and-ci) | The content of a bronze object has no shared contract file, following contract tests only where no runtime check covers the interface | The read schema, DQR11 and R22 check it in every run, and capture's own tests check the stored body | — | Plan |
| 24 | [Transformation in dbt](#transformation-in-dbt) | dbt's models are grouped in one folder per layer, `silver/` and `gold/`, and the published file is a dbt exposure of the gold model `latest_station_count`, following ADR-0018 and dbt's exposures for downstream consumers | The medallion shows in the project, the file reads only gold, and no model copies another | — | Plan |
| 25 | [Runtime and dependencies](#runtime-and-dependencies) | The shell reaches R2 with `obstore`, following a minimal dependency footprint where secrets are held and tests against a real local implementation | One wheel with no Python dependencies in the container, and integration tests run the production code on `LocalStore` | — | Plan |
| 26 | [Publishing](#publishing) | The page's component, `web/`, is created now with only the Worker's `wrangler.jsonc` and the pins of Node and `wrangler`, which Modal's image copies, following one folder per component in a monorepo; **refines #18** | The Worker deploys the page with its data, so its configuration and tool belong to the page, and T041 only adds | R6 | Plan |
| 27 | [Transformation in dbt](#transformation-in-dbt) | The SQL files follow dbt Labs' style guide, stated in `.claude/rules/code/sql.md` and checked by SQLFluff with its default rules, following the style guide and the linter it recommends | A tool checks the SQL's style, as s016 › D2 does for Python | — | Plan |
| 28 | [Components](#25-components), [Publishing](#publishing) | The dbt model contracts of the models the shell reads, the schemas of the Delta tables and the published file's JSON Schema are exact in this design, following spec-driven development, dbt's model contracts and consumer-driven contracts | They are the interfaces between dbt, the shell, the persisted tables and the page, fixed before any production data exists or any consumer is built | R7, R21 | Plan |
| 29 | [Publishing](#publishing), [Tests and CI](#tests-and-ci) | The published file's contract carries shared vectors in `contracts/` beside its JSON Schema, a valid file and one invalid file per kind of violation, following ADR-0050, which supersedes ADR-0015's ODCS schema | The pipeline and the page test against the same cases, and an invalid case that passes shows a gap in the schema | R7 | Plan |
| 30 | [Bronze reading](#bronze-reading) | DuckDB's `threads` stay at its default, 17 in the container, and the `peak_memory_mb` of the reference batch (Step 28) checks it, following defaults until a measure calls for a change; **refines #10** | At 17 threads `memory_limit` leaves about 145 MiB per thread, against the 18 MiB per thread that spilled in Step 16, and fixing `threads` adds a value and reopens a closed step | — | Steps |

### 2.3 Architecture

<!-- Optional. One diagram and 2–3 sentences. -->

### 2.4 File layout

<!-- Every file and folder the task creates or modifies, documents included, as a tree: (new) or (modified), and its purpose or change in one line. A task that adds a component also lists its CI job in `.github/workflows/ci.yml` (recipe in `.claude/rules/code/ci.md`), and its version files, manifest and lockfile (`.claude/rules/code/dependencies.md`). -->

```text
.
├── CLAUDE.md                                (modified)  Project structure: `pipeline/` replaces `src/bikesharing/` and `tests/`; adds `web/`; `scripts/` keeps only the shared helpers
├── .gitignore                               (modified)  Ignores dbt's `target/` and `logs/` under `pipeline/dbt/`, and `web/public/`
├── .claude/
│   ├── settings.json                        (modified)  Registers the Python and SQL lint hooks; allows `uv run --directory pipeline pytest` and its variants with arguments, the test command of `python.md`
│   ├── hooks/
│   │   ├── python-lint.sh                   (new)       `ruff format` and `ruff check --fix` on the edited file through `uv run --project pipeline`; reports what remains on stderr with exit 2 (s016 › P3)
│   │   └── sql-lint.sh                      (new)       `sqlfluff fix` and `sqlfluff lint` on the edited `.sql` file under `pipeline/dbt/`; reports what remains on stderr with exit 2 (#27)
│   └── rules/code/
│       ├── general.md                       (modified)  `paths`: `pipeline/**` instead of `src/**` and `tests/**`; names `sql.md` among the language rules
│       ├── testing.md                       (modified)  `paths`: `pipeline/**` instead of `src/**` and `tests/**`; names `sql.md` among the language rules
│       ├── python.md                        (modified)  `paths` under `pipeline/`; test levels under `pipeline/tests/`; `modal_app.py` as the only importer of `modal`
│       └── sql.md                           (new)       SQL conventions on `pipeline/dbt/**` (#27)
├── .github/workflows/
│   └── ci.yml                               (modified)  Job `pipeline` ([Tests and CI](#tests-and-ci)); `ci-passed` needs it
├── contracts/
│   ├── latest-station-count.schema.json     (new)       JSON Schema (draft 2020-12) of the published file, D2's fields, `additionalProperties: false` (DQR14)
│   └── latest-station-count.json            (new)       Shared vectors of the schema: one `valid` file and one `invalid` file per kind of violation, each with its `reason` (#29)
├── docs/
│   ├── decisions/
│   │   ├── 0050-contract-tests-by-contract-kind-with-native-schemas.md (new) Data-shape contracts as the boundary's native schema with shared vectors; supersedes ADR-0015
│   │   └── archive/0015-contract-tests-by-contract-kind.md (moved) Superseded by ADR-0050; links to it updated
│   └── testing-strategy.md                  (modified)  Python section moves to `pipeline/` with `check-pipeline.sh`; new section for SQL in dbt; the pipeline's CI job
├── pipeline/
│   ├── .python-version                      (new)       Exact patch of Python 3.14 (#3)
│   ├── pyproject.toml                       (new)       Runtime dependencies, groups `dev` and `platform`, `default-groups`, mashumaro constraint; ruff, mypy, import-linter and SQLFluff configuration, with the comment on s016 › D2's defaults policy
│   ├── uv.lock                              (new)       Lockfile of every group
│   ├── modal_image.py                       (new)       The image with `web/` copied in, the container size and the Secrets' references, shared by both apps; an importer of `modal` (#2, #26, DI12)
│   ├── modal_app.py                         (new)       The app of the scheduled function, with its schedule and its four Secrets; an importer of `modal` (#2, #20, DI12)
│   ├── modal_one_off.py                     (new)       The app of the one-off function, with bronze's read-only Secret only; an importer of `modal` (#20, DI12)
│   ├── config/
│   │   └── excluded_objects.txt             (new)       Excluded bronze keys with their reason, with its `TODO(T060.5):` marker (#8)
│   ├── src/bikesharing/
│   │   ├── __init__.py                      (new)       Package root
│   │   ├── core/                                        Pure decisions, no I/O (ADR-0046)
│   │   │   ├── __init__.py                  (new)
│   │   │   ├── settings.py                  (new)       Constants: account ID, bucket names, end instant (#21), batch bound, time budget, DuckDB's memory fraction
│   │   │   ├── discovery.py                 (new)       Listing start key and full sweep (#7); pending objects after the exclusion list (#8)
│   │   │   ├── batching.py                  (new)       Batches, time budget, end instant and `stage_drained` (R12, R13, R18, R19)
│   │   │   ├── read_schema.py               (new)       Read schema of `station_status` (#11)
│   │   │   ├── verdict.py                   (new)       Verdict over dbt's node statuses (#16); DQR2's check on a MERGE's metrics (#13)
│   │   │   ├── events.py                    (new)       Event values of [Observability](#observability), the redaction of secrets (R24) and the log object's key
│   │   │   └── published_file.py            (new)       The published document from `latest_station_count`'s rows, and its validation against its schema (DQR14)
│   │   └── shell/                                       I/O and orchestration (ADR-0046)
│   │       ├── __init__.py                  (new)
│   │       ├── run.py                       (new)       A run end to end: tables, discovery, batches, publishing, log upload, heartbeat
│   │       ├── r2.py                        (new)       Listing, batch download and log upload over R2's S3 API with `obstore` (#7, #9, #25)
│   │       ├── duckdb_session.py            (new)       DuckDB connection with the sandbox and memory settings, and the reads of the scratch database (#9, #10, #17)
│   │       ├── dbt_runner.py                (new)       `dbt build` with the batch's variables, the event callback and node statuses (#12, #16)
│   │       ├── delta.py                     (new)       Table creation, insert-only MERGE, `processed_objects`, retry on conflict, the Parquet inputs of dbt (#4, #14, #17)
│   │       ├── publishing.py                (new)       File writing and `wrangler deploy` as a subprocess (#18, #19)
│   │       ├── heartbeat.py                 (new)       Healthchecks.io pings with their retries
│   │       └── event_log.py                 (new)       Events to stdout and to the run's log object
│   ├── dbt/
│   │   ├── dbt_project.yml                  (new)       dbt project
│   │   ├── profiles.yml                     (new)       The run's scratch database
│   │   ├── models/
│   │   │   ├── sources.yml                  (new)       `ambici` and `bicing`, each with `station_status` and `station_status_raw`; `lakehouse.capture_history`, `lakehouse.latest_captures`
│   │   │   ├── exposures.yml                (new)       The published file as an exposure of `latest_station_count` (#24)
│   │   │   ├── silver/
│   │   │   │   ├── stg_ambici__station_status.sql (new) AMBici's casts, conversions, renames and TR8's nulls
│   │   │   │   ├── stg_bicing__station_status.sql (new) Bicing's casts, conversions and TR9's null
│   │   │   │   ├── station_stock.sql        (new)       Station stock at D1's grain, with calendar keys and lineage
│   │   │   │   ├── capture_volume.sql       (new)       Captures against their 24 h median (DQR12)
│   │   │   │   ├── schema_drift.sql         (new)       Fields added and dropped per object (DQR11)
│   │   │   │   └── silver.yml               (new)       Contracts; DQR1, DQR11, DQR12 and DQR13 data tests; unit tests
│   │   │   └── gold/
│   │   │       ├── latest_station_count.sql (new)       D2's fields in the shape of the published file
│   │   │       └── gold.yml                 (new)       Contract and unit tests
│   │   └── tests/generic/                   (new)       Project generic tests the rules need, each applied with its DQR `name`
│   ├── scripts/
│   │   ├── check-pipeline.sh                (new)       ruff, mypy, import-linter, SQLFluff, `dbt parse`, `dbt run --empty` with unit tests, pytest
│   │   ├── dbt_check_vars.py                (new)       dbt's variables for the checks, over the fixtures and empty Parquet inputs ([Tests and CI](#tests-and-ci) › Check script)
│   │   ├── deploy.sh                        (new)       The only deployment path ([Deploy script](#deploy-script))
│   │   ├── smoke_test.py                    (new)       Invokes the deployed scheduled function once and waits for it ([Deploy script](#deploy-script))
│   │   └── trim_fixtures.py                 (new)       Writes the bronze fixtures from a local sample: trimmed captures and derived edge cases (ADR-0037)
│   └── tests/
│       ├── conftest.py                      (new)       Shared fixtures: local bronze folder, local Delta path
│       ├── unit/core/                       (new)       One test module per core module, mirroring `src/`; consumer of `contracts/bronze-keys.json`
│       ├── integration/                     (new)       Read schema, two-batch run, re-run, stop between commits, unreadable object, DuckDB's sandbox, published file and its contract, failed page deployment, heartbeat pings, the deploy script's refusals (R10); rule 5 without Modal's SDK
│       └── fixtures/
│           └── bronze/                      (new)       Gzip `station_status` objects of both systems, chosen for variety, and `manifest.json` with each one's provenance (ADR-0037)
└── web/                                     (new)       The page's component; T041 adds the page, its tests and its CI job (#26)
    ├── .nvmrc                               (new)       Node version installed in Modal's image for `wrangler`
    ├── package.json                         (new)       `wrangler`, pinned exactly
    ├── package-lock.json                    (new)       Lockfile of `wrangler`
    └── wrangler.jsonc                       (new)       The page's Worker: name, compatibility date, assets directory `public/`, written by the run and ignored by Git
```

### 2.5 Components

<!-- Optional. One subsection per component. The contract is exact, in the component's own language, never pseudocode. -->

Each contract of a Python module is its public interface in stub form (PEP 484): what other modules import and its tests exercise. Names starting with `_` are private to their module and free to the implementation. Every `datetime` is timezone-aware in UTC, and every value object is a frozen dataclass with slots. The dbt models' contracts are dbt model contracts, in dbt's YAML.

#### `bikesharing.core.settings`

- **Responsibility:** the run's constants, reviewed and traced by the code version (#21, [Environments and configuration](#environments-and-configuration)).
- **Location:** `pipeline/src/bikesharing/core/settings.py`
- **Contract:** `CLOUDFLARE_ACCOUNT_ID` takes the owner's account ID, which is not a secret, in the step that writes the module.

```python
from datetime import datetime, timedelta
from typing import Final, Literal
from zoneinfo import ZoneInfo

type System = Literal["ambici", "bicing"]

COMPONENT: Final = "pipeline"
UNRELEASED_VERSION: Final = "unreleased"
SYSTEMS: Final[tuple[System, ...]] = ("ambici", "bicing")
FEED: Final = "station_status"
LOCAL_TIMEZONE: Final = ZoneInfo("Europe/Madrid")

CLOUDFLARE_ACCOUNT_ID: Final[str]
BRONZE_BUCKET: Final = "bikesharing-bronze"
LAKEHOUSE_BUCKET: Final = "bikesharing-lakehouse"
STATION_STOCK_PATH: Final = "silver/station_stock"
PROCESSED_OBJECTS_PATH: Final = "control/processed_objects"
LOG_PREFIX: Final = "logs/pipeline"

END_INSTANT: Final[datetime | None]
MAX_OBJECTS_PER_BATCH: Final = 360
TIME_BUDGET: Final = timedelta(minutes=7)
LISTING_LOOKBACK: Final = timedelta(hours=1)
DUCKDB_MEMORY_FRACTION: Final = 0.6
```

#### `bikesharing.core.discovery`

- **Responsibility:** parses bronze keys, plans each system's listing and selects the pending objects (#7, #8).
- **Location:** `pipeline/src/bikesharing/core/discovery.py`
- **Contract:** `parse_bronze_key` and `bronze_key` follow `contracts/bronze-keys.json`; a listed key that does not parse raises `InvalidBronzeKey` and fails the run. A run sweeps the whole prefix when no object is processed, or when the local date of `now` is later than that of the latest processed capture; otherwise it lists after the key of the latest processed capture minus `lookback`. Each line of the exclusion list is `<key> # <reason>`; blank lines and lines starting with `#` are ignored, and a line with no reason raises `ValueError`.

```python
from collections.abc import Iterable, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from bikesharing.core.settings import System

class InvalidBronzeKey(ValueError): ...

@dataclass(frozen=True, slots=True)
class BronzeObject:
    key: str
    system: System
    feed: str
    captured_at: datetime

@dataclass(frozen=True, slots=True)
class ListingPlan:
    system: System
    prefix: str              # "raw/<system>/station_status/"
    start_after: str | None  # None lists the whole prefix
    full_sweep: bool

def parse_bronze_key(key: str) -> BronzeObject: ...
def bronze_key(system: System, feed: str, captured_at: datetime) -> str: ...
def plan_listing(
    system: System,
    latest_processed: datetime | None,
    *,
    now: datetime,
    lookback: timedelta,
    timezone: ZoneInfo,
) -> ListingPlan: ...
def parse_exclusion_list(text: str) -> frozenset[str]: ...
def pending_objects(
    listed: Iterable[str], processed: Set[str], excluded: Set[str]
) -> list[BronzeObject]: ...  # oldest first, then by key
```

#### `bikesharing.core.batching`

- **Responsibility:** applies the end instant, splits the pending objects into batches and decides whether another batch may start (R12, R13, R18, R19).
- **Location:** `pipeline/src/bikesharing/core/batching.py`
- **Contract:** batches keep the input's order, oldest first across both systems, and are numbered from 1 within the run. A batch may start while less than `budget` has passed since the run started. The stage is drained when an end instant is set and no pending object is captured up to it.

```python
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from bikesharing.core.discovery import BronzeObject

@dataclass(frozen=True, slots=True)
class Batch:
    number: int
    objects: tuple[BronzeObject, ...]

    @property
    def first_capture(self) -> datetime: ...
    @property
    def last_capture(self) -> datetime: ...

def within_end_instant(
    objects: Sequence[BronzeObject], end_instant: datetime | None
) -> list[BronzeObject]: ...
def plan_batches(objects: Sequence[BronzeObject], max_objects: int) -> list[Batch]: ...
def may_start_batch(*, run_started: datetime, now: datetime, budget: timedelta) -> bool: ...
def stage_drained(
    objects: Sequence[BronzeObject], end_instant: datetime | None
) -> bool: ...
```

#### `bikesharing.core.read_schema`

- **Responsibility:** the read schema of each system's `station_status`, passed to dbt as variables (#11, #12, #15).
- **Location:** `pipeline/src/bikesharing/core/read_schema.py`
- **Contract:** `STATION_STATUS_COLUMNS` maps, per system, each top-level field of a `station_status` object to its DuckDB type, as `read_json`'s `columns` takes it, with the stations as a list of structs. Each declares every field its source card's field dictionary lists, with the JSON type as published: a string as `VARCHAR`, a POSIX time as `BIGINT`, a count as `INTEGER`; the staging models cast and convert ([ambici › `station_status`](../sources/ambici.md#station_status), [bicing › `station_status`](../sources/bicing.md#station_status)). `STATION_FIELDS` holds, per system, the station struct's field names, the declared fields DQR11 compares against.

```python
from collections.abc import Mapping
from typing import Final

from bikesharing.core.settings import System

STATION_STATUS_COLUMNS: Final[Mapping[System, Mapping[str, str]]] = {
    "ambici": {
        "last_updated": "BIGINT",
        "ttl": "INTEGER",
        "version": "VARCHAR",
        "data": (
            "STRUCT(stations STRUCT("
            "station_id VARCHAR, "
            "num_bikes_available INTEGER, "
            "vehicle_types_available STRUCT(vehicle_type_id VARCHAR, count INTEGER)[], "
            "num_docks_available INTEGER, "
            "is_installed BOOLEAN, "
            "is_renting BOOLEAN, "
            "is_returning BOOLEAN, "
            "last_reported BIGINT"
            ")[])"
        ),
    },
    "bicing": {
        "last_updated": "VARCHAR",
        "ttl": "INTEGER",
        "version": "VARCHAR",
        "data": (
            "STRUCT(stations STRUCT("
            "station_id VARCHAR, "
            "num_vehicles_available INTEGER, "
            "vehicle_types_available STRUCT(vehicle_type_id VARCHAR, count INTEGER)[], "
            "num_vehicles_disabled INTEGER, "
            "num_docks_available INTEGER, "
            "num_docks_disabled INTEGER, "
            "vehicle_docks_available STRUCT(vehicle_type_ids VARCHAR[], count INTEGER)[], "
            "is_installed BOOLEAN, "
            "is_renting BOOLEAN, "
            "is_returning BOOLEAN, "
            "last_reported VARCHAR"
            ")[])"
        ),
    },
}
STATION_FIELDS: Final[Mapping[System, frozenset[str]]]
```

#### `bikesharing.core.verdict`

- **Responsibility:** decides whether a batch commits from dbt's node statuses, and checks DQR2 on a MERGE's metrics (#13, #16).
- **Location:** `pipeline/src/bikesharing/core/verdict.py`
- **Contract:** a batch commits only if no node ends in `fail` or `error`; nodes in `warn` are returned to be logged. A node is a runtime rule when it is a data test whose name is a DQR ID (`DQR` followed by digits). The MERGE is insert-only when it reports no row updated or deleted.

```python
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

type NodeStatus = Literal["success", "pass", "warn", "fail", "error", "skipped"]
type Severity = Literal["error", "warn"]

@dataclass(frozen=True, slots=True)
class NodeResult:
    unique_id: str
    name: str
    resource_type: Literal["model", "test", "unit_test"]
    status: NodeStatus
    severity: Severity | None  # data tests only
    failures: int | None
    rows: int | None
    duration_s: float

@dataclass(frozen=True, slots=True)
class Verdict:
    commit: bool
    blocking: tuple[NodeResult, ...]
    warnings: tuple[NodeResult, ...]

@dataclass(frozen=True, slots=True)
class MergeMetrics:
    rows_inserted: int
    rows_updated: int
    rows_deleted: int

def judge_batch(results: Sequence[NodeResult]) -> Verdict: ...
def rule_id(result: NodeResult) -> str | None: ...
def is_insert_only(metrics: MergeMetrics) -> bool: ...
```

#### `bikesharing.core.events`

- **Responsibility:** builds each event of [Observability](#observability) as a value, serializes it per ADR-0036 and redacts secrets (R24).
- **Location:** `pipeline/src/bikesharing/core/events.py`
- **Contract:** one builder per event, named after it, whose keyword arguments are the event's own fields; `objects_discovered`'s own fields are the system names, each holding `listed`, `pending` and `full_sweep`. `rule_checked` takes its level from its status: `pass` info, `warn` warn, `fail` and `error` error; `run_finished` is info when `succeeded` and error when `failed`, and carries in `error_type` and `error` an exception raised outside a batch, null otherwise (DI8). `to_json_line` writes `ts`, `level`, `component`, `version`, `run_id` and `event` first, then the own fields, `ts` in RFC 3339 with milliseconds and `Z`, and replaces every occurrence of each secret in any string value with `***`. `peak_memory_mb` converts Linux's `ru_maxrss`, in KiB, to decimal MB. `log_object_key` returns `logs/pipeline/date=YYYY-MM-DD/<run_id>.jsonl`, dated by the run's start in UTC.

```python
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from bikesharing.core.batching import Batch
from bikesharing.core.published_file import Violation
from bikesharing.core.settings import System
from bikesharing.core.verdict import NodeResult, Severity

type Level = Literal["info", "warn", "error"]
type FieldValue = (
    str | int | float | bool | datetime | None
    | Sequence[FieldValue] | Mapping[str, FieldValue]
)

@dataclass(frozen=True, slots=True)
class RunContext:
    run_id: str
    version: str

@dataclass(frozen=True, slots=True)
class Event:
    ts: datetime
    level: Level
    event: str
    fields: Mapping[str, FieldValue]

@dataclass(frozen=True, slots=True)
class SystemDiscovery:
    listed: int
    pending: int
    full_sweep: bool

def run_started(ts: datetime, *, end_instant: datetime | None, excluded_objects: int) -> Event: ...
def objects_discovered(ts: datetime, *, systems: Mapping[System, SystemDiscovery]) -> Event: ...
def stage_drained(ts: datetime, *, end_instant: datetime) -> Event: ...
def batch_started(ts: datetime, *, batch: Batch) -> Event: ...
def node_finished(ts: datetime, *, result: NodeResult) -> Event: ...
def rule_checked(
    ts: datetime,
    *,
    rule: str,
    severity: Severity,
    status: Literal["pass", "warn", "fail", "error"],
    failures: int,
) -> Event: ...
def volume_not_evaluated(
    ts: datetime, *, system: System, captured_at: datetime, captures_in_window: int
) -> Event: ...
def schema_drift_field(
    ts: datetime, *, system: System, field: str, change: Literal["added", "dropped"]
) -> Event: ...
def batch_committed(ts: datetime, *, batch: int, rows_inserted: int, objects: int) -> Event: ...
def batch_failed(
    ts: datetime,
    *,
    batch: int,
    reason: Literal["nodes_failed", "not_insert_only", "exception"],
    error_type: str | None,
    error: str | None,
) -> Event: ...
def file_built(ts: datetime, *, stations: int, data_instant: datetime) -> Event: ...
def file_invalid(ts: datetime, *, violations: Sequence[Violation]) -> Event: ...
def page_deployed(ts: datetime, *, tag: str, deploy_peak_memory_mb: float) -> Event: ...
def page_deploy_failed(ts: datetime, *, exit_code: int, output: str) -> Event: ...
def heartbeat_failed(
    ts: datetime, *, signal: Literal["start", "success", "fail"], attempts: int, error_type: str
) -> Event: ...
def log_upload_failed(ts: datetime, *, error_type: str) -> Event: ...
def run_finished(
    ts: datetime,
    *,
    outcome: Literal["succeeded", "failed"],
    batches: int,
    rows_inserted: int,
    duration_s: float,
    peak_memory_mb: float,
    error_type: str | None,
    error: str | None,
) -> Event: ...

def to_json_line(event: Event, context: RunContext, secrets: Collection[str]) -> str: ...
def redact(text: str, secrets: Collection[str]) -> str: ...
def peak_memory_mb(ru_maxrss_kib: int) -> float: ...
def log_object_key(run_id: str, started_at: datetime) -> str: ...
```

#### `bikesharing.core.published_file`

- **Responsibility:** validates the built file against its JSON Schema (DQR14).
- **Location:** `pipeline/src/bikesharing/core/published_file.py`
- **Contract:** `build_published_file` takes the rows of `latest_station_count`, sorted by system and `station_id`, as the file's `stations`, and sets the file's `data_instant` to their latest `captured_at`; it writes every instant in RFC 3339 with `Z`, and raises `ValueError` on no rows. `validate_published_file` validates with `jsonschema`'s `Draft202012Validator` against the schema, which the shell reads as data from `contracts/latest-station-count.schema.json`; it returns every violation, an empty list when the file passes, each with its path in the file as a JSON Pointer (RFC 6901).

```python
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Violation:
    path: str
    message: str

def build_published_file(stations: Sequence[Mapping[str, object]]) -> dict[str, object]: ...
def validate_published_file(document: object, schema: Mapping[str, object]) -> list[Violation]: ...
```

#### `bikesharing.shell.run`

- **Responsibility:** builds each function's configuration from its environment and runs the pipeline end to end.
- **Location:** `pipeline/src/bikesharing/shell/run.py`
- **Contract:** `scheduled_config` reads the version from `CODE_VERSION` and raises `ValueError` when it is missing or empty (#20); it reads the secrets of [`modal_app`](#modal_app), and points the lakehouse and the log store at `bikesharing-lakehouse`. `one_off_config` reads only bronze's credentials, takes the version `unreleased`, puts the lakehouse on a local path under a `work_dir` created for each configuration, so that every one-off run starts from empty tables, and leaves `log_store`, `publish` and `heartbeat_url` as `None` (R26, R27). Both take the core's constants from `settings`, each path from `root`, the file's schema, which every run validates against, from `contracts/latest-station-count.schema.json` (DI9), and the container's hard limit as `container_memory_mib`, from `modal_image.py`'s `MEMORY_MIB`. `root` is the repository's root locally and in tests, and `/repo` in the image, which holds the same relative paths: `pipeline/dbt/`, `pipeline/config/excluded_objects.txt`, `web/` and `contracts/latest-station-count.schema.json`. `run` passes DuckDB's limit, `DUCKDB_MEMORY_FRACTION` of `container_memory_mib` rounded down, as `duckdb_memory_limit_mib` to `connect` and `DbtPaths` (#10). `run` never raises; it returns the outcome, in this order:
  1. Generates the run ID with `uuid.uuid7()`, creates the run's work folder under `work_dir` (#9), pings `start` and logs `run_started`.
  2. Creates the missing tables, reads the exclusion list and the processing state, lists each system with its `ListingPlan`, and logs `objects_discovered`.
  3. Applies the end instant and logs `stage_drained` when the stage is drained.
  4. For each batch, while `may_start_batch` holds, in a subfolder of the work folder that is removed whatever the outcome: downloads it, writes the capture history, runs `dbt_build` on `silver` and judges it, logging one `rule_checked` per node whose `rule_id` is not `None`. A batch that does not commit logs `batch_failed`, and the run stops with no further batch and no publishing (D9). A batch that commits is merged and logs DQR2's `rule_checked` from the MERGE's metrics; one whose MERGE is not insert-only logs `batch_failed` and the run stops in the same way (R30). Otherwise it is recorded in `processed_objects` and logs `batch_committed`.
  5. Unless a batch failed, and once some system has a processed capture: writes the latest captures, runs `dbt_build` on `gold`, builds and validates the file, and logs DQR14's `rule_checked`. It logs `file_invalid` and fails the run on a violation, logs `file_built` otherwise, and, when `publish` is set, deploys it and logs `page_deployed` or `page_deploy_failed` (R31).
  6. Removes the work folder, logs `run_finished`, uploads the log object when `log_store` is set, and pings `success` or `fail` as its last action, the failure with the event log's `run_finished` and failing lines as its body.

  Any exception fails the run: inside a batch it logs `batch_failed` with the reason `exception`; elsewhere it goes into `run_finished`'s error. Its message passes through the redaction of `to_json_line`.

```python
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from obstore.store import ObjectStore

from bikesharing.shell.delta import Lakehouse

@dataclass(frozen=True, slots=True)
class PublishTarget:
    web_dir: Path
    account_id: str
    api_token: str

@dataclass(frozen=True, slots=True)
class RunConfig:
    version: str
    bronze: ObjectStore
    lakehouse: Lakehouse
    log_store: ObjectStore | None
    publish: PublishTarget | None
    heartbeat_url: str | None
    secrets: frozenset[str]
    file_schema: Mapping[str, object]
    dbt_project_dir: Path
    exclusion_list: Path
    work_dir: Path
    container_memory_mib: int
    end_instant: datetime | None
    max_objects: int
    time_budget: timedelta
    lookback: timedelta
    clock: Callable[[], datetime]

def scheduled_config(env: Mapping[str, str], *, root: Path, container_memory_mib: int) -> RunConfig: ...
def one_off_config(env: Mapping[str, str], *, root: Path, container_memory_mib: int) -> RunConfig: ...
def run(config: RunConfig) -> Literal["succeeded", "failed"]: ...
```

#### `bikesharing.shell.r2`

- **Responsibility:** lists, downloads and uploads over R2's S3 API with `obstore` (#7, #9, #25).
- **Location:** `pipeline/src/bikesharing/shell/r2.py`
- **Contract:** `r2_store` builds an `S3Store` on `https://<account_id>.r2.cloudflarestorage.com`, region `auto`, with the credentials passed and none read from the environment or a profile. `list_keys` lists `plan.prefix` with `plan.start_after` as `offset`, in no guaranteed order. `download_batch` downloads the batch's objects concurrently to `folder/<key>`, so that a file's path ends with its key, from which the models take its system and capture instant, and returns the paths in the batch's order. Tests pass a `LocalStore`.

```python
from pathlib import Path

from obstore.store import ObjectStore

from bikesharing.core.batching import Batch
from bikesharing.core.discovery import ListingPlan

def r2_store(
    bucket: str, *, account_id: str, access_key_id: str, secret_access_key: str
) -> ObjectStore: ...
def list_keys(store: ObjectStore, plan: ListingPlan) -> list[str]: ...
def download_batch(store: ObjectStore, batch: Batch, folder: Path) -> list[Path]: ...
def upload_log(store: ObjectStore, key: str, body: str) -> None: ...
```

#### `bikesharing.shell.duckdb_session`

- **Responsibility:** opens DuckDB with its sandbox and memory settings, and reads the scratch database after `dbt build` (#9, #10, #17).
- **Location:** `pipeline/src/bikesharing/shell/duckdb_session.py`
- **Contract:** `apply_sandbox` sets, on an open connection, `memory_limit`, `temp_directory`, `allowed_directories`, `autoinstall_known_extensions = false`, `autoload_known_extensions = false`, `enable_external_access = false` and, last, `lock_configuration = true` (R28, R29). `connect` opens the scratch database and calls it; `Plugin`, the dbt-duckdb plugin `profiles.yml` declares, calls it once on dbt's connection, with the values the profile passes as its `config`. **DI6** The readers query the scratch database's relations by name, with parameters, never with feed values in SQL text (R25); `station_stock` returns the relation, exported as an Arrow stream with no copy in DuckDB. `station_counts` reads `capture_volume`, which counts a capture that lists no station as 0, for `processed_objects`' `station_count` (#14).

```python
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from dbt.adapters.duckdb.plugins import BasePlugin
from duckdb import DuckDBPyConnection, DuckDBPyRelation

from bikesharing.core.settings import System

class ArrowStream(Protocol):
    def __arrow_c_stream__(self, requested_schema: object | None = None) -> object: ...

@dataclass(frozen=True, slots=True)
class NotEvaluated:
    system: System
    captured_at: datetime
    captures_in_window: int

@dataclass(frozen=True, slots=True)
class DriftField:
    system: System
    field: str
    change: Literal["added", "dropped"]

def apply_sandbox(
    con: DuckDBPyConnection,
    *,
    memory_limit: str,
    temp_directory: str,
    allowed_directories: Sequence[str],
) -> None: ...

class Plugin(BasePlugin):
    def initialize(self, plugin_config: dict[str, Any]) -> None: ...
    def configure_connection(self, conn: DuckDBPyConnection) -> None: ...

def connect(
    database: Path,
    *,
    allowed_directories: Sequence[Path],
    temp_directory: Path,
    duckdb_memory_limit_mib: int,
) -> DuckDBPyConnection: ...
def station_stock(con: DuckDBPyConnection) -> DuckDBPyRelation: ...
def station_stock_local_dates(con: DuckDBPyConnection) -> frozenset[date]: ...
def station_counts(con: DuckDBPyConnection) -> Mapping[tuple[System, datetime], int]: ...
def volume_not_evaluated(con: DuckDBPyConnection) -> list[NotEvaluated]: ...
def schema_drift_fields(con: DuckDBPyConnection) -> list[DriftField]: ...
def latest_station_count(con: DuckDBPyConnection) -> list[dict[str, object]]: ...
def write_parquet(con: DuckDBPyConnection, stream: ArrowStream, path: Path) -> None: ...
```

#### dbt model contracts

- **Responsibility:** the shape of each model the shell reads, enforced by dbt at build time (#27, #28).
- **Location:** `pipeline/dbt/models/silver/silver.yml` and `pipeline/dbt/models/gold/gold.yml`
- **Contract:** each model below sets `contract: {enforced: true}`, so a model whose columns or types differ from its contract fails, and with it the batch (R21). Types are DuckDB's. `not_null` constraints apply to `station_stock` only, the one table; on the views dbt checks names and types, and the published file's nullability is checked by its JSON Schema (DQR14).
  - Every instant is a `timestamp with time zone` in UTC ([ADR-0041](../decisions/0041-utc-timestamps-local-calendar-keys.md)): the staging models convert AMBici's POSIX seconds and Bicing's RFC 3339 strings, keeping the instant each source publishes (TR7, TR53).
  - `local_date` and `local_minute` are the date and the minute of the day, 0 to 1439, of `captured_at` in `Europe/Madrid`; the minute is a number, since Delta has no time type.
  - The nullable measures are `num_vehicles_available` (TR9), `num_docks_available` (conditionally required in GBFS), and `num_vehicles_disabled` and `num_docks_disabled` (TR8, null for AMBici).
  - In `capture_volume`, `median_station_count` is null for a capture with no capture of its system in its window.

```yaml
# models/silver/silver.yml
models:
  - name: station_stock
    config: {materialized: table, contract: {enforced: true}}
    columns:
      - {name: system, data_type: varchar, constraints: [{type: not_null}]}
      - {name: station_id, data_type: varchar, constraints: [{type: not_null}]}
      - {name: captured_at, data_type: timestamp with time zone, constraints: [{type: not_null}]}
      - {name: local_date, data_type: date, constraints: [{type: not_null}]}
      - {name: local_minute, data_type: smallint, constraints: [{type: not_null}]}
      - {name: num_vehicles_available, data_type: integer}
      - {name: num_docks_available, data_type: integer}
      - {name: num_vehicles_disabled, data_type: integer}
      - {name: num_docks_disabled, data_type: integer}
      - {name: is_installed, data_type: boolean, constraints: [{type: not_null}]}
      - {name: is_renting, data_type: boolean, constraints: [{type: not_null}]}
      - {name: is_returning, data_type: boolean, constraints: [{type: not_null}]}
      - {name: last_reported, data_type: timestamp with time zone, constraints: [{type: not_null}]}
      - {name: last_updated, data_type: timestamp with time zone, constraints: [{type: not_null}]}
      - {name: run_id, data_type: varchar, constraints: [{type: not_null}]}
      - {name: code_version, data_type: varchar, constraints: [{type: not_null}]}

  - name: capture_volume
    config: {materialized: view, contract: {enforced: true}}
    columns:
      - {name: system, data_type: varchar}
      - {name: captured_at, data_type: timestamp with time zone}
      - {name: station_count, data_type: integer}
      - {name: captures_in_window, data_type: integer}
      - {name: median_station_count, data_type: double}
      - {name: status, data_type: varchar}  # ok, drop, not_evaluated

  - name: schema_drift
    config: {materialized: view, contract: {enforced: true}}
    columns:
      - {name: system, data_type: varchar}
      - {name: captured_at, data_type: timestamp with time zone}
      - {name: field, data_type: varchar}
      - {name: change, data_type: varchar}  # added, dropped
```

```yaml
# models/gold/gold.yml
models:
  - name: latest_station_count
    config: {materialized: view, contract: {enforced: true}}
    columns:
      - {name: system, data_type: varchar}
      - {name: station_id, data_type: varchar}
      - {name: num_vehicles_available, data_type: integer}
      - {name: num_docks_available, data_type: integer}
      - {name: is_renting, data_type: boolean}
      - {name: is_returning, data_type: boolean}
      - {name: last_reported, data_type: timestamp with time zone}
      - {name: captured_at, data_type: timestamp with time zone}
```

#### The published file's JSON Schema

- **Responsibility:** the contract of `latest-station-count.json` between the pipeline and the page, checked by DQR14 (#28, #29).
- **Location:** `contracts/latest-station-count.schema.json`
- **Contract:** D2's fields, each required, with `additionalProperties: false` at every level (R7). Instants are RFC 3339 strings in UTC with `Z`, checked with `pattern`, since `format` is only an annotation in draft 2020-12 unless a format checker with its own dependency is added. A measure that the station stock may hold as null (TR9, GBFS's conditionally required docks) is `integer` or `null`.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Latest station count",
  "type": "object",
  "additionalProperties": false,
  "required": ["data_instant", "stations"],
  "properties": {
    "data_instant": {"$ref": "#/$defs/instant"},
    "stations": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "system", "station_id", "num_vehicles_available", "num_docks_available",
          "is_renting", "is_returning", "last_reported", "captured_at"
        ],
        "properties": {
          "system": {"enum": ["ambici", "bicing"]},
          "station_id": {"type": "string", "minLength": 1},
          "num_vehicles_available": {"type": ["integer", "null"], "minimum": 0},
          "num_docks_available": {"type": ["integer", "null"], "minimum": 0},
          "is_renting": {"type": "boolean"},
          "is_returning": {"type": "boolean"},
          "last_reported": {"$ref": "#/$defs/instant"},
          "captured_at": {"$ref": "#/$defs/instant"}
        }
      }
    }
  },
  "$defs": {
    "instant": {
      "type": "string",
      "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?Z$"
    }
  }
}
```

#### `bikesharing.shell.dbt_runner`

- **Responsibility:** runs `dbt build` in process with the batch's variables and returns its node statuses as values (#12, #16).
- **Location:** `pipeline/src/bikesharing/shell/dbt_runner.py`
- **Contract:** runs `dbtRunner` with `build --select <select> --exclude-resource-type unit_test`, without fail-fast, and calls `on_node` for each node as it finishes. `profiles.yml` reads the scratch database, the allowed directory, the spill folder and the memory limit with `env_var()` from `BIKESHARING_SCRATCH_DATABASE`, `BIKESHARING_ALLOWED_DIRECTORY`, `BIKESHARING_TEMP_DIRECTORY` and `BIKESHARING_MEMORY_LIMIT`, set by `dbt_build` from `paths`, and passes them to `duckdb_session`'s `Plugin`, which applies `connect`'s settings (DI6). `scratch_database` and `temp_directory` lie inside `allowed_directory`, the run's work folder, which every batch of the run shares (#9). dbt parses the whole project, so every call passes all the variables, whichever layer it selects: `bronze_files`, `read_columns` and `station_fields`, each a mapping keyed by system (DuckDB reads no empty list of files, so a system with no object in the batch lists one empty file of the work folder, which reads as no rows), and `capture_history_file`, `latest_captures_file`, `run_id` and `code_version`; the paths of the two Parquet files are fixed in the work folder at the run's start, and the file of a layer not yet built is not read. When `dbt_build` ends, whatever its outcome, it releases dbt-duckdb's connection, which would keep the scratch database open with its configuration locked, so that the shell reopens it with `connect`. A dbt invocation that fails outside its nodes, such as a parse error, raises `DbtInvocationError`.

```python
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from bikesharing.core.verdict import NodeResult

class DbtInvocationError(RuntimeError): ...

@dataclass(frozen=True, slots=True)
class DbtPaths:
    project_dir: Path
    scratch_database: Path
    allowed_directory: Path
    temp_directory: Path
    duckdb_memory_limit_mib: int

def dbt_build(
    paths: DbtPaths,
    *,
    select: Literal["silver", "gold"],
    variables: Mapping[str, object],
    on_node: Callable[[NodeResult], None],
) -> list[NodeResult]: ...
```

#### `bikesharing.shell.delta`

- **Responsibility:** creates the Delta tables, reads the processing state and writes each batch's two commits (#4, #5, #14, #17).
- **Location:** `pipeline/src/bikesharing/shell/delta.py`
- **Contract:** `STATION_STOCK_SCHEMA` holds the columns of `station_stock`'s dbt contract ([dbt model contracts](#dbt-model-contracts)) in its order, each nullable unless it has `not_null`, with Delta's type for DuckDB's: `varchar` as `string`, `integer` as `integer`, `smallint` as `short`, `boolean` as `boolean`, `date` as `date`, and `timestamp with time zone` as `timestamp`; the table is partitioned by `local_date`. `PROCESSED_OBJECTS_SCHEMA` holds the columns of #4, none nullable, and the table has no partitions. `r2_lakehouse` sets R2's endpoint and conditional put in the storage options. `merge_station_stock` runs the insert-only MERGE on the natural key, bounded by the batch's capture range and `local_dates`, and retries a commit conflict on a fresh table handle up to `attempts` times in all. `record_processed` runs an insert-only MERGE on `key`, so that a second writer of the same batch adds no row. `capture_history` returns the rows of `processed_objects` captured in `[since, until)`, and `latest_captures` the rows of `station_stock` of each system's latest capture, pruned by its local date.

```python
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final, Literal

from deltalake import Field, Schema

from bikesharing.core.settings import System
from bikesharing.core.verdict import MergeMetrics
from bikesharing.shell.duckdb_session import ArrowStream

@dataclass(frozen=True, slots=True)
class Lakehouse:
    uri: str
    storage_options: Mapping[str, str]

    def table_uri(self, path: str) -> str: ...

@dataclass(frozen=True, slots=True)
class ProcessedObject:
    key: str
    system: System
    feed: str
    captured_at: datetime
    station_count: int
    status: Literal["processed"]
    run_id: str
    code_version: str

STATION_STOCK_SCHEMA: Final[Schema]
PROCESSED_OBJECTS_SCHEMA: Final = Schema([
    Field("key", "string", nullable=False),
    Field("system", "string", nullable=False),
    Field("feed", "string", nullable=False),
    Field("captured_at", "timestamp", nullable=False),
    Field("station_count", "integer", nullable=False),
    Field("status", "string", nullable=False),
    Field("run_id", "string", nullable=False),
    Field("code_version", "string", nullable=False),
])

def r2_lakehouse(*, account_id: str, access_key_id: str, secret_access_key: str) -> Lakehouse: ...
def local_lakehouse(path: Path) -> Lakehouse: ...
def ensure_tables(lakehouse: Lakehouse) -> None: ...
def processed_keys(lakehouse: Lakehouse) -> frozenset[str]: ...
def latest_processed(lakehouse: Lakehouse) -> dict[System, datetime | None]: ...
def capture_history(lakehouse: Lakehouse, *, since: datetime, until: datetime) -> ArrowStream: ...
def merge_station_stock(
    lakehouse: Lakehouse,
    rows: ArrowStream,
    *,
    first_capture: datetime,
    last_capture: datetime,
    local_dates: Collection[date],
    attempts: int = 3,
) -> MergeMetrics: ...
def record_processed(lakehouse: Lakehouse, objects: Sequence[ProcessedObject]) -> None: ...
def latest_captures(lakehouse: Lakehouse, latest: Mapping[System, datetime]) -> ArrowStream: ...
```

`deltalake`'s reads and writes and DuckDB's hand-off work over the Arrow C stream interface without `pyarrow`; `record_processed` builds its MERGE's source from Python values with `arro3-core` (DI7).

#### `bikesharing.shell.publishing`

- **Responsibility:** writes the published file and deploys the page with `wrangler` (#18, #19, #26).
- **Location:** `pipeline/src/bikesharing/shell/publishing.py`
- **Contract:** `write_published_file` writes the document as UTF-8 JSON to `assets_dir/latest-station-count.json`, creating the folder. `deploy_page` runs `web_dir/node_modules/.bin/wrangler deploy --config wrangler.jsonc --tag <tag>` with `web_dir` as its working directory and an environment holding only `PATH`, `HOME`, `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`, and returns its exit code, its combined output and its peak memory from `RUSAGE_CHILDREN`. A failed deployment is returned, never raised: a non-zero exit as it is, a `wrangler` killed at its timeout of 120 s as exit code 124, GNU `timeout`'s, with the output it wrote, and a `wrangler` that cannot start as exit code 127, the shell's "command not found", with the error's type and message.

```python
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

FILE_NAME: Final = "latest-station-count.json"

@dataclass(frozen=True, slots=True)
class DeployResult:
    exit_code: int
    output: str
    peak_memory_mb: float

def write_published_file(document: Mapping[str, object], assets_dir: Path) -> Path: ...
def deploy_page(
    web_dir: Path, *, tag: str, account_id: str, api_token: str, timeout_s: float = 120.0
) -> DeployResult: ...
```

#### `bikesharing.shell.heartbeat`

- **Responsibility:** pings Healthchecks.io with its retries ([Observability](#observability)).
- **Location:** `pipeline/src/bikesharing/shell/heartbeat.py`
- **Contract:** sends a POST with `urllib.request` from the standard library to `<url>/start`, `<url>` or `<url>/fail` by signal, with `body`, a timeout of `timeout_s` per attempt, and one more attempt after each delay in `delays_s`. It returns `None` once a ping gets a 2xx response, and a `PingFailure` after the last attempt fails, or after a single attempt if the URL has no scheme, which no retry fixes, with the exception's type name only, never its message, which may quote the URL (R24).

```python
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

type Signal = Literal["start", "success", "fail"]

@dataclass(frozen=True, slots=True)
class PingFailure:
    signal: Signal
    attempts: int
    error_type: str

def ping(
    url: str,
    signal: Signal,
    *,
    body: str = "",
    timeout_s: float = 10.0,
    delays_s: Sequence[float] = (1.0, 2.0),
    sleep: Callable[[float], None] = time.sleep,
) -> PingFailure | None: ...
```

#### `bikesharing.shell.event_log`

- **Responsibility:** writes each event to stdout as it happens and keeps it for the run's log object.
- **Location:** `pipeline/src/bikesharing/shell/event_log.py`
- **Contract:** `emit` serializes with `to_json_line`, writes the line and a newline to `stream`, flushes it, keeps it and returns it; `body` joins the kept lines, each ending in a newline, as JSON Lines.

```python
from collections.abc import Collection
from typing import TextIO

from bikesharing.core.events import Event, RunContext

class EventLog:
    def __init__(self, context: RunContext, secrets: Collection[str], stream: TextIO) -> None: ...
    def emit(self, event: Event) -> str: ...
    def body(self) -> str: ...
```

#### `modal_app`

- **Responsibility:** the platform modules: the shared image, and one Modal app for each function, with its schedule, secrets and size, so that a run from a branch never creates the scheduled function (#2, #20, DI12, [Run operation on Modal](#run-operation-on-modal)).
- **Location:** `pipeline/modal_image.py` (the image, the container size and the Secrets' references), `pipeline/modal_app.py` (the scheduled function) and `pipeline/modal_one_off.py` (the one-off function).
- **Contract:** `modal_image.py` builds the image, and holds `MEMORY_MIB`, the Secrets' references and the check of a run's outcome that both functions use; it declares no app and no function. The image runs Python at `.python-version`'s patch, installs the locked runtime dependencies with no `dev` or `platform` group, installs Node at `web/.nvmrc`'s version from nodejs.org's official Linux tarball, verified against that release's `SHASUMS256.txt`, and `web/`'s locked `wrangler` with `npm ci`, copies `pipeline/dbt/`, `pipeline/config/`, `web/` and `contracts/latest-station-count.schema.json` to the same paths under `/repo`, the `root` of [`bikesharing.shell.run`](#bikesharingshellrun), adds the package and `modal_image` with `add_local_python_source("bikesharing", "modal_image")`, since Modal mounts only the entrypoint's own file, and stores `CODE_VERSION` from the deploying shell's environment, empty when it is unset. The install of the dependencies points `uv` at `https://pypi.org/simple`, since Modal's builder sets a mirror of its own and `uv.lock` names that index, which `--locked` needs. Each Modal Secret holds the environment variables named beside it, which `scheduled_config` and `one_off_config` read:
  - `bikesharing-pipeline-bronze-read`: `BRONZE_R2_ACCESS_KEY_ID`, `BRONZE_R2_SECRET_ACCESS_KEY`;
  - `bikesharing-pipeline-lakehouse-write`: `LAKEHOUSE_R2_ACCESS_KEY_ID`, `LAKEHOUSE_R2_SECRET_ACCESS_KEY`;
  - `bikesharing-pipeline-deploy`: `CLOUDFLARE_API_TOKEN`;
  - `bikesharing-pipeline-heartbeat`: `HEARTBEAT_URL`.

  `modal_app.py` declares the app `bikesharing-pipeline` with `scheduled_run` and the four Secrets, and the deploy script deploys it. `modal_one_off.py` declares the app `bikesharing-pipeline-one-off` with `one_off_run` and bronze's Secret only, and is started with `modal run`. Each function calls `run` with its configuration from `os.environ` and raises `RuntimeError` when the outcome is `failed`, so that Modal records the call as failed, which the deploy script's smoke test reads.

```python
# modal_image.py
import modal

MEMORY_MIB = 4096

image: modal.Image

def secret(spec: tuple[str, list[str]]) -> modal.Secret: ...
def raise_if_failed(outcome: str) -> None: ...

# modal_app.py
app = modal.App("bikesharing-pipeline")

@app.function(
    image=image,
    schedule=modal.Cron("*/15 * * * *"),
    secrets=[
        modal.Secret.from_name("bikesharing-pipeline-bronze-read"),
        modal.Secret.from_name("bikesharing-pipeline-lakehouse-write"),
        modal.Secret.from_name("bikesharing-pipeline-deploy"),
        modal.Secret.from_name("bikesharing-pipeline-heartbeat"),
    ],
    cpu=1.0,
    memory=(MEMORY_MIB, MEMORY_MIB),
    timeout=600,
    max_containers=1,
)
def scheduled_run() -> None: ...

# modal_one_off.py
app = modal.App("bikesharing-pipeline-one-off")

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("bikesharing-pipeline-bronze-read")],
    cpu=1.0,
    memory=(MEMORY_MIB, MEMORY_MIB),
    timeout=600,
)
def one_off_run() -> None: ...
```

### 2.6 Test plan

<!-- Optional. Every requirement has at least one verification method (IADT: Inspection, Analysis, Demonstration, Test). Test is the default, at the lowest level that can verify the requirement. Another method only when no test can: Inspection for configuration or documents, Analysis for production data or measurements, Demonstration for behaviour observed end to end, such as a third-party service. -->

| R | Method | What is verified | Level |
|---|---|---|---|
| R1 | Test | `station_stock` holds the rows of both systems' staging models, one per station and capture, keyed by system, `station_id` and capture instant in UTC | unit (dbt) |
| R2 | Test | Each staging model's casts, conversions and renames, with TR8's nulls in AMBici's | unit (dbt) |
| R3 | Test | Bicing's staging model writes null as `num_vehicles_available` for a station with `is_renting` and `is_returning` false | unit (dbt) |
| R4 | Test | `station_stock`'s local calendar keys, on captures on both sides of a local midnight | unit (dbt) |
| R5 | Test | `station_stock`'s lineage columns carry the run's ID and code version passed to dbt | unit (dbt) |
| R6 | Test | `latest_station_count` builds D2's fields; the shell's file holds the latest capture of each system, a system with no capture in the run keeping its earlier count | unit (dbt), integration |
| R7 | Test | The file built from the fixtures passes the schema, and the vectors' `invalid` file with a field outside D2's list fails it | contract |
| R8 | Test | A run logs `rule_checked` for each of the six rules with its severity, and the verdict maps dbt's node statuses to them | unit, integration |
| R9 | Demonstration | After the first deployment, the smoke test's `run_started` and rows carry the SHA of `origin/main` | — |
| R10 | Test | In a temporary Git repository with a stand-in for `uv` first on the `PATH`, the deploy script refuses an uncommitted change, an untracked file and a commit other than `origin/main`, each with its cause, and never calls the stand-in | integration |
| R11 | Inspection | The scheduled function in `modal_app.py` declares `timeout=600` | — |
| R12 | Test | Batching stops opening batches once the time budget is spent | unit |
| R13 | Test | Batching splits pending objects into batches of at most 360 | unit |
| R14 | Test | A run that ends without failing pings `/start` and then success on a local stub of the check | integration |
| R15 | Test | A failing run pings `/fail` with `run_finished` and the failing event as its body; a ping that fails is retried and then logged as `heartbeat_failed` | integration |
| R16 | Inspection | The scheduled function declares no `retries`; the memory-kill probe of [Run operation on Modal](#run-operation-on-modal) records how Modal treats a memory kill | — |
| R17 | Inspection | The Healthchecks.io check has a period of 15 min and a grace of 15 min | — |
| R18 | Test | With an end instant set, `within_end_instant` keeps only the objects captured up to it, oldest first | unit |
| R19 | Test | With an end instant set and no pending object up to it, the run builds `stage_drained` | unit |
| R20 | Test | A batch whose model fails DQR1 or DQR13 commits nothing, its objects stay pending and the run fails | integration |
| R21 | Test | A batch with a row that violates a model's contract commits nothing, its objects stay pending and the run fails | integration |
| R22 | Test | A batch with an unreadable bronze object commits nothing, its objects stay pending and the run fails | integration |
| R23 | Inspection | Every secret reaches the functions in the platform modules as a `modal.Secret`, and `bikesharing.core.settings` holds none | — |
| R24 | Test | Redaction replaces each secret's value in an error's message, the heartbeat's URL included | unit |
| R25 | Inspection | The shell's SQL and dbt's models take feed values only as columns or bound parameters, never by string formatting | — |
| R26 | Test | `one_off_config` holds only bronze's credentials and writes its tables locally, and `modal_one_off.py` names no Secret other than bronze's read-only one | integration |
| R27 | Test | `one_off_config` leaves the page's deployment target empty, and `modal_one_off.py` names no Cloudflare Secret and no `modal_app` | integration |
| R28 | Test | DuckDB refuses a file outside its allowed folder | integration |
| R29 | Test | DuckDB refuses an extension load | integration |
| R30 | Test | DQR2's check fails on a MERGE's metrics with a row updated or deleted | unit |
| R31 | Test | A deployment whose stand-in for `wrangler` exits with an error keeps the run's commits, logs `page_deploy_failed` and fails the run | integration |

### 2.7 What does not change

<!-- Optional. Code or documents that must not be modified. Out of scope limits the what; this section limits the how. -->

- `capture/` and its CI job: the pipeline reads bronze as capture writes it ([d004](d004-bronze-data-capture.md)).
- `contracts/bronze-keys.json`: the pipeline is only its consumer; a key the discovery cannot parse is fixed in the pipeline, not in the contract.
- `bikesharing-bronze`: the pipeline only reads it, with a read-only token; no object is moved, rewritten or deleted, the excluded ones included (#8).
- `scripts/lint-docs.sh` and the `docs` CI job.

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

| # | Prerequisite | Version or value | Verification |
|---|---|---|---|
| P1 | uv on the local machine, through Homebrew, upgraded if older | 0.13.5 (DI3) | `uv --version` prints `uv 0.13.5` |
| P2 | Node on the local machine, through fnm, for `web/` | 26.12.1, as `capture/.nvmrc` | `node --version` prints `v26.12.1` with `web/`'s pin active |
| P3 | Modal's usage limit and spend limit, on the existing account's billing page ([Run operation on Modal](#run-operation-on-modal)) | Starter plan; usage limit $30; spend limit $1 | the billing page shows the plan and both limits |
| P4 | Modal's CLI authenticated on the local machine, with `uv run --group platform modal token new` if it is not | the existing account | `uv run --group platform modal profile current` names the account |
| P5 | R2 bucket `bikesharing-lakehouse` ([ADR-0035](../decisions/0035-cloud-resource-naming.md)), with a lifecycle rule on the prefix `logs/pipeline/` ([Observability](#observability)) | objects deleted 30 days after creation | the bucket's settings list the rule with its prefix and age |
| P6 | R2 API token `bikesharing-pipeline-bronze-read` | Object Read, on `bikesharing-bronze` only, with a one-year expiry (DI1) | R2's API tokens page shows its permission, bucket and expiry |
| P7 | R2 API token `bikesharing-pipeline-lakehouse-write` | Object Read & Write, on `bikesharing-lakehouse` only, with a one-year expiry (DI1) | R2's API tokens page shows its permission, bucket and expiry |
| P8 | Cloudflare API token `bikesharing-pipeline-deploy` ([ADR-0038](../decisions/0038-account-wide-workers-editor-deploy-token.md)) | Workers Editor, with an expiry date | the API tokens page shows its role and expiry |
| P9 | Healthchecks.io check of [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md) | period 15 min, grace 15 min | the check's page shows both values |
| P10 | Modal Secrets, each with the environment variables that [`modal_app`](#modal_app) names: `bikesharing-pipeline-bronze-read` from P6, `bikesharing-pipeline-lakehouse-write` from P7, `bikesharing-pipeline-deploy` from P8, `bikesharing-pipeline-heartbeat` with P9's ping URL | four Secrets | `uv run --group platform modal secret list` lists the four names |
| P11 | A sample of bronze `station_status` objects in a local folder outside the repository, as the source of the fixtures ([Tests and CI](#tests-and-ci)), downloaded with the owner's own tool and bronze's read-only token | one full local day of each system, at their bronze keys as relative paths | the folder holds both systems' prefixes with about 1,440 objects a day each, one per minute; its path is given at Step 5 |

### Step 1 — Python project

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** — (committed with Step 4)
- **R:** —
- **Model:** sonnet · high
- **Review:** no

#### Scope

The pipeline's Python project, installable and with its lint and import contracts configured, with no code yet.

- `pipeline/.python-version` (new): `3.14.9` (DI3).
- `pipeline/pyproject.toml` (new): metadata, `requires-python = ">=3.14,<3.15"`, build backend for the `src/` layout, runtime dependencies, groups `dev` and `platform`, `[tool.uv] default-groups = ["dev"]` and the `mashumaro>=3.15` constraint; ruff, mypy, import-linter (rules 1–3) and SQLFluff configuration.
- `pipeline/uv.lock` (new).
- `pipeline/src/bikesharing/__init__.py`, `core/__init__.py`, `shell/__init__.py` (new): module docstrings only.
- `.gitignore` (modified): dbt's `target/` and `logs/` under `pipeline/dbt/`, and `web/public/`.

#### Reads

- [Runtime and dependencies](#runtime-and-dependencies), this design: the versions, groups and constraint the manifest declares.
- [Component structure](#component-structure), this design: ADR-0046's rules 1–3 as import-linter contracts and the check of `include_external_packages`.
- [Transformation in dbt](#transformation-in-dbt) › SQL conventions, this design: SQLFluff's dialect and templater.
- [s016 › D2](../spikes/s016-code-workflow.md): the defaults policy that the comment in `[tool.ruff]` and `[tool.mypy]` states.
- `.claude/rules/code/dependencies.md` and `python.md`: how dependencies are added and what the Python rule expects of the configuration.

#### Do

1. Write `pipeline/.python-version` with `3.14.9`.
2. Write `pipeline/pyproject.toml` with the metadata, `requires-python`, the build backend, `default-groups`, the `mashumaro` constraint and the tool configuration; import-linter's root packages are `bikesharing` only, since `modal_app` and rule 4 come with Step 25.
3. Add the runtime dependencies with `uv add --directory pipeline`: `duckdb==2.0.0`, `dbt-core==1.12.7`, `dbt-duckdb==1.11.1`, `deltalake`, `obstore`, `jsonschema`.
4. Add the `dev` group with `uv add --directory pipeline --dev`: `pytest`, `ruff`, `mypy`, `import-linter`, `sqlfluff`, `sqlfluff-templater-dbt`.
5. Add the `platform` group with `uv add --directory pipeline --group platform modal`.
6. Write the three `__init__.py` files.
7. Run import-linter once with a temporary `import duckdb` in `core/__init__.py` to confirm that rule 2's forbidden contract on an external package fails; remove the import. If it does not fail, record it as a finding and fall back to PyTestArch, as Component structure sets.
8. Update `.gitignore`.

#### Check

- `uv sync --directory pipeline --locked` ends without error on Python 3.14.9; if it fails on 3.14, both pins move to 3.13.18 and the cause is recorded as a finding ([Runtime and dependencies](#runtime-and-dependencies)).
- `uv run --directory pipeline lint-imports` reports every contract kept.

### Step 2 — Lint hooks

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** — (committed with Step 4)
- **R:** —
- **Model:** sonnet · medium
- **Review:** no

#### Scope

Claude Code's lint hooks for Python and for dbt's SQL, and the permission for the pipeline's test command.

- `.claude/hooks/python-lint.sh` (new): `ruff format` and `ruff check --fix` on the edited `.py` file under `pipeline/`, through `uv run --project pipeline`; what remains goes to stderr with exit 2.
- `.claude/hooks/sql-lint.sh` (new): `sqlfluff fix` and `sqlfluff lint` on the edited `.sql` file under `pipeline/dbt/`; what remains goes to stderr with exit 2.
- `.claude/settings.json` (modified): both hooks as `PostToolUse` on `Edit` and `Write`; `uv run --directory pipeline pytest` and its variants with arguments allowed.

#### Reads

- `.claude/hooks/markdown-lint.sh`: the existing hook's input parsing, path filter and exit codes, which both hooks follow.
- [s016 › P3](../spikes/s016-code-workflow.md): the Python hook's behaviour.
- `.claude/rules/code/python.md` › the test command: the exact form allowed in `settings.json`.

#### Do

1. Write `.claude/hooks/python-lint.sh`.
2. Write `.claude/hooks/sql-lint.sh`; since SQLFluff's dbt templater needs dbt's profile, it sets the `BIKESHARING_*` variables of [`bikesharing.shell.dbt_runner`](#bikesharingshelldbt_runner) to a temporary folder, as `check-pipeline.sh` does.
3. Update `.claude/settings.json`.

#### Check

- An edit to a scratch `.py` file under `pipeline/src/` with an unused import is fixed by the hook, and one with an error ruff cannot fix makes the hook exit 2 with the error on stderr.
- An edit to a `.md` file still runs only the Markdown hook.

### Step 3 — Empty dbt project

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** — (committed with Step 4)
- **R:** —
- **Model:** sonnet · medium
- **Review:** no

#### Scope

The dbt project with no models, parsed against the run's scratch database.

- `pipeline/dbt/dbt_project.yml` (new): the project, its profile, `models/silver/` and `models/gold/` with views as the default materialization ([Transformation in dbt](#transformation-in-dbt) › Materialization).
- `pipeline/dbt/profiles.yml` (new): a `duckdb` target whose path, allowed directory, temporary directory and memory limit come from `env_var()` with the four `BIKESHARING_*` variables, with `enable_external_access: false` and `lock_configuration: true` among its settings (#9, #10).

#### Reads

- [`bikesharing.shell.dbt_runner`](#bikesharingshelldbt_runner) › Contract, this design: the variables `profiles.yml` reads.
- [Bronze reading](#bronze-reading) › Batch reading and Memory, this design: DuckDB's settings.
- `dbt-duckdb`'s README, profile settings: how `settings` and `path` are declared.

#### Do

1. Write `pipeline/dbt/dbt_project.yml`.
2. Write `pipeline/dbt/profiles.yml`.

#### Check

- `env BIKESHARING_SCRATCH_DATABASE=<tmp>/scratch.duckdb BIKESHARING_ALLOWED_DIRECTORY=<tmp> BIKESHARING_TEMP_DIRECTORY=<tmp>/spill BIKESHARING_MEMORY_LIMIT=1GiB uv run --directory pipeline dbt parse --project-dir dbt --profiles-dir dbt` ends without error, with `<tmp>` a folder in the scratchpad.

### Step 4 — Check script and CI job

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `d008.s4 - build: add the pipeline component with its checks and CI job` (Steps 1–4)
- **R:** —
- **Model:** sonnet · high
- **Review:** code

#### Scope

The pipeline's checks in one script, run by its CI job, and rule 5 of ADR-0046 as a test.

- `pipeline/scripts/check-pipeline.sh` (new): ruff format check, ruff check, mypy, import-linter, SQLFluff, `dbt parse`, `dbt run --empty` with dbt's unit tests, and pytest, in that order; it runs from any folder, and sets the `BIKESHARING_*` variables to a temporary folder it removes at its end.
- `pipeline/tests/integration/test_platform_separation.py` (new): `modal` cannot be imported, and `bikesharing` imports without it; Step 6 extends it to `bikesharing.core.settings`.
- `.github/workflows/ci.yml` (modified): job `pipeline` ([Tests and CI](#tests-and-ci) › CI job); `ci-passed` needs it.

#### Reads

- [Tests and CI](#tests-and-ci) › Check script, CI job and Platform separation, this design.
- `.claude/rules/code/ci.md`: the recipe of a component's job and its path filter.
- `.github/workflows/ci.yml`: the `capture` job and `ci-passed`, which the new job mirrors.
- `docs/testing-strategy.md` › Python: the levels and the command the script runs.

#### Do

1. Write `pipeline/tests/integration/test_platform_separation.py`.
2. Write `pipeline/scripts/check-pipeline.sh`.
3. Update `.github/workflows/ci.yml`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` exits 0, with pytest passing on Python 3.14.9; if a test fails on 3.14 for a cause of the runtime, both pins move to 3.13.18 and the cause is recorded as a finding.
- The `pipeline` job's path filter lists `pipeline/**`, `.github/workflows/ci.yml` and the three contract files, and `ci-passed` lists `pipeline` among its needs.

### Step 5 — Bronze fixtures and read schema

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** — (committed with Step 11)
- **R:** —
- **Model:** sonnet · medium
- **Review:** no

#### Scope

The bronze fixtures of both systems and the read schema of `station_status` per system.

- `pipeline/tests/fixtures/bronze/` (new): `station_status` objects of both systems from the 13 days of the capture spike's sample (`spikes/cloudflare-capture-spike/data/V4/raw`, 2026-10-14 to 2026-10-26), kept at their bronze keys, gzip-compressed and trimmed to a few stations each: a Bicing station out of service, a station without GBFS's optional fields, two consecutive captures with a station added or removed, and an object with a field outside the read schema. A variety no sampled object carries is a copy of a captured object with the field added or removed, marked as derived in the manifest.
- `pipeline/tests/fixtures/bronze/manifest.json` (new): each fixture's key, capture date, source key if derived, and Bicing's attribution (ADR-0037).
- `pipeline/scripts/trim_fixtures.py` (new): writes the fixtures and the manifest from the sample folder given as its argument.
- `pipeline/src/bikesharing/core/read_schema.py` (new): [`bikesharing.core.read_schema`](#bikesharingcoreread_schema).
- `pipeline/tests/unit/core/test_read_schema.py` (new): each system's schema declares its source card's fields with their types.

The read of the fixtures with each schema is an integration test of Step 16, since reading needs DuckDB.

#### Reads

- [`bikesharing.core.read_schema`](#bikesharingcoreread_schema), this design: the module's contract.
- [Bronze reading](#bronze-reading) › Read schema, this design: one schema per system and feed, from the field dictionary.
- `station_status`'s field dictionary in [AMBici](../sources/ambici.md) and [Bicing](../sources/bicing.md)'s source cards.
- [Tests and CI](#tests-and-ci) › Fixtures, this design, and [ADR-0037](../decisions/0037-test-fixtures-per-component.md): what the fixtures hold.

#### Do

1. Search P11's sample, at the path the owner gives, for an object of each kind of variety.
2. Write the trimmed fixtures to `pipeline/tests/fixtures/bronze/`.
3. Write `pipeline/tests/unit/core/test_read_schema.py`.
4. Implement `pipeline/src/bikesharing/core/read_schema.py`.

#### Check

- `uv run --directory pipeline pytest tests/unit/core/test_read_schema.py` passes.
- The fixtures folder holds every kind of variety listed in Scope, for its system.

### Step 6 — Settings and discovery

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** — (committed with Step 11)
- **R:** —
- **Model:** sonnet · high
- **Review:** no

#### Scope

The run's constants and the core's decisions on what a run lists and which objects are pending.

- `pipeline/src/bikesharing/core/settings.py` (new): [`bikesharing.core.settings`](#bikesharingcoresettings), with the owner's account ID and, as `END_INSTANT`, the end of the local day of the oldest bronze capture, D8's first stage.
- `pipeline/src/bikesharing/core/discovery.py` (new): [`bikesharing.core.discovery`](#bikesharingcorediscovery).
- `pipeline/tests/unit/core/test_discovery.py` (new): the listing's start key and full sweep (#7), the pending objects after the exclusion list (#8), and the consumer of `contracts/bronze-keys.json`.
- `pipeline/tests/integration/test_platform_separation.py` (modified): `bikesharing.core.settings` loads without Modal's SDK.

#### Reads

- [`bikesharing.core.settings`](#bikesharingcoresettings) and [`bikesharing.core.discovery`](#bikesharingcorediscovery), this design: the contracts.
- [Bronze reading](#bronze-reading) › Discovery of pending objects and Unreadable objects, this design.
- [D8](#d8-first-load-in-chronological-stages), this design: the first stage's end instant.
- `contracts/bronze-keys.json` and [testing.md](../../.claude/rules/code/testing.md) › Contracts between components: the vectors the consumer test reads.

#### Do

1. Ask the owner for the Cloudflare account ID and the local date of the oldest bronze capture.
2. Write `pipeline/tests/unit/core/test_discovery.py`.
3. Implement `pipeline/src/bikesharing/core/settings.py`.
4. Implement `pipeline/src/bikesharing/core/discovery.py`.
5. Update `pipeline/tests/integration/test_platform_separation.py`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` exits 0.

### Step 7 — Batching

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** — (committed with Step 11)
- **R:** R12, R13, R18, R19
- **Model:** sonnet · high
- **Review:** no

#### Scope

The batches of a run, the time budget and the end of a stage.

- `pipeline/src/bikesharing/core/batching.py` (new): [`bikesharing.core.batching`](#bikesharingcorebatching).
- `pipeline/tests/unit/core/test_batching.py` (new): batches of at most the bound (R13), no batch opened once the budget is spent (R12), only the objects captured up to the end instant kept, oldest first (R18), and `stage_drained` with an end instant and no pending object up to it (R19), with small bounds and a fixed UTC time.

#### Reads

- [`bikesharing.core.batching`](#bikesharingcorebatching), this design: the contract.
- [D6](#d6-provisional-run-bounds), this design: the bounds the settings hold.

#### Do

1. Write `pipeline/tests/unit/core/test_batching.py`.
2. Implement `pipeline/src/bikesharing/core/batching.py`.

#### Check

- `uv run --directory pipeline pytest tests/unit/core/test_batching.py` passes.

### Step 8 — Verdict

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** — (committed with Step 11)
- **R:** R8, R30
- **Model:** sonnet · medium
- **Review:** no

#### Scope

The verdict over dbt's node statuses and DQR2's check on a MERGE's metrics.

- `pipeline/src/bikesharing/core/verdict.py` (new): [`bikesharing.core.verdict`](#bikesharingcoreverdict).
- `pipeline/tests/unit/core/test_verdict.py` (new): a batch commits only with no node in `fail` or `error`, `warn` stops nothing, each node maps to its rule (R8), and DQR2 fails on a row updated or deleted (R30).

#### Reads

- [`bikesharing.core.verdict`](#bikesharingcoreverdict), this design: the contract.
- [Transformation in dbt](#transformation-in-dbt) › Runtime rules and Severity and verdict, this design.

#### Do

1. Write `pipeline/tests/unit/core/test_verdict.py`.
2. Implement `pipeline/src/bikesharing/core/verdict.py`.

#### Check

- `uv run --directory pipeline pytest tests/unit/core/test_verdict.py` passes.

### Step 9 — Contract of the published file

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** — (committed with Step 11)
- **R:** R7
- **Model:** sonnet · medium
- **Review:** no

#### Scope

The published file's schema and its shared vectors, tested before the file is built ([testing.md](../../.claude/rules/code/testing.md) › Contracts between components).

- `contracts/latest-station-count.schema.json` (new): [The published file's JSON Schema](#the-published-files-json-schema), as written.
- `contracts/latest-station-count.json` (new): one `valid` file and one `invalid` file per kind of violation (a missing field, a wrong type, a field outside D2's list), each with its `reason`.
- `pipeline/tests/integration/test_latest_station_count_contract.py` (new): the `valid` file passes the schema and each `invalid` file fails it, with `jsonschema`'s `Draft202012Validator`, the validator of `validate_published_file`; Step 24 adds the file built from the fixtures.

#### Reads

- [Publishing](#publishing) › Contract, this design.
- [The published file's JSON Schema](#the-published-files-json-schema), this design.
- [ADR-0050](../decisions/0050-contract-tests-by-contract-kind-with-native-schemas.md): data-shape contracts as a native schema with vectors.

#### Do

1. Write `contracts/latest-station-count.schema.json`.
2. Write `contracts/latest-station-count.json`.
3. Write `pipeline/tests/integration/test_latest_station_count_contract.py`.

#### Check

- `uv run --directory pipeline pytest tests/integration/test_latest_station_count_contract.py` passes.

### Step 10 — Published file in the core

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** — (committed with Step 11)
- **R:** R7
- **Model:** sonnet · high
- **Review:** no

#### Scope

The published document from `latest_station_count`'s rows, and its validation against the schema (DQR14).

- `pipeline/src/bikesharing/core/published_file.py` (new): [`bikesharing.core.published_file`](#bikesharingcorepublished_file).
- `pipeline/tests/unit/core/test_published_file.py` (new): the document built from rows, and each violation reported with its path in the file, against the schema of Step 9.

#### Reads

- [`bikesharing.core.published_file`](#bikesharingcorepublished_file), this design: the contract.
- [Publishing](#publishing) › Runtime check, this design.

#### Do

1. Write `pipeline/tests/unit/core/test_published_file.py`.
2. Implement `pipeline/src/bikesharing/core/published_file.py`.

#### Check

- `uv run --directory pipeline pytest tests/unit/core/test_published_file.py` passes.

### Step 11 — Events

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d008.s11 add the run's events, their redaction and the log object's key`
- **R:** R24
- **Model:** sonnet · high
- **Review:** code and security

#### Scope

The events of a run as values, their redaction and the log object's key.

- `pipeline/src/bikesharing/core/events.py` (new): [`bikesharing.core.events`](#bikesharingcoreevents).
- `pipeline/tests/unit/core/test_events.py` (new): each event's common fields in ADR-0036's order and its own fields, the redaction of each secret's value in an error's message, the heartbeat's URL included (R24), and the log object's key.

#### Reads

- [`bikesharing.core.events`](#bikesharingcoreevents), this design: the contract.
- [Observability](#observability), this design: the event table, run measures and redaction.
- [ADR-0036](../decisions/0036-log-convention-across-components.md): the common fields and their order.

#### Do

1. Write `pipeline/tests/unit/core/test_events.py`.
2. Implement `pipeline/src/bikesharing/core/events.py`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` exits 0.

### Step 12 — Sources and staging models

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d008.s12 add bronze as dbt sources and a staging model per system`
- **R:** R2, R3, R25
- **Model:** opus · high
- **Review:** no

#### Scope

Bronze as dbt sources, and one staging model per system.

- `pipeline/dbt/models/sources.yml` (new): `ambici` and `bicing`, each with `station_status` and `station_status_raw` over the batch's local files, and `lakehouse.capture_history` and `lakehouse.latest_captures` over the Parquet files the shell writes.
- `pipeline/dbt/models/silver/stg_ambici__station_status.sql` (new): AMBici's casts, conversions to UTC, renames and TR8's nulls.
- `pipeline/dbt/models/silver/stg_bicing__station_status.sql` (new): Bicing's casts, conversions and TR9's null.
- `pipeline/dbt/models/silver/silver.yml` (new): both models' descriptions and dbt unit tests (R2, R3).
- `pipeline/scripts/dbt_check_vars.py` (new) and `pipeline/scripts/check-pipeline.sh` (modified): dbt's variables for the checks, passed with `--vars` ([Tests and CI](#tests-and-ci) › Check script).

#### Reads

- [Transformation in dbt](#transformation-in-dbt) › Bronze as external sources and Models, this design.
- [dbt model contracts](#dbt-model-contracts), this design: the `silver.yml` block.
- [D1](#d1-first-version-of-the-station-stock), this design: the rules on measures and flags.
- [`bikesharing.shell.r2`](#bikesharingshellr2) › Contract, this design, and `contracts/bronze-keys.json`: the file's path ends with its bronze key, from which each row takes its system and capture instant.
- [sql.md](../../.claude/rules/code/sql.md): the SQL conventions.

#### Do

1. Write `pipeline/dbt/models/sources.yml`; confirm that `external_location` renders dbt variables, and if it does not, apply the fallback of #12 (each staging model calls `read_json` with the variables and declares its source with `depends_on`), recording it as a finding.
2. Write `pipeline/scripts/dbt_check_vars.py` and pass its variables to the dbt commands of `check-pipeline.sh`.
3. Write the unit tests in `pipeline/dbt/models/silver/silver.yml`.
4. Write both staging models.
5. Confirm that SQLFluff's dbt templater lints them with `dbt-core` 1.12.7 and the variables of `dbt_check_vars.py`, in `check-pipeline.sh` and in the SQL hook; if it does not, switch `[tool.sqlfluff]` to the Jinja templater, as #27 sets, and record it as a finding.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` exits 0, with both staging models' unit tests passing.
- An edit to a staging model runs `.claude/hooks/sql-lint.sh`, which fixes a keyword in the wrong case and exits 2 with what it cannot fix on stderr.

### Step 13 — Station stock

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d008.s13 add the station stock with its contract and grain rules`
- **R:** R1, R4, R5, R8
- **Model:** opus · high
- **Review:** no

#### Scope

`station_stock` at D1's grain, with its contract, calendar keys, lineage and the rules on its grain.

- `pipeline/dbt/models/silver/station_stock.sql` (new): the union of both staging models, the local calendar keys and the lineage columns, materialized as a table.
- `pipeline/dbt/models/silver/silver.yml` (modified): its contract, DQR1 and DQR13 with their `name`, severity and `meta`, and unit tests (R1, R4, R5).
- `pipeline/dbt/tests/generic/` (new): the generic tests DQR1 and DQR13 need.

#### Reads

- [Transformation in dbt](#transformation-in-dbt) › Models, Rule traceability, Runtime rules and Materialization, this design.
- [dbt model contracts](#dbt-model-contracts), this design: `station_stock`'s columns.
- DQR1 and DQR13 in [data-quality.md](../data-quality.md).
- [ADR-0041](../decisions/0041-utc-timestamps-local-calendar-keys.md) and [ADR-0043](../decisions/0043-lineage-at-four-levels.md): calendar keys and lineage columns.

#### Do

1. Write the unit tests and data tests in `pipeline/dbt/models/silver/silver.yml`.
2. Write the generic tests in `pipeline/dbt/tests/generic/`.
3. Write `pipeline/dbt/models/silver/station_stock.sql`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` exits 0.

### Step 14 — Volume and schema drift

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d008.s14 add the batch's volume and schema drift audits`
- **R:** R8
- **Model:** opus · high
- **Review:** no

#### Scope

The batch's audits of DQR12 and DQR11, with their warn tests.

- `pipeline/dbt/models/silver/capture_volume.sql` (new): each capture against its system's 24 h median, with `ok`, `drop` or `not_evaluated` (#14).
- `pipeline/dbt/models/silver/schema_drift.sql` (new): the fields added and dropped per object (#15).
- `pipeline/dbt/models/silver/silver.yml` (modified): both models, DQR12 and DQR11 with severity warn, and unit tests.
- `pipeline/dbt/tests/generic/` (modified): the generic tests DQR11 and DQR12 need.

#### Reads

- [Transformation in dbt](#transformation-in-dbt) › Volume drop and Schema drift, this design.
- [D4](#d4-volume-drop-against-a-rolling-median), this design.
- DQR11 and DQR12 in [data-quality.md](../data-quality.md).

#### Do

1. Write the unit tests and data tests in `pipeline/dbt/models/silver/silver.yml`.
2. Write the generic tests in `pipeline/dbt/tests/generic/`.
3. Write `capture_volume.sql` and `schema_drift.sql`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` exits 0.

### Step 15 — Latest station count and exposure

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d008.s15 add the latest station count and the published file as an exposure`
- **R:** R6
- **Model:** sonnet · high
- **Review:** code

#### Scope

The gold model in the shape of the published file, and the file as dbt's exposure.

- `pipeline/dbt/models/gold/latest_station_count.sql` (new): D2's fields from `lakehouse.latest_captures`.
- `pipeline/dbt/models/gold/gold.yml` (new): its contract and unit tests (R6).
- `pipeline/dbt/models/exposures.yml` (new): the published file as an exposure of type `application` (#24).

#### Reads

- [Publishing](#publishing) › Source of the file, this design.
- [dbt model contracts](#dbt-model-contracts), this design: the `gold.yml` block.
- [D2](#d2-published-file-the-latest-count-of-each-station), this design.

#### Do

1. Write the unit tests in `pipeline/dbt/models/gold/gold.yml`.
2. Write `latest_station_count.sql`.
3. Write `pipeline/dbt/models/exposures.yml`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` exits 0.

### Step 16 — DuckDB session

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d008.s16 add the DuckDB session with its sandbox and memory settings`
- **R:** R25, R28, R29
- **Model:** opus · high
- **Review:** security

#### Scope

DuckDB's connection with its sandbox and memory settings, and the reads of the scratch database.

- `pipeline/src/bikesharing/shell/duckdb_session.py` (modified): [`bikesharing.shell.duckdb_session`](#bikesharingshellduckdb_session); it already holds `apply_sandbox` and `Plugin` (DI6), and `connect` calls `apply_sandbox`.
- `pipeline/tests/conftest.py` (new): the shared fixtures, a local bronze folder and a local Delta path.
- `pipeline/tests/integration/test_duckdb_session.py` (modified): it already tests `apply_sandbox`, with a file outside the allowed folder refused (R28) and an extension load refused (R29), and `Plugin`; it adds `connect`, each system's fixtures read with its schema (#11), and a spill to the temporary folder with external access off (#10).

#### Reads

- [`bikesharing.shell.duckdb_session`](#bikesharingshellduckdb_session), this design: the contract.
- [Bronze reading](#bronze-reading) › Batch reading, Memory and Read schema, this design.

#### Do

1. Write `pipeline/tests/conftest.py`.
2. Write `pipeline/tests/integration/test_duckdb_session.py`.
3. Implement `pipeline/src/bikesharing/shell/duckdb_session.py`.

#### Check

- `uv run --directory pipeline pytest tests/integration/test_duckdb_session.py` passes.

### Step 17 — R2 adapter

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d008.s17 add the R2 adapter for listing, batch download and log upload`
- **R:** —
- **Model:** sonnet · high
- **Review:** no

#### Scope

Listing, batch download and log upload over R2's S3 API, tested through `LocalStore`.

- `pipeline/src/bikesharing/shell/r2.py` (new): [`bikesharing.shell.r2`](#bikesharingshellr2).
- `pipeline/tests/integration/test_r2.py` (new): listing after a key, concurrent download of explicit keys to a folder, and the log object's upload, on `LocalStore` over local folders.

Whether files on the container's local disk count against its memory needs a Modal container, so Step 27 confirms it.

#### Reads

- [`bikesharing.shell.r2`](#bikesharingshellr2), this design: the contract.
- [Runtime and dependencies](#runtime-and-dependencies) › S3 client, this design.
- `obstore`'s documentation of `list` with `offset`, `S3Store` and `LocalStore`.

#### Do

1. Write `pipeline/tests/integration/test_r2.py`.
2. Implement `pipeline/src/bikesharing/shell/r2.py`.

#### Check

- `uv run --directory pipeline pytest tests/integration/test_r2.py` passes.

### Step 18 — Listing probe against R2

- **Status:** ✅ done
- **Who:** Owner
- **Commit:** `docs: d008.s18 record the listing probe against R2`
- **R:** —
- **Model:** —
- **Review:** no

#### Scope

The confirmation that `obstore`'s `list` with `offset` returns the keys after it on R2, as `start-after` does (#25). Claude writes a throwaway script to the scratchpad that lists one day of AMBici's `station_status` prefix in `bikesharing-bronze` from a key in the middle of the day with `r2.py`'s listing; the owner runs it with bronze's read-only token in their shell's environment. Claude records the result in [Runtime and dependencies](#runtime-and-dependencies) › S3 client.

#### Reads

- [Runtime and dependencies](#runtime-and-dependencies) › S3 client, this design.

#### Do

1. Write the probe script to the scratchpad (Claude).
2. Run it with bronze's read-only token (owner).
3. Update the S3 client item with the result (Claude).

#### Check

- The listing holds only keys after the given one; if it does not, the finding goes back to this design before Step 19.

### Step 19 — Delta tables

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d008.s19 add the Delta tables with the insert-only MERGE and the control table`
- **R:** R20
- **Model:** opus · high
- **Review:** code

#### Scope

Table creation, the insert-only MERGE, `processed_objects`, the retry on conflict and the Parquet inputs of dbt.

- `pipeline/src/bikesharing/shell/delta.py` (new): [`bikesharing.shell.delta`](#bikesharingshelldelta).
- `pipeline/tests/integration/test_delta.py` (new): tables created with their schemas, a batch merged twice that adds no row (#4), the MERGE's metrics returned for DQR2, a conflict retried on a fresh handle, and the history and latest captures written as Parquet.

#### Reads

- [`bikesharing.shell.delta`](#bikesharingshelldelta), this design: the contract.
- [Delta writes](#delta-writes), this design.
- `deltalake`'s documentation of the storage options for R2: the name of the conditional put option.

#### Do

1. Write `pipeline/tests/integration/test_delta.py`.
2. Implement `pipeline/src/bikesharing/shell/delta.py`, with the conditional put option `deltalake`'s documentation names, `conditional_put` or `aws_conditional_put`; record which in [Delta writes](#delta-writes) › Conditional put.

#### Check

- `uv run --directory pipeline pytest tests/integration/test_delta.py` passes.

### Step 20 — dbt runner

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d008.s20 run dbt build in process and return its node statuses`
- **R:** R8
- **Model:** sonnet · high
- **Review:** no

#### Scope

`dbt build` in process with the batch's variables, returning its node statuses.

- `pipeline/src/bikesharing/shell/dbt_runner.py` (new): [`bikesharing.shell.dbt_runner`](#bikesharingshelldbt_runner).
- `pipeline/tests/integration/test_dbt_runner.py` (new): a build over the fixtures returns every node with its status and calls `on_node` for each, a failing data test ends in `fail` without stopping the others, and a parse error raises `DbtInvocationError`.

#### Reads

- [`bikesharing.shell.dbt_runner`](#bikesharingshelldbt_runner), this design: the contract.
- [s017 › P4, P7](../spikes/s017-dbt-in-the-pipeline.md#55-production-inputs): the node fields and the two-batch run in one process.

#### Do

1. Confirm what a bronze source does with an empty list of files, as in a batch with no object of one system; if the build fails, stop and report it as a deviation.
2. Confirm that `duckdb_session.connect` opens the scratch database once `dbt_build` returns, in the same process: Step 16 found that DuckDB reuses an instance of the same file still open in the process, whose locked configuration refuses `apply_sandbox` ("the configuration has been locked"); if it fails, stop and report it as a deviation.
3. Write `pipeline/tests/integration/test_dbt_runner.py`.
4. Implement `pipeline/src/bikesharing/shell/dbt_runner.py`.

#### Check

- `uv run --directory pipeline pytest tests/integration/test_dbt_runner.py` passes.

### Step 21 — Event log and heartbeat

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d008.s21 add the event log and the heartbeat pings`
- **R:** R14, R15
- **Model:** sonnet · high
- **Review:** code

#### Scope

Events to stdout and to the run's log object, and the pings to Healthchecks.io.

- `pipeline/src/bikesharing/shell/event_log.py` (new): [`bikesharing.shell.event_log`](#bikesharingshellevent_log).
- `pipeline/src/bikesharing/shell/heartbeat.py` (new): [`bikesharing.shell.heartbeat`](#bikesharingshellheartbeat).
- `pipeline/tests/integration/test_heartbeat.py` (new): `/start` then success (R14), `/fail` with its body (R15), and a ping retried and then given up, against a local stub of the check, with small timeouts.
- `pipeline/tests/integration/test_event_log.py` (new): each event to stdout as it happens and all of them in the log object.

#### Reads

- [`bikesharing.shell.event_log`](#bikesharingshellevent_log) and [`bikesharing.shell.heartbeat`](#bikesharingshellheartbeat), this design: the contracts.
- [Observability](#observability) › Log object and Heartbeat, this design.

#### Do

1. Write both test modules.
2. Implement `event_log.py`.
3. Implement `heartbeat.py`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` exits 0.

### Step 22 — Page component

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `build: d008.s22 add the page's component with the Worker's deployment configuration`
- **R:** —
- **Model:** sonnet · medium
- **Review:** no

#### Scope

`web/` with only what the page's deployment needs (#26).

- `web/.nvmrc` (new): `26.12.1`.
- `web/package.json` (new): `"private": true` and `wrangler` 4.165.0, pinned exactly.
- `web/package-lock.json` (new).
- `web/wrangler.jsonc` (new): the Worker `bikesharing-web` of static assets only ([ADR-0035](../decisions/0035-cloud-resource-naming.md)), its compatibility date and the assets directory `public/`.

#### Reads

- [Publishing](#publishing) › Worker configuration, this design.
- [cloudflare-worker.md](../../.claude/rules/code/cloudflare-worker.md) and [dependencies.md](../../.claude/rules/code/dependencies.md).
- `capture/wrangler.jsonc` and `capture/package.json`: the existing Worker's configuration, which the new one mirrors.

#### Do

1. Write `web/.nvmrc`.
2. Install `wrangler` with `npm install --save-exact wrangler@4.165.0` in `web/`.
3. Write `web/wrangler.jsonc`.

#### Check

- `npm ci --prefix web` installs `wrangler` 4.165.0 from the lockfile.

### Step 23 — Publishing

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d008.s23 publish the file by deploying the page with wrangler`
- **R:** R31
- **Model:** sonnet · high
- **Review:** security

#### Scope

The file's writing to the assets directory and `wrangler deploy` as a subprocess.

- `pipeline/src/bikesharing/shell/publishing.py` (new): [`bikesharing.shell.publishing`](#bikesharingshellpublishing).
- `pipeline/tests/integration/test_publishing.py` (new): the file written to the assets directory, `wrangler` called with `--config` and `--tag` and the token in its environment only, and a stand-in for `wrangler` that exits with an error returned as a failed deployment with its exit code and output (R31).

#### Reads

- [`bikesharing.shell.publishing`](#bikesharingshellpublishing), this design: the contract.
- [Publishing](#publishing) › Deployment tool and Failed deployment, this design.

#### Do

1. Write `pipeline/tests/integration/test_publishing.py`.
2. Implement `pipeline/src/bikesharing/shell/publishing.py`.

#### Check

- `uv run --directory pipeline pytest tests/integration/test_publishing.py` passes.

### Step 24 — Run end to end

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d008.s24 run the pipeline end to end with the exclusion list`
- **R:** R6, R7, R8, R14, R15, R20, R21, R22, R31
- **Model:** opus · high
- **Review:** code

#### Scope

A run end to end over local fixtures and tables, and the exclusion list.

- `pipeline/src/bikesharing/shell/run.py` (new): [`bikesharing.shell.run`](#bikesharingshellrun).
- `pipeline/config/excluded_objects.txt` (new): empty, with its format and its `TODO(T060.5):` marker (#8).
- `pipeline/tests/integration/test_run.py` (new): two batches in one process with a failing model and a contract violation, checking the tables and the log (R8, R20, R21); a run that stops between its two commits; a batch with an unreadable object (R22); an excluded key never processed; the published file built from the tables, a system with no capture keeping its earlier count (R6); a failed page deployment, with a stand-in for `wrangler` that exits with an error, that keeps the run's commits, logs `page_deploy_failed` and fails the run (R31); and the heartbeat's pings for each outcome against a local stub of the check, `/start` then success (R14), and `/fail` with `run_finished` and the failing event as its body (R15).
- `pipeline/tests/integration/test_latest_station_count_contract.py` (modified): the file built from the fixtures through the same models passes the schema (R7, [Publishing](#publishing) › CI check).

#### Reads

- [`bikesharing.shell.run`](#bikesharingshellrun), this design: the contract.
- [Tests and CI](#tests-and-ci) › Integration, shell, this design.
- [D9](#d9-a-failed-batch-halts-the-pipeline-until-t0605), this design.

#### Do

1. Write `pipeline/config/excluded_objects.txt`.
2. Write `pipeline/tests/integration/test_run.py`.
3. Update `pipeline/tests/integration/test_latest_station_count_contract.py`.
4. Implement `pipeline/src/bikesharing/shell/run.py`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` exits 0.

### Step 25 — Modal app

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d008.s25 add the Modal app with its image, functions and secrets`
- **R:** R11, R16, R23, R26, R27
- **Model:** sonnet · high
- **Review:** security

#### Scope

The platform module, with its image, both functions and their secrets, and ADR-0046's rule 4.

- `pipeline/modal_app.py` (new): [`modal_app`](#modal_app).
- `pipeline/pyproject.toml` (modified): mypy's override for `modal` ([Tests and CI](#tests-and-ci) › Platform separation).
- `pipeline/scripts/check-pipeline.sh` (modified): mypy also checks `modal_app.py`.
- `pipeline/tests/integration/test_platform_separation.py` (modified): rule 4's test, which fails if `modal_app.py` imports `duckdb` (DI11).

#### Reads

- [`modal_app`](#modal_app), this design: the contract.
- [Run operation on Modal](#run-operation-on-modal) and [Environments and configuration](#environments-and-configuration), this design.
- Modal's documentation of `Image.from_registry`, `add_local_dir`, `add_local_python_source`, `Secret.from_name` and `Cron`.

#### Do

1. Write rule 4's test in `pipeline/tests/integration/test_platform_separation.py`.
2. Update mypy's configuration in `pipeline/pyproject.toml` and its command in `pipeline/scripts/check-pipeline.sh`.
3. Implement `pipeline/modal_app.py`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` exits 0, with rule 4's test passing.
- `modal_app.py` declares the scheduled function with `timeout=600`, `max_containers=1` and no `retries`, and the one-off function with bronze's Secret only (R11, R16, R23, R26, R27).

### Step 26 — Deploy script

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `build: d008.s26 add the deploy script with its refusals, tag and smoke test`
- **R:** R9, R10
- **Model:** sonnet · high
- **Review:** code and security

#### Scope

The only deployment path, with its refusals, its tag and its smoke test.

- `pipeline/scripts/deploy.sh` (new): [Deploy script](#deploy-script).
- `pipeline/scripts/smoke_test.py` (new): the post-deploy smoke test ([Deploy script](#deploy-script)).
- `pipeline/tests/integration/test_deploy_script.py` (new): in a temporary Git repository with a stand-in for `uv` first on the `PATH`, which records its calls, the script refuses an uncommitted change, an untracked file and a commit other than `origin/main`, each with its cause, and never calls the stand-in (R10).

#### Reads

- [Deploy script](#deploy-script), this design.

#### Do

1. Write `pipeline/tests/integration/test_deploy_script.py`.
2. Write `pipeline/scripts/deploy.sh`.
3. Write `pipeline/scripts/smoke_test.py`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` exits 0.

### Step 27 — Platform probes

- **Status:** ✅ done
- **Who:** Owner
- **Commit:** `docs: d008.s27 record the platform probes`
- **R:** R16
- **Model:** —
- **Review:** no

#### Scope

The confirmations on Modal and Cloudflare that the Plan leaves to the build, each on a temporary resource; Claude writes the probes to the scratchpad and records each result in its section of this design.

- **Memory kill:** a temporary app with a function that exceeds its hard limit, deployed, invoked once and stopped: whether Modal retries it ([Run operation on Modal](#run-operation-on-modal) › Timeout and retries).
- **Local disk:** a temporary app, run once with `modal run`, with a function of `one_off_run`'s `cpu` and `memory` that writes a file larger than the container's memory to its local disk: whether local disk counts against memory ([Bronze reading](#bronze-reading) › Batch reading). The same function records the `threads` DuckDB detects in the container, since Step 16 found that the memory a sort needs grows with DuckDB's threads: with 14 threads, 128 MiB fell short where 256 MiB spilled ([Bronze reading](#bronze-reading) › Memory).
- **Modal's tag:** `modal deploy --tag` on `bikesharing-t0601-tag-probe` with a 40-character tag: where it shows in `modal app history --json`, its length limit, and whether Modal records the Git commit ([Deploy script](#deploy-script) › Tag).
- **wrangler's tag:** `wrangler deploy --tag` with a 40-character tag on a temporary Worker of static assets, `bikesharing-t0601-tag-probe` (#18).

#### Reads

- The sections each probe names, this design.

#### Do

1. Write the probes to the scratchpad (Claude).
2. Run each probe (owner).
3. Record each result in its section (Claude).

#### Check

- Each probe's section states its result; a tag that cannot hold 40 characters goes back to this design before Step 28, as D5 sets.

### Step 28 — Reference batch

- **Status:** ✅ done
- **Who:** Owner
- **Commit:** `docs: d008.s28 record the reference batch`; if the bound is lowered, that change goes first in its own commit, `fix: d008.s28 lower the batch bound to <N> objects`
- **R:** —
- **Model:** —
- **Review:** no

#### Scope

D6's reference batch: a one-off run, from the task's branch, of one full batch of 360 objects of real bronze, whose `peak_memory_mb` and `duration_s` confirm or lower the batch bound before the first deployment. Claude records the measures in Close › Implemented and, if the bound is lowered, changes `MAX_OBJECTS_PER_BATCH`.

#### Reads

- [D6](#d6-provisional-run-bounds) and [Run operation on Modal](#run-operation-on-modal) › Container size, this design.

#### Do

1. Run `one_off_run` on Modal from the task's branch (owner).
2. Read `run_finished`'s `peak_memory_mb` and `duration_s` in Modal's logs (owner).
3. Record the measures and, if needed, lower `MAX_OBJECTS_PER_BATCH` in `pipeline/src/bikesharing/core/settings.py` (Claude).

#### Check

- `peak_memory_mb` leaves margin below the container's 4 GiB, and the run ends within its time budget; otherwise the bound is lowered and the run repeated.

### Step 29 — Production rollout

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** one per stage, `feat: d008.s29 move the end instant to <stage>`, and the closing one, `docs: d008.s29 record the production checks`
- **R:** R9, R17
- **Model:** —
- **Review:** no

#### Scope

The first deployment, D8's stages and the checks of [Done when](#14-done-when) that need production data. The PR that ships the code carries `Refs #N`; each stage's PR moves `END_INSTANT` from a branch recreated from `main`; the closing PR, after the 14 days of [Cost recalibration](#cost-recalibration), records the checks and carries `Closes #N`.

#### Reads

- [D8](#d8-first-load-in-chronological-stages), [Done when](#14-done-when), [Deploy script](#deploy-script) and [Cost recalibration](#cost-recalibration), this design.

#### Do

1. Merge the task's PR and run `pipeline/scripts/deploy.sh` (owner); its smoke test's `run_started` and rows carry the SHA of `origin/main` (R9).
2. Check each stage when `stage_drained` is logged: runtime rules, reconciliation, run time and memory (owner); move `END_INSTANT` to the end of the first week, then to none, each by a PR and a deployment (Claude writes, owner merges and deploys).
3. Check the Healthchecks.io check's period and grace (R17), the spend limit and the pipeline's Cloudflare token (owner).
4. Compare `duration_s` and `peak_memory_mb` of the scheduled runs after the last stage with the thresholds that reopen ADR-0027 ([d007 › Carried-over inputs](d007-pipeline-design.md#carried-over-inputs)), review the 15-minute cadence against them (owner), and record the result in Close (Claude).
5. Measure R2's operations and storage over 14 days, recalibrate the cost model and set Cloudflare's R2 alerts ([Cost recalibration](#cost-recalibration)).
6. Measure the `pull_request` run's wall-clock and update [testing-strategy.md › Moving tests](../testing-strategy.md#moving-tests) (Claude).
7. Delete both `bikesharing-t0601-tag-probe` resources (owner).

#### Check

- Every item of [Done when](#14-done-when) holds.

## 4. Close

<!-- The record of what the task delivered, for whoever opens this design later. -->

### 4.1 Implemented

<!-- Component — what was delivered; tests passing. In a document-only task: Deliverable — what it holds. A parent also names the children's issues created at its close; this block is not updated as they progress, since their state lives in their issues and their own working documents. -->

- **Reference batch (Step 28):** a `one_off_run` from the task's branch on 2026-11-20, over the real bronze up to the configured end instant. It listed 106,103 objects (53,262 of AMBici and 52,841 of Bicing) in a full sweep that took about 74 s, and processed 4 batches: three of 360 objects and a last one of 245, 516,597 rows in all. The first batch, of 360 objects, inserted 140,094 rows in 9.3 s. `run_finished` reports `outcome` `succeeded`, `duration_s` 106.1 and `peak_memory_mb` 1,358 (about 1,295 MiB, 32% of the container's 4 GiB), and no rule failed. D6's bound of 360 objects is confirmed, `MAX_OBJECTS_PER_BATCH` stays, and the peak, with DuckDB's default 17 threads, leaves the `threads` of #30 as it is.

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
| DI1 | [3.1 Prerequisites](#31-prerequisites) › P6, P7 | The pipeline's R2 tokens expire after one year, as its Cloudflare token does | Credential rotation (NIST SP 800-53 IA-5): a leaked token stops working within a year; an expired one fails the run and the heartbeat alerts | Step 1 |
| DI2 | [Runtime and dependencies](#runtime-and-dependencies), [Step 1](#step-1--python-project), [Step 4](#step-4--check-script-and-ci-job) | The `dev` group adds `pytest-cov`, `pyproject.toml` sets `[tool.coverage.run] source = ["bikesharing"]`, and `check-pipeline.sh` runs pytest with `--cov` | `python.md` › Testing: line coverage is reported, never enforced | Step 1 |
| DI3 | [3.1 Prerequisites](#31-prerequisites) › P1, [Step 1](#step-1--python-project), [Step 4](#step-4--check-script-and-ci-job) | Local uv is 0.13.5, Homebrew's stable release, instead of 0.13.9, and Python is 3.14.9, the latest patch uv 0.13.5 downloads, instead of 3.14.10 | The machine's package manager keeps local tools; patches of 0.13 share the lockfile format, and CI's `setup-uv` pins no version | Step 1 |
| DI4 | `pipeline/dbt/dbt_project.yml`, `.gitignore` | dbt's anonymous usage telemetry is off (`send_anonymous_usage_stats: false`), and dbt's `.user.yml` is ignored by Git | Minimal data egress: the pipeline sends nothing to a third party its design does not name | Step 4 |
| DI5 | [2.4 File layout](#24-file-layout), [Step 5](#step-5--bronze-fixtures-and-read-schema) | The fixtures come from the capture spike's 13 days, are written by `pipeline/scripts/trim_fixtures.py` and listed with their provenance in `manifest.json`; a variety absent from the sample is a derived copy of a captured object | ADR-0037's rule (committed trimming script, provenance per fixture), as capture does; P11's one day lacks AMBici's station changes | Step 5 |
| DI6 | [`bikesharing.shell.duckdb_session`](#bikesharingshellduckdb_session), [`bikesharing.shell.dbt_runner`](#bikesharingshelldbt_runner), `pipeline/dbt/profiles.yml` | dbt's connection takes DuckDB's sandbox and memory settings from a dbt-duckdb plugin, `Plugin` in `duckdb_session`, applied once per database with the function `connect` also uses, following the adapter's plugin hook for connection setup | dbt-duckdb applies a profile's `settings` again on every cursor, which a sandboxed or locked DuckDB refuses, and `config_options` cannot set `allowed_directories`; D10's settings and their order stay as designed | Step 12 |
| DI7 | [Runtime and dependencies](#runtime-and-dependencies), [`bikesharing.shell.delta`](#bikesharingshelldelta), `pipeline/pyproject.toml` | `arro3-core` joins the runtime dependencies, and `record_processed` builds its MERGE's source with it instead of `pyarrow` | Every directly imported package is declared (ADR-0017); it is already locked as `deltalake`'s own Arrow library, so the image gains no package, and its use is a few lines a test covers | Step 19 |
| DI8 | [Observability](#observability), [`bikesharing.core.events`](#bikesharingcoreevents) | `run_finished` carries `error_type` and `error`, as `batch_failed` and capture's failure events do, holding an exception raised outside a batch | Structured logging of the exception on the terminal event: the log object and the failure ping carry the cause of a run that fails outside its batches | Step 24 |
| DI9 | [`bikesharing.shell.run`](#bikesharingshellrun) | The file's schema moves from `PublishTarget` to `RunConfig` as `file_schema`, so a one-off run builds and validates the file too | A producer validates its contract whether or not it deploys: a one-off run from a branch checks DQR14 on real bronze before the merge | Step 24 |
| DI10 | [`bikesharing.shell.publishing`](#bikesharingshellpublishing) | `wrangler` is killed after 120 s, and a timeout or a `wrangler` that cannot start is returned as a failed deployment, exit codes 124 and 127 | Every subprocess call is bounded: a hung deployment ends as `page_deploy_failed` well inside the run's timeout, and the run still logs, uploads and pings | Step 24 |
| DI11 | [Component structure](#component-structure), [Tests and CI](#tests-and-ci), [Step 25](#step-25--modal-app) | ADR-0046's rule 4 is a test of `modal_app.py`'s imports from its syntax tree, in `test_platform_separation.py`, not an import-linter contract | Import-linter takes only packages as root packages and `modal_app.py` is a single module; the test checks the same direct imports and fails the PR like a contract | Step 25 |
| DI12 | [Environments and configuration](#environments-and-configuration), [`modal_app`](#modal_app), [Component structure](#component-structure), [Tests and CI](#tests-and-ci), [Step 25](#step-25--modal-app) | The one-off function moves to its own Modal app in `modal_one_off.py`, the image and the Secrets' references to `modal_image.py`, and `modal_app.py` keeps the scheduled function only; R26 and R27 become a test of the one-off module's names | `modal run` creates every function of its app: `scheduled_run`, with production's credentials, ran during Step 28's one-off run and only the empty code version stopped it; least privilege per app makes R26 and R27 hold whatever the owner's shell holds; also, the image's `uv sync` takes `--default-index https://pypi.org/simple`, since Modal's builder mirror makes `--locked` fail on the lockfile's index, and installs `libatomic1`, which Node's binary links | Step 28 |
