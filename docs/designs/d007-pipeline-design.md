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
- **New ADRs from this doc:** [ADR-0042](../decisions/0042-data-quality-classes-and-severity.md), [ADR-0043](../decisions/0043-lineage-at-four-levels.md), [ADR-0044](../decisions/0044-deployments-tagged-with-their-commit.md), [ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md)

## Status

<!-- State: Draft 📝 · Complete ✅.
Phase: the blocks and reviews completed. -->

- State: Draft 📝
- Phase: [x] Spec · [x] Plan · [ ] Plan review
- Next: Plan review (`review-plan`), the final review of this parent. The next log entry is #13.

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

Observability comes right after T060.1, following the SRE practice of monitoring from the first production release: from T060.1 the pipeline runs 24/7, and a run that fails publishes nothing with no other sign (D4). It needs only what T060.1 and capture already emit, the log events of [ADR-0036](../decisions/0036-log-convention-across-components.md), so a later child's rules reach its alerts with no change, and a later indicator, such as DQM4, only adds its target. From T060.1, a run that fails or never starts reaches the owner through the heartbeat of [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md), which T060.1 builds. Until T060.2 closes, a batch set aside or a failed rule of severity warn reaches the owner late, since its run ends well; the risk is accepted, since the page has no visitors until T041 (D2) and D7 recovers every batch.

After T060.2, no child depends on another, so they follow increasing difficulty: each adds one new kind of work to what the previous ones built. The stock by vehicle type repeats T060.1's pattern with one more dimension; the stock movements compare each count with the previous one of its station, across runs; the historical load brings a new source, a bulk load that can be rerun and its check against real-time capture. The two real-time processes share one child, since neither takes an architecture decision.

What would change it: the measurements of T060.1 can reopen [ADR-0027](../decisions/0027-modal-as-execution-platform.md) (Carried-over inputs › Execution platform check); the later children are then built on the platform that review keeps. If T060.3's steps exceed ten, its design splits it into one child per process.

Rejected: a split by layer (silver, then gold), since silver would be built with no consumer to validate it, and real runs would be measured late; observability as the last child, since two children would be built with the pipeline in production and no alert of a failed run; a provisional alert in T060.1, since it would take T060.2's choice of tool early and be thrown away; one child per business process, since the stock by vehicle type would take a full design and pull request for little to decide; the historical load right after T060.1, since nothing depends on it and the archives are already held by the owner.

#### D2. Visualization after all slices

Each slice ends at a published file, not at a page. The public page (T041) is built once every business process publishes, so it is designed as a whole. Without a page, a slice is validated by data tests on its silver and gold tables, by reconciling its row counts from bronze to silver to gold, and by one acceptance query on gold per question it closes, checked on real data. Each published file has a fixed contract, a JSON Schema checked by a contract test ([ADR-0015](../decisions/0015-contract-tests-by-contract-kind.md)) in CI and by a runtime rule before every publish (D4), which is what T041 builds on.

What would change it: if T041 needs a file shaped differently, the contract and its test change in T041.

Rejected: a minimal page after T060.1, to validate the file's shape and the page's deployment early, since the data validation above does not need a page and T060.1 already deploys the file.

#### D3. Continuous mode with a 15-minute cadence

