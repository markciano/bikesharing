<!--
Spike doc template. A spike is a time-boxed investigation of one task: it reaches the decisions a task needs, by analysis where possible and with evidence only where an unknown would change the choice. Its output is knowledge (decisions, answers, a verdict, inputs for designs and ADRs); its code is throwaway and lives in spikes/<name>/.
Blocks: Questions (what we need to know), Method (how we find out), Steps, Findings (filled during execution), Conclusion (filled after the last step).
Sections marked Optional are kept only when they apply.
-->

# Spike: Pipeline run time and R2 reads

- **Task:** T077
- **ADRs:** `<ADRs this spike must respect, set at framing>`
- **Code:** [`spikes/t077-run-time-and-r2-reads/`](../../spikes/t077-run-time-and-r2-reads/)

## Status

<!-- State: Draft 📝 · Ready 🎬 · Running 🔄 · Concluded ✅.
Phase: the blocks and the review completed.
Started / Finished: UTC dates of the first step executed and of the Conclusion.
Current: where work resumes, with only the context the next session needs: the step being executed, or the section of the report; — when concluded. -->

- State: Draft 📝
- Phase: [ ] Questions · [ ] Method · [ ] Steps · [ ] Steps review · [ ] Conclusion
- Started: — · Finished: —
- Current: —

## 1. Questions — what we need to know

### 1.1 Context

<!-- 2–4 sentences: the decisions this spike takes, which of them depend on evidence and why, and the spikes or designs it builds on. -->

