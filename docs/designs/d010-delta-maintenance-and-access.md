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
- **New ADRs from this doc:** none

## Status

<!-- State: Draft 📝 · Ready for implementation 🎬 · In progress 🔄 · Complete ✅. A document-only task goes from Draft to Complete.
Phase: the blocks and reviews completed. A document-only task shows only Spec · Plan · Plan review.
Current: where work resumes (the step being implemented, or the block and section of the design; — when complete), plus only what the next session cannot derive from the document, such as an instruction from the owner. Nothing it can re-derive: options, recommendations, files to read, later sections. A document-only task names the section. -->

- State: In progress 🔄
- Phase: [x] Spec · [x] Plan · [x] Plan review · [x] Steps · [x] Steps review
- Current: Step 11.

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

Their data files differ by design. If a check fails, the migration restores the version before its rewrite with Delta's time travel and reports which check failed, and the schedule stays paused while the owner fixes the cause and runs the migration again. A restore writes one commit that points the table back to the earlier version's data files, which stay in R2 until a vacuum removes them 7 days later, so it copies no data. **#6**

Options rejected:

- **A layout check in the new code:** the run would fail before writing if `processed_objects` lacked the new partitioning, but it adds code to every run for a one-off change that the order above already covers.

#### D3. Discovery keeps a watermark per system and feed

