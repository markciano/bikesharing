<!--
Spike doc template. A spike is a time-boxed investigation of one task: it reaches the decisions a task needs, by analysis where possible and with evidence only where an unknown would change the choice. Its output is knowledge (decisions, answers, a verdict, inputs for designs and ADRs); its code is throwaway and lives in spikes/<name>/.
Blocks: Questions (what we need to know), Method (how we find out), Steps, Findings (filled during execution), Conclusion (filled after the last step).
Sections marked Optional are kept only when they apply.
-->

# Spike: Pipeline run time and R2 reads

- **Task:** T077
- **ADRs:** [ADR-0019](../decisions/0019-own-lakehouse-on-cloudflare-r2.md), [ADR-0022](../decisions/0022-delta-lake-for-silver-and-gold.md), [ADR-0024](../decisions/0024-duckdb-as-processing-engine.md), [ADR-0027](../decisions/0027-modal-as-execution-platform.md), [ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md)
- **Code:** [`spikes/t077-run-time-and-r2-reads/`](../../spikes/t077-run-time-and-r2-reads/)

## Status

<!-- State: Draft 📝 · Ready 🎬 · Running 🔄 · Concluded ✅.
Phase: the blocks and the review completed.
Started / Finished: UTC dates of the first step executed and of the Conclusion.
Current: where work resumes, with only the context the next session needs: the step being executed, or the section of the report; — when concluded. -->