The pipeline runs 24/7 on a schedule, every 15 minutes, so the visitor sees data about 17 minutes old (cadence plus a run of about 2 min, not measured). This refines [d002 › R3](d002-requirements.md#requirements), and the same data age is the freshness of every question answered from the current state, [d002 › Q1, Q2 and Q5](d002-requirements.md#guiding-questions). The cadence starts with margin because its cost estimate rests on a run time nobody has measured yet ([s012 › D1](../spikes/s012-execution-target.md#d1-execution-platform)). **#12**

What would change it: when the runs measured in T060.1 show that a 10-minute cadence costs less per month than Modal's monthly credit of $30, the cadence lowers to 10 min. It does not go below 10 min, the shortest interval R2's Class B quota allows running 24/7 ([s010 › P5](../spikes/s010-storage-table-format.md#production-inputs)). The review uses the cost Modal bills for the measured runs, container start included, and the data age they reach.

Rejected: on-demand runs, since the station status (d002's Q1) must stay current with no one asking for it; a 10-minute cadence from the start, since it would rest on the unmeasured run time.

#### D4. Data quality in four classes

The data quality catalog sorts every rule of [data-model.md › Data contract](../data-model.md#data-contract), every indicator and every new check into four classes, following the dimensions of DAMA-DMBOK and ISO/IEC 25012. The runtime rules and the quality indicators form the catalog, in a document of their own apart from the model, as the Open Data Contract Standard keeps quality apart from the schema; the Plan fixes its file and format. A class sets how the item is verified:

| Class | What it is | Verified by | Items of the Data contract |
|---|---|---|---|
| Transformation spec | How a table or value is built | Unit or integration test in CI, on fixtures | TR1–TR53 |
| Runtime rule | What must always hold on real data | Data test in every run | DQR1–DQR10 |
| Quality indicator | A measure tracked over time | Gold table or observability, queried by the owner | DQM1–DQM8, the first three in the review table |
| Documentation | The model's structure, worksheets, source cards and the feeds read | Inspection | RDM1–RDM6 |

A column's type, nullability and accepted values are its schema, cells of its row in its table's worksheet with no ID, checked in every run; the catalog holds only what no column's schema states. Until their worksheets exist, TR44's nullability and TR50's domain stay as transformation specs. **#1**

Besides the Data contract, these checks join the catalog:

| ID | Check | Class | Dimension | Severity |
|---|---|---|---|---|
| DQR11 | Schema drift: a bronze feed adds or drops a field of those the model reads (RDM2, RDM6) | Runtime rule | Validity | warn |
| DQR12 | Volume: a capture lists fewer stations than the recent median, by more than the threshold the slice building it fixes | Runtime rule | Completeness | warn |
| DQR13 | Reconciliation: the rows a run adds to silver and gold match the items it reads from bronze, by count, or by total in a gold table that aggregates | Runtime rule | Completeness | error |
| DQR14 | Published file contract: each file matches its JSON Schema (D2) before it is deployed | Runtime rule | Validity | error |
| DQM9 | Counts above `capacity`: the share of station items whose vehicles and docks exceed the station's `capacity`, leaving out AMBici's +P stations (TR44), whose bikes in +P spaces exceed it by design | Quality indicator | Consistency | — |
| DQM10 | Published file age: the time since the capture of the data in each file the page serves, which alerts the owner when it exceeds one cadence plus one run ([d002 › R3](d002-requirements.md#requirements)) | Quality indicator | Timeliness | — |

Severity follows who causes a failure. A rule on the pipeline's own logic fails with severity error, following Write-Audit-Publish at both points where data becomes visible: each batch is audited before it is committed to silver and gold, and each file the page serves is audited before it is deployed, at the end of the run. A batch that fails commits nothing and is set aside until a new code version (D7); a file that fails is not deployed, and the run ends with no failure signal. Either way the page keeps the last file that passed and the failure is logged in the run's events, so the visitor sees at most an older data age, or a gap in the history until the batch returns. A rule on a provider's data fails with severity warn: the failure is logged and the batch is committed. The owner learns of a failure of either severity through observability (T060.2), not through the heartbeat, which reports runs that fail or never start. **#9**

A row that fails its column's schema is quarantined instead, following a quarantine table: it is written there with the check it failed and the bronze object it comes from, the failure is logged, and the rest of its batch publishes. A provider's new value then removes only its rows from the page, never shows the visitor a value outside the schema, and reaches the owner through observability like any failed rule. **#1**

A quality indicator is kept if it is actionable, when the owner acts on capture, on a provider or on the model's reference data as it moves, or if it measures a provider's quality, which answers [d002 › Q2](d002-requirements.md#guiding-questions). DQM4, DQM5, DQM8 and the counts above `capacity` form each provider's scorecard. An indicator that measures silver and gold is built by the pipeline as a gold table; one that measures something outside the model is built by the observability child: DQM10, the age of the files the page serves, which the pipeline cannot measure while it is not running, and DQM11, [d002 › R14](d002-requirements.md#requirements), which reads capture's logs. **#1** TR52, a station's service, measures the business, not its data, and stays in the model outside the catalog.

Each quality indicator has a target, such as a minimum monthly completeness. Capture's completeness target of [d004 › D6](d004-bronze-data-capture.md) joins the catalog. An initial value comes from what the source cards measured on real captures, and it is reviewed against weeks of production indicators before a child closes: by T060.2, which builds the alerts, for the indicators built up to it, and by the child that builds any later one, following the SRE practice of setting an objective from a measured baseline. This task builds the whole catalog; T042 is absorbed by it. **#11**

Frozen counts also reach the visitor: a published file that holds a station's latest count marks it when that count is frozen (DQM5), so a stale count is never shown as current. How the page shows the mark is decided by T041.

Rejected: severity warn for rules on the pipeline's logic, since the visitor could then see wrong data with no sign of it; severity error for rules on a provider's data, since the page would stop for what the project cannot fix; a rule that blocks counts above `capacity`, since GBFS defines no relation between the two and both are kept as published; frozen counts for the owner only, since the visitor could then trust a count hours old.

#### D5. Lineage at four levels

Lineage is covered at the four levels that OpenLineage and Kimball's audit dimension name, adding as little as each level needs:

| Level | Question | Where it is answered |
|---|---|---|
| Table | Which tables feed which | The bus matrix and the table worksheets ([d005](d005-data-model.md)) |
| Column | Which source field a column comes from | The source field dictionary (RDM5, RDM6) |
| Run | What a run read and wrote, and its outcome | The run's log events, kept 30 days ([ADR-0036](../decisions/0036-log-convention-across-components.md)) |
| Row | Which run and code version wrote a row, and which bronze object it comes from | Every silver and gold row carries the ID of the run that wrote it and the code version of that run, kept as long as the row; a silver row's bronze object follows from its system, feed and capture instant, since bronze is kept indefinitely ([ADR-0021](../decisions/0021-retention-per-layer.md)) |

Rejected: a table of runs, with the bronze object's key in every silver row and the configuration version of each run, since this project does not need more than the levels above; the run's ID alone in each row, since the code version would be lost with the logs and the Delta history after 30 days at most.

#### D6. Deployments tagged with their commit

Every production deployment is tagged with the commit it deploys, following Twelve-Factor's unique ID for each release. Each component deploys through a deploy script of its own, run instead of the platform's command: it deploys only when the working tree is clean and its commit is the latest of `main`, and passes that commit's SHA as the deployment's tag. The platform's version history then names the commit behind each deployment, which each component's own version in what it produces leads to: capture's Worker version ID ([ADR-0036](../decisions/0036-log-convention-across-components.md)), the pipeline's code version in its rows and logs (D5). The page, which the pipeline redeploys in its runs ([ADR-0033](../decisions/0033-data-published-by-redeploying-static-assets.md)), is tagged with the code version of the run that deploys it.

The script takes its token from the environment and asks for nothing, so a CI job can run it unchanged (Out of scope).

Rejected: finding a deployment's commit as the last merge to `main` before its time, since the lookup is manual and gives the wrong commit for a deployment from an out-of-date or modified local copy; one health query reading every component's running version, since each platform's history already answers an occasional lookup. **#8**

#### D7. Catch-up in bounded batches

Each run processes the bronze objects no run has processed yet, whatever their capture instant, in bounded batches, oldest first, one after another until none is left or its time budget is spent, and then ends, following the drain mode of bounded micro-batches (Spark's `AvailableNow` trigger). Each batch is audited and committed to silver and gold as it ends (D4), so a failure keeps what earlier batches committed; the page's files are generated, audited and deployed once, at the end of the run. **#9** Processing an object again adds no rows, and a run never starts while another is running, so scheduled runs wait while a run drains and the cadence resumes by itself.

A batch whose processing fails, on reading, writing or the platform, stays pending and is retried by the next run. A batch that fails a runtime rule of severity error is set aside, following a dead-letter queue with redrive: the run logs it with its rule (D4) and goes on with the next batch, and every batch set aside returns to pending when a new code version is deployed (D5). Each batch is processed from bronze as a whole, so nothing of a failed batch counts as done. A bronze object with rows in quarantine (D4) also returns to pending with a new code version, and processing it again adds only the rows silver and gold do not hold yet. **#1**

A backlog, from the first load of the bronze captured so far or from an outage of capture or Modal, drains with the same code, in consecutive runs when it exceeds one run's time budget, and an object that reaches bronze late, or a batch that returns from being set aside, enters the next run. While a backlog drains, the published file serves older data and its age says so (D4). A batch is bounded in objects and in bytes so that it fits in a run's memory with margin, and an object above the byte bound on its own is set aside like a batch that fails a rule (D8).

A run takes no further batch once the time it has spent reaches its time budget, a fixed value: the run's timeout less the longest batch measured and the run's close (generating, auditing and deploying the files, uploading the logs, signalling the heartbeat). It then closes and ends well, leaving the rest pending and logging how many objects remain, following a graceful shutdown before a deadline. The timeout is a backstop for a run that hangs. T060.1 fixes both bounds, the time budget and the timeout from the memory and run time it measures. **#10** How a late object changes the stock movements already derived is decided by T060.3.

What would change it: if the pipeline processed bronze slower than capture writes it, a backlog would never drain; the run's memory or the platform then change in T060.1's review of [ADR-0027](../decisions/0027-modal-as-execution-platform.md).

Rejected: stopping at a batch that fails a rule until the code is fixed, since one faulty object would freeze the page; one batch per run, since a backlog would drain by one batch per cadence; a fixed window, each run processing only the captures of its last cadence, since an outage would leave a gap until a manual reload; a separate first load followed by unbounded incremental runs, since it needs two code paths and a long outage could still overflow a run.

#### D8. Pipeline security threats

One STRIDE pass covers what this design adds, following threat modelling per change: storage access is set by [ADR-0023](../decisions/0023-storage-security-baseline.md), the pipeline's runtime on Modal by [s012 › D3](../spikes/s012-execution-target.md#d3-pipeline-security), and the heartbeat's secret by [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md). What a child adds, a tool, a source or a credential, gets its own pass in that child's design (Children).

| # | Threat (STRIDE) | Impact | Control | Requirement |
|---|---|---|---|---|
| `TH1` | Tampering: the record of which bronze objects are processed or set aside (D7) is altered or lost | Batches skipped, leaving a gap, or processed again | Only the pipeline's token writes to the lakehouse bucket (ADR-0023); processing again adds no rows (D7); the record can be rebuilt from bronze and the silver rows' lineage (D5) | R14, R20 |
| `TH2` | Denial of service: a bronze object too large for a run's memory, from a provider or capture, kills every run that reads it | Its batch is retried in every run and blocks the backlog behind it | A batch is bounded in bytes as well as in objects (D7); an object above the bound is set aside like a batch that fails a rule, and logged | R13, R18 |
| `TH3` | Denial of wallet: a run that drains a large backlog, or a fault that keeps it busy, runs on Modal for hours | Cost beyond the pipeline's budget share ([ADR-0026](../decisions/0026-budget-shares-per-component.md)) | Each run takes no further batch once its time budget is spent, and ends well; a run that hangs ends at the timeout T060.1 fixes, a failure the heartbeat reports; the next run resumes the backlog (D7) | R17, R21, R25 |

Repudiation is covered by row lineage (D5): every row names the run and the code version that wrote it.

Rejected: one STRIDE pass over the whole pipeline here, since storage and runtime are already covered and each child knows best what its tool or source adds.

### 1.3 Requirements

<!-- Optional. The acceptance criteria, cited by number in the Test plan and the steps. They translate Decided at framing and cite the decision they come from; nothing is decided here.
One behaviour per requirement, verifiable, with a measurable threshold where one applies. Written in EARS:
- Ubiquitous: The <system> shall <response>.
- Event: When <trigger>, the <system> shall <response>.
- State: While <state>, the <system> shall <response>.
- Unwanted: If <condition>, then the <system> shall <response>.
- Optional: Where <feature is included>, the <system> shall <response>.
Only requirements specific to this task; project-wide rules (CLAUDE.md, ADRs) are not repeated. -->

- **R1** The pipeline shall publish each file the page serves with a JSON Schema contract, checked by a contract test in CI. (D2)
- **R2** If a file fails its JSON Schema, then the pipeline shall not deploy it, keep the last file that passed, log the failure in the run's events and end the run with no failure signal. (D2, D4, #9)
- **R3** The pipeline shall run every 15 min, 24/7. (D3)
- **R4** The pipeline shall check every runtime rule of the quality catalog, and every column against its schema, in every run. (D4, #1)
- **R5** If a batch fails a runtime rule of severity error, then the pipeline shall commit nothing from it, set it aside and log the failure with its rule in the run's events. (D4, D7, #9)
- **R6** If a batch fails a runtime rule of severity warn, then the pipeline shall log the failure with its rule in the run's events and commit the batch. (D4, #9)
- **R7** The pipeline shall build each quality indicator of the catalog that measures silver and gold as a gold table, with its target. (D4)
- **R8** Where a published file holds a station's latest count, the pipeline shall mark the count when it is frozen (DQM5). (D4)
- **R9** When the age of a published file exceeds one cadence plus one run, the observability shall alert the owner. (D4)
- **R10** When a batch fails a runtime rule of either severity, or a row is quarantined, the observability shall alert the owner. (D4, #1)
- **R11** The pipeline shall write in every silver and gold row the ID of the run that wrote it and that run's code version. (D5)
- **R12** The pipeline shall log, for each run, what it read, what it wrote and its outcome. (D5)
- **R13** When a run starts, the pipeline shall process the bronze objects no run has processed yet, oldest first, in batches bounded in objects and in bytes, one after another until none is left or the run's time budget is spent. (D7, #10)
- **R14** When processing a bronze object again, the pipeline shall add no row that silver and gold already hold. (D7, #1)
- **R15** While a run is running, the pipeline shall not start another run. (D7)
- **R16** When a batch passes its audit, the pipeline shall commit it to silver and gold before processing the next one. (D7, #9)
- **R17** If a batch fails on reading, writing or the platform, then the pipeline shall leave it pending for the next run. (D7)
- **R18** If a bronze object on its own exceeds the batch's byte bound, then the pipeline shall set it aside and log it. (D7, D8)
- **R19** When a new code version is deployed, the pipeline shall return every batch set aside, and every bronze object with rows in quarantine, to pending. (D7, #1)
- **R20** The pipeline shall rebuild its record of the bronze objects processed and set aside from bronze and the silver rows' lineage. (D8)
- **R21** If a run reaches its timeout, then the pipeline shall end it and signal a failure to the heartbeat. (D8)
- **R22** If a row fails its column's schema, then the pipeline shall write it to the quarantine table with the check it failed and its bronze object, log the failure in the run's events, and commit the rest of its batch. (D4, D7, #1, #9)
- **R23** If the working tree is not clean, or its commit is not the latest of `main`, then the pipeline's deploy script shall not deploy; otherwise it shall tag the deployment with that commit's SHA. (D6, #8)
- **R24** When the pipeline deploys the page, it shall tag the deployment with the run's code version. (D6, #8)
- **R25** When the time a run has spent reaches its time budget, the pipeline shall take no further batch, leave the rest pending, log how many objects remain, and end the run with no failure signal. (D7, D8, #10)

### 1.4 Done when

<!-- Optional. Only what closes this task and Requirements cannot express: operational actions, checks on real data, understanding. The general closing rule is checked in `.claude/skills/implement/review.md`. -->

- T060.1–T060.4 exist as sub-issues of T060, each with the scope of Children and blocked by the tasks it depends on.

### 1.5 Out of scope

- Capture's deploy script, with the checks and the tag of D6, built after the pipeline — T065
- Deployments from GitHub Actions on merge to `main` (continuous deployment), running each component's deploy script — T066

### 1.6 Children

<!-- Parent only. The child map, in build order: each child's scope (e.g. the business process it builds), the questions or requirements it closes, the children it depends on, and the condition that closes it. Each child has its own working document, which cites the parent's decisions instead of repeating them. Every open question and requirement of the parent is closed by the parent or by one child. The parent's Done when: its Open questions closed and its children created. -->

| Child | Scope | Closes | Depends on | Done when |
|---|---|---|---|---|
| T060.1 | The station stock from real-time capture as a walking skeleton (D1), with the conformed dimensions Date, Time of day, System and Station, up to its published file; its STRIDE pass covers the token that publishes the file and the secrets of Modal and the heartbeat (D8) | [d002 › Q1](d002-requirements.md#guiding-questions) without the split by type, Q2, Q3, Q5, Q8; [d002 › R23](d002-requirements.md#requirements), with the heartbeat of [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md); R1–R6, R7 but DQM4, R8, R11–R25; the cadence review (D3); the Carried-over inputs but where the history load runs | T064 | It runs on Modal every 15 min in production; one acceptance query per question passes on real data (D2); its run time and memory are measured, and the cadence and [ADR-0027](../decisions/0027-modal-as-execution-platform.md) are reviewed against them |
| T060.2 | Observability of capture and the pipeline: their logs queried together, and alerts on failed runtime rules and on quality indicators off target (D4); its STRIDE pass covers the tool's account and secret and who can read the logs (D8) | How the owner queries the logs of capture, the pipeline and the page together, and learns of a failed runtime rule of either severity; a script with the owner's common health queries, and whether it runs from a phone ([s013 › D5](../spikes/s013-visualization-tool.md#d5-no-separate-operations-panel), [P9](../spikes/s013-visualization-tool.md#55-production-inputs)); [d002 › R14](d002-requirements.md#requirements); R9, R10 | T060.1 | A failed rule of each severity reaches the owner; the targets of the indicators built by T060.1 and T060.2 are reviewed against weeks of production indicators (D4) |
| T060.3 | The stock by vehicle type, then the stock movements, from real-time capture, with the Vehicle type dimension | [d002 › Q1](d002-requirements.md#guiding-questions)'s split by type, Q4, Q6, Q7; R7 for DQM4, with its target in T060.2's alerts | T060.1, T060.2 | One acceptance query per question passes on real data (D2); DQM4's target is reviewed against weeks of production indicators (D4) |
| T060.4 | The historical archives, loaded into the station stock; its STRIDE pass covers the archives' upload and their integrity (D8) | How the archives reach R2 and are loaded, and where the load runs (Carried-over inputs › Run operation); how Bicing's archive is checked against real-time capture, the check handed over by [d002 › Out of scope](d002-requirements.md) | T060.1 | The archives the model takes ([data-model.md › Grain](../data-model.md#grain)) are in the station stock and pass their check against real-time capture |

Each child changes its tables' `TODO(T060)` markers in [data-model.md › Data contract](../data-model.md#data-contract) to its own ID.

## 2. Plan — how

<!-- 2-3 sentences -->

### 2.1 Approach

<!-- Detailed plan organized by #### blocks.
Approach lists the main and supporting deliverables, each already written.
If some block contains `options considered`, include them with pros and cons.
-->

#### Quality catalog

[data-quality.md](../data-quality.md) holds the quality catalog of D4, apart from the model, after the terms of DAMA-DMBOK and ISO/IEC 25024. Each item lives in one place, with its full text and a flat ID whose prefix tells its class, numbered per class in the order the items appear:

- **Runtime rules** (`DQR1`, `DQR2`…): in the catalog, each with its dimension and severity.
- **Quality indicators** (`DQM1`, `DQM2`…), quality measures in ISO/IEC 25024: in the catalog, each with its dimension, its target, where it is built (a gold table, or observability for what lies outside the model) and why it is kept: the action it prompts or the provider's quality it measures (D4).
- **Transformation specs** (`TR1`, `TR2`…), the transformation rules of a source-to-target mapping: in [data-model.md › Data contract](../data-model.md#data-contract). A spec on one column moves to its table's worksheet with its ID.
- **Documentation items** (`RDM1`, `RDM2`…): in the Data contract.
- **Column schema:** a column's type, nullability and accepted values, cells of its worksheet row with no ID, checked in every run; the catalog holds only what no schema states, and a row that fails its schema is quarantined (D4). Until its table's worksheet exists, a rule that becomes schema stays a transformation spec with its pending marker, and the child that creates the worksheet turns it into the column's cells.

Tests and alerts cite these IDs. The child that builds an item translates it into its data-test tool; a machine-readable file that tool needs is derived from the catalog, which stays the source. **#1**

Options considered:

| Option | Pros | Cons |
|---|---|---|
| Markdown document in `docs/` holding the rules' text, with `DQR` and `DQM` IDs (chosen) | The approved document is the source; the catalog reads on its own; the ID tells a check from a transformation; leaves T060.1 free to choose its data-test tool | Each rule is translated into code by hand; about 60 citations change once |
| Markdown catalog that cites the RDM items without moving them | No citation changes | The catalog cannot be read without the model |
| Markdown catalog that moves the RDM items with their IDs | No citation changes | Two prefixes in the catalog; the ID does not tell a check from a transformation |
| YAML file with ODCS v3's `quality` section, loaded by the runtime tests | One source that runs, with no translation | Fixes a format before T060.1 chooses how data tests run ([ADR-0025](../decisions/0025-sql-models-directed-by-python.md) fixes only SQL directed by Python); targets and their reasons are hard to review in it |

#### Carried-over inputs

Inputs about the how, left to this design by earlier spikes and designs; each goes to the first child that needs it, named at its end. **#3**

- **Execution platform check:** if the first slice measures runs of 1 minute or less, or normal runs of 2 GB or less, the decision of [ADR-0027](../decisions/0027-modal-as-execution-platform.md) is reopened with Cloud Run and Fly.io as candidates. The run's final log event carries `duration_s` and `peak_memory_mb`, the latter from `ru_maxrss` ([s012 › D1, P1](../spikes/s012-execution-target.md#d1-execution-platform)). → T060.1
- **Memory:** set DuckDB's memory limit below the container's; decide on a hard container limit (`memory=(request, limit)`; without one, usage above the request is billed, as Modal charges the higher of the two); cap what one run processes and leave the rest to the next; do not retry memory errors, since they are permanent; check in the first slice how Modal treats a memory kill of a scheduled function ([s012 › D3, TH12](../spikes/s012-execution-target.md#d3-pipeline-security), [d002 › R23](d002-requirements.md#requirements)). → T060.1
- **Reading many JSON files:** in DuckDB 2.0.0, `read_json` over thousands of files runs out of memory when it binds each file's schema, with `union_by_name` or a schema sample over every file ([duckdb#27806](https://github.com/duckdb/duckdb/issues/27806)). The fix is merged upstream, but no release carrying it was confirmed. The d005 profile met it ([spikes/d005-data-model › profile](../../spikes/d005-data-model/README.md#profile)). → T060.1
- **Platform separation:** CI checks for rules 1, 2 and 4 of [ADR-0029](../decisions/0029-pipeline-code-architecture.md), and where the platform module lives in the repository ([s012 › D4](../spikes/s012-execution-target.md#d4-processing-logic-separated-from-the-platform)). → T060.1
- **Run operation** ([s012 › Out of scope](../spikes/s012-execution-target.md#15-out-of-scope)): which events the pipeline logs; preventing two runs from overlapping; the region (`eu` costs 1.15x); runs safe to run again after an interruption; Modal's usage and spend limits; the size of catch-up batches and the run's time budget; the end-to-end and post-deploy smoke tests. → T060.1. Where the one-off history load runs. → T060.4
- **Publishing:** the pipeline generates the prepared files from an explicit list and deploys them at the end of a run, with the token from the secret store; a failed deployment does not fail the run's data ([s013 › P8](../spikes/s013-visualization-tool.md#55-production-inputs)). Before building it, try a few deployments with the token limited to one Worker and read Cloudflare's terms ([s013 › Not verified](../spikes/s013-visualization-tool.md#54-not-verified)). → T060.1
- **R2 operation classes:** confirm with R2's per-operation metrics (GraphQL Analytics) the class of conditional PutObject, ListObjectsV2 and DeleteObjects, which the pricing page does not name; s010 confirmed only class totals ([s010 › F14](../spikes/s010-storage-table-format.md#4-findings)). → T060.1
- **Rule names in code:** the convention for the name each catalog item takes in the data-test tool, such as ODCS's `name` beside its `id`. → T060.1
- **Deployment tags:** `wrangler deploy --tag` and `modal deploy --tag` exist; confirm on a test deployment where each tag shows (`wrangler versions list --json`, `modal app history --json`), any length limit, how the tag behaves on a Worker with static assets, and whether Modal's own record of the Git commit makes its tag redundant ([D6](#d6-deployments-tagged-with-their-commit)). → T060.1

### 2.2 Decision summary

<!-- It logs decisions about the plan, including changes. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Applies to: anchor link(s) to the section where the decision is applied, named in one or two words.
- Decided at: the Status phase where it was decided (Plan, Steps), or `<phase> review` when decided while reviewing that phase.
- R: Requirement affected.
-->

| # | Applies to | Decision | Reason | R | Decided at |
|---|---|---|---|---|---|
| 1 | [Quality catalog](#quality-catalog), [D4](#d4-data-quality-in-four-classes), [D7](#d7-catch-up-in-bounded-batches) | The quality catalog is a Markdown document, `docs/data-quality.md`, holding the runtime rules (`DQR`) and the quality indicators (`DQM`), each indicator with a Why and where it is built: a gold table when it measures silver and gold, the observability child otherwise; the Data contract keeps transformation specs (`TR`) and documentation items (`RDM`); a column's type, nullability and accepted values are its schema in its worksheet, with no ID, and a row that fails it is quarantined while the rest of its batch publishes; following DAMA-DMBOK and ISO/IEC 25024, docs-as-code, source-to-target mapping, ODCS's schema apart from quality, dbt's model contracts, and a quarantine table with D7's redrive; **refines [d005 › D29](d005-data-model.md#d29-data-contract-of-the-model)** | One place per rule, readable on its own; the ID tells the item's class and how it is verified; each check stated once; a provider's change removes only its rows from the page | R4, R7, R10, R14, R19, R22 | Plan |
| 2 | [Approach](#21-approach) | D4, D5, D6 and D7 become ADRs, following Nygard's ADRs for cross-cutting architecture decisions | Each binds work after T060 and outside it: every future rule and table, every component's deployment, the pipeline's run mode | R4–R6, R11–R21 | Plan |
| 3 | [Carried-over inputs](#carried-over-inputs), [Children](#16-children) | Each carried-over input goes to the first child that needs it: all to T060.1 but where the history load runs, to T060.4 | Each is first needed where the pipeline first reads bronze, runs on Modal and publishes | — | Plan |
| 8 | [D6](#d6-deployments-tagged-with-their-commit), [Out of scope](#15-out-of-scope), [Carried-over inputs](#carried-over-inputs) | Every production deployment is tagged with its commit by its component's deploy script, which deploys only a clean, latest `main`; the page with the code version of the run that deploys it; following Twelve-Factor's unique release ID; **replaces D6's lookup by time** | The commit behind any deployment is read directly, and no deployment carries code that is not on `main`; the same script can run from CI later | R23, R24 | Plan |
| 9 | [D4](#d4-data-quality-in-four-classes), [D7](#d7-catch-up-in-bounded-batches) | Write-Audit-Publish at both points where data becomes visible: each batch audited before it is committed to silver and gold, each file audited before it is deployed at the end of the run; a file that fails is not deployed, the page keeps the last that passed, and the run ends with no failure signal, since rule failures reach the owner through observability and the heartbeat reports only failed runs | A file's check has no batch to set aside; each rule is audited where its output becomes visible, and one alert channel per kind of failure | R2, R5, R6, R16, R22 | Plan review |
| 10 | [D7](#d7-catch-up-in-bounded-batches), [D8](#d8-pipeline-security-threats) | A run takes no further batch once a fixed time budget is spent, the timeout less the longest batch measured and the run's close, and ends well, leaving the rest pending; the timeout only catches a run that hangs; following a graceful shutdown before a deadline | A backlog has no bound, so draining it in one run would end each run at the timeout and alert as a failure what is normal work | R13, R21, R25 | Plan review |
| 11 | [D4](#d4-data-quality-in-four-classes), [Children](#16-children) | Each indicator's target is reviewed against weeks of production indicators before a child closes: by T060.2 for those built up to it, by the child that builds any later one, such as T060.3 for DQM4; following the SRE practice of an objective set from a measured baseline | An indicator built after the alerts would otherwise keep its initial target unreviewed | R7 | Plan review |
| 12 | [D3](#d3-continuous-mode-with-a-15-minute-cadence) | Every question answered from the current state (d002's Q1, Q2, Q5) has the freshness of R3, one cadence plus one run; following one freshness target per pipeline, since its outputs share its cadence; **refines [d002 › Guiding questions](d002-requirements.md#guiding-questions)** | Q2 and Q5 come from the same 15-minute pipeline, so 5 min could not be met; the cadence review of D3 then improves them all | R3 | Plan review |

### 2.3 File layout

<!-- Every file and folder the task creates or modifies, documents included, as a tree: (new) or (modified), and its purpose or change in one line. A task that adds a component also lists its CI job in `.github/workflows/ci.yml` (recipe in `.claude/rules/code/ci.md`), and its version files, manifest and lockfile (`.claude/rules/code/dependencies.md`). -->

```text
.claude/rules/docs/
└── data-model.md                              (modified)  Rule IDs: a column rule keeps its TR ID when it moves to its worksheet
docs/
├── data-quality.md                            (new)       Quality catalog: runtime rules (DQR) and quality indicators (DQM) (#1)
├── data-model.md                              (modified)  Data contract loses the runtime rules and quality indicators; the rest renumbered as TR and RDM (#1)
├── architecture.md                            (modified)  §1.1 and QS1 freshness as one cadence plus one run (#12); §6.2 runs in bounded batches, audited before publishing; §8 data quality, lineage and deployments cite their ADRs; §10 scenarios grouped by goal, its introduction pointing to the quality catalog; §11 cadence risk owned by T060.1
├── decisions/
│   ├── 0042-data-quality-classes-and-severity.md  (new)   D4: four classes, severity by who causes a failure, write-audit-publish (#2)
│   ├── 0043-lineage-at-four-levels.md         (new)       D5: lineage by table, column, run and row (#2)
│   ├── 0044-deployments-tagged-with-their-commit.md  (new)  D6: each deployment tagged with its commit by its component's deploy script (#2, #8)
│   └── 0045-catch-up-in-bounded-batches.md    (new)       D7: drain mode in bounded batches, dead-letter with redrive (#2)
└── designs/
    ├── d002-requirements.md                   (modified)  Q2 and Q5 freshness as one cadence plus one run (#12)
    ├── d005-data-model.md                     (modified)  D29 and Implemented: the contract's IDs per class, refined by #1; citations renumbered
    └── d007-pipeline-design.md                (modified)  Header lists the new ADRs; D4 and every citation renumbered
```

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