Each feed lists bronze from its own latest processed capture minus the lookback, following a watermark with allowed lateness kept per stream, and the daily full sweep is removed. **replaces [d008 › #7](d008-pipeline-platform-and-walking-skeleton.md#bronze-reading)**

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

#### D5. Security of the migration and of retention

The task adds two writes to the production lakehouse: the one-off migration of D2, and the deletion of partitions of D4. The storage baseline of [ADR-0023](../decisions/0023-storage-security-baseline.md) applies as it stands and is not repeated. Its threats, from one STRIDE pass over D1–D4, are below.

- **The migration's credential:** the owner runs the migration locally, from the merged `main`, with an R2 token of its own, following least privilege with a short-lived credential, ADR-0023's token per component. The token can write only to `bikesharing-lakehouse`, expires after one day, and the owner revokes it once the migration passes. The scheduled function stays the only holder of the pipeline's write token ([d008 › Environments and configuration](d008-pipeline-platform-and-walking-skeleton.md#environments-and-configuration)).
- **Retention's reach:** a deletion only affects partitions of months before the window's start. A wrong deletion is undone with Delta's 7 days of history or rebuilt from bronze ([ADR-0021](../decisions/0021-retention-per-layer.md)).
- **The migration's trace:** its commit records its own code version in the Delta log, since the rows keep the lineage of the runs that wrote them (D2).

| # | Threat (STRIDE) | Impact | Control | Requirement |
|---|---|---|---|---|
| `TH1` | Tampering, Elevation of privilege: the migration writes to the production lakehouse from outside the scheduled function | Rows rewritten by unreviewed code, or a long-lived write credential outside Modal | Run from the merged `main`, with a token that writes only to `bikesharing-lakehouse`, expires after one day and is revoked after the migration | [Done when](#14-done-when) |
| `TH2` | Tampering: a wrong window computation deletes partitions inside the window | Silver history lost until restored or rebuilt | Deletion limited to months before the window's start; time travel and rebuild from bronze | R13; 7 days of history by [ADR-0021](../decisions/0021-retention-per-layer.md) |
| `TH3` | Repudiation: the rewritten table does not show which code rewrote it | A faulty migration cannot be traced to its code | The migration's commit records its code version in the Delta log | R9 |

Options rejected:

- **A Modal function for the migration:** the token would never reach the owner's machine, but it adds an app with production credentials for a single use.

### 1.3 Requirements

<!-- Optional. The acceptance criteria, cited by number in the Test plan and the steps. They translate Decided at framing and cite the decision they come from; nothing is decided here.
One behaviour per requirement, verifiable, with a measurable threshold where one applies. Written in EARS:
- Ubiquitous: The <system> shall <response>.
- Event: When <trigger>, the <system> shall <response>.
- State: While <state>, the <system> shall <response>.
- Unwanted: If <condition>, then the <system> shall <response>.
- Optional: Where <feature is included>, the <system> shall <response>.
Only requirements specific to this task; project-wide rules (CLAUDE.md, ADRs) are not repeated. -->

- **R1** For the same bronze, the pipeline shall produce the same rows of `station_stock` and a published file with the same content as before this task. (D1)
- **R2** The pipeline shall keep the names and fields of its existing events and heartbeat, adding events or fields only. (D1)
- **R3** The pipeline shall keep one `processed_objects` table for every system and feed, with one row per processed bronze object. (D1)
- **R4** When a run reads `processed_objects` for a feed, the pipeline shall read only the data files that hold that feed's rows. (D1)
- **R5** In its runs, the pipeline shall read and write `processed_objects` only through its common table access. (D1) **#3**
- **R6** When the migration has rewritten a table, the migration shall verify that the rewritten table and the version before it hold the same number of rows, the same set of bronze object keys, and the same run ID and code version on each row. (D2)
- **R7** If a check of the migration's verification fails, then the migration shall report which check failed. (D2)
- **R8** The migration shall rewrite only the tables whose partitioning changes. (D2)
- **R9** The migration shall record its code version in the metadata of its Delta commit. (D5, TH3)
- **R10** When a run lists bronze for a system and feed with processed objects, the pipeline shall list it from the capture instant in the key of that system and feed's latest processed object minus 15 min, and from no earlier key. (D3)
- **R11** When a run lists bronze for a system and feed with no processed object, the pipeline shall list it from its start. (D3)
- **R12** When the daily maintenance runs, the pipeline shall delete every partition of `station_stock` whose local month is before the current local month minus 12 months. (D4, TH2)
- **R13** The pipeline shall not delete any partition of `station_stock` whose local month is the current one or one of the 12 before it. (D4, TH2)
- **R14** While no partition of `station_stock` is outside the retention window, the daily maintenance shall write no commit for retention. (D4)
- **R15** When the daily maintenance applies retention, the pipeline shall delete no rows of `processed_objects`. (D4)
- **R16** When a batch is processed again, the pipeline shall add no rows to `station_stock` or `processed_objects`. (D1)
- **R17** If a check of the migration's verification fails, then the migration shall restore the rewritten table to the version before its rewrite. (D2)

### 1.4 Done when

<!-- Optional. Only what closes this task and Requirements cannot express: operational actions, checks on real data, understanding. The general closing rule is checked in `.claude/skills/implement/review.md`. -->

The owner ran the change in D2's order, and the migration from the merged `main` with a token that writes only to `bikesharing-lakehouse` and expires after one day, revoked once the migration passed (D2, D5, TH1).

Checked on production after the deploy, over a window of at least 3 h that starts with the first scheduled run with no catch-up (one batch), and includes a checkpoint of each table and the run of the daily maintenance ([s019 › P7](../spikes/s019-pipeline-run-time-r2-reads.md#55-production-inputs)):

- GetObject per run on `bikesharing-lakehouse` (`r2_metrics.py`) stays at or below 700, with about 400 on average expected;
- p95 run time (`run_stats.py`) is at most 2 min, the estimate [ADR-0027](../decisions/0027-modal-as-execution-platform.md) rests on.

If either fails, `capture_history`'s pruning is checked first.

### 1.5 Out of scope

<!-- Optional. What someone could expect and will not be done, each item pointing to the task that covers it. -->

- Moving Modal's region ([s019 › P8](../spikes/s019-pipeline-run-time-r2-reads.md#55-production-inputs)): its steps are written in [Modal's region](#modals-region) and not run in this task — T080
- Keeping other catalogs in sync with the code or configuration they describe: this design keeps `docs/lakehouse.md` in sync with `settings.py` ([Table settings and catalog](#table-settings-and-catalog)), which sets no rule for other catalogs. TODO(T078.2): consider the same for `docs/observability.md`'s alerts and events, only if its complexity is affordable — T078.2

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

#### Common table access

`bikesharing/shell/delta.py` is the pipeline's common table access, the one place every run reaches its Delta tables through ([ADR-0052](../decisions/0052-delta-maintenance-and-access-pattern.md)):

- it opens each table once per run, and refreshes it after its own writes;
- every read and MERGE it offers takes the table's range, so no caller can read a table whole;
- it reads values the log's file statistics hold, such as a feed's latest capture, from the log;
- every query names the columns it returns, never `select *`, following explicit projection at a component boundary: `capture_history` and `latest_captures` feed dbt, and a column a table gains, such as `utc_date`, would otherwise reach dbt's inputs, whose columns R1 keeps.

An import-linter contract in `pipeline/pyproject.toml` makes it the only module of the package that imports `deltalake`, following module boundaries enforced by tooling, as ADR-0046's rules are. A slice that reads `processed_objects` on its own fails CI, instead of bringing back full reads that only R2's request counts would show (R5). `.claude/rules/code/python.md` › Structure states the same rules. **#5**

#### `processed_objects` layout

`processed_objects` is partitioned by `system`, `feed` and `utc_date`, in that order, following partitioning by the range its readers filter by ([ADR-0052](../decisions/0052-delta-maintenance-and-access-pattern.md)):

- **`system` and `feed`:** each feed reads only its own rows, and a new feed adds its own partitions (D1, R4).
- **`utc_date`:** a new column, the UTC date of `captured_at`, the date in the bronze key, which the pipeline writes with each row. Every reader filters by UTC instants (discovery's watermark minus the lookback, `capture_history`'s 7 days, a batch's capture range), so each range maps to whole partitions with no time-zone conversion. ADR-0041's local calendar keys apply to fact rows, not to control state.
- **Size:** one partition per system, feed and day, compacted into one file once closed, adds about 365 files a year per system and feed to the log.

**extends [d008 › #4](d008-pipeline-platform-and-walking-skeleton.md#delta-writes)**

#### Bounded calls

Each of a run's calls states the range it needs, as partition values and as a `captured_at` range, so the engine prunes by partition and then by the log's file statistics ([ADR-0052](../decisions/0052-delta-maintenance-and-access-pattern.md)). The calls are those of [s019 › Lakehouse reads per run](../spikes/s019-pipeline-run-time-r2-reads.md#lakehouse-reads-per-run):

| # | Phase | Call | Table | Range it states | Requirement |
|---|---|---|---|---|---|
| 1 | Discovery | `ensure_tables` | both | Opens each table once for the run; creates a missing one without opening the others again | R5 |
| 2 | Discovery | `latest_processed` | `processed_objects` | None read: per system and feed, the maximum of `captured_at`'s statistics over the files of its latest `utc_date` partition, from the log | R10, R11 |
| 3 | Discovery | `processed_keys` | `processed_objects` | Per system and feed, from its latest capture minus 15 min: its `utc_date` partitions from that instant's date, and `captured_at` at or after it | R4, R10 |
| 4 | Batch | `capture_history` | `processed_objects` | The batch's system and feed, `utc_date` and `captured_at` within the 7 days before the batch | R4 |
| 5 | Batch | `merge_station_stock` | `station_stock` | The batch's `local_date` partitions and its `captured_at` range, which `deltalake` 1.7.0's MERGE prunes its target by | R1, R16 |
| 6 | Batch | `record_processed` | `processed_objects` | The MERGE's predicate adds the batch's systems, feeds, `utc_date` partitions and `captured_at` range to the match on `key`; the result is the same, since `captured_at` derives from the key | R4, R16 |
| 7 | Gold | `latest_processed` | `processed_objects` | As call 2, on the handle refreshed after call 6 | R4 |
| 8 | Gold | `latest_captures` | `station_stock` | The latest capture's `local_date` partition and its `captured_at` | R1 |

A feed with no processed object has no partition, so call 2 returns nothing for it and call 3 lists bronze from its start (R11).

#### deltalake 1.7.0

- **Upgrade:** `deltalake` moves from 1.6.6 to 1.7.0 for call 5's pruning, raising the manifest's minimum to `>=1.7.0` so that no relock goes back to a version without it ([ADR-0017](../decisions/0017-dependencies-locked-per-component.md)); R1 and R16's tests check that the upgrade keeps the outputs.
- **Impact:** the [1.7.0 release notes](https://github.com/delta-io/delta-rs/releases/tag/python-v1.7.0) and its `table.py` change no API or default the pipeline uses. They add the MERGE's pruning by the source's statistics and correct the pruning statistics of timestamps, which `captured_at`'s ranges rely on.
- **Commit conflicts:** the pruning also narrows what a MERGE declares as read, which is what a concurrent commit is checked against: besides the predicate's literal bounds, a range from the source's minimum to its maximum for each join column equal to a source column ([delta-rs #4790](https://github.com/delta-io/delta-rs/pull/4790)). A commit whose rows fall outside those ranges no longer conflicts. Two writers that insert a same key still do, since each range holds every key of its source; delta-rs does not state this as a guarantee, so `merge_station_stock`'s retry tests check it with one shared key among others. **DI1**
- **Explicit values:** `vacuum` simulates by default and keeps the table's retention, so the pipeline passes `dry_run=False`, a retention of 7 days ([ADR-0021](../decisions/0021-retention-per-layer.md)) and `enforce_retention_duration=False` ([Vacuum and tombstone retention](#vacuum-and-tombstone-retention)).
- **File statistics:** call 2 reads `get_add_actions(flatten=True)`, one row per data file with its `partition.<col>`, `min.<col>` and `max.<col>` columns, checked against the installed version before it is built. If the columns are missing, call 2 reads its feed's latest `utc_date` partition instead ([s019 › P4](../spikes/s019-pipeline-run-time-r2-reads.md#55-production-inputs)).

#### Compaction

After each batch, the run compacts the partitions the batch left over their rule, with `optimize.compact` restricted to those partitions, which keeps insertion order ([ADR-0052](../decisions/0052-delta-maintenance-and-access-pattern.md), [s019 › P2, P3](../spikes/s019-pipeline-run-time-r2-reads.md#55-production-inputs)). A catch-up compacts as it writes, and nothing runs alongside a MERGE.

- **Closed partition:** one whose date is before the date of the batch's latest capture minus the 15 min lookback, since no later batch writes to it (D3). For `station_stock`, the local date of that instant.
- **Compacted once, on state:** every closed partition with more than one data file is compacted, found from the log with no data read, so a run that fails before compacting is caught up by the next one.

| Table | Active partitions | Closed partitions |
|---|---|---|
| `processed_objects` | Compacted when a batch leaves one at or over its threshold of data files, since every reader reads a partition whole | Compacted into one file |
| `station_stock` | Never compacted: its MERGE and `latest_captures` prune within the day by `captured_at`, which one file spanning the day would defeat | Compacted into one file |

The threshold is a constant per table in `pipeline/src/bikesharing/core/settings.py`, `COMPACTION_THRESHOLD`, keyed by table name; a table with no entry never compacts its active partitions. `processed_objects`' threshold is 10, the highest that keeps a run within the Done when's 700 GetObject: s019's arithmetic reaches 700 at its worst point, 95 commits since the checkpoint with full active partitions, at 10, and each 10 files more add about 180 ([s019 › Verdict](../spikes/s019-pipeline-run-time-r2-reads.md#53-verdict)). A lower threshold saves under 1 s per run, and the compaction events measure whether another value runs better.

**replaces [d008 › #6](d008-pipeline-platform-and-walking-skeleton.md#delta-writes)**

#### Daily maintenance

The daily maintenance runs inside one run a day, after its last batch, following a fixed maintenance window off-peak with idempotent tasks ([ADR-0052](../decisions/0052-delta-maintenance-and-access-pattern.md)):

- **Which run:** the run that starts within the 15 min from `MAINTENANCE_LOCAL_TIME` in Europe/Madrid, a constant in `settings.py` set to `04:00`, outside the slow hours of [s019 › Not verified](../spikes/s019-pipeline-run-time-r2-reads.md#54-not-verified). The run decides from its own start time, which it receives as a parameter, so no state records whether maintenance ran.
- **In order:**
  1. Retention deletes every partition of `station_stock` whose local date is before the first day of the current local month minus 12 months, with partition values read from the log; with none, it writes no commit (D4, R12–R14).
  2. Vacuum removes, from both tables, the data files their log removed more than 7 days ago, with `dry_run=False` (ADR-0021), as [Vacuum and tombstone retention](#vacuum-and-tombstone-retention) sets.
  3. Log cleanup removes, from both tables, the log files older than the log's 30-day retention, with `cleanup_metadata()`. Both tables set `delta.enableExpiredLogCleanup` to `false`, the way [Checkpoint interval](#checkpoint-interval) sets its property, so no commit lists `_delta_log/` to clean it.
- **A missed day:** the three tasks act on the tables' state, not on the date, so the next day's maintenance does what a failed or skipped one left (D4).
- **Cost:** 1 run in 96 takes longer, so it stays out of the p95; no task lists a table's data files.

**replaces [d008 › #6](d008-pipeline-platform-and-walking-skeleton.md#delta-writes)**

#### Vacuum and tombstone retention

Vacuum finds the data files to delete from the log's remove actions (tombstones), each recording a file the table removed and when, and lists no data file, so its cost does not grow with the table's history ([ADR-0052](../decisions/0052-delta-maintenance-and-access-pattern.md)). Each checkpoint drops the tombstones older than the table's `delta.deletedFileRetentionDuration`. A file whose tombstone is gone is no longer referenced anywhere: no later vacuum finds it, and it stays in R2 for good ([`vacuum.rs`](https://github.com/delta-io/delta-rs/blob/python-v1.7.0/crates/core/src/operations/vacuum.rs), [`log_replay.rs`](https://github.com/delta-io/delta-kernel-rs/blob/main/kernel/src/action_reconciliation/log_replay.rs)). With both at 7 days, a file would be deletable only from its 7th day until the next checkpoint, about 2 h, and a daily vacuum would miss most files.

The tables therefore keep their tombstones longer than vacuum waits to delete:

| Setting | Value | Where |
|---|---|---|
| Tombstone retention | 10 days | `TOMBSTONE_RETENTION` in `settings.py`, set as each table's `delta.deletedFileRetentionDuration` the way [Checkpoint interval](#checkpoint-interval) sets its property |
| Vacuum retention | 7 days, the table history of ADR-0021 | `VACUUM_RETENTION` in `settings.py`, passed as `retention_hours=168` with `enforce_retention_duration=False` |

- **Attempts per file:** a file is deletable from 7 days after its removal until the first checkpoint after 10 days, so the daily vacuum sees it on at least 10 − 7 = 3 days. A file removed on a Monday at 10:00 is deletable from the next Monday at 10:00, vacuum sees it on Tuesday, Wednesday and Thursday at 04:00, and the first checkpoint after Thursday at 10:00 drops its tombstone.
- **A missed day:** the next vacuum catches up on up to 2 consecutive days without one. From the third, the files removed in that gap stay in R2 unreferenced: once the cause is fixed, a one-off `vacuum(full=True)`, which lists the table once, deletes them.
- **Cost:** each checkpoint holds 3 days more of tombstones, about 1,200 rows and 30 kB per table. No data or log file is added, and the table history stays at 7 days.
- **Safety check:** `enforce_retention_duration=False` turns off `deltalake`'s check that vacuum keeps at least the tombstone retention, since the two differ by design. A unit test checks instead that `VACUUM_RETENTION` is 7 days and below `TOMBSTONE_RETENTION`.

#### Checkpoint interval

Each table's `delta.checkpointInterval` is the N that minimizes its R2 requests per run, following the square-root rule for a fixed cost paid every N periods against a cost that grows with N ([s019 › P6](../spikes/s019-pipeline-run-time-r2-reads.md#55-production-inputs)):

N = √(2 · c · a · w / o)

| Input | Meaning | Value | Source |
|---|---|---|---|
| `c` | Commits per run | 1.1: the MERGE, and a compaction now and then | [Compaction](#compaction) |
| `a` | Class A requests per checkpoint | 3: the checkpoint's Parquet and `_last_checkpoint` (2 PUT), and the LIST of `_delta_log/` that rebuilds the snapshot it writes | `deltalake` 1.7.0, `crates/core/src/protocol/checkpoints.rs` and `kernel/transaction/mod.rs` |
| `w` | Weight of a Class A request against a Class B one | 10: R2's monthly free allowance is 1M Class A and 10M Class B | R2 pricing |
| `o` | Opens per run that replay the log | 1: each table is opened once, and its refresh reads only its own commits | [Common table access](#common-table-access) |

- **Value:** 8 for both tables, since both have the same inputs. A checkpoint's Class B reads are about N + 2, about one per commit whatever N is, so they do not move the optimum.
- **Bound:** N stays at or below 12, the commits of the Done when's 3 h window, so that the window includes a checkpoint of each table.
- **Where it lives:** `CHECKPOINT_INTERVAL` in `settings.py`, keyed by table name. `ensure_tables` sets it as the table property when it creates a table, through `configuration`, and the migration script sets it on existing tables with `alter.set_table_properties`.
- **A new table, or other inputs:** the interval is computed again from the formula. The Done when's GetObject per run measure the result.

#### Maintenance events

Each maintenance task writes one event per table it acts on, following one structured event per unit of work, as `batch_committed` and `node_finished` do. The events are added to `contracts/log-events.registry.json` with `needs_action: false` and no alert, and no existing event changes (R2):

| Event | Level | Written | Fields | Values from `deltalake` |
|---|---|---|---|---|
| `table_compacted` | `info` | After a batch's compaction of one table, when the batch left partitions due; none otherwise **DI3** | `table`, `partitions`, `files_removed`, `files_added`, `duration_s` | `optimize.compact`'s `partitionsOptimized`, `numFilesRemoved` and `numFilesAdded` |
| `retention_applied` | `info` | After the retention of `station_stock`, also when it deletes nothing | `table`, `partitions_deleted`, `rows_deleted`, `duration_s` | `partitions_deleted` from the partitions given; `delete`'s `num_deleted_rows`, present since every data file the pipeline writes has its row count in its statistics |
| `table_vacuumed` | `info` | After the vacuum of one table | `table`, `files_deleted`, `duration_s` | The length of the list `vacuum` returns |
| `log_cleaned` | `info` | After the log cleanup of one table | `table`, `duration_s` | None: `cleanup_metadata()` returns no count |
| `maintenance_failed` | `warn` | When a task fails on one table, in place of its event | `table`, `task` (`compaction`, `retention`, `vacuum` or `log_cleanup`), `error_type`, `error` | The exception's type and message |

Every count is an integer. The events measure each task on its own: the compaction events show whether `COMPACTION_THRESHOLD` runs well, and the daily ones show the Done when's run of the daily maintenance.

- **A failed task:** the run writes `maintenance_failed` and goes on with the next table, task or batch, and `run_finished`'s outcome does not change, following graceful degradation of non-critical work. The batch's data is already committed, and each task acts on the table's state, so the next run or day does what the failed one left ([Compaction](#compaction), [Daily maintenance](#daily-maintenance)).
- **Not actionable:** one failure is fixed by waiting, as `docs/observability.md` › Actionable events sets. Failures on consecutive days are not: from the third day without a vacuum, removed files stay in R2 ([Vacuum and tombstone retention](#vacuum-and-tombstone-retention)). TODO(T078.2): alert on `maintenance_failed` over consecutive days.

#### Table settings and catalog

Each table's settings have one source, `settings.py`, and the catalog `docs/lakehouse.md` explains them without copying them, following a single source of truth:

- **`settings.py`:** `TABLE_PATHS` maps each table's name to its path in `bikesharing-lakehouse`, and its keys are the pipeline's tables. `CHECKPOINT_INTERVAL` and `COMPACTION_THRESHOLD` are keyed by the same names, and `TOMBSTONE_RETENTION`, `VACUUM_RETENTION` and `MAINTENANCE_LOCAL_TIME` hold for every table. `delta.py`, the migration script and the tests import them, and no other module or test writes a table's path.
- **`docs/lakehouse.md`:** one entry per table, headed by its name, states how the table applies [ADR-0052](../decisions/0052-delta-maintenance-and-access-pattern.md): its partition columns, the range each reader states, its compaction and retention, and how each tunable value is computed. It names the constant that holds each value and never writes the value. `docs/architecture.md` › 8 links to it from a bullet on Delta tables.
- **Kept in step by one test:** an integration test, `tests/integration/test_lakehouse_catalog.py`, checks that the catalog's table headings are `TABLE_PATHS`' keys, so a table added or removed without its entry fails CI. It reads a file outside `pipeline/`, so `docs/lakehouse.md` joins the `pipeline` path filter in `.github/workflows/ci.yml`. A table with no `CHECKPOINT_INTERVAL` fails `ensure_tables`' test of the table properties, which runs once per key of `TABLE_PATHS` (`pytest.mark.parametrize`), so a new table is covered with no new test.
- **Adding a table:** the catalog opens with the steps to add a table, each linking to the part of an entry that explains its value and stating what checks it: the entry by the catalog's test, its `CHECKPOINT_INTERVAL` by `ensure_tables`' test, its access through `delta.py` by import-linter. No test checks the values themselves, such as the checkpoint interval's formula or whether its active partitions compact. `.claude/rules/code/python.md` › Structure links to these steps.

#### Modal's region

T080 runs these steps once this task's Done when has passed, so that the fix and the region are each measured on their own, following one variable changed at a time. They are written here and not run in this task:

1. **Pin the region.** A PR sets `region="eu"` on the scheduled function in `pipeline/modal_app.py`, and is merged and deployed with `deploy.sh`. `eu` is Modal's broad region for the European Economic Area, which avoids the transatlantic round trip to R2's WEUR buckets, with a surcharge of 1.15× on every resource, against 1.75× for a narrow region such as `eu-west` ([Modal › Region selection](https://modal.com/docs/guide/region-selection)).
2. **Measure.** `run_stats.py` gives the run times of 12 consecutive scheduled runs with no catch-up (one batch) in the US, before the PR, and of the first 12 such runs in Europe, after it: a window of 3 h each, as in the Done when.
3. **Decide.** Modal stays in Europe if the median run time in Europe × 1.15 is at most the median run time in the US. Modal bills a container by the second, so a run's cost follows its time times the surcharge. Otherwise a PR removes `region` and is deployed, since an older commit is never redeployed. **#1, #2**

#### Migration

`pipeline/scripts/migrate_delta_tables.py` is the one-off migration of D2, which the owner runs locally with D5's token in the environment. It calls `deltalake` directly, following a self-contained data migration that adds nothing to the application's API for a single use: ADR-0052's common table access covers the runs, and import-linter the package. It takes from `bikesharing.shell.delta` and `settings.py` only each table's path, schema, partition columns and properties. **#3**

It runs in this order:

1. **Checks the code.** It refuses unless the working tree is clean, untracked files included, and HEAD is `origin/main`, the checks of `deploy.sh`, and takes HEAD's full SHA as its code version (TH1).
2. **Checks the layout.** When `processed_objects` is already partitioned by `system`, `feed` and `utc_date`, it skips steps 3 and 4 and goes on to step 5, so a second run never rewrites the table again and still completes a run that failed in step 5.
3. **Rewrites `processed_objects`.** It reads the current version, adds `utc_date` from `captured_at`, and overwrites the table with `partition_by` set to the new partition columns and `schema_mode="overwrite"`, Delta's way of changing a table's partitioning. It takes the schema and the partition columns from `bikesharing.shell.delta`, so it writes the table `ensure_tables` would create. `station_stock` is not rewritten (R8).
4. **Verifies the rewrite.** It compares the new version with the one before it, read by time travel, on the three checks of D2: the number of rows, the set of `key`s, and the set of `key`, run ID and code version (R6). On a failed check, it restores the version before the rewrite with `restore`, checks that its partition columns and number of rows are back, and exits non-zero naming each failed check (R7, R17). If the restore itself fails, it reports the version to restore. **#6**
5. **Sets the table properties.** Only once the verification passes, it sets on both tables `delta.checkpointInterval`, `delta.enableExpiredLogCleanup` and `delta.deletedFileRetentionDuration` from `settings.py`, the values `ensure_tables` sets on a new table ([Checkpoint interval](#checkpoint-interval), [Daily maintenance](#daily-maintenance), [Vacuum and tombstone retention](#vacuum-and-tombstone-retention)), with `alter.set_table_properties`. A failed verification thus leaves only the rewrite to undo. Setting a property to the value it already holds only adds a commit, so the step can run again.

Every commit it writes carries its code version in `custom_metadata`, through `CommitProperties` (R9).

`check-pipeline.sh` type-checks the script with mypy, as it does `scripts/smoke_test.py`, since its one run rewrites a production table.

The script, its test and its line in `check-pipeline.sh` are removed in the PR that records the Done when, once the migration has passed, following dead code removal: they run once, depend on `bikesharing.shell.delta`'s schema, and Git keeps them. **#4**

### 2.2 Decision summary

<!-- It logs decisions about the plan, including changes. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Applies to: anchor link(s) to the section where the decision is applied, named in one or two words.
- Decided at: the Status phase where it was decided (Plan, Steps), or `<phase> review` when decided while reviewing that phase.
- R: Requirement affected.
-->

| # | Applies to | Decision | Reason | R | Decided at |
|---|---|---|---|---|---|
| 1 | [Modal's region](#modals-region) | Modal's region is tried in production right after this task's Done when, with no estimate first, following one variable changed at a time **refines [s019 › D2](../spikes/s019-pipeline-run-time-r2-reads.md#d2-modals-region-is-decided-after-the-fix)** | The trial is one reversible line, and the estimate would not save it; a trial alongside the fix would mix both in the Done when | — | Plan |
| 2 | [Modal's region](#modals-region) | Modal stays in Europe only if a run costs no more there, its median time × 1.15 at most the US median, following a decision by unit cost **refines [s019 › D2](../spikes/s019-pipeline-run-time-r2-reads.md#d2-modals-region-is-decided-after-the-fix)** | With the p95 within 2 min, a shorter run changes nothing the page shows | — | Plan |
| 3 | [Migration](#migration), [Requirements](#13-requirements) | The migration calls `deltalake` directly, taking only each table's schema, partition columns and properties from the package, following a self-contained data migration; R5 and `.claude/rules/code/python.md` › Structure limit the common table access to the runs and the package, as ADR-0052's scope does | Nothing is added to `delta.py` for a single use, so nothing is left in it to clean up when the script is removed | R5 | Plan review |
| 4 | [Migration](#migration), [File layout](#23-file-layout) | mypy type-checks the migration script in `check-pipeline.sh`, following the same checks for all of a component's Python code, as `scripts/smoke_test.py` | Its one run rewrites a production table, and a type error would otherwise show only there; the line is removed with the script | — | Steps |
| 5 | [Common table access](#common-table-access), [Step 6](#step-6--processed_objects-by-system-feed-and-utc-date) | Every query of `bikesharing.shell.delta` names the columns it returns, following explicit projection at a component boundary; `.claude/rules/code/python.md` › Structure states it, and `capture_history` and `latest_captures`, the two that feed dbt, follow it from Step 6 | With `select *`, `utc_date` would reach dbt's input from Step 6, as any column a table gains would | R1 | Steps review |
| 6 | [D2](#d2-existing-data-moves-to-the-new-layout-in-a-one-off-migration), [Migration](#migration) | On a failed verification, the migration itself restores the version before its rewrite, following an automatic rollback on failed validation, as schema migration tools do **refines D2** | Only reviewed code writes to production (TH1), and a restore is one commit that copies no data | R7, R17 | Steps review |

### 2.3 File layout

<!-- Every file and folder the task creates or modifies, documents included, as a tree: (new) or (modified), and its purpose or change in one line. A task that adds a component also lists its CI job in `.github/workflows/ci.yml` (recipe in `.claude/rules/code/ci.md`), and its version files, manifest and lockfile (`.claude/rules/code/dependencies.md`). -->

```text
.
├── .claude/rules/code/
│   └── python.md                          (modified)  Structure: only bikesharing.shell.delta imports deltalake in the package, and its queries name their columns; a new Delta table follows docs/lakehouse.md › Adding a table
├── .github/workflows/
│   └── ci.yml                             (modified)  docs/lakehouse.md joins the pipeline path filter
├── contracts/
│   └── log-events.registry.json           (modified)  The five maintenance events, needs_action false, no alert
├── docs/
│   ├── architecture.md                    (modified)  § 6.2: compaction after each batch and the daily maintenance; § 8: a bullet on Delta tables linking to the catalog
│   └── lakehouse.md                       (new)       Catalog of the lakehouse's tables: how each applies ADR-0052, how its values are computed, Adding a table
└── pipeline/
    ├── pyproject.toml                     (modified)  deltalake >=1.7.0; import-linter contract: only bikesharing.shell.delta imports deltalake
    ├── uv.lock                            (modified)  deltalake 1.7.0
    ├── scripts/
    │   ├── check-pipeline.sh              (modified)  mypy also checks migrate_delta_tables.py; the line is removed with the script
    │   └── migrate_delta_tables.py        (new)       One-off migration of D2: checks, rewrite of processed_objects, verification, table properties; removed in the PR that records the Done when
    ├── src/bikesharing/core/
    │   ├── discovery.py                   (modified)  plan_listing lists from the latest capture minus the lookback, with no daily full sweep
    │   ├── events.py                      (modified)  Builders of the five maintenance events
    │   ├── delta_maintenance.py           (new)       Pure decisions: closed partitions, partitions to compact, retention cutoff, whether a run is the maintenance run
    │   └── settings.py                    (modified)  TableName, SystemFeed; TABLE_PATHS replaces the two path constants; COMPACTION_THRESHOLD, CHECKPOINT_INTERVAL, RETENTION_MONTHS, TOMBSTONE_RETENTION, VACUUM_RETENTION, MAINTENANCE_LOCAL_TIME; LISTING_LOOKBACK to 15 min
    ├── src/bikesharing/shell/
    │   ├── delta.py                       (modified)  Table paths from settings; utc_date partitioning; bounded calls; table properties on creation; compaction, retention, vacuum and log cleanup
    │   └── run.py                         (modified)  RunConfig.maintenance_window; compaction after each batch; daily maintenance after the last batch of the maintenance run; maintenance_failed without changing the outcome
    └── tests/
        ├── unit/core/
        │   ├── test_discovery.py          (modified)  Listing from the latest capture minus the lookback
        │   ├── test_events.py             (modified)  The five maintenance events
        │   ├── test_delta_maintenance.py  (new)       The decisions of delta_maintenance.py
        │   └── test_settings.py           (modified)  VACUUM_RETENTION is 7 days and below TOMBSTONE_RETENTION
        └── integration/
            ├── test_delta.py              (modified)  Table paths from settings; bounded calls; table properties per key of TABLE_PATHS; maintenance tasks
            ├── test_lakehouse_catalog.py  (new)       The catalog's table headings are TABLE_PATHS' keys
            ├── test_migrate_delta_tables.py (new)     The migration's checks, rewrite and verification; removed with the script
            ├── test_r2.py                 (modified)  ListingPlan with its feed
            └── test_run.py                (modified)  Compaction, daily maintenance and maintenance_failed within a run
```

### 2.4 Components

<!-- Optional. One subsection per component. The contract is exact, in the component's own language, never pseudocode. -->

The contracts of what this task adds, and of what changes its signature; a function whose signature does not change is not listed. Each line under a signature says what it decides; the behaviour behind it is in [Approach](#21-approach).

#### `bikesharing.core.settings`

- **Responsibility:** holds each table's settings, the one source `docs/lakehouse.md` explains ([Table settings and catalog](#table-settings-and-catalog)).
- **Location:** `pipeline/src/bikesharing/core/settings.py`
- **Contract:** all new except `LISTING_LOOKBACK`, whose value changes. `STATION_STOCK_PATH` and `PROCESSED_OBJECTS_PATH` are removed, here and in `delta.py`.

```python
type TableName = Literal["station_stock", "processed_objects"]
type SystemFeed = tuple[System, str]  # a system and one of its feeds: the key of each watermark (D3)

TABLE_PATHS: Final[Mapping[TableName, str]] = {
    "station_stock": "silver/station_stock",
    "processed_objects": "control/processed_objects",
}
CHECKPOINT_INTERVAL: Final[Mapping[TableName, int]] = {"station_stock": 8, "processed_objects": 8}
COMPACTION_THRESHOLD: Final[Mapping[TableName, int]] = {"processed_objects": 10}
RETENTION_MONTHS: Final[Mapping[TableName, int]] = {"station_stock": 12}
TOMBSTONE_RETENTION: Final = timedelta(days=10)
VACUUM_RETENTION: Final = timedelta(days=7)
MAINTENANCE_LOCAL_TIME: Final = time(4, 0)
LISTING_LOOKBACK: Final = timedelta(minutes=15)  # was timedelta(hours=1)
```

- A table with no `COMPACTION_THRESHOLD` never compacts its active partitions ([Compaction](#compaction)).
- A table with no `RETENTION_MONTHS` keeps all its rows, as `processed_objects` does (D4, R15).

#### `bikesharing.core.delta_maintenance`

- **Responsibility:** the pure decisions of compaction, retention and the daily maintenance, over values read from the log.
- **Location:** `pipeline/src/bikesharing/core/delta_maintenance.py` (new)
- **Contract:**

```python
@dataclass(frozen=True, slots=True)
class Partition:
    values: tuple[tuple[str, str], ...]  # (column, value) pairs in the table's partition order, as the log writes them
    day: date                            # its date column: utc_date or local_date
    files: int                           # its data files


@dataclass(frozen=True, slots=True)
class CompactionMetrics:
    partitions: int
    files_removed: int
    files_added: int


@dataclass(frozen=True, slots=True)
class RetentionMetrics:
    partitions_deleted: int
    rows_deleted: int


def first_open_day(latest_capture: datetime, *, lookback: timedelta, timezone: tzinfo) -> date: ...
def partitions_to_compact(
    partitions: Iterable[Partition], *, first_open_day: date, threshold: int | None
) -> list[Partition]: ...
def retention_start(today: date, *, months: int) -> date: ...
def partitions_to_delete(partitions: Iterable[Partition], *, start: date) -> list[Partition]: ...
def is_maintenance_run(
    started_at: datetime, *, local_time: time, window: timedelta, timezone: tzinfo
) -> bool: ...
```

- `first_open_day`: the date, in `timezone`, of `latest_capture` minus `lookback`; a partition of an earlier day is closed, since no later batch writes to it.
- `partitions_to_compact`: every closed partition with more than one file, and every open one with at least `threshold` files; with `threshold` `None`, no open one.
- `retention_start`: the first day of `today`'s month minus `months`; e.g. 2025-12-01 for 2026-12-01 and 12, so November 2025 leaves (D4).
- `partitions_to_delete`: every partition whose day is before `start`; none while all are inside the window (R12–R14).
- `is_maintenance_run`: whether `started_at`, in `timezone`, falls within `[local_time, local_time + window)` of its day.

#### `bikesharing.core.discovery`

- **Responsibility:** unchanged: how a run lists bronze and which listed objects are pending.
- **Location:** `pipeline/src/bikesharing/core/discovery.py`
- **Contract:** what changes.

```python
@dataclass(frozen=True, slots=True)
class ListingPlan:
    system: System
    feed: str                 # new
    prefix: str               # raw/<system>/<feed>/
    start_after: str | None
    full_sweep: bool          # now true only for a feed with nothing processed


def plan_listing(
    system: System,
    feed: str,                          # new
    latest_processed: datetime | None,
    *,
    lookback: timedelta,                # now and timezone removed: no daily full sweep
) -> ListingPlan: ...
```

- `plan_listing`: lists after the key of `latest_processed` minus `lookback`, or the whole prefix when it is `None` (R10, R11).
- `full_sweep` keeps its name and its field in `objects_discovered` (R2).

#### `bikesharing.shell.delta`

- **Responsibility:** unchanged: the pipeline's common table access ([Common table access](#common-table-access)).
- **Location:** `pipeline/src/bikesharing/shell/delta.py`
- **Contract:** what is new, and the signatures that change.

```python
PROCESSED_OBJECTS_SCHEMA: Final = Schema([...])  # gains _field("utc_date", "date") after captured_at
TABLE_SCHEMAS: Final[Mapping[TableName, Schema]] = {
    "station_stock": STATION_STOCK_SCHEMA,
    "processed_objects": PROCESSED_OBJECTS_SCHEMA,
}
PARTITION_COLUMNS: Final[Mapping[TableName, tuple[str, ...]]] = {
    "station_stock": ("local_date",),
    "processed_objects": ("system", "feed", "utc_date"),
}
DATE_PARTITION: Final[Mapping[TableName, tuple[str, tzinfo]]] = {
    "station_stock": ("local_date", LOCAL_TIMEZONE),
    "processed_objects": ("utc_date", UTC),
}


@dataclass(frozen=True, slots=True)
class Tables:
    lakehouse: Lakehouse
    _handles: Mapping[TableName, DeltaTable]


# Calls of a run: lakehouse becomes tables in every one
def ensure_tables(lakehouse: Lakehouse) -> Tables: ...  # was -> None
def latest_processed(tables: Tables) -> dict[SystemFeed, datetime]: ...  # was dict[System, datetime | None]
def processed_keys(tables: Tables, since: Mapping[SystemFeed, datetime]) -> frozenset[str]: ...
def capture_history(
    tables: Tables, *, feeds: Collection[SystemFeed], since: datetime, until: datetime
) -> ArrowStream: ...
def merge_station_stock(
    tables: Tables, rows: ArrowStream, *, first_capture: datetime, last_capture: datetime,
    local_dates: Collection[date], attempts: int = 3,
) -> MergeMetrics: ...
def record_processed(tables: Tables, objects: Sequence[ProcessedObject]) -> None: ...
def latest_captures(tables: Tables, latest: Mapping[System, datetime]) -> ArrowStream: ...

# Maintenance, new
def table_partitions(tables: Tables, table: TableName) -> list[Partition]: ...
def compact(tables: Tables, table: TableName, partitions: Collection[Partition]) -> CompactionMetrics: ...
def delete_partitions(
    tables: Tables, table: TableName, partitions: Collection[Partition]
) -> RetentionMetrics: ...
def vacuum(tables: Tables, table: TableName, *, retention: timedelta) -> int: ...
def cleanup_log(tables: Tables, table: TableName) -> None: ...
```

- `Tables`: the run's handle on each table, opened once; only this module reads `_handles`, and it refreshes a handle after its own writes and before a retried MERGE.
- `ensure_tables`: creates each missing table of `TABLE_PATHS` with its schema, partition columns and the three table properties, then opens each once (call 1).
- `latest_processed`: per system and feed with processed objects, its latest `captured_at`, from the log's file statistics; one with none is left out (calls 2 and 7, R11).
- `processed_keys`: the keys of each system and feed captured at or after its instant, its latest capture minus the lookback; one left out reads nothing (call 3, R4).
- `capture_history`: the rows of those feeds within `[since, until)`, in the columns it returned before, without `utc_date`, so dbt's input stays the same (call 4, R1).
- `merge_station_stock`: unchanged but for `tables` (call 5).
- `latest_captures`: unchanged but for `tables`, and for the columns it returns, those of `station_stock` today, listed in its query in place of `select *` (call 8, R1).
- `record_processed`: writes each row's `utc_date` from `captured_at`, and bounds its MERGE as call 6 sets (R16).
- `table_partitions`: each partition with its data files, from the log's add actions, reading no data file.
- `compact`, `delete_partitions`: act on those partitions only, and write no commit when given none (R14).
- `vacuum`: deletes the files removed more than `retention` ago, passed in whole hours as `retention_hours`, with `dry_run=False` and `enforce_retention_duration=False`, and returns how many it deleted.
- `cleanup_log`: deletes the log files older than the log's retention, with `cleanup_metadata()`.

#### `bikesharing.core.events`

- **Responsibility:** unchanged: the builders of the run's events.
- **Location:** `pipeline/src/bikesharing/core/events.py`
- **Contract:** five new builders, `table_compacted`, `retention_applied`, `table_vacuumed`, `log_cleaned` and `maintenance_failed`, in the form of the existing ones: the instant first, then the fields of [Maintenance events](#maintenance-events) as keyword-only arguments. `table_compacted` and `retention_applied` take a `CompactionMetrics` or a `RetentionMetrics` in place of its counts.

#### `bikesharing.shell.run`

- **Responsibility:** unchanged: runs the pipeline end to end.
- **Location:** `pipeline/src/bikesharing/shell/run.py`
- **Contract:** `run(config)` keeps its signature; `RunConfig` gains one field.

```python
@dataclass(frozen=True, slots=True)
class RunConfig:
    ...
    maintenance_window: timedelta | None  # new: RUN_SETTINGS.cadence in scheduled_config, None in one_off_config
```

- **Tables:** the run calls `ensure_tables` once and passes its `Tables` to every other call.
- **Compaction:** after each committed batch, per table: `compact` with `partitions_to_compact` over `table_partitions`, from the batch's latest capture and `DATE_PARTITION`'s time zone.
- **Daily maintenance:** after the batch loop ends, whether by the last batch, the time budget or a batch that did not commit, and before publishing: when `maintenance_window` is set and `is_maintenance_run` holds for the run's start, retention, vacuum and log cleanup, in that order ([Daily maintenance](#daily-maintenance)). A one-off run never runs it; the next scheduled one at `MAINTENANCE_LOCAL_TIME` does.
- **A failed task:** each task runs per table inside its own `try`, and an exception writes `maintenance_failed` and goes on; the run's outcome does not change ([Maintenance events](#maintenance-events)).
- **Gold:** `latest_captures` takes, for each system, the instant `latest_processed` holds for `(system, FEED)`, the feed `station_stock` is built from (call 8).

### 2.5 Test plan

<!-- Optional. Every requirement has at least one verification method (IADT: Inspection, Analysis, Demonstration, Test). Test is the default, at the lowest level that can verify the requirement. Another method only when no test can: Inspection for configuration or documents, Analysis for production data or measurements, Demonstration for behaviour observed end to end, such as a third-party service. -->

| R | Method | What is verified | Level |
|---|---|---|---|
| R1 | Test | The existing tests of a run's `station_stock` rows and published file pass unchanged on `deltalake` 1.7.0 and the new layout; `capture_history` returns the columns it returned before, and `latest_captures` those of `station_stock` | integration |
| R2 | Test | The existing tests of the run's events and heartbeat pass unchanged, and the registry's test finds the five new events registered | unit |
| R3 | Test | Objects of two systems are recorded in the one `processed_objects`, one row each | integration |
| R4 | Test | With a data file of another system's partition removed from disk, `processed_keys` and `capture_history` still return the feed's rows, so they never read it | integration |
| R5 | Inspection | import-linter's contract that only `bikesharing.shell.delta` imports `deltalake`, run by `check-pipeline.sh` in CI | — |
| R6 | Test | On a correct rewrite, the migration's verification passes its three checks | integration |
| R7 | Test | On a rewrite with one row, key, or run ID and code version altered, the migration's verification names that check, one case per check | integration |
| R8 | Test | After the migration, `station_stock` holds the same data files as before it, and its only new commit sets the table properties | integration |
| R9 | Test | Each commit the migration writes carries its code version in its custom metadata | integration |
| R10 | Test | `plan_listing` starts after the key of the latest capture minus 15 min; `processed_keys` returns no key captured before that instant | unit, integration |
| R11 | Test | `plan_listing` lists the whole prefix when nothing is processed; `latest_processed` leaves out a feed with no row | unit, integration |
| R12 | Test | `retention_start` and `partitions_to_delete` on month and year edges; `delete_partitions` removes the partitions given | unit, integration |
| R13 | Test | `partitions_to_delete` keeps the first day of the window and every later one | unit |
| R14 | Test | `delete_partitions` with no partition leaves the table's version unchanged | integration |
| R15 | Test | A run's daily maintenance leaves every row of `processed_objects` | integration |
| R16 | Test | A batch recorded twice adds no rows to `station_stock` or `processed_objects` | integration |
| R17 | Test | On a rewrite that fails a check, the migration exits non-zero and the table has the version before the rewrite's partition columns and rows again | integration |

### 2.6 Breaking changes

<!-- Optional. Shared models or interfaces this design changes, and how their dependants are handled. -->

| File | Why it breaks | Strategy |
|---|---|---|
| `control/processed_objects` in `bikesharing-lakehouse` | Its partition columns change and it gains `utc_date`, so the deployed code and the new one cannot read each other's layout | D2's order: the schedule is paused, the migration rewrites the table, and the new code's deployment resumes the schedule ([Migration](#migration)) |
| `pipeline/src/bikesharing/shell/delta.py`, `pipeline/src/bikesharing/core/settings.py` | The path constants are removed, and the run's calls take `Tables` in place of `Lakehouse` ([Components](#24-components)) | Every dependant changes in this task: `run.py`, `test_delta.py`, `test_run.py` and `test_discovery.py`, all in [File layout](#23-file-layout) |

### 2.7 What does not change

<!-- Optional. Code or documents that must not be modified. Out of scope limits the what; this section limits the how. -->

- `pipeline/dbt/`: its models, sources and contracts. dbt's Parquet inputs keep their columns (R1).
- `pipeline/modal_app.py`: its region and its schedule ([Modal's region](#modals-region), T080).
- `station_stock`'s schema and partitioning, which the migration does not rewrite (D2, R8).
- The existing events of `contracts/log-events.registry.json`, which only gains the five new ones (R2).
- `capture/` and `bikesharing-bronze`, which discovery only reads.

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

None.

### Step 1 — Upgrade `deltalake` to 1.7.0

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `build: d010.s1 upgrade deltalake to 1.7.0`
- **R:** R1
- **Model:** `sonnet · low`
- **Review:** `no`

#### Scope

- `pipeline/pyproject.toml`: `deltalake>=1.7.0`.
- `pipeline/uv.lock`: `deltalake` 1.7.0.
- `pipeline/tests/integration/test_delta.py`: in `merge_station_stock`'s two retry tests, both writers insert several stations and share one key ([deltalake 1.7.0](#deltalake-170) › Commit conflicts).
- Tests: the rest of the existing suite passes unchanged, the first half of the Test plan's R1 row. **DI1**
- A throwaway script in the session's scratchpad, not committed, prints the columns of `get_add_actions(flatten=True)` on the installed version.

#### Reads

| What | Where | Why |
|---|---|---|
| [deltalake 1.7.0](#deltalake-170) | d010 › Plan | The upgrade, its minimum, and the add actions' columns that call 2 relies on |
| Lines 42–51 | `.claude/rules/code/dependencies.md` | How a range and the lockfile change, and that only locked versions run |

#### Do

1. Run `uv add --directory pipeline "deltalake>=1.7.0"`.
2. Run `uv lock --directory pipeline --upgrade-package deltalake==1.7.0`, so the lockfile holds 1.7.0 even if a later 1.7.x exists.
3. Write the throwaway script: it creates a local table partitioned by `system`, `feed` and `utc_date` with a `captured_at` timestamp column, writes two rows, and prints the columns of `get_add_actions(flatten=True)`.
4. Run it with `uv run --directory pipeline python <scratchpad>/add_actions_columns.py`.

#### Check

```bash
bash pipeline/scripts/check-pipeline.sh
grep -n -A1 'name = "deltalake"' pipeline/uv.lock
```

- Yes if the checks exit 0 and the lockfile shows `version = "1.7.0"`.
- Yes if the script prints `partition.utc_date`, `min.captured_at` and `max.captured_at`. If not, Step 8 builds call 2 with the fallback of [deltalake 1.7.0](#deltalake-170) › File statistics.

### Step 2 — Table settings in one place

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `refactor: d010.s2 keep each table's settings in settings.py`
- **R:** —
- **Model:** `sonnet · medium`
- **Review:** `no`

#### Scope

- `pipeline/src/bikesharing/core/settings.py`: adds `TableName`, `SystemFeed`, `TABLE_PATHS`, `CHECKPOINT_INTERVAL`, `COMPACTION_THRESHOLD`, `RETENTION_MONTHS`, `TOMBSTONE_RETENTION`, `VACUUM_RETENTION` and `MAINTENANCE_LOCAL_TIME`; removes `STATION_STOCK_PATH` and `PROCESSED_OBJECTS_PATH`. `LISTING_LOOKBACK` changes in Step 7.
- `pipeline/src/bikesharing/shell/delta.py`: its two path constants removed; every path from `TABLE_PATHS`.
- `pipeline/tests/integration/test_run.py`: reads paths from `TABLE_PATHS` in place of the two constants.
- `pipeline/tests/unit/core/test_settings.py`: `VACUUM_RETENTION` is 7 days and below `TOMBSTONE_RETENTION`.

#### Reads

| What | Where | Why |
|---|---|---|
| [`bikesharing.core.settings`](#bikesharingcoresettings) | d010 › Components | The constants, their types and values |
| [Table settings and catalog](#table-settings-and-catalog) › `settings.py` | d010 › Plan | No other module or test writes a table's path |
| [Vacuum and tombstone retention](#vacuum-and-tombstone-retention) › Safety check | d010 › Plan | Why the unit test pins the two retentions |

#### Do

1. Write the test of the two retentions in `test_settings.py`, failing.
2. Add the constants to `settings.py` and remove the two path constants.
3. Update `delta.py` and `test_run.py` to take every path from `TABLE_PATHS`.

#### Check

```bash
bash pipeline/scripts/check-pipeline.sh
grep -rn -E "STATION_STOCK_PATH|PROCESSED_OBJECTS_PATH" pipeline
```

Yes if the checks exit 0 and the search finds nothing.

### Step 3 — Pure maintenance decisions

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d010.s3 add the pure decisions of Delta maintenance`
- **R:** R12, R13
- **Model:** `sonnet · medium`
- **Review:** `no`

#### Scope

- `pipeline/src/bikesharing/core/delta_maintenance.py` (new): `Partition`, `CompactionMetrics`, `RetentionMetrics`, `first_open_day`, `partitions_to_compact`, `retention_start`, `partitions_to_delete` and `is_maintenance_run`.
- `pipeline/tests/unit/core/test_delta_maintenance.py` (new):
  - R12: `retention_start` and `partitions_to_delete` on month and year edges;
  - R13: `partitions_to_delete` keeps the window's first day and every later one;
  - `partitions_to_compact`: a closed partition with one file and with more, an open one below and at the threshold, and a threshold of `None`;
  - `first_open_day`: a latest capture within the lookback after midnight, in UTC and in Europe/Madrid;
  - `is_maintenance_run`: a start at the window's start, just before its end, and at its end.

#### Reads

| What | Where | Why |
|---|---|---|
| [`bikesharing.core.delta_maintenance`](#bikesharingcoredelta_maintenance) | d010 › Components | The contract and what each function decides |
| [Compaction](#compaction) › Closed partition, Compacted once | d010 › Plan | Which partitions compact |
| [Daily maintenance](#daily-maintenance) › Which run, In order item 1 | d010 › Plan | The maintenance run and the retention cutoff |
| [D4](#d4-silver-keeps-the-current-local-month-and-the-12-whole-months-before-it) | d010 › Spec | The retention window the edge cases follow |

#### Do

1. Write the tests in `test_delta_maintenance.py`, failing.
2. Implement `delta_maintenance.py` until they pass.

#### Check

```bash
bash pipeline/scripts/check-pipeline.sh
```

Yes if it exits 0.

### Step 4 — Maintenance events

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d010.s4 add the maintenance events`
- **R:** R2
- **Model:** `sonnet · low`
- **Review:** `no`

#### Scope

- `pipeline/src/bikesharing/core/events.py`: the builders `table_compacted`, `retention_applied`, `table_vacuumed`, `log_cleaned` and `maintenance_failed`.
- `contracts/log-events.registry.json`: the five events, with `needs_action: false` and no alert; no existing entry changes.
- `pipeline/tests/unit/core/test_events.py`: one test per builder; the existing tests of the run's events and the registry's test pass unchanged (R2).

#### Reads

| What | Where | Why |
|---|---|---|
| [Maintenance events](#maintenance-events) | d010 › Plan | Each event's level, fields and integer counts |
| [`bikesharing.core.events`](#bikesharingcoreevents) | d010 › Components | The builders' form, and the metrics they take |
| The `batch_committed` builder and its registry entry | `events.py`, `contracts/log-events.registry.json` | The form the new builders and entries follow |

#### Do

1. Write the builders' tests in `test_events.py`, failing.
2. Implement the five builders in `events.py`.
3. Add the five entries to `contracts/log-events.registry.json`.

#### Check

```bash
bash pipeline/scripts/check-pipeline.sh
```

Yes if it exits 0.

### Step 5 — A run opens each table once

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `refactor: d010.s5 open each Delta table once per run`
- **R:** R1
- **Model:** `opus · medium`
- **Review:** `no`

#### Scope

- `pipeline/src/bikesharing/shell/delta.py`:
  - `Tables`, the run's handle on each table;
  - `ensure_tables` returns `Tables`, opening each table once after creating any missing one;
  - every call of a run takes `tables` in place of `lakehouse`, with its other parameters unchanged until Steps 6 and 8;
  - a handle is refreshed after the module's own writes and before a retried MERGE.
- `pipeline/src/bikesharing/shell/run.py`: calls `ensure_tables` once and passes its `Tables` to every other call.
- `pipeline/tests/integration/test_delta.py`, `pipeline/tests/integration/test_run.py`: their calls take `Tables`; the existing tests of a run's `station_stock` rows and published file pass unchanged (R1).
- `pipeline/tests/integration/test_delta.py` and the example in `Lakehouse.table_uri`'s docstring in `delta.py`: every table path from `TABLE_PATHS`, none written as a literal ([Table settings and catalog](#table-settings-and-catalog)).

#### Reads

| What | Where | Why |
|---|---|---|
| [Common table access](#common-table-access) | d010 › Plan | One open per table per run, and the refresh after its own writes |
| [`bikesharing.shell.delta`](#bikesharingshelldelta) › `Tables`, `ensure_tables` | d010 › Components | The new type and the signatures that change |
| [Breaking changes](#26-breaking-changes), second row | d010 › Plan | The dependants that change with the signatures |
| `_table`, `_query` and `merge_station_stock`'s retry | `delta.py` | The open per call that `Tables` replaces, and where a retried MERGE refreshes |

#### Do

1. Implement `Tables` and the new `ensure_tables` in `delta.py`.
2. Change every call of a run in `delta.py` to take `tables`, reading through its handles.
3. Update `run.py` to call `ensure_tables` once and pass `Tables`.
4. Update `test_delta.py` and `test_run.py` to the new signatures.
5. Replace the table paths written as literals in `test_delta.py` and in `delta.py`'s docstring.

#### Check

```bash
bash pipeline/scripts/check-pipeline.sh
grep -rn -E "silver/station_stock|control/processed_objects" pipeline/src pipeline/tests --include="*.py"
```

Yes if the checks exit 0 with no test removed, and the search finds only `TABLE_PATHS`' two lines in `settings.py`.

### Step 6 — `processed_objects` by system, feed and UTC date

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d010.s6 partition processed_objects by system, feed and UTC date`
- **R:** R1, R3, R16
- **Model:** `opus · medium`
- **Review:** `no`

#### Scope

- `pipeline/src/bikesharing/shell/delta.py`:
  - `PROCESSED_OBJECTS_SCHEMA` gains `utc_date` after `captured_at`; `TABLE_SCHEMAS`, `PARTITION_COLUMNS` and `DATE_PARTITION`;
  - `ensure_tables` creates each missing table of `TABLE_PATHS` with its schema, its partition columns and three properties from `settings.py`: `delta.checkpointInterval`, `delta.enableExpiredLogCleanup` set to `false`, and `delta.deletedFileRetentionDuration`;
  - `record_processed` writes each row's `utc_date` from `captured_at`, and its MERGE predicate adds the batch's systems, feeds, `utc_date` partitions and `captured_at` range (call 6);
  - `capture_history` and `latest_captures` list the columns they return in their queries, in place of `select *`: `capture_history` those it returned before, without `utc_date`, and `latest_captures` those of `station_stock` today (#5).
- `pipeline/tests/integration/test_delta.py`:
  - R1: `capture_history` returns the columns it returned before, without `utc_date`, and `latest_captures` those of `station_stock`;
  - the table properties of a new table, once per key of `TABLE_PATHS` (`pytest.mark.parametrize`);
  - R3: objects of two systems are recorded in the one `processed_objects`, one row each;
  - R16: a batch recorded twice adds no rows to `station_stock` or `processed_objects`.

#### Reads

| What | Where | Why |
|---|---|---|
| [`processed_objects` layout](#processed_objects-layout) | d010 › Plan | The partition columns and `utc_date` |
| [Bounded calls](#bounded-calls), rows 1 and 6 | d010 › Plan | What `ensure_tables` and `record_processed` state |
| [Checkpoint interval](#checkpoint-interval) › Where it lives; [Vacuum and tombstone retention](#vacuum-and-tombstone-retention), table; [Daily maintenance](#daily-maintenance), In order item 3 | d010 › Plan | The three properties and where their values come from |
| [`bikesharing.shell.delta`](#bikesharingshelldelta) › constants, `ensure_tables`, `record_processed`, `capture_history`, `latest_captures` | d010 › Components | The contract |
| [Common table access](#common-table-access), last bullet | d010 › Plan | Every query names the columns it returns |

#### Do

1. Write the tests in `test_delta.py`, failing.
2. Implement the schema, the three mappings and `ensure_tables`' creation in `delta.py`.
3. Implement `record_processed`'s `utc_date` and its bounded MERGE.
4. List the columns of `capture_history`'s and `latest_captures`' queries.

#### Check

```bash
bash pipeline/scripts/check-pipeline.sh
```

Yes if it exits 0.

### Step 7 — Discovery from each feed's latest capture

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d010.s7 list bronze from each feed's latest capture`
- **R:** R10, R11
- **Model:** `sonnet · medium`
- **Review:** `no`

#### Scope

- `pipeline/src/bikesharing/core/discovery.py`: `ListingPlan` gains `feed`; `plan_listing` takes the feed and drops `now` and `timezone`, so there is no daily full sweep, and `full_sweep` is true only for a feed with nothing processed.
- `pipeline/src/bikesharing/core/settings.py`: `LISTING_LOOKBACK` becomes 15 min.
- `pipeline/src/bikesharing/shell/run.py`: passes each feed to `plan_listing`, with `latest_processed`'s value for its system until Step 8.
- `pipeline/tests/unit/core/test_discovery.py`:
  - R10: `plan_listing` starts after the key of the latest capture minus 15 min;
  - R11: `plan_listing` lists the whole prefix when nothing is processed;
  - the tests of the daily full sweep are removed with it.
- `pipeline/tests/integration/test_r2.py`: its `ListingPlan` gains `feed`.

#### Reads

| What | Where | Why |
|---|---|---|
| [D3](#d3-discovery-keeps-a-watermark-per-system-and-feed) | d010 › Spec | The watermark per system and feed, and the lookback |
| [`bikesharing.core.discovery`](#bikesharingcorediscovery) | d010 › Components | The new `ListingPlan` and `plan_listing` |
| The paragraph after the table in [Bounded calls](#bounded-calls) | d010 › Plan | A feed with no processed object lists from its start |

#### Do

1. Update the tests in `test_discovery.py`, failing.
2. Implement the new `plan_listing` in `discovery.py`.
3. Set `LISTING_LOOKBACK` to 15 min in `settings.py`.
4. Update the call in `run.py`.

#### Check

```bash
bash pipeline/scripts/check-pipeline.sh
```

Yes if it exits 0.

### Step 8 — Bounded reads of `processed_objects`

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d010.s8 bound the reads of processed_objects per system and feed`
- **R:** R1, R4, R10, R11
- **Model:** `opus · high`
- **Review:** `no`

#### Scope

- `pipeline/src/bikesharing/shell/delta.py`:
  - `latest_processed` returns each system and feed's latest `captured_at` from the log's file statistics of its latest `utc_date` partition, leaving out a feed with no row (calls 2 and 7), or by the fallback of Step 1's check;
  - `processed_keys` takes each feed's instant and reads only its partitions from that instant's date (call 3);
  - `capture_history` takes the batch's feeds and reads their partitions within `[since, until)` (call 4).
- `pipeline/src/bikesharing/shell/run.py`: each feed's instant is its latest capture minus `LISTING_LOOKBACK`; `latest_captures` takes, per system, the instant of `(system, FEED)`.
- `pipeline/tests/integration/test_delta.py`:
  - R4: with a data file of another system's partition removed from disk, `processed_keys` and `capture_history` still return the feed's rows;
  - R10: `processed_keys` returns no key captured before the feed's instant;
  - R11: `latest_processed` leaves out a feed with no row;
  - R1: the existing tests of a run's `station_stock` rows and published file pass unchanged.

#### Reads

| What | Where | Why |
|---|---|---|
| [Bounded calls](#bounded-calls), rows 2, 3, 4, 7 and 8 | d010 › Plan | The range each call states |
| [deltalake 1.7.0](#deltalake-170) › File statistics | d010 › Plan | The add actions' columns, and the fallback if Step 1's check failed |
| [`bikesharing.shell.delta`](#bikesharingshelldelta) › `latest_processed`, `processed_keys`, `capture_history` | d010 › Components | The signatures and what each returns |
| [`bikesharing.shell.run`](#bikesharingshellrun) › Gold | d010 › Components | How gold takes each system's instant |

#### Do

1. Write the tests in `test_delta.py`, failing.
2. Implement `latest_processed`, `processed_keys` and `capture_history` in `delta.py`.
3. Update their calls in `run.py`.

#### Check

```bash
bash pipeline/scripts/check-pipeline.sh
```

Yes if it exits 0.

### Step 9 — Maintenance tasks on a table

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d010.s9 add compaction, retention, vacuum and log cleanup to the table access`
- **R:** R12, R14
- **Model:** `opus · medium`
- **Review:** `no`

#### Scope

- `pipeline/src/bikesharing/shell/delta.py`: `table_partitions`, `compact`, `delete_partitions`, `vacuum` and `cleanup_log`.
- `pipeline/tests/integration/test_delta.py`:
  - `table_partitions` returns each partition with its data files, with every data file removed from disk;
  - `compact` compacts only the partitions given and returns their metrics;
  - R12: `delete_partitions` removes the partitions given and returns the rows deleted;
  - R14: `compact` and `delete_partitions` given no partition leave the table's version unchanged;
  - `vacuum` with a retention of 0 deletes a file the table removed and returns 1; with a retention of 1 h it deletes nothing and returns 0, since `retention_hours` takes whole hours and no test waits one.

#### Reads

| What | Where | Why |
|---|---|---|
| [`bikesharing.shell.delta`](#bikesharingshelldelta) › Maintenance | d010 › Components | The five functions |
| [Compaction](#compaction) | d010 › Plan | `optimize.compact` restricted to the partitions given |
| [Vacuum and tombstone retention](#vacuum-and-tombstone-retention); [deltalake 1.7.0](#deltalake-170) › Explicit values | d010 › Plan | Vacuum's explicit arguments |
| [Maintenance events](#maintenance-events), column Values from `deltalake` | d010 › Plan | Where each metric comes from |

#### Do

1. Write the tests in `test_delta.py`, failing.
2. Implement the five functions in `delta.py`.

#### Check

```bash
bash pipeline/scripts/check-pipeline.sh
```

Yes if it exits 0.

### Step 10 — Compaction and daily maintenance in a run

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `feat: d010.s10 compact after each batch and run the daily maintenance`
- **R:** R2, R15
- **Model:** `opus · high`
- **Review:** `code`

#### Scope

- `pipeline/src/bikesharing/shell/run.py`:
  - `RunConfig.maintenance_window`: `RUN_SETTINGS.cadence` in `scheduled_config`, `None` in `one_off_config`;
  - after each committed batch, per table, `compact` with `partitions_to_compact` over `table_partitions`, writing `table_compacted`;
  - after the batch loop and before publishing, in the maintenance run only: retention, vacuum and log cleanup, in that order, writing their events; retention's `today` is the date of the run's start in `LOCAL_TIMEZONE`, the current local month of R12;
  - each task runs per table in its own `try`, and a failure writes `maintenance_failed` and goes on, with the run's outcome unchanged.
- `pipeline/tests/integration/test_run.py`, with the run's start passed as a fixed UTC time:
  - a batch that leaves partitions over their rule compacts them;
  - the daily maintenance runs in the maintenance run and in no other, nor in a one-off run;
  - R15: the daily maintenance leaves every row of `processed_objects`;
  - a failing task writes `maintenance_failed`, and the run's outcome does not change;
  - R2: the events the run writes are registered.
- `docs/architecture.md` › 6.2 Pipeline run: compaction after each batch and the daily maintenance after the last batch of the maintenance run.

#### Reads

| What | Where | Why |
|---|---|---|
| [`bikesharing.shell.run`](#bikesharingshellrun) | d010 › Components | `RunConfig`'s new field, and where each task runs |
| [Daily maintenance](#daily-maintenance) | d010 › Plan | Which run, the order of the tasks, a missed day |
| [Maintenance events](#maintenance-events) › A failed task | d010 › Plan | Graceful degradation of a failed task |
| 6.2 Pipeline run | `docs/architecture.md` | The run's flow the update extends |

#### Do

1. Write the tests in `test_run.py`, failing.
2. Implement `maintenance_window`, the compaction after each batch and the daily maintenance in `run.py`.
3. Update `docs/architecture.md` › 6.2.

#### Check

```bash
bash pipeline/scripts/check-pipeline.sh
```

Yes if it exits 0.

### Step 11 — Only the table access imports `deltalake`

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `chore: d010.s11 allow only the table access to import deltalake`
- **R:** R5
- **Model:** `sonnet · low`
- **Review:** `no`

#### Scope

- `pipeline/pyproject.toml`: a `forbidden` import-linter contract, with `source_modules = ["bikesharing"]`, `forbidden_modules = ["deltalake"]` and `ignore_imports = ["bikesharing.shell.delta -> deltalake"]`, after the three existing contracts; `include_external_packages` is already `true`.
- Tests: none; R5 is verified by Inspection of the contract, which `check-pipeline.sh` runs in CI.

#### Reads

| What | Where | Why |
|---|---|---|
| [Common table access](#common-table-access), last paragraph | d010 › Plan | What the contract enforces, and why by tooling |
| `[tool.importlinter]` and its three contracts | `pipeline/pyproject.toml` | The form and the comment the new contract follows |

#### Do

1. Add the contract to `pyproject.toml`, with a comment citing ADR-0052.
2. Run `uv run --directory pipeline lint-imports`.

#### Check

```bash
bash pipeline/scripts/check-pipeline.sh
```

Yes if it exits 0 and `lint-imports` lists the new contract as kept.

### Step 12 — Lakehouse catalog

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `docs: d010.s12 add the lakehouse catalog`
- **R:** —
- **Model:** `opus · medium`
- **Review:** `no`

#### Scope

- `docs/lakehouse.md` (new):
  - the catalog's opening: what it holds and what for, how to read an entry, and one worked example that follows `processed_objects` through a run;
  - `## Adding a table`: the steps to add a table, each linking to the part of an entry that explains its value and stating what checks it;
  - `## Tables`: one `###` entry per table, headed by its name, with its partition columns, the range each reader states, its compaction and retention, and how each tunable value is computed, naming its constant in `settings.py` and never its value.
- `pipeline/tests/integration/test_lakehouse_catalog.py` (new): the `###` headings under `## Tables` are `TABLE_PATHS`' keys.
- `.github/workflows/ci.yml`: `docs/lakehouse.md` joins the `pipeline` path filter.
- `docs/architecture.md` › 8 Cross-cutting concepts: a bullet on Delta tables linking to the catalog.

#### Reads

| What | Where | Why |
|---|---|---|
| [Table settings and catalog](#table-settings-and-catalog) | d010 › Plan | What the catalog holds, its test and the path filter |
| [ADR-0052](../decisions/0052-delta-maintenance-and-access-pattern.md) | `docs/decisions/` | The pattern each entry applies |
| [Compaction](#compaction), [Checkpoint interval](#checkpoint-interval), [Vacuum and tombstone retention](#vacuum-and-tombstone-retention), [Daily maintenance](#daily-maintenance) | d010 › Plan | How each tunable value is computed |
| Catalogs | `.claude/rules/docs/general.md` | The opening every catalog starts with |
| The `pipeline` path filter | `.github/workflows/ci.yml` | Where the catalog's path joins |
| 8 Cross-cutting concepts | `docs/architecture.md` | Where the bullet goes, with its source |

#### Do

1. Write the test in `test_lakehouse_catalog.py`, failing.
2. Write `docs/lakehouse.md`.
3. Add `docs/lakehouse.md` to the `pipeline` path filter in `ci.yml`.
4. Add the bullet to `docs/architecture.md` › 8.

#### Check

```bash
bash pipeline/scripts/check-pipeline.sh
```

Yes if it exits 0, and the lint hook reports nothing on the two documents.

### Step 13 — One-off migration script

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d010.s13 add the one-off migration of the Delta tables`
- **R:** R6, R7, R8, R9, R17
- **Model:** `opus · high`
- **Review:** `code and security`

#### Scope

- `pipeline/scripts/migrate_delta_tables.py` (new), calling `deltalake` directly and taking from `bikesharing.shell.delta` and `settings.py` only each table's path, schema, partition columns and properties:
  - `main()`: Migration step 1 (clean working tree, untracked files included; HEAD is `origin/main`; HEAD's full SHA as code version); reads `MIGRATION_R2_ACCESS_KEY_ID` and `MIGRATION_R2_SECRET_ACCESS_KEY` from the environment; builds the storage options of `bikesharing-lakehouse` from `CLOUDFLARE_ACCOUNT_ID`, as `r2_lakehouse` does; exits non-zero naming each failed check;
  - `migrate`: Migration steps 2–5, on a lakehouse URI, its storage options and the code version;
  - `rewrite`, `verify` and `set_properties`: steps 3, 4 and 5; `verify` returns the names of the checks that failed;
  - on a failed verification, `migrate` restores the version before the rewrite and checks its partition columns and number of rows, reporting the version to restore if the restore fails;
  - every commit carries the code version in `custom_metadata`, through `CommitProperties`.
- `pipeline/scripts/check-pipeline.sh`: mypy also checks `scripts/migrate_delta_tables.py` (#4).
- `pipeline/tests/integration/test_migrate_delta_tables.py` (new), loading the script by path with `importlib`, on a local lakehouse whose `processed_objects` the test writes in the current layout:
  - R6: a correct rewrite passes the three checks;
  - R7: a rewritten table with one row, one key, or one run ID and code version altered fails `verify` naming that check, one case per check;
  - R17: `migrate`, with `rewrite` patched to drop one row, fails and leaves the table with the version before the rewrite's partition columns and rows, its restore commit carrying the code version;
  - R8: `station_stock` keeps the same data files, and its only new commit sets the table properties;
  - R9: each commit the migration writes carries the code version in its custom metadata;
  - a second run on a migrated table skips the rewrite and sets the properties;
  - the rewritten `processed_objects` has `captured_at` statistics in every data file, so `latest_processed` returns each feed's latest capture.
  - `main`'s code checks are not tested: the Done when checks TH1 in Step 15.

#### Reads

| What | Where | Why |
|---|---|---|
| [Migration](#migration) | d010 › Plan | The script's steps, its scope of the package, and its removal |
| [D2](#d2-existing-data-moves-to-the-new-layout-in-a-one-off-migration), [D5](#d5-security-of-the-migration-and-of-retention) | d010 › Spec | The verification's checks, the recovery, and the token's limits |
| [`bikesharing.shell.delta`](#bikesharingshelldelta) › constants | d010 › Components | The schema, partition columns and properties the rewrite takes |
| [d008 › Delta writes](d008-pipeline-platform-and-walking-skeleton.md#delta-writes) | d008 › Plan | The current layout of `processed_objects`, which the test writes |
| Its working-tree and `origin/main` checks | `pipeline/scripts/deploy.sh` | The checks `main` repeats |
| `r2_lakehouse` | `delta.py` | The storage options of R2 |
| The mypy line | `pipeline/scripts/check-pipeline.sh` | Where the script joins |

#### Do

1. Write the tests in `test_migrate_delta_tables.py`, failing.
2. Implement `migrate_delta_tables.py` until they pass.
3. Add the script to the mypy line of `check-pipeline.sh`.

#### Check

```bash
bash pipeline/scripts/check-pipeline.sh
```

Yes if it exits 0.

### Step 14 — Merge the implementation

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** —
- **R:** —
- **Model:** —
- **Review:** `no`

#### Scope

The PR of Steps 1–13, `T072: Delta maintenance and access in the pipeline` with `Refs #86`, merged into `main`. Merging deploys nothing: the scheduled function keeps the deployed code until Step 16.

#### Reads

| What | Where | Why |
|---|---|---|
| Branches, PRs and CI | `CLAUDE.md` › Git | Push, PR, checks, rebase merge and clean-up |

#### Do

1. Push the branch and mark its PR ready for review.
2. Wait for every required check to pass.
3. Rebase merge the PR.
4. Delete the local branch with `git branch -D`.

#### Check

```bash
gh pr view <number> --json state,mergedAt
```

Yes if `state` is `MERGED`, with `<number>` the PR of Do 1, since the local branch is gone.

### Step 15 — Pause the schedule and run the migration

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** —
- **R:** —
- **Model:** `sonnet · medium`
- **Review:** `no`

#### Scope

Steps 1 and 2 of D2's order, in production:

- the app `bikesharing-pipeline` stopped in Modal, so no run overlaps the migration;
- an R2 token, `bikesharing-t072-migration`: Object Read & Write on `bikesharing-lakehouse` only, with a TTL of one day (D5, TH1);
- `processed_objects` rewritten and verified, and the properties set on both tables, by the script from the merged `main`.

#### Reads

| What | Where | Why |
|---|---|---|
| [D2](#d2-existing-data-moves-to-the-new-layout-in-a-one-off-migration) | d010 › Spec | The order, and the recovery if a check fails |
| [D5](#d5-security-of-the-migration-and-of-retention) | d010 › Spec | The token's limits |
| [Migration](#migration) | d010 › Plan | What the script does and in which order |

#### Do

1. Wait until no run is in progress in Modal's dashboard, then run `uv run --directory pipeline --group platform modal app stop bikesharing-pipeline`.
2. Create the token in Cloudflare's dashboard › R2 › Manage API tokens, with the limits above.
3. Load its S3 access key pair into the shell without echo or history: `read -s "MIGRATION_R2_ACCESS_KEY_ID?Access key ID: " && export MIGRATION_R2_ACCESS_KEY_ID`, and the same for `MIGRATION_R2_SECRET_ACCESS_KEY`.
4. Switch to `main`, up to date with `origin/main`, with a clean working tree.
5. Run `uv run --directory pipeline python scripts/migrate_delta_tables.py`.
6. If it exits non-zero, keep the schedule stopped: the script has restored the version before its rewrite, or named the version to restore if it could not. Fix the cause and run the migration again.

#### Check

- Yes if the script exits 0 after reporting that its three checks passed.
- Yes if Modal's dashboard shows `bikesharing-pipeline` stopped until Step 16.

### Step 16 — Deploy the new code and revoke the token

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** —
- **R:** —
- **Model:** —
- **Review:** `no`

#### Scope

Step 3 of D2's order: the merged `main` deployed, which resumes the schedule; catch-up then processes what bronze received during the pause. The migration's token revoked (D5, TH1).

#### Reads

| What | Where | Why |
|---|---|---|
| The script's header | `pipeline/scripts/deploy.sh` | Its checks, the deploy and the smoke test |

#### Do

1. Run `bash pipeline/scripts/deploy.sh` from `main`.
2. Revoke `bikesharing-t072-migration` in Cloudflare's dashboard.
3. Run `unset MIGRATION_R2_ACCESS_KEY_ID MIGRATION_R2_SECRET_ACCESS_KEY`.

#### Check

- Yes if `deploy.sh` exits 0, its smoke test included.
- Yes if `bikesharing-t072-migration` is no longer listed in R2 › Manage API tokens.

### Step 17 — Check the Done when in production

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** —
- **R:** —
- **Model:** `sonnet · medium`
- **Review:** `no`

#### Scope

The Done when's measures, over a window of at least 3 h that starts with the first scheduled run after Step 16 with one batch, and includes the run at `MAINTENANCE_LOCAL_TIME` (04:00 Europe/Madrid). Step 16 is therefore run so that this window can start by 01:00 local time. The results are recorded in d010 › Close.

- **A checkpoint of each table:** by Analysis. A window with at least `CHECKPOINT_INTERVAL` (8) commits of a table includes a checkpoint of it, and every batch commits to both tables.
- **The tools:** `run_stats.py` and `r2_metrics.py` from `spikes/t077-run-time-and-r2-reads/`, with their credentials as its README sets. Their window is set in local edits that are discarded after the check.

#### Reads

| What | Where | Why |
|---|---|---|
| [Done when](#14-done-when) | d010 › Spec | The window and its thresholds |
| Prerequisites, Run time and memory, R2 operations and storage | `spikes/t077-run-time-and-r2-reads/README.md` | Each tool's credentials, window and command |

#### Do

1. Find the window's first run: the first scheduled run after Step 16 whose log has one `batch_committed`.
2. Set `START`, `END` and `DAYS` in `run_stats.py` to the window, and run it as its README sets.
3. Run `r2_metrics.py` with `--bucket bikesharing-lakehouse --start <window start> --end <window end>`, and divide its GetObject total by the window's runs.
4. Count the window's `batch_committed` events.
5. Read the maintenance run's log for `retention_applied`, `table_vacuumed`, `log_cleaned` and `maintenance_failed`. Record with the results that run's total run time and its margin to the timeout (`timeout_s` in `run_settings.json`), with no threshold, since the p95 leaves this run out. **DI2**
6. If a threshold fails, check `capture_history`'s pruning first.
7. Discard the local edits of the spike's scripts.

#### Check

Yes if every item holds:

- GetObject per run on `bikesharing-lakehouse` is at most 700;
- p95 run time is at most 2 min;
- the window has at least 8 `batch_committed` events;
- the maintenance run's log has its events for each table, and no `maintenance_failed`.

### Step 18 — Remove the one-off migration

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `chore: d010.s18 remove the one-off migration`
- **R:** —
- **Model:** `sonnet · low`
- **Review:** `code`

#### Scope

On the task's branch recreated from `main`, in the PR that records the Done when, with `Closes #86`:

- `pipeline/scripts/migrate_delta_tables.py`: removed;
- `pipeline/tests/integration/test_migrate_delta_tables.py`: removed;
- `pipeline/scripts/check-pipeline.sh`: the script leaves the mypy line (#4).

#### Reads

| What | Where | Why |
|---|---|---|
| [Migration](#migration), last paragraph | d010 › Plan | What is removed and why |

#### Do

1. Remove the script and its test.
2. Remove the script from the mypy line of `check-pipeline.sh`.

#### Check

```bash
bash pipeline/scripts/check-pipeline.sh
grep -rn "migrate_delta_tables" pipeline
```

Yes if the checks exit 0 and the search finds nothing.

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
| DI1 | [deltalake 1.7.0](#deltalake-170), [Step 1](#step-1--upgrade-deltalake-to-170) | `deltalake` 1.7.0 is kept, and the two retry tests provoke the conflict with one key both writers insert, following tests of observable behaviour | 1.7.0 no longer conflicts on every concurrent insert within the batch's capture range; no case tried duplicated a key | Step 1 |
| DI2 | [Step 17](#step-17--check-the-done-when-in-production) | Step 17 also records the maintenance run's total run time and its margin to the timeout, with no threshold, following measuring the headroom to a limit | The p95 leaves that run out, and no data yet sets a threshold | Step 1 |
| DI3 | [Maintenance events](#maintenance-events) | `table_compacted` is written only when a batch's compaction of a table has partitions due, following one event per unit of work done | Each event is then one compaction, with no event at zero from every batch, about 190 a day | Step 10 |