The pipeline's scheduled runs get slower every day and read far more objects from R2 than they process, as measured at d008's close ([d008 › Known gaps at close](../designs/d008-pipeline-platform-and-walking-skeleton.md#42-known-gaps-at-close)): about 6,600 GetObject per run on `bikesharing-lakehouse`, a bucket of about 2,250 objects. This spike finds the causes and chooses the fix for each one, which is built outside the spike (D1). Reading the code and `deltalake`'s documentation already explains most of it; evidence is sought only where the size of each cause would change the fix.

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

#### D2. Modal's region is decided after the fix, by arithmetic

Both buckets are in Western Europe (WEUR) and the pipeline runs on Modal in the US, with no region pinned, the cheapest option ([ADR-0027](../decisions/0027-modal-as-execution-platform.md) leaves the region open). The distance adds no R2 cost, since R2 charges no egress, but each operation pays a transatlantic round trip, and Modal bills the container's waiting time. That latency per operation is roughly constant: what grows is the number of operations, so the fix of the causes comes first. At the Conclusion, the network time left after the fix, from the operations and latencies measured in Q1, is compared with the surcharge of pinning Modal to Europe.

- **What would change it:** the network time left after the fix is a large share of the run, or keeps growing with the feeds → pinning Modal to Europe is proposed as part of the fix.
- **Rejected:** moving Modal to Europe now. It pays the surcharge before knowing it is needed and hides part of the growth that Q1 must measure.

<!-- In this order, so the reader finds what matters first:
1. The decision and why, in one short paragraph. If it depends on a Q, name it and what happens if its Gate fails.
2. What would change it, and what would not, each with the action to take. Only when a later event could reopen it.
3. The options rejected and how robust the result is.
4. The evaluation behind it: the table or weighted matrix (needs, cuts, anchors and scores) if one was used. A security decision lists its threats in a table: `| # | Threat (STRIDE) | Impact | Control | Requirement |`, with IDs `TH1`, `TH2`… per document. -->

### 1.3 Questions

<!-- The main question, answered by the Verdict. Then Q1..Qn, each answerable with evidence.
"Observe only": things to note during the run with no dedicated effort. -->

Main question: what makes the pipeline's run time and its lakehouse reads per run grow, and which fix keeps both bounded as the processed objects accumulate?

- **Q1.** Does the run time follow each table's commits since its last Delta checkpoint, written every 100 commits, rather than the hour of the day? Answered over the existing window, from the runs' log objects and the `LastModified` of each table's `_delta_log/`. It decides between the checkpoint cycle and the network to Modal's region ([D2](#d2-modals-region-is-decided-after-the-fix-by-arithmetic)) as the cause of the daily pattern.
- **Q2.** Do the calls of [Lakehouse reads per run](#lakehouse-reads-per-run) account for the lakehouse's GetObject per run, and for the time and growth of discovery and batch work? Counted per call, on the tables' state in production. It decides whether the fix is chosen on H1 and H2 alone: its Gate, in Exit criteria, sets the share that must be accounted for; below it, the remaining share is a cause still to find.
- **Observe only:**
  - the daily pattern, up to twice as slow from 16:00 to 23:00 Madrid time, whether it holds per operation or only per run;
  - the pipeline's own GetObject on `bikesharing-bronze` per run, against the objects it downloads, about 65.

### 1.4 Exit criteria

<!-- Fixed before the first run; a later change is recorded in the Decision log.
Derived from the standard that applies to this kind of question, named in the first line: e.g. DAMA data quality dimensions for a data source, a weighted decision matrix for a technology choice.
Each criterion is measurable and says whether it is a hard cut or a guide. The timebox says what ends the run. State whether one variant meeting the criteria is enough. -->

- **Standard:** `<standard or pattern applied>`
- **Timebox:** `<window, and what ends it>`
- `<criterion>` — `<threshold>` — hard cut | guide

### 1.5 Out of scope

<!-- Optional. What someone could expect this spike to answer and it will not, each item pointing to the task that covers it. -->

- Which readers other than the pipeline account for `bikesharing-bronze`'s GetObject: they do not slow the runs, and the cost model needs them per bucket — T077, in the cost recalibration of [d008 › Known gaps at close](../designs/d008-pipeline-platform-and-walking-skeleton.md#42-known-gaps-at-close)

### 1.6 Open questions

<!-- Optional. Unresolved questions about what to find out. Questions about how belong to Method. -->

| Question | Notes |
|---|---|
| Why does the run time grow and why do the runs read so many objects from R2? | From [d008 › Known gaps at close](../designs/d008-pipeline-platform-and-walking-skeleton.md#42-known-gaps-at-close), which holds the measure. |

## 2. Method — how we find out

### 2.1 Approach

<!-- The variants, options or probes compared, and what each one tells that the others do not. -->

| Variant | What it is | What it tells |
|---|---|---|
| | | |

#### 2.1.1 Shared behaviour

<!-- Optional. Rules every variant follows (schedules, formats, key layouts, logs), stated once so the steps can cite them. -->

-

#### `<A>`. `<Title of variant, option or probe A>`

<!-- Detailed description -->

### 2.3 Decision log

<!-- It logs decisions about the method, before and during the run, including changes of course. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Column Applies to: anchor link(s) to the section where the decision is applied, named in one or two words (e.g. Q1, Probe A, File layout).
- Column Decided at: the Status phase where it was decided (Method, Steps), `<phase> review` when decided while reviewing that phase, or `Running step N` when decided during the run.
-->

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| `<N>` |  |  |  |  |

### 2.4 File layout

<!-- Every file and folder the spike creates, as a tree with its purpose in one line. Captured data and outputs are marked as ignored by Git. The README is always included. -->

```text
spikes/t077-run-time-and-r2-reads/
├── README.md        Question, setup and commands, what each script does, link to the report
└── <file>           <purpose>
```

## 3. Steps
<!-- Each step is one reviewable result, touching at most 2–3 files.
- Status: where the step is: 💤 todo · 🎬 ready · 🔄 in progress · ⛔ blocked · ✅ done
- Who: Owner (manual actions: dashboards, accounts, deploys, runs, checks) or Claude (code and documents).
- Commit: only in a step that changes committed files: the proposed message, following the Git conventions in CLAUDE.md.
- Model: the model and effort the step's session runs with (e.g. sonnet · medium), or — when Who is Owner.
- Gate: optional. <condition> → <consequence if it fails: variants or steps dropped or re-decided>. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

### Step 1 — `<title>`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** following the Git conventions in CLAUDE.md.
- **Model:** `<model · effort>` (or —)
- **Gate:** `<condition>` → `<consequence>`

#### Scope

<!-- The result of the step. List the components and the files created or changed (code, tests, docs). A reviewer should know what the diff will contain from this section alone. -->

#### Reads

<!-- List of reads containing what to read (be specific with paragraph or line), what contains the read, and why it is interesting here.  -->

#### Do

<!-- Numbered actions in execution order, one verb each (write, implement, update, run). Every file named here must appear in Scope; add nothing Scope does not list. -->

#### Check

<!-- command/s or verification with a yes/no result. -->

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