- State: Running 🔄
- Phase: [x] Questions · [x] Method · [x] Steps · [x] Steps review · [ ] Conclusion
- Started: 2026-11-25 · Finished: —
- Current: Conclusion › 5.6 Records, the ADR on the Delta pattern; 5.1–5.5 are written. Then the tear-down (copy bucket `bikesharing-t077-lakehouse-copy`, tokens `bikesharing-t077-copy` and `bikesharing-t077-prod-read`, run by the owner) and the close.
  - **ADR-0052, Proposed:** the decision in one sentence: every pipeline Delta table is opened once per run, partitioned by the range its readers filter by, read and merged stating that range, compacted without merging files within a range a reader prunes by, and vacuumed within its history. Only the principles go to the ADR; how each table applies them is the Verdict's fix and P1–P6.
  - **Options to weigh:** maintenance as a job apart from the run (T072's earlier premise; conflicts with the MERGE and misses a catch-up); compaction at fixed times (no response to a catch-up); the control table out of Delta, as a manifest (loses atomic commits for a few hundred GetObject); no partitions and one compacted file (bounds GetObject, not the bytes read); one compaction rule for every partition, the active one included (defeats pruning by capture range where a reader prunes within the day).
  - The official documentation is checked ([Sources](#6-sources)).

## 1. Questions — what we need to know

### 1.1 Context

<!-- 2–4 sentences: the decisions this spike takes, which of them depend on evidence and why, and the spikes or designs it builds on. -->

The pipeline's scheduled runs get slower every day and read far more objects from R2 than they process, as measured at d008's close ([d008 › Known gaps at close](../designs/d008-pipeline-platform-and-walking-skeleton.md#42-known-gaps-at-close)): about 6,600 GetObject per run on `bikesharing-lakehouse`, a bucket of about 2,250 objects. This spike finds the causes and chooses the fix for each one, which is built outside the spike (D1). Reading the code and `deltalake`'s documentation already explains most of it; evidence is sought only where the size of each cause would change the fix.

R2's hourly Class B operations on `bikesharing-lakehouse` form a rising sawtooth after the first feed's catch-up, which peaked at about 22,000 GetObject per run on 2026-11-21. Per run, at 4 runs an hour:

| Tooth | Trough, at its start | Peak, before the drop | Drop | Drop at (UTC hour, about) |
|---|---|---|---|---|
| 21 → 22 Nov | 4,000 | 7,500 | 2,000 | 03:00 |
| 22 → 23 Nov | 5,500 | 8,750 | 2,000 | 04:00 |
| 23 → 24 Nov | 6,750 | 11,250 | 2,500 | 05:00 |

- **Period:** a drop every ~25 h, an hour later each day.
- **Trend:** the troughs rise by 1,500–2,000 per run each day and never fall back.

#### Lakehouse reads per run

The run's calls in `pipeline/src/bikesharing/shell/delta.py`, in order, with one batch per run as in the measured window. Every call opens a fresh `DeltaTable`, which rebuilds the table's state from `_delta_log/`: the last checkpoint and up to 99 JSON commits after it, since `deltalake` 1.6.6 writes a checkpoint every 100 commits by default.

| # | Phase | Call | Table | Data files read |
|---|---|---|---|---|
| 1 | Discovery | `ensure_tables` | both | none |
| 2 | Discovery | `processed_keys` | `processed_objects` | **all**: it needs every key |
| 3 | Discovery | `latest_processed` | `processed_objects` | **all**: a grouped `max` is not answered from file statistics |
| 4 | Batch | `capture_history` | `processed_objects` | the last 7 days', skipped by `captured_at`'s min and max |
| 5 | Batch | `merge_station_stock` | `station_stock` | the batch's local dates, pruned by partition |
| 6 | Batch | `record_processed` | `processed_objects` | **all**: an insert-only MERGE on `key` prunes no file with the default `streamed_exec=True` |
| 7 | Gold | `latest_processed` | `processed_objects` | **all**, as in row 3 |
| 8 | Gold | `latest_captures` | `station_stock` | the latest capture's local date, pruned by partition |

A run opens a table 9 times and reads `processed_objects` in full 4 times (rows 2, 3, 6 and 7). That table gains one small file per run and is never compacted.

#### Hypotheses

- **H1. Unbounded reads of the control table.** The 4 full reads of `processed_objects` grow with every run, with no limit. It is the main candidate for the growth and for the read volume.
- **H2. Log replay on every open.** The 9 opens each read up to 99 commits, a cost that rises for about 25 h and drops at each checkpoint, with about 96 commits a day per table. It could explain the daily pattern (Q1).
- **H3. Network distance.** Modal runs in the US and both buckets in Western Europe, so each operation pays a transatlantic round trip (D2).

### 1.2 Decided at framing

#### D1. The fix is built outside the spike

The spike finds the causes and chooses the fix for each one; the fix itself is built in the `pipeline` component, through a design or, if it is a single step, through a one-step task. Spike code is throwaway and no component imports from `spikes/` (`.claude/rules/code/spikes.md`), so code that must stay in production is not written here.

- **What would change it:** nothing in the findings; a fix's size only chooses between a design and a one-step task, at the Conclusion.
- **Rejected:** building the fix in the spike, against the rule above.

#### D2. Modal's region is decided after the fix

Both buckets are in Western Europe (WEUR) and the pipeline runs on Modal in the US, with no region pinned, the cheapest option ([ADR-0027](../decisions/0027-modal-as-execution-platform.md) leaves the region open). The distance adds no R2 cost, since R2 charges no egress, but each operation pays a transatlantic round trip, and Modal bills the container's waiting time. That latency per operation is roughly constant: what grows is the number of operations, so the fix of the causes comes first. After the fix, a worst-case estimate settles it: the lakehouse requests left per run × 0.1 s, as if every request were serial. Below 20% of the run time, Modal stays in the US. Above it, a few production runs with Modal pinned to Europe are compared with the same number of runs in the US, in run time and cost. The Conclusion hands this rule to the fix's task as a production input.

- **What would change it:** a trial shows that Europe's shorter runs pay for the surcharge → pinning Modal to Europe is proposed. New feeds that push the estimate above 20% apply the same rule again.
- **Rejected:** moving Modal to Europe now. It pays the surcharge before knowing it is needed and hides part of the growth that Q1 must measure.
- **Rejected:** measuring latencies in the spike. It needs the spike's code deployed on Modal, while the estimate settles the likely case and a trial measures the real workload with a reversible configuration change.

<!-- In this order, so the reader finds what matters first:
1. The decision and why, in one short paragraph. If it depends on a Q, name it and what happens if its Gate fails.
2. What would change it, and what would not, each with the action to take. Only when a later event could reopen it.
3. The options rejected and how robust the result is.
4. The evaluation behind it: the table or weighted matrix (needs, cuts, anchors and scores) if one was used. A security decision lists its threats in a table: `| # | Threat (STRIDE) | Impact | Control | Requirement |`, with IDs `TH1`, `TH2`… per document. -->

### 1.3 Questions

<!-- The main question, answered by the Verdict. Then Q1..Qn, each answerable with evidence.
"Observe only": things to note during the run with no dedicated effort. -->

Main question: what makes the pipeline's run time and its lakehouse reads per run grow, and which fix keeps both bounded as the processed objects accumulate, in steady runs and in a new feed's catch-up? A catch-up is answered by arithmetic: the batches it runs within the limit of [ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md), times the cost of one batch (calls 4–6), counted in Q2. **#1**

- **Q1.** Does the run time follow each table's commits since its last Delta checkpoint, written every 100 commits, rather than the hour of the day? Answered over the observed window (Exit criteria), from the runs' log objects and the `LastModified` of each table's `_delta_log/`. It decides between the checkpoint cycle and the network to Modal's region ([D2](#d2-modals-region-is-decided-after-the-fix)) as the cause of the daily pattern.
- **Q2.** Do the calls of [Lakehouse reads per run](#lakehouse-reads-per-run) account for the lakehouse's GetObject per run, and for the time and growth of discovery and batch work? Counted per call, on the tables' state in production. It decides whether the fix is chosen on H1 and H2 alone: its Gate, in Exit criteria, sets the share that must be accounted for; below it, the remaining share is a cause still to find.
- **Observe only:**
  - the daily pattern, up to twice as slow from 16:00 to 23:00 Madrid time, whether it holds per operation or only per run: per run, the baseline's *Phases by hour* in the spike's README shows it; per operation, no probe measures it, so the Conclusion lists it in Not verified;
  - the pipeline's own GetObject on `bikesharing-bronze` per run, against the objects it downloads, about 65: bounded from above by the bucket's GetObject in pass 1's production hour ÷ 4, read in Step 7.

### 1.4 Exit criteria

<!-- Fixed before the first run; a later change is recorded in the Decision log.
Derived from the standard that applies to this kind of question, named in the first line: e.g. DAMA data quality dimensions for a data source, a weighted decision matrix for a technology choice.
Each criterion is measurable and says whether it is a hard cut or a guide. The timebox says what ends the run. State whether one variant meeting the criteria is enough. -->

- **Standard:** drill-down analysis with workload characterization (Brendan Gregg, *Systems Performance*). A cause is found when it accounts for most of the measured effect, following the Pareto principle: the dominant causes are sought, not 100%.
- **Timebox:** 1 working day, over at most 3 run sessions. It ends when Q1 and Q2 are answered, or when Q2's Gate fails.
- **Variants:** none are compared; every Q answered is enough.
- **Observed window:** from 2026-11-22 00:00 UTC, the first full day after the first feed's catch-up, to the last run session. The catch-up is a different regime and stays out. **#1**

| Criterion | Threshold | Kind | Why this threshold |
|---|---|---|---|
| **Q2, reads:** GetObject counted in the calls of [Lakehouse reads per run](#lakehouse-reads-per-run), against production's GetObject per run in each pass's hour ([Probe B](#b-count-per-call)) | ≥ 80% | **Hard cut (Gate)** | R2's sampled totals are accepted within ±0.5% of an exact count ([s010 › #39](s010-storage-table-format.md#decision-log)), so the margin is for what the map leaves out: small calls, such as the log's upload, and other readers of the bucket during the window, such as analysis scripts |
| **Q2, time:** local time of the calls that hold 80% of the counted GetObject, against the local time of all the mapped calls | ≥ 70% | Guide | Probe B runs locally, where latency is lower than from Modal, so time is compared as a share among calls, not against production's runs |
| **Q2, growth:** the part of the count that grows with `processed_objects`' files, against the measured growth per run | Same sign and order of magnitude | Guide | It confirms that H1 is what grows, not only what weighs |
| **Q1, checkpoint cycle:** discovery's time in the 4 runs right after each checkpoint, against the 4 right before | A drop of 20% or more at every checkpoint of the window | Guide | The hour of the day causes no sudden drop at a checkpoint; 4 runs span 1 h, too short for the slow growth to interfere |

If Q2's Gate fails, the share not accounted for is a cause still to find: the Decision log records it, with the choice of widening the map within the timebox or opening a new task.

### 1.5 Out of scope

<!-- Optional. What someone could expect this spike to answer and it will not, each item pointing to the task that covers it. -->

- Which readers other than the pipeline account for `bikesharing-bronze`'s GetObject: they do not slow the runs, and the cost model needs them per bucket — no task: the cost recalibration of [d008 › Known gaps at close](../designs/d008-pipeline-platform-and-walking-skeleton.md#42-known-gaps-at-close) is postponed

## 2. Method — how we find out

### 2.1 Approach

<!-- The variants, options or probes compared, and what each one tells that the others do not. -->

R2's hourly sawtooth ([Context](#11-context)) already answers Q1 in count: the reads drop at every checkpoint, an hour later each day. It does not answer Q1 in time, nor which calls make up the reads that never fall back. Two probes cover the rest.

| Probe | What it is | What it tells |
|---|---|---|
| [A](#a-checkpoint-cycle-in-time) | Offline analysis of the runs already made, over the observed window | Whether the run time drops at each checkpoint or follows the hour of the day (Q1) |
| [B](#b-count-per-call) | The 8 calls of the map, one by one, through a counting proxy | GetObject and time per call (Q2), and the cost of one batch for a feed's catch-up |

#### A. Checkpoint cycle in time

The phase times in the runs' log objects are joined with the `LastModified` of each table's `_delta_log/` files, which places every run at its commit count since the last checkpoint. Nothing runs against the pipeline. Discovery's time is the gap between two events of each run's log object under `logs/pipeline/`: `run_started` and `objects_discovered`, which marks the end of discovery. It answers Q1's criterion: discovery's time in the 4 runs right after each checkpoint, against the 4 right before.

#### B. Count per call

The calls of [Lakehouse reads per run](#lakehouse-reads-per-run) run one at a time through the counting proxy of [s010 › Probe A](s010-storage-table-format.md#a-delta-on-r2), which gave exact requests per operation class against R2. For each call it records GetObject, time, and each table's commits since its last checkpoint. It answers Q2's three criteria, and calls 4–6 give the cost of one batch for the catch-up's arithmetic.

It runs on the owner's machine, against a copy of both tables in a separate bucket, since calls 5 and 6 write. The copy is whole: `processed_objects` is never compacted, so every version still reads data files from the first day. The probe holds only an R2 token scoped to the copy's bucket, so no misconfiguration can reach production; the owner makes the copy with a read-only token on production.

The batch of calls 4–6 replays the last run present in the copy, since the probe does not reach `bikesharing-bronze`. Call 5 merges again that run's `station_stock` rows, which fall on the same local date and so read the same partition's files. Call 6 records as many objects as that run had, under new keys (`t077-probe/…`), so its MERGE stays insert-only and reads the whole table, as in production. Reading the replayed rows is counted apart, as setup. **#2**

The probe runs twice, at the two latest peaks of the sawtooth: before `processed_objects`' last checkpoint, then before the checkpoint before it, about 100 commits earlier. Each pass's version is the one read by the last run of the last whole UTC hour before the hour of the checkpoint's commit, so that the 4 runs of that hour all read before the drop. **#4** Each pass is reproduced with Delta's time travel on the copy:

- both tables' logs are cut at that pass's instant, dropping later commits and checkpoints, and `_last_checkpoint` points to the last checkpoint before it;
- the cut also drops what the earlier pass wrote;
- data files added after the cut are left orphaned and nothing reads them.

Q2's Gate compares each pass's count with production in that pass's hour: `bikesharing-lakehouse`'s GetObject in it, divided by its 4 runs. The difference between the passes is one day's growth at the same point of the cycle, compared with the sawtooth's peak-to-peak growth for Q2's growth criterion. The cut runs only on the copy, never on production.

Each pass is checked against an independent count. The copy's bucket receives only the probe's requests, so its total requests in the count's window must not exceed the proxy's total for that pass, failed ones included, by more than 0.5% (tolerance from [s010 › #39](s010-storage-table-format.md#decision-log)). This catches a client that reaches R2 without the proxy. The count's window is in whole UTC minutes: it starts at the minute before the one the count starts in, and ends, exclusive, two minutes after the one it ends in. Nothing else touches the copy's bucket within it, so that its figure holds that count alone (F5). **#9, #10**

Every operation figure, of production and of the copy, comes from Cloudflare's GraphQL Analytics API (`r2OperationsAdaptiveGroups`), through the baseline's `r2_metrics.py` extended with a bucket and a window. R2's dashboard is not used: its figures are not exact and it documents no breakdown per operation ([cloudflare › R2: metrics](../sources/cloudflare.md#r2-metrics)). **#5**

### 2.3 Decision log

<!-- It logs decisions about the method, before and during the run, including changes of course. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Column Applies to: anchor link(s) to the section where the decision is applied, named in one or two words (e.g. Q1, Probe A, File layout).
- Column Decided at: the Status phase where it was decided (Method, Steps), `<phase> review` when decided while reviewing that phase, or `Running step N` when decided during the run.
-->

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| 1 | [Questions](#13-questions), [Exit criteria](#14-exit-criteria) | Questions reopened: the observed window starts on 2026-11-22 00:00 UTC, after the first feed's catch-up, and the main question also covers a new feed's catch-up, by arithmetic on the cost per batch counted in Q2. Standard: workload characterization, one regime at a time | The catch-up's runs read up to 22,000 GetObject each and would skew Q2's Gate and growth; more feeds are still to come, each with its own catch-up | Method |
| 2 | [Probe B](#b-count-per-call) | The batch of calls 4–6 replays the copy's last run: its `station_stock` rows merged again, and its object count recorded under new keys. Standard: replay of a representative workload | The copy's token does not reach `bikesharing-bronze`; the replay reads the same files as the real batch, and only the writes, which are not measured, differ | Steps |
| 3 | [File layout](#24-file-layout) | Probe A's inputs are downloaded with `rclone` commands, not by a script. Standard: least privilege (NIST SP 800-53 AC-6) | The production token stays in rclone's configuration and reaches no spike code; three one-off commands need no script | Steps |
| 4 | [Probe B](#b-count-per-call) | Each pass's version is the one read by the last run of the last whole UTC hour before the checkpoint's hour, and production is read for that hour. Standard: like-for-like comparison, one regime at a time | In the checkpoint's own hour, runs after the drop read about 2,000 GetObject less, which would lower production's mean per run by up to ~18% and let Q2's Gate pass on a map that does not account for 80% | Steps review |
| 5 | [Probe B](#b-count-per-call) | Every R2 operation figure comes from the GraphQL Analytics API, through the baseline's `r2_metrics.py` extended with a bucket and an hour; total requests match within ±0.5% ([s010 › #39](s010-storage-table-format.md#decision-log)). Standard: reuse of a validated measurement tool ([s010 › Step 5](s010-storage-table-format.md#step-5--run-probe-a-and-verify-the-analysis)) **→ #9, #10** | The dashboard is not exact and documents no breakdown per operation, while Q2's Gate needs GetObject | Steps review |
| 6 | [File layout](#24-file-layout) | The baseline's four folders stay in the spike folder, unchanged except `r2_metrics.py`; Step 1 updates the README instead of writing it. Standard: provenance of cited evidence | d008 and this report cite their figures; keeping them costs only the README's update | Steps review |
| 7 | [Step 4](#step-4--run-the-proxys-smoke-test) | The token check matches the baseline on `bikesharing-lakehouse`'s GetObject, PutObject and ListObjects and on both buckets' storage; `bikesharing-bronze`'s operations need not match. Standard: sampled metrics are not validated by exact equality | `bronze`'s operations differ from the baseline for the same window (F2); no check of this spike reads that bucket | Running step 4 |
| 8 | [Step 6](#step-6--count-per-call-script) | A table's commits since its last checkpoint are `(version + 1) % 100`. Standard: Delta protocol, a checkpoint at version v holds the table's state through commit v | `deltalake` 1.6.6 checkpoints at versions 99, 199, …, so `version % 100` counts one commit less than an open replays, and differs from `cut_log.py`'s count | Running step 6 |
| 9 | [Probe B](#b-count-per-call), [Step 7](#step-7--pass-1-the-latest-peak) | The copy's figures are read for a window of whole UTC minutes around each count, instead of the count alone in its UTC hour. Standard: a measurement window isolated from other activity; **refines #5** | The query filters by the minute (F5), and waiting for a clean hour only delays the run | Running step 7 |
| 10 | [Probe B](#b-count-per-call), [Step 7](#step-7--pass-1-the-latest-peak) | The independent count fails only when R2's total exceeds the proxy's by more than 0.5%. Standard: one-sided tolerance, on the side of the fault the check looks for; **refines #5** | Set after seeing pass 1, which ±0.5% fails at −1.40% (F8): a client bypassing the proxy only raises R2's total | Running step 7 |

### 2.4 File layout

<!-- Every file and folder the spike creates, as a tree with its purpose in one line. Captured data and outputs are marked as ignored by Git. The README is always included. -->

```text
spikes/t077-run-time-and-r2-reads/
├── README.md                Question, setup and commands, what each script does, link to the report
├── pyproject.toml           Python and dependencies; the pipeline package as a local path dependency, so its deltalake version is the production one
├── uv.lock                  Locked dependencies
├── .python-version          Python 3.14.9, the pipeline's pin
├── .env.example             The copy token's variables, empty; .env holds the values (ignored by Git)
├── .gitignore               Ignores .env, data/ and output/
├── run-time-and-memory/     Baseline, unchanged
│   └── run_stats.py         Run time and memory against ADR-0027's thresholds
├── time-per-phase/          Baseline, unchanged
│   └── run_phases.py        Time per phase from the run's events; Probe A follows how it reads them
├── phases-by-hour/          Baseline, unchanged
│   └── run_by_hour.py       Phases per local hour; its output is the daily pattern per run
├── r2-operations-and-storage/
│   └── r2_metrics.py        The baseline's GraphQL query, extended with optional bucket and window arguments for Probe B's checks
├── checkpoint-cycle/        Probe A; its inputs are downloaded with rclone, as the README shows
│   └── cycle_times.py       Places each run in its checkpoint cycle and compares discovery's time in the 4 runs before and after each checkpoint
├── count-per-call/          Probe B
│   ├── proxy.py             Counting proxy between deltalake and R2, adapted from s010's Probe A
│   ├── cut_log.py           Cuts the copy's logs at a pass's version
│   └── count_calls.py       Runs the map's calls one by one through the proxy, with GetObject, time and commits since the checkpoint per call
├── data/                    Downloaded inputs (ignored by Git)
└── output/                  Results per probe and pass (ignored by Git)
```

Probe A has no download script: its inputs come from `rclone` commands in the README. **#3**

The four baseline folders hold the first measurements, taken at T060.1's close, which [d008 › Known gaps at close](../designs/d008-pipeline-platform-and-walking-skeleton.md#42-known-gaps-at-close) and this report's Context cite. They keep their scripts, commands and README sections; only `r2_metrics.py` changes (#5). **#6**

## 3. Steps
<!-- Each step is one reviewable result, touching at most 2–3 files.
- Status: where the step is: 💤 todo · 🎬 ready · 🔄 in progress · ⛔ blocked · ✅ done
- Who: Owner (manual actions: dashboards, accounts, deploys, runs, checks) or Claude (code and documents).
- Commit: only in a step that changes committed files: the proposed message, following the Git conventions in CLAUDE.md.
- Model: the model and effort the step's session runs with (e.g. sonnet · medium), or — when Who is Owner.
- Gate: optional. <condition> → <consequence if it fails: variants or steps dropped or re-decided>. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

Resource names follow [ADR-0035](../decisions/0035-cloud-resource-naming.md) for a temporary resource; all of them are deleted when T077 closes.

| Item | Value | Verify |
|---|---|---|
| Copy bucket | R2 bucket `bikesharing-t077-lakehouse-copy`, same account and location as `bikesharing-lakehouse`, no bucket lock, empty | Listed in the R2 dashboard with 0 objects |
| Copy token | R2 API token `bikesharing-t077-copy`, Object Read & Write on `bikesharing-t077-lakehouse-copy` only | At creation, the summary shows that permission and that bucket alone |
| Production read token | R2 API token `bikesharing-t077-prod-read`, Object Read only on `bikesharing-lakehouse` only | At creation, the summary shows that permission and that bucket alone |
| rclone | 1.75.2, with two remotes (provider Cloudflare): `r2-prod` with the production read token, `r2-copy` with the copy token | `rclone version` and `rclone listremotes` |
| Python and uv | Python 3.14.9, the pipeline's pin (`pipeline/.python-version`); uv 0.13.5 | `uv --version`; `uv python find 3.14.9` |
| Analytics token | The baseline's Cloudflare API token, Account Analytics: Read only, in the shell's `CF_ANALYTICS_API_TOKEN`, loaded as the README shows | After Step 3, `r2_metrics.py` with no arguments prints the README's baseline figures |

Each token is used by one side only: the copy token by Probe B, the production read token by Probe A's downloads and by the copy. Since the two remotes hold different credentials, the copy is not server-side: rclone downloads each object and uploads it to the copy's bucket, with free egress.

All paths below are relative to `spikes/t077-run-time-and-r2-reads/`, and commands run from there unless they say otherwise. Times are UTC; R2's operation figures are read with `r2_metrics.py` for a window of whole UTC minutes, given as `YYYY-MM-DDTHH:MM:00Z`, once it has ended (#5, #9): production's for whole hours, and the copy's for each count's window ([Probe B](#b-count-per-call)).

| Step | Title | Who | Gate | Files |
|---|---|---|---|---|
| 1 | Scaffold the spike folder | Claude | — | `README.md`, `pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore`, `.env.example` |
| 2 | Copy both tables to the copy's bucket | Owner | The copy matches the listed snapshot | — |
| 3 | Counting proxy with a smoke mode, and hourly metrics | Claude | — | `count-per-call/proxy.py`, `r2-operations-and-storage/r2_metrics.py`, `README.md` |
| 4 | Run the proxy's smoke test | Owner | The proxy's count matches the copy's GraphQL count | — |
| 5 | Log cut script | Claude | — | `count-per-call/cut_log.py`, `README.md` |
| 6 | Count-per-call script | Claude | — | `count-per-call/count_calls.py`, `README.md` |
| 7 | Pass 1: the latest peak | Owner | Q2's Gate | — |
| 8 | Pass 2: the peak before it | Owner | — | — |
| 9 | Download Probe A's inputs | Owner | — | — |
| 10 | Checkpoint cycle script | Claude | — | `checkpoint-cycle/cycle_times.py`, `README.md` |
| 11 | Run and hand-check the checkpoint cycle | Owner | — | — |

### Step 1 — Scaffold the spike folder

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `chore: step 1 - scaffold run time and r2 reads spike`
- **Model:** sonnet · low
- **Gate:** —

#### Scope

The spike folder's environment, with no probe code yet: `pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore`, `.env.example`, and the existing `README.md` updated. The baseline's folders do not change, nor anything outside `spikes/t077-run-time-and-r2-reads/`.

#### Reads

- [File layout](#24-file-layout): the files and their purpose.
- `.claude/rules/code/spikes.md`: the README's shape.
- `README.md` in full: the baseline's sections, kept as they are.
- `spikes/storage-table-format/pyproject.toml` and `.env.example`: s010's setup for R2 through a proxy, to follow.

#### Do

1. Write `.python-version` with `3.14.9`.
2. Write `pyproject.toml`: Python `==3.14.9`; dependencies `bikesharing` as a path dependency on `../../pipeline`, so `deltalake` resolves to the pipeline's locked version, and `boto3` for `cut_log.py`.
3. Run `uv lock` from the spike folder to write `uv.lock`.
4. Write `.env.example` with `R2_ACCOUNT_ID`, `R2_COPY_ACCESS_KEY_ID` and `R2_COPY_SECRET_ACCESS_KEY`, empty.
5. Write `.gitignore` with `.env`, `data/` and `output/`.
6. Update `README.md`, keeping the baseline's sections and commands as they are, first and in their order: add a link to this report to the question, add the prerequisites of [Prerequisites](#31-prerequisites) apart from the baseline's, and add after the baseline's sections one empty section per check in run order (Probe B, then Probe A), filled by the steps that add them.

#### Check

`uv sync --locked --directory spikes/t077-run-time-and-r2-reads` succeeds, and `uv run --directory spikes/t077-run-time-and-r2-reads python -c "import deltalake; print(deltalake.__version__)"` prints `1.6.6`.

### Step 2 — Copy both tables to the copy's bucket

- **Status:** ✅ done
- **Who:** Owner
- **Model:** —
- **Gate:** `rclone check` reports 0 differences → otherwise repeat Do 3 and 4; never go on to Step 4 with a difference.

#### Scope

The copy of `silver/station_stock/` and `control/processed_objects/` in `bikesharing-t077-lakehouse-copy`, taken from a listed snapshot, so that production's runs during the copy do not change what is copied. The `_delta_log/` listing with production's `LastModified` is saved for `cut_log.py`, since the copied objects get new dates. Its dates are in RFC 3339 with their offset, since `rclone lsf` prints local time by default.

#### Do

1. Copy `.env.example` to `.env` and fill in the account ID and the copy token's keys; create `data/copy/`.
2. Save the snapshot and the logs' dates:

   ```text
   rclone lsf -R --files-only --include "/silver/station_stock/**" --include "/control/processed_objects/**" r2-prod:bikesharing-lakehouse > data/copy/keys.txt
   rclone lsf -R --files-only --format "tp" --time-format RFC3339 --include "/silver/station_stock/_delta_log/**" --include "/control/processed_objects/_delta_log/**" r2-prod:bikesharing-lakehouse > data/copy/delta-log.txt
   ```

3. Copy the snapshot: `rclone copy -P --files-from data/copy/keys.txt r2-prod:bikesharing-lakehouse r2-copy:bikesharing-t077-lakehouse-copy`.
4. Check it: `rclone check --files-from data/copy/keys.txt r2-prod:bikesharing-lakehouse r2-copy:bikesharing-t077-lakehouse-copy`.
5. Note the UTC hour the copy ended.

#### Check

Report: the number of lines of `keys.txt`, the result of `rclone check`, and the UTC hour of Do 5. Yes when `rclone check` reports 0 differences.

### Step 3 — Counting proxy with a smoke mode, and hourly metrics

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `chore: step 3 - add counting proxy and hourly metrics to run time spike`
- **Model:** opus · medium
- **Gate:** —

#### Scope

`count-per-call/proxy.py` and its section in `README.md`. The proxy runs in the calling process, on a background thread, between `deltalake` and the copy's bucket, and records every request with the label of the call in progress. Smoke mode opens each table once, through the proxy. It reads the copy token from `.env` and targets `bikesharing-t077-lakehouse-copy` as a constant, with no argument to change the bucket.

`r2-operations-and-storage/r2_metrics.py` gains optional arguments for one bucket and one time range (#5); with none, it keeps its constants and prints the same as the baseline. Nothing else of the baseline's folders changes.

#### Reads

- `spikes/storage-table-format/r2_proxy.py` in full: s010's proxy, which gave exact counts per operation class against R2 ([s010 › Probe A](s010-storage-table-format.md#a-delta-on-r2)); this proxy adapts it.
- `r2-operations-and-storage/r2_metrics.py` in full: the query this step extends.
- `pipeline/src/bikesharing/shell/delta.py`, lines 50–60 and 176–220: `Lakehouse` and the storage options the pipeline passes to `deltalake`, which the proxy's lakehouse reproduces with its own endpoint.

#### Do

1. Write `proxy.py`, adapted from s010's proxy: start it on a free local port, set a label per call, and record per request the label, method, S3 operation, R2 class (A or B), key, status, bytes and duration, written as JSON lines to a file given by the caller. Expose a `Lakehouse` for the copy's bucket through the proxy.
2. Implement smoke mode, `python count-per-call/proxy.py --smoke`: open each table once with `DeltaTable`, under the label `smoke`, write `output/count-per-call/smoke-requests.jsonl`, and print GetObject, the other Class B operations and Class A per table and in total.
3. Extend `r2_metrics.py` with `--bucket`, `--start` and `--end`, the last two in `YYYY-MM-DDTHH:00:00Z`, defaulting to its current `BUCKETS`, `START` and `END`. After the per-operation table, print each bucket's GetObject, Class B and Class A totals, classed as `proxy.py` classes them.
4. Update `README.md` with Probe B's section: its question, the smoke command, the metrics command for one bucket and hour, their outputs and run time.

#### Check

`uv run --directory spikes/t077-run-time-and-r2-reads python count-per-call/proxy.py --help` and `… python r2-operations-and-storage/r2_metrics.py --help` print their usage; the runs against R2 and the API are Step 4.

### Step 4 — Run the proxy's smoke test

- **Status:** ✅ done
- **Who:** Owner
- **Model:** —
- **Gate:** the proxy's Class B total equals the copy's Class B from `r2_metrics.py` for that hour, within 0.02% → otherwise a client reaches R2 without the proxy: fix `proxy.py` (back to Step 3) before Step 5.

#### Scope

The cheapest test of Probe B's riskiest assumption: that the proxy sees every request `deltalake` makes, before the scripts are built on it.

#### Do

1. In a UTC hour after the one in which the copy ended (Step 2), with nothing else using the copy's bucket, run `uv run python count-per-call/proxy.py --smoke`, once.
2. Check the token: `uv run python r2-operations-and-storage/r2_metrics.py` with no arguments prints the README's baseline figures.
3. Once the smoke's hour has ended, run `uv run python r2-operations-and-storage/r2_metrics.py --bucket bikesharing-t077-lakehouse-copy --start <hour> --end <next hour>`.

#### Check

Report the smoke output, whether Do 2 matched the baseline, and Do 3's output. Yes when Do 2 matches the baseline on `bikesharing-lakehouse`'s GetObject, PutObject and ListObjects and on both buckets' storage, and the proxy's Class B total equals Do 3's within 0.02%. **#7**

### Step 5 — Log cut script

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `chore: step 5 - add log cut to run time spike`
- **Model:** opus · high
- **Gate:** —

#### Scope

`count-per-call/cut_log.py` and its section in `README.md`. It rewinds both tables in the copy to the instant of a pass ([Probe B](#b-count-per-call)), with `boto3` straight to R2, not through the proxy. It targets `bikesharing-t077-lakehouse-copy` as a constant, with no argument to change the bucket, and reads production's dates only from `data/copy/delta-log.txt`, converted to UTC from their RFC 3339 offset.

#### Reads

- [Probe B](#b-count-per-call): what the cut keeps and drops.
- Delta's protocol, sections *Delta Log Entries* and *Last Checkpoint File*, at <https://github.com/delta-io/delta/blob/master/PROTOCOL.md>: the names of commits and checkpoints, and the fields of `_last_checkpoint` that `deltalake` reads.

#### Do

1. Write `cut_log.py --pass 1|2`. From `delta-log.txt`, take `processed_objects`' latest checkpoint (pass 1) or the checkpoint before it (pass 2), and the UTC hour `H` of that checkpoint's commit. Its production hour is `H − 1`, and the pass's version `N` of `processed_objects` is the one read by that hour's last run: the version of the last commit in `H − 1`, minus 1. The pass's instant is the `LastModified` of `N`'s commit. For `station_stock`, the pass's version is its latest commit at or before that instant.
2. For each table: list its `_delta_log/` in the copy's bucket, not in `delta-log.txt`, so that what an earlier pass wrote is also found, and delete every object of a version above the pass's version, and rewrite `_last_checkpoint` with the version and size of the latest checkpoint at or before it, its size being the row count of that checkpoint's file. Data files are not touched.
3. Print per table the pass's version, its commits since the last checkpoint, and the objects deleted. Also print the production hour `H − 1`, for Q2's Gate, and the number of commits of `processed_objects` in it, which is 4 when its 4 runs all read before the checkpoint.
4. Update `README.md` with the cut command, its output and run time.

#### Check

`uv run --directory spikes/t077-run-time-and-r2-reads python count-per-call/cut_log.py --help` prints the usage; the cut runs in Step 7.

### Step 6 — Count-per-call script

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `chore: step 6 - add count per call to run time spike`
- **Model:** opus · medium
- **Gate:** —

#### Scope

`count-per-call/count_calls.py` and its section in `README.md`. It runs the 8 calls of [Lakehouse reads per run](#lakehouse-reads-per-run) one by one, through the proxy of Step 3, with the pipeline's own functions on the copy's `Lakehouse`. The batch of calls 4–6 replays the copy's last run (#2). Nothing in `pipeline/` changes.

#### Reads

- `pipeline/src/bikesharing/shell/run.py`, lines 549–680: the order of the calls and the arguments the run gives them; `count_calls.py` passes the same.
- `pipeline/src/bikesharing/shell/delta.py`, lines 238–490: the 8 calls' signatures and what each reads.

#### Do

1. Write `count_calls.py --pass 1|2`. Setup, labelled `setup`: read the copy's last run, meaning its `run_id` in `processed_objects`, its objects and their capture range, and that run's `station_stock` rows with their local dates.
2. Run the calls in the map's order, each labelled with its number and name, with the run's arguments: `capture_history` with `since` 7 days before the batch's first capture; `merge_station_stock` with the replayed rows, capture range and local dates; `record_processed` with one `ProcessedObject` per object of that run under the key `t077-probe/<n>`; `latest_processed` and `latest_captures` as in `_publish`.
3. Write `output/count-per-call/pass-<n>-requests.jsonl` and `pass-<n>-calls.csv`, with one row per call and one for setup: GetObject, other Class B, Class A, seconds, the table's version before the call and its commits since the last checkpoint (`(version + 1) % 100`, since `deltalake` 1.6.6 checkpoints at versions 99, 199, …). Print the table with the totals of calls 1–8 and of all rows. **#8**
4. Update `README.md` with the pass command, its outputs and run time.

#### Check

`uv run --directory spikes/t077-run-time-and-r2-reads python count-per-call/count_calls.py --help` prints the usage; the count runs in Step 7.

### Step 7 — Pass 1: the latest peak

- **Status:** ✅ done
- **Who:** Owner
- **Model:** —
- **Gate:** Q2's Gate in [Exit criteria](#14-exit-criteria): calls 1–8's GetObject ≥ 80% of production's GetObject per run in the hour `cut_log.py` printed → otherwise the share not accounted for is recorded in the Decision log, with the choice of widening the map within the timebox or opening a new task; Steps 8–11 run only if the map is widened, since otherwise the run ends ([Exit criteria](#14-exit-criteria) › Timebox).

#### Scope

The count per call at the version read by the last run of the last whole UTC hour before `processed_objects`' latest checkpoint, the worst case in the cycle that a whole production hour matches, checked against production in that hour and against the copy's own count in GraphQL.

#### Do

1. Run `uv run python count-per-call/cut_log.py --pass 1`.
2. At least 3 minutes after the cut ends, run `uv run python count-per-call/count_calls.py --pass 1`, once, noting its start and end.
3. Once the count's window has ended, run `r2_metrics.py` three times: `--bucket bikesharing-t077-lakehouse-copy` for that window, and `--bucket bikesharing-lakehouse` and `--bucket bikesharing-bronze` for the production hour `cut_log.py` printed.

#### Check

Report the two outputs and the three queries' figures. Yes when all three hold:

- each table's version before call 1 is the pass's version `cut_log.py` printed, and it printed 4 commits in the production hour;
- the copy's total requests for the count's window do not exceed the lines of `pass-1-requests.jsonl`, one per request, setup and failed ones included, by more than 0.5%;
- calls 1–8's GetObject, divided by production's GetObject in its hour ÷ 4, is ≥ 80%.

### Step 8 — Pass 2: the peak before it

- **Status:** ✅ done
- **Who:** Owner
- **Model:** —
- **Gate:** —

#### Scope

The same count one checkpoint earlier, about one day before. The difference between the passes is one day's growth at the same point of the cycle, for Q2's growth criterion. The cut also drops what pass 1 wrote.

#### Do

1. After pass 1's count window has ended, run `uv run python count-per-call/cut_log.py --pass 2`.
2. At least 3 minutes after the cut ends, run `uv run python count-per-call/count_calls.py --pass 2`, once, noting its start and end.
3. Once the count's window has ended, run the copy's and `bikesharing-lakehouse`'s queries of Step 7 for pass 2's window, in whole minutes as [Probe B](#b-count-per-call) defines it, and for its production hour.
4. From both passes' `calls.csv` and production queries, work out Q2's two guides in [Exit criteria](#14-exit-criteria):
   - **time:** per pass, the share of the mapped calls' seconds taken by the calls that hold 80% of their GetObject, adding calls from the largest count down;
   - **growth:** per call, pass 1's GetObject minus pass 2's, and its total against production's GetObject per run in pass 1's hour minus pass 2's.

#### Check

Report the two outputs, the queries' figures and Do 4's two results. Yes when each table's version before call 1 is the pass's version, `cut_log.py` printed 4 commits in the production hour, and the copy's total requests for the count's window do not exceed the lines of `pass-2-requests.jsonl` by more than 0.5%.

### Step 9 — Download Probe A's inputs

- **Status:** ✅ done
- **Who:** Owner
- **Model:** —
- **Gate:** —

#### Scope

The observed window's run log objects and each table's `_delta_log/` listing with production's `LastModified`, taken now, so that the window ends at this download. Read-only, with `r2-prod` (#3).

#### Do

1. Download the run logs from 2026-11-22 on: `rclone copy -P --include "/date=2026-11-2[2-9]/**" --include "/date=2026-11-30/**" --include "/date=2026-12-*/**" r2-prod:bikesharing-lakehouse/logs/pipeline data/logs`.
2. List both logs, with dates in RFC 3339 and their offset: `rclone lsf -R --files-only --format "tp" --time-format RFC3339 --include "/silver/station_stock/_delta_log/**" --include "/control/processed_objects/_delta_log/**" r2-prod:bikesharing-lakehouse > data/delta-log.txt`.

#### Check

Report the number of `.jsonl` files under `data/logs/` per date folder and the line count of `data/delta-log.txt`. Yes when every date from 2026-11-22 to today has a folder.

### Step 10 — Checkpoint cycle script

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `chore: step 10 - add checkpoint cycle analysis to run time spike`
- **Model:** sonnet · medium
- **Gate:** —

#### Scope

`checkpoint-cycle/cycle_times.py`, with the standard library only, and Probe A's section in `README.md`. Offline: it reads `data/logs/` and `data/delta-log.txt`, whose RFC 3339 dates it converts to UTC from their offset, and makes no request.

#### Reads

- [Probe A](#a-checkpoint-cycle-in-time) and Q1's criterion in [Exit criteria](#14-exit-criteria).
- `time-per-phase/run_phases.py`: how the baseline reads the run's events and derives discovery's time, which `cycle_times.py` follows on local files.
- `pipeline/src/bikesharing/core/events.py`, the builders of `run_started` and `objects_discovered`: the fields and the `ts` format of the events it reads.

#### Do

1. Write `cycle_times.py`: per run, its discovery time as `objects_discovered.ts` − `run_started.ts`. Per table, the times of its checkpoints, from the `LastModified` of `NNN.checkpoint.parquet`. Per run, its commits since the last checkpoint of `processed_objects` at its start.
2. For each checkpoint of `processed_objects` in the window: the mean discovery time of the 4 runs right before it and the 4 right after, and the drop in percent. Mark each drop ≥ 20%.
3. Write `output/checkpoint-cycle/runs.csv` (one row per run) and `checkpoints.csv` (one row per checkpoint), and print `checkpoints.csv`. Runs with no `objects_discovered` are listed apart with their count.
4. Update `README.md` with Probe A's section: its question, Step 9's commands, this script's command, outputs and run time.

#### Check

`uv run --directory spikes/t077-run-time-and-r2-reads python checkpoint-cycle/cycle_times.py` prints one row per checkpoint of the window.

### Step 11 — Run and hand-check the checkpoint cycle

- **Status:** ✅ done
- **Who:** Owner
- **Model:** —
- **Gate:** —

#### Scope

Probe A's result for Q1, with the script checked by hand against known arithmetic on one checkpoint and one run.

#### Do

1. Run `uv run python checkpoint-cycle/cycle_times.py`.
2. Choose one checkpoint from `checkpoints.csv`, find its `LastModified` in `data/delta-log.txt`, and check that the 4 runs before and after it in `runs.csv` are the ones whose `run_started` falls right before and after that time.
3. For one of those runs, open its `.jsonl` under `data/logs/`, subtract `run_started`'s `ts` from `objects_discovered`'s, and compare with its discovery time in `runs.csv`.

#### Check

Report `checkpoints.csv` and the two hand checks. Yes when the runs of Do 2 are the right ones and Do 3 matches to the millisecond.

## 4. Findings

<!-- Filled during the run, in the step that produces the evidence. One fact per finding: what was observed, the evidence (figures, tables) and its consequence for the spike. Numbering is never reused. An earlier finding is not rewritten to fit a later result; the later one says which finding it corrects. -->

### F1. The copy's bucket holds the listed snapshot of both tables, identical to production

Step 2 · 2026-11-25 · `rclone copy` and `rclone check` output, `data/copy/keys.txt`, `data/copy/delta-log.txt`

- The snapshot lists 3,081 objects in `silver/station_stock/` and `control/processed_objects/`, 1,530 of them under `_delta_log/`; they take 227 MB.
- `rclone copy` transferred 3,081 of 3,081 objects from 20:17 to about 20:35 UTC, in 17 min 46 s, with no errors.
- `rclone check` over the same list reported 0 differences at 22:03 UTC.
- Requests on the copy's bucket so far: one listing in the hour 19:00Z, the copy in 20:00Z and the check in 22:00Z.
- Consequence: the Gate passes; Probe B reads this copy, and Step 4's smoke test runs in an hour with no other requests on the copy's bucket.

### F2. A later query of the baseline window returns other operation counts for `bikesharing-bronze`

Step 4 · 2026-11-26 · `r2_metrics.py` with no arguments, compared with the [README's output](../../spikes/t077-run-time-and-r2-reads/README.md#r2-operations-and-storage) of 2026-11-23

| `bikesharing-bronze` | 2026-11-23 | 2026-11-26 | Difference |
|---|---|---|---|
| GetObject | 161,760 | 163,526 | +1.1% |
| PutObject | 12,420 | 11,754 | −5.4% |
| ListObjects | 1,040 | 1,026 | −1.3% |
| Sum of the three | 175,220 | 176,306 | +0.6% |

- The 2026-11-26 figures include 4 GetObject and 1 PutObject with status `internalError`.
- `bikesharing-lakehouse`'s GetObject (1,263,034), PutObject (993) and ListObjects (3,783) and both buckets' storage figures are identical in both queries.
- Since the baseline, `r2_metrics.py` has gained its arguments and totals; the GraphQL query's text is unchanged, and with no arguments it takes the same buckets and window.
- Not confirmed: the cause. R2's operation metrics are sampled ([s010 › F14](s010-storage-table-format.md#4-findings)), which did not study how a window's counts change between queries.
- Consequence: the token check passes on the figures that match (#7).

### F3. The proxy sees every request that opening both tables makes on R2

Step 4 · 2026-11-26 · `proxy.py --smoke`, started at 06:50:55 UTC, and `r2_metrics.py` on `bikesharing-t077-lakehouse-copy` from 06:00 to 07:00 UTC

| Source | GetObject | Other Class B | Class B | Class A | Total |
|---|---|---|---|---|---|
| Proxy | 252 | 0 | 252 | 2 | 254 |
| R2 metrics | 252 | 0 | 252 | 2 (ListObjects) | 254 |

- `silver/station_stock/` and `control/processed_objects/` opened at version 756, with 126 GetObject and 1 Class A request each and no failed request, in 4.3 s.
- The metrics report 3,081 objects in the bucket, as many as the snapshot lists (F1), with a payload of 0.221 GB; F1 gives 227 MB, and the difference was not examined.
- Consequence: the Gate passes with no difference in any count; the scripts of Probe B can be built on the proxy.

### F4. A MERGE that inserts no row writes no commit

Step 6 · 2026-11-26 · `count_calls.py`'s setup and 8 calls on a local lakehouse with two runs, `deltalake` 1.6.6, no proxy

- Call 5's replay merged the last run's 4 rows again: 0 inserted, 0 updated, and `station_stock` stayed at its version.
- Call 6 recorded the 2 objects under `t077-probe/` keys and moved `processed_objects` one version up.
- Consequence: in Probe B, call 5 writes no commit, while production's merge does. Call 8 opens `station_stock` with one commit fewer to replay than production, at the same version as call 5. `count_calls.py` moves a version only on a commit the proxy sees written.

### F5. The operations query filters the copy's requests to the minute

Step 7 · 2026-11-26 · `r2_metrics.py` on the copy's bucket, three windows around pass 1's first count, which started at 08:05:00 UTC and stopped in setup

- Total requests: 0 from 08:00 to 08:05, 448 from 08:05 to 08:10 and 0 from 08:10 to 08:30.
- The proxy had logged 406 of them. The missing 42 fit the requests whose client had gone before the proxy answered, which it did not record then; it records them now.
- Consequence: a window of whole minutes isolates a count (#9).

### F6. Pass 1 counts 12,369 GetObject in the 8 calls, most in five full reads of `processed_objects`

Step 7 · 2026-11-26 · `count_calls.py --pass 1` from the owner's machine, both tables at version 694, 95 commits since the checkpoint, replaying a run of 26 objects and 9,834 `station_stock` rows

| Row | Call | GetObject | Time (s) |
|---|---|---|---|
| setup | Replayed run's read, counted apart | 2,518 | 14.9 |
| 1 | `ensure_tables` | 808 | 7.95 |
| 2 | `processed_keys` | 2,310 | 12.68 |
| 3 | `latest_processed` | 2,310 | 12.61 |
| 4 | `capture_history` | 1,901 | 10.35 |
| 5 | `merge_station_stock` | 205 | 1.78 |
| 6 | `record_processed` | 2,312 | 13.16 |
| 7 | `latest_processed` | 2,315 | 12.36 |
| 8 | `latest_captures` | 208 | 2.04 |
| 1–8 | Total | 12,369 | 72.93 |

- No request failed. Call 6 moved `processed_objects` to version 695.
- Calls 2, 3, 4, 6 and 7 make 11,148 GetObject (90%).

### F7. The 8 calls account for production's GetObject per run

Step 7 · 2026-11-26 · `r2_metrics.py` on `bikesharing-lakehouse` from 04:00 to 05:00 UTC on 2026-11-25, the hour `cut_log.py` printed, with 4 commits of `processed_objects`

- 49,369 GetObject in the hour, 12,342 per run.
- Calls 1–8 make 12,369 (F6): 100.2%.
- Consequence: Q2's Gate passes.

### F8. R2 counts 1.4% fewer requests than the proxy in pass 1's window

Step 7 · 2026-11-26 · the copy's bucket from 08:44 to 08:48 UTC, queried twice, minutes apart; the count ran from 08:45:21 to 08:46:51

- The proxy logged 14,907 requests, none failed. R2 gave 14,698 both times: −1.40%.
- By operation, R2 gave 14,683 GetObject against the proxy's 14,887, and 15 Class A against 20.
- The cause of the difference is not verified.
- Consequence: no sign of a client that reaches R2 without the proxy (#10).

### F9. `bikesharing-bronze` has at most 61 GetObject per run in pass 1's production hour

Step 7 · 2026-11-26 · `r2_metrics.py` on `bikesharing-bronze` from 04:00 to 05:00 UTC on 2026-11-25

- 243 GetObject in the hour, from the pipeline and any other reader: at most 60.75 per run of the pipeline.

### F10. Pass 2 counts 10,801 GetObject in the 8 calls

Step 8 · 2026-11-26 · `count_calls.py --pass 2` from the owner's machine, both tables at version 594, 95 commits since the checkpoint, replaying a run of 30 objects and 11,715 `station_stock` rows

| Row | Call | GetObject | Time (s) |
|---|---|---|---|
| setup | Replayed run's read, counted apart | 2,218 | 14.83 |
| 1 | `ensure_tables` | 808 | 8.67 |
| 2 | `processed_keys` | 2,010 | 12.64 |
| 3 | `latest_processed` | 2,010 | 11.06 |
| 4 | `capture_history` | 1,533 | 8.78 |
| 5 | `merge_station_stock` | 205 | 1.85 |
| 6 | `record_processed` | 2,012 | 12.51 |
| 7 | `latest_processed` | 2,015 | 11.16 |
| 8 | `latest_captures` | 208 | 2.15 |
| 1–8 | Total | 10,801 | 68.82 |

- No request failed. `cut_log.py` set both tables at version 594, with 4 commits of `processed_objects` in the production hour.
- Production's hour, from 03:00 to 04:00 UTC on 2026-11-24, has 43,187 GetObject on `bikesharing-lakehouse`, 10,797 per run: the 8 calls make 100.0%.

### F11. R2 counts 0.25% more requests than the proxy in pass 2's window

Step 8 · 2026-11-26 · the copy's bucket from 09:09 to 09:13 UTC; the count ran from 09:10:06 to 09:11:32

- The proxy logged 13,039 requests, none failed. R2 gave 13,071: +0.25%.
- By operation, R2 gave 13,048 GetObject against the proxy's 13,019, and 23 Class A against 20.
- In pass 1's window the difference had the other sign (F8). The cause of either is not verified.
- Consequence: the difference is within the 0.5% of the independent count (#10).

### F12. The calls that hold 80% of the GetObject take over 80% of the mapped calls' time

Step 8 · 2026-11-26 · F6 and F10, adding calls from the largest GetObject count down

| Pass | Calls that hold 80% | Their GetObject | Their time (s) | Time of calls 1–8 (s) | Share of time |
|---|---|---|---|---|---|
| 1 | 7, 6, 2, 3, 4 | 11,148 (90.1%) | 61.16 | 72.93 | 83.9% |
| 2 | 7, 6, 2, 3, 4 | 9,580 (88.7%) | 56.15 | 68.82 | 81.6% |

- Calls 2, 3, 6 and 7 alone stay under 80% of the GetObject in both passes (74.8% and 74.5%), so call 4 is included.
- Consequence: Q2's time guide (≥ 70%) is met in both passes.

### F13. From pass 2 to pass 1, only the calls 2, 3, 4, 6 and 7 grow

Step 8 · 2026-11-26 · F6 minus F10

| Call | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | Total |
|---|---|---|---|---|---|---|---|---|---|
| GetObject, pass 1 − pass 2 | 0 | 300 | 300 | 368 | 0 | 300 | 300 | 0 | 1,568 |

- Calls 5 and 8, which open `station_stock` alone, and call 1 make the same GetObject in both passes.

### F14. The count's growth matches production's growth per run

Step 8 · 2026-11-26 · F7, F10 and F13

- Production's GetObject per run goes from 10,796.75 (03:00 UTC on 2026-11-24) to 12,342.25 (04:00 UTC on 2026-11-25), 25 h later: +1,545.5.
- Calls 1–8 grow by 1,568 between the two passes: 101.5% of production's growth.
- Consequence: Q2's growth guide (same sign and order of magnitude) is met.
- The run replayed in F6 recorded 26 objects. How many objects each of the hour's runs downloads was not read.

### F15. Discovery's time drops by 20% or more at none of the window's 5 checkpoints

Step 11 · 2026-11-26 · `cycle_times.py` over the 424 runs from 00:00 UTC on 2026-11-22 to 09:15 UTC on 2026-11-26, all with a discovery time

| Checkpoint of `processed_objects` | Written (UTC) | Mean of the 4 runs before (s) | Mean of the 4 runs after (s) | Change in discovery's time |
|---|---|---|---|---|
| 399 | 2026-11-22 03:17:08 | 24.372 | 35.093 | +44.0% |
| 499 | 2026-11-23 04:16:02 | 21.501 | 35.587 | +65.5% |
| 599 | 2026-11-24 04:45:54 | 33.565 | 51.637 | +53.8% |
| 699 | 2026-11-25 05:48:40 | 49.055 | 41.243 | −15.9% |
| 799 | 2026-11-26 06:47:04 | 53.836 | 72.965 | +35.5% |

- The change is the mean after against the mean before; `checkpoints.csv` gives it as a drop, with the opposite sign. Discovery's time rises at four checkpoints and drops at one.
- Hand check on checkpoint 799: its `LastModified` splits the runs as the script does, the commits since the last checkpoint going from 99 to 0 there, and the 8 runs' discovery times give both means. For the run started at 06:45:09, the gap between the two events in its log object is 55.251 s, as in `runs.csv`.
- Consequence: Q1's checkpoint cycle guide (a drop of 20% or more at every checkpoint) is not met.

### F16. The lakehouse calls take about 90% of a production run's time

Conclusion · 2026-11-26 · the events of the production run started at 07:15:07.861 UTC, in Grafana Cloud's logs; one run, 28 min after `processed_objects`' checkpoint 799

| Segment | From → to | Time (s) | Holds |
|---|---|---|---|
| Discovery | `run_started` → `objects_discovered` | 65.5 | Calls 1–3 and the bronze listing |
| Batch preparation | `batch_started` → first `node_finished` | 27.1 | Call 4 and the bronze downloads |
| Transformation | first → ninth `node_finished` | 0.8 | The dbt models on DuckDB |
| Rules | first → last `rule_checked` | 5.7 | Almost all of it in one rule |
| Write | last `rule_checked` → `batch_committed` | 28.5 | Calls 5 and 6 |
| Gold | `batch_committed` → last `node_finished` | 30.6 | Calls 7 and 8, and the gold model |
| Publish | last `node_finished` → `page_deployed` | 6.5 | Building and deploying the page |
| Total | `run_started` → `run_finished` | 165.2 | |

- The segments that hold the 8 calls take about 150 s, twice their 73 s from the owner's machine (F6); this split includes the bronze downloads, which were not timed apart.
- Consequence: no cause of the run time outside the lakehouse calls is as large as they are; the rules' 5.7 s and the publish's 6.5 s are the largest left.

## 5. Conclusion

<!-- Filled after the last step. Covers only the observed window. -->

Observed window: 2026-11-22 00:00 to 2026-11-26 09:15 UTC for Probe A; Probe B at the two latest peaks, the versions read at 2026-11-24 03:00 and 2026-11-25 04:00 UTC. It does not cover a feed's catch-up, answered by arithmetic in the Verdict, nor the daily pattern per operation.

### 5.1 Answers

- **Q1. Checkpoint cycle in time.** No. The GetObject per run drop at each checkpoint ([Context](#11-context)), but discovery's time does not: it rises after four of the window's five checkpoints and drops by 15.9% at the other. Log replay (H2) shapes the reads' sawtooth, not the run time. (F15)
- **Q2. Count per call.** Yes. The 8 calls account for 100.2% and 100.0% of production's GetObject per run (F7, F10); the four full reads of `processed_objects` and `capture_history` (calls 2, 3, 4, 6, 7) hold about 90% of them and over 80% of the calls' time (F12), and are the only calls that grow, by 101.5% of production's growth (F14). The unbounded reads of the control table (H1) are the cause of the read volume and of its growth. (F6–F14)

### 5.2 Exit criteria

<!-- One result per criterion and variant. -->

| Criterion | Kind | Result | Findings |
|---|---|---|---|
| **Q2, reads:** GetObject counted in the 8 calls, against production's per run | Hard cut (Gate), ≥ 80% | **Pass:** 100.2% in pass 1, 100.0% in pass 2 | F7, F10 |
| **Q2, time:** local time of the calls that hold 80% of the GetObject, against all the mapped calls | Guide, ≥ 70% | **Met:** 83.9% and 81.6% | F12 |
| **Q2, growth:** the count's growth between passes, against production's growth per run | Guide, same sign and order of magnitude | **Met:** +1,568 against +1,545.5 (101.5%) | F13, F14 |
| **Q1, checkpoint cycle:** discovery's time, 4 runs after each checkpoint against 4 before | Guide, a drop of 20% or more at every checkpoint | **Not met:** no checkpoint reaches it; the time rises at four of the five | F15 |

### 5.3 Verdict

<!-- The answer to the main question in 2–3 sentences. -->

The lakehouse reads per run grow because the pipeline reads its control table in full, again and again, while that table only accumulates small files. A Delta maintenance and access pattern for every pipeline table bounds them, in steady runs and in a catch-up.

**Causes:** the evidence confirms H1 and only part of H2.

- **H1, confirmed:** `processed_objects` is read in full four times per run, plus `capture_history`; it gains one small file per run and is never compacted. These calls hold about 90% of the GetObject and all of their growth (Q2).
- **H2, partly:** log replay on each of the run's 9 opens shapes the reads' checkpoint sawtooth, not the run time (Q1).
- **The run time's daily pattern:** not explained by either ([Not verified](#54-not-verified)).

**Fix:** one Delta maintenance and access pattern for every pipeline table, recorded as an ADR and applied by a design (D1). Each table is treated by how it is written and read:

- every table is opened once per run, and its handle is reused across the run's calls;
- every table is partitioned by the range its readers filter by, and every read and MERGE states that range, so that it is pruned by partition and by file statistics:
  - `processed_objects` by system and capture date; its MERGE's predicate adds the batch's capture range, since a batch's keys span both systems and prune no file by key alone;
  - `station_stock` by local date, with `deltalake` 1.7.0, whose MERGE prunes its target by the batch's capture range;
- a compaction never merges files within the range a reader prunes by:
  - `processed_objects`' active partitions are compacted after any batch that leaves them with a threshold of small files, since its readers read them whole;
  - `station_stock`'s active partition is not compacted, since its MERGE and `latest_captures` prune within the day;
  - every closed partition is compacted once;
- discovery reads only the processed keys from its listing's start, the latest processed capture minus the lookback, and the daily full sweep is removed: an object later than the lookback is recovered by rediscovering its window on demand;
- each system's latest processed capture is taken from the log's file statistics, with no data read, so that it stays bounded when a system stops capturing;
- every table is vacuumed, within the retention of [ADR-0021](../decisions/0021-retention-per-layer.md).

**Effect, by arithmetic on F3, F6 and F13** (about 2 GetObject per commit replayed and 3 per data file):

- **Steady runs:** pass 1's 12,369 GetObject per run drop to about 400 on average and 700 at most, at 95 commits since the checkpoint and a threshold of 10 small files; none of the terms grows with the processed objects, and `processed_objects`' reads cover 7 days instead of its whole history.
- **Catch-up:** each batch reads only its own partitions and the 7 days before them, so its cost stays flat instead of growing with each batch.

**Left out of the fix:** Modal's region, until D2's rule calls for it ([Production inputs](#55-production-inputs)).

### 5.4 Not verified

<!-- What the evidence does not cover, each with its risk and mitigation. "None" is valid. -->

- **The run time's daily pattern** (up to twice as slow from 16:00 to 23:00 Madrid time, US Eastern business hours) has two candidate causes not told apart: load on Modal's US infrastructure or on the transatlantic network, or `station_stock`'s active partition, largest by evening and read in full by `deltalake` 1.6.6's MERGE. Nor is it known why discovery's time rises after four of the five checkpoints (F15) — a cause outside the lakehouse's reads stays after the fix — with `deltalake` 1.7.0 the partition no longer weighs, so a pattern left after the fix is external, and D2's rule applies to it
- **Why `capture_history` skips about 23 files fewer in pass 1 than in pass 2** (F13: +368 GetObject against +300 for a full read), although its 7-day window only moves forward: the bound `until` depends on the replayed run, the files may not cost 3 GetObject each, or the reader may prune by Parquet footers instead of the Delta log's statistics — its bound prunes less than designed — if P7's reads are not met after the fix, its pruning is checked first

### 5.5 Production inputs

<!-- Optional. What a later task must take into account when it builds, from any part of the spike: done when that task runs. Each one has a Destination: the `TODO(TNNN)` marker (CLAUDE.md › Pending items), or discarded with a reason. -->

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | Every pipeline table follows the Delta maintenance and access pattern: opened once per run and its handle reused across the run's calls, which is safe since runs never overlap, and refreshed after a MERGE if `deltalake` does not refresh it; a missing table is created without opening the existing ones again; every read and MERGE states the range it needs, pruned by partition and by file statistics; `deltalake` 1.7.0, whose MERGE prunes its target | Verdict, F6–F14 | TODO(T072): apply the Delta pattern to every pipeline table |
| P2 | `processed_objects` is partitioned by system and capture date, UTC as in the bronze key or local as in [ADR-0041](../decisions/0041-utc-timestamps-local-calendar-keys.md), as the design sets. Its MERGE's predicate adds the batch's capture range, which keeps the result, since `captured_at` derives from the key. Its active partitions are compacted with `optimize.compact`, which keeps insertion order, after any batch that leaves them with a threshold of small files (10 in the Verdict's arithmetic, set by the design); every closed partition is compacted once. Sorting by key adds nothing: within a partition, key order is capture order | Verdict, F13 | TODO(T072): partition `processed_objects` by system and date, bound its MERGE, compact by threshold |
| P3 | `station_stock`'s active partition is not compacted, since one file spanning the day would defeat pruning by capture range; the MERGE prunes it by the batch's capture range, and `latest_captures` by the latest capture; each partition is compacted once it closes | Verdict | TODO(T072): prune `station_stock` by capture range, compact closed partitions |
| P4 | Discovery reads only the processed keys from its listing's start, the latest processed capture minus the lookback; the daily full sweep is removed, following a watermark with allowed lateness, the lookback; a system with nothing processed keeps the full listing. Each system's latest processed capture is taken from the log's file statistics, with no data read, so that it stays bounded when a system stops capturing; if `deltalake` 1.7.0 does not expose them, from that system's latest partition. The lookback, a constant of 1 h with no recorded reason ([d008 › `bikesharing.core.settings`](../designs/d008-pipeline-platform-and-walking-skeleton.md#bikesharingcoresettings)), becomes the only net for late objects: it is set from bronze's measured lateness, each object's `LastModified` minus the capture instant in its key, plus a margin | Verdict | TODO(T072): bound discovery's reads, take the latest capture from the log, set the lookback from lateness |
| P5 | A window of bronze is rediscovered on demand through the one-off run, given its start and end: listed, compared with the processed keys of that window, and processed through the same batch path as a scheduled run | Verdict | TODO(T072): rediscover a window through the one-off run |
| P6 | Every table is vacuumed within the table history of [s010 › D6](s010-storage-table-format.md), and has a checkpoint interval set per table | Verdict | TODO(T072): vacuum and set a checkpoint interval per table |
| P7 | Done when, 24 h after the deploy: GetObject per run on `bikesharing-lakehouse` (`r2_metrics.py`) is about 400 on average and at most 700, and p95 run time (`run_stats.py`) is at most 2 min, the estimate [ADR-0027](../decisions/0027-modal-as-execution-platform.md) rests on; if not, `capture_history`'s pruning is checked first | Verdict, F16 | TODO(T072): check reads and run time 24 h after the deploy |
| P8 | Modal's region follows D2's rule, applied to the lakehouse requests left per run after the fix | D2 | TODO(T072): apply D2's rule to Modal's region after the fix |
| P9 | A regression indicator: per-run metrics (run and phase durations, objects processed) sent over OTLP, and R2's operations per bucket and hour from Cloudflare's GraphQL Analytics API, fetched 2–3 times a day; alerts on their trend instead of a log query | Verdict | TODO(T078.2): metrics and alerts for the pipeline's run time and R2 operations |
| P10 | A failed checkpoint after a commit raises from the write although the commit has landed ([delta-rs#4986](https://github.com/delta-io/delta-rs/issues/4986)), so the run takes a written batch as failed | Verification of 5.6 Records | Discarded: every Delta write of the pipeline is an insert-only MERGE by key, so the next run's retry of the batch inserts nothing, and the only effect is a run reported as failed |

### 5.6 Records

<!-- Documents this spike updates before it closes: ADRs from Decided at framing (each in its own commit), architecture, requirements, source cards and new tasks agreed with the owner. A decision that updates no document has no row. Commit: "Done", or "Pending" until delivered; the spike closes when every row is Done. Production inputs are not repeated here. -->

| Output | From | Destination | Commit |
|---|---|---|---|
| ADR on the Delta maintenance and access pattern for the pipeline's tables: the control table stays in Delta; every table is opened once per run, partitioned by the range its readers filter by, read and merged stating that range, compacted inside the run without merging files within a range a reader prunes by, and vacuumed within its history | Verdict | `docs/decisions/` | Pending |
| T072 rewritten as the fix's task, blocked by T077 | Verdict | Issue #86 | Done |
| T077's Done when reduced to what this spike delivers | Verdict | Issue #101 | Done |

## 6. Sources

<!-- Optional. Earlier spikes, benchmarks and documentation used. -->

- `deltalake` 1.6.6's source, at the tag `python-v1.6.6` of [delta-io/delta-rs](https://github.com/delta-io/delta-rs/tree/python-v1.6.6):
  - checkpoints every 100 commits by default: `crates/core/src/table/config.rs` and `crates/core/src/kernel/transaction/mod.rs`;
  - no target pruning in a streamed MERGE: `crates/core/src/operations/merge/mod.rs` and `filter.rs`, and [delta-rs#3491](https://github.com/delta-io/delta-rs/issues/3491); fixed in 1.7.0 by [delta-rs#4790](https://github.com/delta-io/delta-rs/pull/4790);
  - a grouped aggregate is not answered from statistics: DataFusion's [`aggregate_statistics.rs`](https://github.com/apache/datafusion/blob/main/datafusion/physical-optimizer/src/aggregate_statistics.rs).
- `deltalake` 1.7.0's source and release, at the tag [`python-v1.7.0`](https://github.com/delta-io/delta-rs/releases/tag/python-v1.7.0), checked for the ADR of [Records](#56-records):
  - streamed MERGE prunes target files with the source's statistics (#4790, #4796): the release notes;
  - `optimize.compact` keeps the files' order and does not sort; only `optimize.z_order` reorders, also on an unpartitioned table; the default target size is 100 MiB: `python/deltalake/table.py` and `crates/core/src/operations/optimize.rs`;
  - `vacuum` keeps 7 days by default (`delta.deletedFileRetentionDuration`), and `delta.checkpointInterval` is honoured per table, 100 by default: `crates/core/src/table/config.rs`;
  - scans prune whole files by partition values and the log's file statistics, not confirmed by Parquet row group: `crates/core/src/delta_datafusion/table_provider.rs`;
  - no auto compaction, only an explicit `optimize`; the threshold of 50 small files found for Spark's auto compaction is in no Delta or Databricks page, so the threshold is set by the design;
  - a failed checkpoint after a commit raises from the write: [delta-rs#4986](https://github.com/delta-io/delta-rs/issues/4986).
