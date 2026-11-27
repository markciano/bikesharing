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
- Phase: [x] Spec · [ ] Plan · [ ] Plan review · [ ] Steps · [ ] Steps review
- Current: Plan › concerns, C1–C5 written (Common table access to Daily maintenance). Left, in order: C6 `delta.checkpointInterval` per table, between 5 and 10, from each table's opens per run (settled); C7 maintenance events (compaction, retention, vacuum) in the event registry (asked; Compaction's last sentence assumes compaction events); C8 migration script in `pipeline/scripts/`, its verification and code version in the commit metadata (settled, D2, D5, R6–R9); C9 rewrite [d008 › Delta writes](d008-pipeline-platform-and-walking-skeleton.md#delta-writes), whose #6 makes maintenance a separate job, with `**replaces …**` (settled, ADR-0052); C10 steps for moving Modal's region, written and not run (settled, T080). Parked for File layout: a catalog of the lakehouse's tables (physical model, every layer, storage only), e.g. `docs/lakehouse.md`, linked from architecture.md › 8.

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
- **R5** The pipeline shall read and write `processed_objects` only through its common table access. (D1)
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

### 1.4 Done when

<!-- Optional. Only what closes this task and Requirements cannot express: operational actions, checks on real data, understanding. The general closing rule is checked in `.claude/skills/implement/review.md`. -->

The owner ran the change in D2's order, and the migration from the merged `main` with a token that writes only to `bikesharing-lakehouse` and expires after one day, revoked once the migration passed (D2, D5, TH1).

Checked on production after the deploy, over a window of at least 3 h that starts with the first scheduled run with no catch-up (one batch), and includes a checkpoint of each table and the run of the daily maintenance ([s019 › P7](../spikes/s019-pipeline-run-time-r2-reads.md#55-production-inputs)):

- GetObject per run on `bikesharing-lakehouse` (`r2_metrics.py`) stays at or below 700, with about 400 on average expected;
- p95 run time (`run_stats.py`) is at most 2 min, the estimate [ADR-0027](../decisions/0027-modal-as-execution-platform.md) rests on.

If either fails, `capture_history`'s pruning is checked first.

### 1.5 Out of scope

<!-- Optional. What someone could expect and will not be done, each item pointing to the task that covers it. -->

- Moving Modal's region ([s019 › P8](../spikes/s019-pipeline-run-time-r2-reads.md#55-production-inputs)): its steps are written in this design and not run in it — T080

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
- it reads values the log's file statistics hold, such as a feed's latest capture, from the log.

An import-linter contract in `pipeline/pyproject.toml` makes it the only module of the package that imports `deltalake`, following module boundaries enforced by tooling, as ADR-0046's rules are. A slice that reads `processed_objects` on its own fails CI, instead of bringing back full reads that only R2's request counts would show (R5). `.claude/rules/code/python.md` › Structure states the same rule.

#### `processed_objects` layout

`processed_objects` is partitioned by `system`, `feed` and `utc_date`, in that order, following partitioning by the range its readers filter by ([ADR-0052](../decisions/0052-delta-maintenance-and-access-pattern.md)):

- **`system` and `feed`:** each feed reads only its own rows, and a new feed adds its own partitions (D1, R4).
- **`utc_date`:** a new column, the UTC date of `captured_at`, the date in the bronze key, which the pipeline writes with each row. Every reader filters by UTC instants (discovery's watermark minus the lookback, `capture_history`'s 7 days, a batch's capture range), so each range maps to whole partitions with no time-zone conversion. ADR-0041's local calendar keys apply to fact rows, not to control state.
- **Size:** one partition per system, feed and day, compacted into one file once closed, adds about 365 files a year per system and feed to the log.

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

#### Daily maintenance

The daily maintenance runs inside one run a day, after its last batch, following a fixed maintenance window off-peak with idempotent tasks ([ADR-0052](../decisions/0052-delta-maintenance-and-access-pattern.md)):

- **Which run:** the run that starts within the 15 min from `MAINTENANCE_LOCAL_TIME` in Europe/Madrid, a constant in `settings.py` set to `04:00`, outside the slow hours of [s019 › Not verified](../spikes/s019-pipeline-run-time-r2-reads.md#54-not-verified). The run decides from its own start time, which it receives as a parameter, so no state records whether maintenance ran.
- **In order:**
  1. Retention deletes every partition of `station_stock` whose local date is before the first day of the current local month minus 12 months, with partition values read from the log; with none, it writes no commit (D4, R12–R14).
  2. Vacuum removes, from both tables, the data files their log removed more than 7 days ago, with `dry_run=False` (ADR-0021), as [Vacuum and tombstone retention](#vacuum-and-tombstone-retention) sets.
  3. Log cleanup removes, from both tables, the log files older than the log's 30-day retention, with `cleanup_metadata()`. Both tables set `delta.enableExpiredLogCleanup` to `false`, the way [Checkpoint interval](#checkpoint-interval) sets its property, so no commit lists `_delta_log/` to clean it.
- **A missed day:** the three tasks act on the tables' state, not on the date, so the next day's maintenance does what a failed or skipped one left (D4).
- **Cost:** 1 run in 96 takes longer, so it stays out of the p95; no task lists a table's data files.

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

Each maintenance task writes one event per table it acts on, following one structured event per unit of work, as `batch_committed` and `node_finished` do. The events are added to `contracts/log-events.registry.json`, at level `info`, with `needs_action: false` and no alert, and no existing event changes (R2):

| Event | Written | Fields | Counts from `deltalake` |
|---|---|---|---|
| `table_compacted` | After a batch's compaction of one table | `table`, `partitions`, `files_removed`, `files_added`, `duration_s` | `optimize.compact`'s metrics |
| `retention_applied` | After the retention of `station_stock`, also when it deletes nothing | `table`, `partitions_deleted`, `rows_deleted`, `duration_s` | `delete`'s metrics |
| `table_vacuumed` | After the vacuum of one table | `table`, `files_deleted`, `duration_s` | The length of the list `vacuum` returns |
| `log_cleaned` | After the log cleanup of one table | `table`, `duration_s` | None: `cleanup_metadata()` returns no count |

Every count is an integer. The events measure each task on its own: the compaction events show whether `COMPACTION_THRESHOLD` runs well, and the daily ones show the Done when's run of the daily maintenance.

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
