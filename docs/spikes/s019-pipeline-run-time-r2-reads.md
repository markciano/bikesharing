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
- Current: Step 2.
- Parked for the Conclusion: whether the control table stays in Delta; which full reads of `processed_objects` can be bounded to a recent window (late or out-of-order objects, a feed's catch-up, discovery's `full_sweep`); and what Delta maintenance (compaction, checkpoint interval) fixes versus a code change; all among the fix's candidates.

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
| **Q2, reads:** GetObject counted in the calls of [Lakehouse reads per run](#lakehouse-reads-per-run), against production's GetObject per run in each pass's hour ([Probe B](#b-count-per-call)) | ≥ 80% | **Hard cut (Gate)** | R2's totals match an exact count within 0.02% ([s010 › F14](s010-storage-table-format.md#4-findings)), so the margin is for what the map leaves out: small calls, such as the log's upload, and other readers of the bucket during the window, such as analysis scripts |
| **Q2, time:** local time of the calls that hold 80% of the counted GetObject, against the local time of all the mapped calls | ≥ 70% | Guide | Probe B runs locally, where latency is lower than from Modal, so time is compared as a share among calls, not against production's runs |
| **Q2, growth:** the part of the count that grows with `processed_objects`' files, against the measured growth per run | Same sign and order of magnitude | Guide | It confirms that H1 is what grows, not only what weighs |
| **Q1, checkpoint cycle:** discovery's time in the 4 runs right after each checkpoint, against the 4 right before | A drop of 20% or more at every checkpoint of the window | Guide | The hour of the day causes no sudden drop at a checkpoint; 4 runs span 1 h, too short for the slow growth to interfere |

If Q2's Gate fails, the share not accounted for is a cause still to find: the Decision log records it, with the choice of widening the map within the timebox or opening a new task.

### 1.5 Out of scope

<!-- Optional. What someone could expect this spike to answer and it will not, each item pointing to the task that covers it. -->

- Which readers other than the pipeline account for `bikesharing-bronze`'s GetObject: they do not slow the runs, and the cost model needs them per bucket — T077, in the cost recalibration of [d008 › Known gaps at close](../designs/d008-pipeline-platform-and-walking-skeleton.md#42-known-gaps-at-close)

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

Each pass is checked against an independent count. The copy's bucket receives only the probe's requests, so its hourly Class B operations must match the proxy's total for that pass within 0.02% ([s010 › F14](s010-storage-table-format.md#4-findings)). This catches a client that reaches R2 without the proxy. The two passes and the cut run in separate hours, so that each hourly figure holds one of them alone.

Every operation figure, of production and of the copy, comes from Cloudflare's GraphQL Analytics API (`r2OperationsAdaptiveGroups`), through the baseline's `r2_metrics.py` extended with a bucket and an hour. R2's dashboard is not used: its figures are not exact and it documents no breakdown per operation ([cloudflare › R2: metrics](../sources/cloudflare.md#r2-metrics)). **#5**

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
| 5 | [Probe B](#b-count-per-call) | Every R2 operation figure comes from the GraphQL Analytics API, through the baseline's `r2_metrics.py` extended with a bucket and an hour; counts match within 0.02%. Standard: reuse of a validated measurement tool ([s010 › Step 5](s010-storage-table-format.md#step-5--run-probe-a-and-verify-the-analysis)) | The dashboard is not exact and documents no breakdown per operation, while Q2's Gate needs GetObject | Steps review |
| 6 | [File layout](#24-file-layout) | The baseline's four folders stay in the spike folder, unchanged except `r2_metrics.py`; Step 1 updates the README instead of writing it. Standard: provenance of cited evidence | d008 and this report cite their figures; keeping them costs only the README's update | Steps review |

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
│   └── r2_metrics.py        The baseline's GraphQL query, extended with optional bucket and hour arguments for Probe B's checks
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

All paths below are relative to `spikes/t077-run-time-and-r2-reads/`, and commands run from there unless they say otherwise. Times are UTC; R2's operation figures are read with `r2_metrics.py` for whole UTC hours, given as `YYYY-MM-DDTHH:00:00Z`, once the hour has ended (#5). Steps that put requests on the copy's bucket (2, 4, 7, 8) each run their parts in separate hours, as the step says, so that each hourly figure holds one part alone ([Probe B](#b-count-per-call)).

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

- **Status:** 💤 todo
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

- **Status:** 💤 todo
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

- **Status:** 💤 todo
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

Report the smoke output, whether Do 2 matched the baseline, and Do 3's output. Yes when Do 2 matches and the proxy's Class B total equals Do 3's within 0.02%.

### Step 5 — Log cut script

- **Status:** 💤 todo
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

- **Status:** 💤 todo
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
3. Write `output/count-per-call/pass-<n>-requests.jsonl` and `pass-<n>-calls.csv`, with one row per call and one for setup: GetObject, other Class B, Class A, seconds, the table's version before the call and its commits since the last checkpoint (`version % 100`, since `deltalake` 1.6.6 checkpoints every 100 commits). Print the table with the totals of calls 1–8 and of all rows.
4. Update `README.md` with the pass command, its outputs and run time.

#### Check

`uv run --directory spikes/t077-run-time-and-r2-reads python count-per-call/count_calls.py --help` prints the usage; the count runs in Step 7.

### Step 7 — Pass 1: the latest peak

- **Status:** 💤 todo
- **Who:** Owner
- **Model:** —
- **Gate:** Q2's Gate in [Exit criteria](#14-exit-criteria): calls 1–8's GetObject ≥ 80% of production's GetObject per run in the hour `cut_log.py` printed → otherwise the share not accounted for is recorded in the Decision log, with the choice of widening the map within the timebox or opening a new task; Steps 8–11 run only if the map is widened, since otherwise the run ends ([Exit criteria](#14-exit-criteria) › Timebox).

#### Scope

The count per call at the version read by the last run of the last whole UTC hour before `processed_objects`' latest checkpoint, the worst case in the cycle that a whole production hour matches, checked against production in that hour and against the copy's own count in GraphQL.

#### Do

1. In one UTC hour, run `uv run python count-per-call/cut_log.py --pass 1`.
2. In the next UTC hour, run `uv run python count-per-call/count_calls.py --pass 1`, once.
3. Once that hour has ended, run `r2_metrics.py` three times: `--bucket bikesharing-t077-lakehouse-copy` for the count's hour, and `--bucket bikesharing-lakehouse` and `--bucket bikesharing-bronze` for the production hour `cut_log.py` printed.

#### Check

Report the two outputs and the three queries' figures. Yes when all three hold:

- each table's version before call 1 is the pass's version `cut_log.py` printed, and it printed 4 commits in the production hour;
- the copy's Class B for the hour equals the Class B total of all rows of `pass-1-calls.csv`, setup included, within 0.02%;
- calls 1–8's GetObject, divided by production's GetObject in its hour ÷ 4, is ≥ 80%.

### Step 8 — Pass 2: the peak before it

- **Status:** 💤 todo
- **Who:** Owner
- **Model:** —
- **Gate:** —

#### Scope

The same count one checkpoint earlier, about one day before. The difference between the passes is one day's growth at the same point of the cycle, for Q2's growth criterion. The cut also drops what pass 1 wrote.

#### Do

1. In a UTC hour after the one in which pass 1's count ran, run `uv run python count-per-call/cut_log.py --pass 2`.
2. In the next UTC hour, run `uv run python count-per-call/count_calls.py --pass 2`, once.
3. Once that hour has ended, run the copy's and `bikesharing-lakehouse`'s queries of Step 7 for pass 2's hours.
4. From both passes' `calls.csv` and production queries, work out Q2's two guides in [Exit criteria](#14-exit-criteria):
   - **time:** per pass, the share of the mapped calls' seconds taken by the calls that hold 80% of their GetObject, adding calls from the largest count down;
   - **growth:** per call, pass 1's GetObject minus pass 2's, and its total against production's GetObject per run in pass 1's hour minus pass 2's.

#### Check

Report the two outputs, the queries' figures and Do 4's two results. Yes when each table's version before call 1 is the pass's version, `cut_log.py` printed 4 commits in the production hour, and the copy's Class B for the hour equals the Class B total of `pass-2-calls.csv`, within 0.02%.

### Step 9 — Download Probe A's inputs

- **Status:** 💤 todo
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

- **Status:** 💤 todo
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

- **Status:** 💤 todo
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

### F1. `<one-line statement>`

Step N · YYYY-MM-DD · `<source of evidence>`

- `<evidence>`
- Consequence: `<for variants, steps or questions>`

## 5. Conclusion

<!-- Filled after the last step. Covers only the observed window. -->

Observed window: `<from–to, UTC; what it does not cover>`

### 5.1 Answers

- **Q1. Title** `<answer>` (FN)

### 5.2 Exit criteria

<!-- One result per criterion and variant. -->

| Criterion | Kind | Result | Findings |
|---|---|---|---|

### 5.3 Verdict

<!-- The answer to the main question in 2–3 sentences. -->

### 5.4 Not verified

<!-- What the evidence does not cover, each with its risk and mitigation. "None" is valid. -->

- `<item>` — `<risk>` — `<mitigation>`

### 5.5 Production inputs

<!-- Optional. What a later task must take into account when it builds, from any part of the spike: done when that task runs. Each one has a Destination: the `TODO(TNNN)` marker (CLAUDE.md › Pending items), or discarded with a reason. -->

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | | `<e.g. D1, #2, F3>` | |

### 5.6 Records

<!-- Documents this spike updates before it closes: ADRs from Decided at framing (each in its own commit), architecture, requirements, source cards and new tasks agreed with the owner. A decision that updates no document has no row. Commit: "Done", or "Pending" until delivered; the spike closes when every row is Done. Production inputs are not repeated here. -->

| Output | From | Destination | Commit |
|---|---|---|---|
| `<ADR, requirement, source card or task>` | `<e.g. D1, F3>` | `<document and section>` | `<Done, or Pending>` |

## 6. Sources

<!-- Optional. Earlier spikes, benchmarks and documentation used. -->

- `deltalake` 1.6.6's source, at the tag `python-v1.6.6` of [delta-io/delta-rs](https://github.com/delta-io/delta-rs/tree/python-v1.6.6):
  - checkpoints every 100 commits by default: `crates/core/src/table/config.rs` and `crates/core/src/kernel/transaction/mod.rs`;
  - no target pruning in a streamed MERGE: `crates/core/src/operations/merge/mod.rs` and `filter.rs`, and [delta-rs#3491](https://github.com/delta-io/delta-rs/issues/3491); fixed in 1.7.0 by [delta-rs#4790](https://github.com/delta-io/delta-rs/pull/4790);
  - a grouped aggregate is not answered from statistics: DataFusion's [`aggregate_statistics.rs`](https://github.com/apache/datafusion/blob/main/datafusion/physical-optimizer/src/aggregate_statistics.rs).
