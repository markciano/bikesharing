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
Current: where work resumes, with only the context the next session needs: the step being implemented, or the block and section of the design; — when complete. A document-only task names the section. -->

- State: Draft 📝
- Phase: [x] Spec · [ ] Plan · [ ] Plan review · [ ] Steps · [ ] Steps review
- Current: Plan › 1, the list of concerns in dependency order, from Carried-over inputs and these items left by the Spec: where a one-off `modal run` from a branch writes, a bucket apart from production (R26, R27); where D8's end instant lives and how it is changed, a Modal Secret or the repository; whether T060.1 already sends the copy of events over OTLP or leaves it to T060.2 ([ADR-0049](../decisions/0049-log-events-copied-to-monitoring-over-otlp.md)); how an unreadable bronze object is excluded until T060.5 (D9, R22)

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

The heartbeat of [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md) sends the failure signal on the first failed run: the platform does not retry a run, since the next scheduled run is its retry, as a failed batch stays pending ([d007 › D7](d007-pipeline-design.md#d7-catch-up-in-bounded-batches)), following the scheduled cycle as the retry of an idempotent pipeline. The monitor expects a signal every 15 min, the cadence, with 15 min of grace, which covers a run up to its 10-minute timeout (D6). The owner then learns of a failed run at once, of a run that hangs when it reaches its timeout, and of a run that never starts about 30 min after the last signal.

What would change it: alerts from transient failures that the next run resolves, frequent enough to be ignored, change the retries.

Rejected: one platform retry 1 min after a failure, since it can overlap the next scheduled run, which then waits, and delays the alert of a real failure.

#### D8. First load in chronological stages

The first load of the bronze captured before the first deployment drains in three stages, following an incremental backfill with a check between stages: first the oldest day of captures, then the first week, then everything. The pipeline processes only the bronze objects captured up to a configured end instant, oldest first as in [d007 › D7](d007-pipeline-design.md#d7-catch-up-in-bounded-batches); the owner checks each stage's runtime rules, reconciliation, run time and memory, and moves the end instant forward for the next one. Once the last stage drains, the end instant is removed and the pipeline processes every object, as d007 › D7 sets. Each stage then exercises a larger volume only after the smaller one passed, in the same order and with the same code as any backlog.

While an end instant is set, a run that finds no pending object captured up to it logs an event of severity warn, following the completion notice of a backfill: it tells the owner that a stage has drained and that it is time to check it and move the end instant. Until T060.2 builds the alerts on warn events ([d007 › R10](d007-pipeline-design.md#13-requirements)), the owner reads it in the run's logs on Modal, and in the run's events on R2 when those are not enough; the end instant's removal after the last stage is checked in Done when.

Rejected: draining each stage in one-off runs that take the end instant as an argument, with no end instant in the scheduled run, since a large stage would need many runs launched by hand within D6's time budget; draining the first load as any backlog, since a problem that only shows at volume would be found in the middle of it; stages from the most recent captures backwards, since the current file it gives earlier has no visitors until T041 ([d007 › D2](d007-pipeline-design.md#d2-visualization-after-all-slices)), the first backlog is estimated to drain in under a day, and it reverses d007 › D7's order.

#### D9. A failed batch halts the pipeline until T060.5

Until T060.5 builds the set-aside with redrive and the quarantine table ([d007 › D7](d007-pipeline-design.md#d7-catch-up-in-bounded-batches)), a batch that fails a runtime rule of severity error on its rows (DQR1, DQR2, DQR13), holds a row that fails its column's schema, or holds a bronze object that cannot be read fails the run and stays pending, following fail-fast: nothing of the batch is committed, the next run retries it, and the heartbeat sends the failure signal on every run until a new code version fixes it (D7). The pipeline then never commits a row a rule rejected, and while it halts the published file only grows older, with no visitors until T041 ([d007 › D2](d007-pipeline-design.md#d2-visualization-after-all-slices)). This is a provisional state of [d007 › D7](d007-pipeline-design.md#d7-catch-up-in-bounded-batches), not a change to it: D7 rejects this halt since one faulty object would freeze the page, which cannot happen before T041, and T041 comes after T060.5. A rule of severity warn (DQR11, DQR12) does not halt it, and a file that fails DQR14 follows [d007 › R2](d007-pipeline-design.md#13-requirements): it is not deployed and the last file that passed is kept.

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
- **R20** If a batch fails a runtime rule of severity error on its rows (DQR1, DQR2, DQR13), then the pipeline shall commit nothing of the batch, leave it pending and fail the run. (D9)
- **R21** If a batch holds a row that fails its column's schema, then the pipeline shall commit nothing of the batch, leave it pending and fail the run. (D9)
- **R22** If a batch holds a bronze object that cannot be read, then the pipeline shall commit nothing of the batch, leave it pending and fail the run. (D9)
- **R23** The pipeline shall receive its secrets only as Modal Secrets. (TH5)
- **R24** The pipeline shall not write a secret's value, the heartbeat's URL included, to its events or error messages. (TH1, TH5)
- **R25** The pipeline shall pass feed values to SQL only as data or parameters, never as SQL text. (TH2)
- **R26** While a run is a one-off run of code that is not deployed, the pipeline shall not write to the production lakehouse. (TH3)
- **R27** While a run is a one-off run of code that is not deployed, the pipeline shall not deploy the page. (TH3)
- **R28** The pipeline shall let DuckDB reach only the pipeline's buckets. (TH9)
- **R29** The pipeline shall load no DuckDB extension at run time. (TH9)

### 1.4 Done when

<!-- Optional. Only what closes this task and Requirements cannot express: operational actions, checks on real data, understanding. The general closing rule is checked in `.claude/skills/implement/review.md`. -->

- Before the first deployment, the memory of a reference batch on real data confirms or lowers the batch bound (D6).
- The owner has set Modal's spend limit (TH7).
- The owner has created the pipeline's own Cloudflare token, with the Workers Editor role and an expiry, and the run deploys the page with it (D10, TH8).
- The first load has drained through D8's three stages, each with its runtime rules, reconciliation, run time and memory checked before the next, and the end instant removed after the last (D8).
- The pipeline runs on Modal every 15 min in production; its run time and memory are measured on the feeds' real volume, and the cadence and [ADR-0027](../decisions/0027-modal-as-execution-platform.md) are reviewed against them ([d007 › Children](d007-pipeline-design.md#16-children)).

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

The package `bikesharing` has the two subpackages of [ADR-0046](../decisions/0046-functional-core-imperative-shell-for-the-pipeline.md), `bikesharing.core` and `bikesharing.shell`. The platform module is `pipeline/modal_app.py`, at the component's root and outside `src/`, so it is never installed with the package; it is the only file that imports `modal`, and it adds the package to the image with `add_local_python_source("bikesharing")`. **#2**

ADR-0046's rules 1–4 are import-linter contracts in `pyproject.toml`, with `bikesharing` and `modal_app` as root packages: rule 1 forbids `modal` in `bikesharing`, rule 2 forbids `duckdb`, `dbt` and HTTP clients in `bikesharing.core`, rule 3 is a layers contract of `shell` above `core`, and rule 4 forbids `duckdb` in `modal_app`. A forbidden contract on an external package needs `include_external_packages = true`; the step that writes the contracts confirms it with a contract that must fail, and falls back to PyTestArch if import-linter cannot express it. Rule 5 is a CI test that imports the package and builds its configuration in an environment synced without Modal's SDK, which sits in its own dependency group.

Options considered for the component folder:

- `pipeline/` as the component folder (chosen): pros, the runtime and lockfile stay in the component's own files ([ADR-0016](../decisions/0016-runtime-versions-pinned-per-component.md), [ADR-0017](../decisions/0017-dependencies-locked-per-component.md)) and its CI job targets one folder, as with `capture/`; cons, longer paths and an edit to CLAUDE.md › Project structure.
- The repository root, the layout of a single-project Python repository: pros, shorter paths; cons, the Python project shares the root with the documentation's Node project, and `scripts/` and `tests/` mix the pipeline with the rest.

Options considered for the platform module:

- `pipeline/modal_app.py`, outside `src/` (chosen): pros, PyPA's `src/` layout keeps it out of the installed package, so rule 5 holds by construction, and its name states the platform; cons, import-linter sees it only once it is added to its root packages.
- `pipeline/src/bikesharing_modal/`, a second top-level package: pros, import-linter sees it as one more package; cons, two packages declared in `pyproject.toml`, and rule 5 depends on keeping one of them out of the installation.

#### Runtime and dependencies

- **Python:** `pipeline/.python-version` holds the exact patch of 3.14, with `requires-python = ">=3.14,<3.15"`; if `uv sync --locked` or the tests fail on 3.14, both move to 3.13.17 and the cause is recorded as a finding.
- **Python on Modal:** the image is built from the official `python:<patch>-slim-bookworm` image, whose patch `modal_app.py` reads from `.python-version` at deploy time, so production runs the patch that passed CI. **#3**
- **Manifest and lockfile:** `pyproject.toml` declares the runtime dependencies (DuckDB on its pinned 2.0.x patch, `dbt-core` 1.12.7, `dbt-duckdb` 1.11.1, `deltalake`) and two dependency groups: `dev` (pytest, ruff, mypy, import-linter) and `platform` (Modal's SDK). `uv.lock` locks them all. `mashumaro>=3.15` is a constraint on a transitive dependency of dbt, set in `[tool.uv] constraint-dependencies`, against the truncation of float model versions below 3.15.
- **Image dependencies:** the image installs only the runtime dependencies, at the versions locked in `uv.lock`; Modal provides its own client inside the container.
- **Checks:** `pipeline/scripts/check-pipeline.sh` runs ruff, mypy, import-linter and pytest; it is the Check of every code step and the command of the pipeline's CI job.

Options considered for the Python patch on Modal:

- The official image with the exact patch (chosen): pros, one line in `modal_app.py`, and the patch matches local and CI; cons, a new patch waits for its official image, published within hours of the release.
- Modal's `debian_slim` with the exact patch installed by `uv python install`: pros, the same build of Python as local and CI; cons, two or three more image steps for the same patch.
- Modal's `debian_slim(python_version="3.14")`: pros, the simplest image; cons, Modal picks the patch, so production can run one CI never tested.

#### Delta writes

- **Fact rows:** a batch's station stock is written with an insert-only MERGE on the natural key (system, `station_id`, capture instant), bounded by the batch's range of capture instants, so that processing an object again adds only the rows the table does not hold ([ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md)) and no row is updated or deleted (DQR2).
- **Partitioning:** the station stock is partitioned by the row's local calendar date ([ADR-0041](../decisions/0041-utc-timestamps-local-calendar-keys.md)), so that a normal run's MERGE and the read of the latest counts touch one partition, and retention drops whole partitions. The MERGE's partition predicate is the set of local dates the batch's own rows carry. **#5**
- **Processing state:** a Delta table, `processed_objects`, holds one row per bronze object a run has processed: its key, system, feed, capture instant, status, run ID and code version. A bronze object is pending while it has no row there. Each batch commits its fact rows first and its rows in `processed_objects` second, following an idempotent sink with a progress log written after it: a run that stops between the two commits leaves the batch pending, and processing it again adds no fact row. In T060.1 the only status is `processed`; T060.5 adds the status of a batch set aside and of an object with rows in quarantine. The table can be rebuilt from the fact rows, since each row's bronze object follows from its system, feed and capture instant ([ADR-0043](../decisions/0043-lineage-at-four-levels.md)). **#4**
- **Conflicts:** a MERGE that conflicts with a concurrent commit is retried on a fresh table handle. Runs never overlap, so a conflict means a one-off run wrote at the same time.
- **Table creation:** the shell creates each missing table with its explicit schema at the start of a run, before any write; no write uses `schema_mode="merge"`, so a column change takes a new code version.
- **Table maintenance:** the run neither compacts nor vacuums its tables; their maintenance, with silver's retention, is a scheduled job of its own, T072. Until then each partition keeps the small files of its commits, which only reads of past days touch. **#6**
- **Conditional put:** `deltalake` writes to R2 with conditional put; the step that writes the storage options confirms whether the option is `conditional_put` or `aws_conditional_put`.

Options considered for the processing state:

- A control table of processed objects (chosen): pros, it records objects that produce no rows, T060.5 extends it with one status, and pending objects are read from a small table; cons, one more table, and a second commit per batch.
- Derived from the fact rows, as the distinct pairs of system and capture instant: pros, no extra table; cons, an object with no rows looks pending for ever, each fact table of later children needs its own derivation, and T060.5 needs a table for batches set aside anyway.

Options considered for the partitioning:

- By local date, one partition per day (chosen): pros, each run reads one day, the table is read by local day, and the column already exists; cons, about 96 small files a day per partition until they are compacted.
- By UTC date, one partition per day: pros, the same reach per run; cons, a query for one local day touches two partitions, and the table carries a column used only to partition it.
- By week or by month: pros, fewer partitions; cons, the same number of files a day, and each run's MERGE and read scan up to a week or a month.

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
