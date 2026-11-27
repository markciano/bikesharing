# Lakehouse catalog

This catalog lists the Delta tables the pipeline keeps in the `bikesharing-lakehouse` bucket, and how each applies the Delta maintenance and access pattern of [ADR-0052](decisions/0052-delta-maintenance-and-access-pattern.md): it is opened once per run, partitioned by the range its readers filter by, read and merged only within that range, compacted without merging files within a range a reader prunes by, and vacuumed within its history. It is the reference for changing a table's settings and for adding a table.

Each table's settings have one source, `pipeline/src/bikesharing/core/settings.py`, and `bikesharing.shell.delta` is the only module that reads or writes the tables. This catalog explains how each value is chosen and names the constant that holds it, never the value itself, so the code stays the one place to read it.

## How to read an entry

[Tables](#tables) opens with a summary table, one row per table, that names the constant behind each setting. Each entry below it is headed by the table's name, the key of `TABLE_PATHS` in `settings.py` that maps it to its path in the bucket. It has five parts, always in this order:

- **Partitions:** the partition columns, in order, held in `PARTITION_COLUMNS` in `bikesharing.shell.delta`, and why each one.
- **Readers:** each call of `bikesharing.shell.delta` that reads or merges the table, and the range it states. A call that states no range reads the whole table.
- **Compaction:** what is compacted after each batch, for active partitions (those a later batch can still write to) and closed ones.
- **Retention:** which rows the daily maintenance deletes, if any.
- **Log and vacuum:** the checkpoint interval, vacuum and log cleanup, and how each value is computed.

## Worked example

`processed_objects` through one scheduled run:

1. **Opening:** the run opens the table once, creating it if missing with the properties of [`processed_objects` › Log and vacuum](#processed_objects). Every later call of the run reuses this handle, refreshed after the run's own writes.
2. **Discovery:** the run reads each system and feed's latest capture from the file statistics in the log, with no data read, then the keys recorded from that instant minus `LISTING_LOOKBACK`: only the `utc_date` partitions from that instant's date are read.
3. **Each batch:** dbt's capture volume reads the batch's system and feed over the window before the batch. The batch's objects are then recorded with a MERGE whose predicate names the batch's systems, feeds, `utc_date` partitions and `captured_at` range, so it rewrites no file outside them.
4. **After each batch:** the run compacts every partition the batch left over its rule: an active one at or over `COMPACTION_THRESHOLD["processed_objects"]` data files, and every closed one with more than one file. Each compaction writes a `table_compacted` event.
5. **Daily maintenance:** if the run starts within one schedule interval after `MAINTENANCE_LOCAL_TIME`, it vacuums the table and cleans its log after its last batch, writing `table_vacuumed` and `log_cleaned`. `processed_objects` has no retention, so it deletes no rows.

A run thus reads a number of files that depends on its window and on the commits since the last checkpoint, not on the table's history.

## Adding a table

A new table follows these steps, in order. Each names what checks it; where nothing does, the run's events and R2's request counts are the only signal.

1. **Name and path:** add the name to `TableName` and its path to `TABLE_PATHS` in `settings.py`. `TABLE_PATHS`' keys are the pipeline's tables, and every module and test takes a table's path from it.
2. **Entry:** add the table's row to the summary table and its entry under [Tables](#tables), following [How to read an entry](#how-to-read-an-entry). Checked by `tests/integration/test_lakehouse_catalog.py`, which fails when the catalog's table headings and `TABLE_PATHS`' keys differ, or when an entry lacks one of its five parts or has them out of order.
3. **Schema and partitions:** add the schema to `TABLE_SCHEMAS`, and the partition columns to `PARTITION_COLUMNS` and `DATE_PARTITION` in `bikesharing.shell.delta`, chosen from the ranges its readers filter by, as in [`processed_objects` › Partitions](#processed_objects). `ensure_tables` creates the table from them, so a missing entry fails its test of the table properties; no test checks the choice of columns.
4. **Readers:** add each read and MERGE to `bikesharing.shell.delta`, stating the table's range and naming the columns it returns, as in [`processed_objects` › Readers](#processed_objects). Import-linter checks that no other module of the package imports `deltalake`; no test checks that a call states its range.
5. **Checkpoint interval:** add the table to `CHECKPOINT_INTERVAL`, computed as in [`processed_objects` › Log and vacuum](#processed_objects). `ensure_tables`' test of the table properties runs once per key of `TABLE_PATHS`, so a table with no interval fails it; no test checks the formula.
6. **Compaction:** add the table to `COMPACTION_THRESHOLD` only if its readers read its active partitions whole, as in [`processed_objects` › Compaction](#processed_objects); a table with no entry compacts only its closed partitions. No test checks the choice.
7. **Retention:** add the table to `RETENTION_MONTHS` only if its layer's retention ([ADR-0021](decisions/0021-retention-per-layer.md)) bounds its rows, as in [`station_stock` › Retention](#station_stock); a table with no entry keeps all its rows. No test checks the choice.

## Tables

| Table | Layer | Partitions | Active partitions | Retention | Checkpoint |
|---|---|---|---|---|---|
| [`station_stock`](#station_stock) | Silver | `local_date` | Never compacted | `RETENTION_MONTHS` | `CHECKPOINT_INTERVAL` |
| [`processed_objects`](#processed_objects) | Control | `system`, `feed`, `utc_date` | `COMPACTION_THRESHOLD` | None | `CHECKPOINT_INTERVAL` |

### `station_stock`

Silver table: one row per station and capture, the input of every gold model.

- **Partitions:** `local_date`, the Europe/Madrid date of `captured_at`, the fact row's local calendar key ([ADR-0041](decisions/0041-utc-timestamps-local-calendar-keys.md)). Its writers and readers both work by capture range, and retention deletes whole local months.
- **Readers:**
  - `merge_station_stock`: the batch's `local_date` partitions and its `captured_at` range, which the MERGE also prunes its target files by, through the source's statistics.
  - `latest_captures`: the `local_date` partition of each system's latest capture, and that `captured_at`.
- **Compaction:**
  - Active partitions are never compacted: both readers prune within the day by `captured_at`, which one file spanning the day would defeat. The table has no `COMPACTION_THRESHOLD` entry.
  - A partition is closed once its date is before the local date of the batch's latest capture minus `LISTING_LOOKBACK`, since no later batch writes to it. Every closed partition with more than one data file is compacted into one, found from the log, so a run that fails before compacting is caught up by the next.
- **Retention:** the daily maintenance deletes every partition whose local date is before the first day of the current local month minus `RETENTION_MONTHS["station_stock"]` months. The value is the number of whole months the longest gold window needs, so silver keeps the current month and those before it ([ADR-0021](decisions/0021-retention-per-layer.md)). With no partition to delete, it writes no commit.
- **Log and vacuum:** as for [`processed_objects`](#processed_objects), with the same inputs, so `CHECKPOINT_INTERVAL["station_stock"]` comes from the same formula.

### `processed_objects`

Control table: one row per bronze object the pipeline has processed, with its system, feed, capture instant, run ID and code version. Discovery reads it to skip what is already processed, and dbt reads it for the capture volume.

- **Partitions:** `system`, `feed` and `utc_date`, in that order:
  - `system` and `feed`: each feed reads only its own rows, and a new feed adds its own partitions.
  - `utc_date`: the UTC date of `captured_at`, the date in the bronze key. Every reader filters by UTC instants, so each range maps to whole partitions with no time-zone conversion.
- **Readers:**
  - `latest_processed`: no data read; per system and feed, the maximum of `captured_at`'s statistics over the files of its latest `utc_date` partition, from the log.
  - `processed_keys`: per system and feed, the `utc_date` partitions from its latest capture minus `LISTING_LOOKBACK`, and `captured_at` at or after that instant. A feed with no partition lists bronze from its start.
  - `capture_history`: the batch's system and feed, with `utc_date` and `captured_at` within the window of dbt's capture volume before the batch, `_VOLUME_WINDOW` in `bikesharing.shell.run`.
  - `record_processed`: a MERGE on `key` whose predicate adds the batch's systems, feeds, `utc_date` partitions and `captured_at` range, so it reads and rewrites only those files.
- **Compaction:**
  - Every reader reads a partition whole, so an active partition is compacted when a batch leaves it at or over `COMPACTION_THRESHOLD["processed_objects"]` data files. The value is the highest that keeps a run within the GetObject budget of [d010 › Done when](designs/d010-delta-maintenance-and-access.md#14-done-when), by the request arithmetic of [s019 › Verdict](spikes/s019-pipeline-run-time-r2-reads.md#53-verdict); a lower one saves under a second per run. The `table_compacted` events show whether another value runs better.
  - Closed partitions, as for `station_stock` but by UTC date, are compacted into one file each, so the table adds about one file per system, feed and day.
- **Retention:** none. The table has no `RETENTION_MONTHS` entry and keeps every row, since bronze keeps every object ([ADR-0021](decisions/0021-retention-per-layer.md)).
- **Log and vacuum:**
  - **Checkpoint interval:** `CHECKPOINT_INTERVAL["processed_objects"]`, the table's `delta.checkpointInterval`, is the N that minimizes the table's R2 requests per run, N = √(2 · c · a · w / o), rounded: `c` the commits per run (the MERGE, and a compaction now and then), `a` the Class A requests a checkpoint costs, `w` the weight of a Class A request against a Class B one in R2's free allowance, and `o` the opens per run that replay the log. N stays at or below the commits of 3 h of runs, so that any 3-hour window includes a checkpoint. The inputs and their sources are in [d010 › Checkpoint interval](designs/d010-delta-maintenance-and-access.md#checkpoint-interval); a change in them means computing N again.
  - **Vacuum:** the daily maintenance deletes the data files the log removed more than `VACUUM_RETENTION` ago, the table history of [ADR-0021](decisions/0021-retention-per-layer.md). It finds them from the log's tombstones, which each checkpoint drops after `TOMBSTONE_RETENTION`, the table's `delta.deletedFileRetentionDuration`. `TOMBSTONE_RETENTION` is longer than `VACUUM_RETENTION` by the number of daily vacuums that see each file, so vacuum catches up after missed days up to that number less one; a file whose tombstone is gone stays in R2 until a full vacuum. `tests/unit/core/test_settings.py` checks that `VACUUM_RETENTION` is the table history and below `TOMBSTONE_RETENTION`.
  - **Log cleanup:** the daily maintenance removes the log files older than the log's retention, `deltalake`'s default. `delta.enableExpiredLogCleanup` is off, so no commit lists `_delta_log/` to clean it.
  - **When:** the daily maintenance runs after the last batch of the run that starts within one schedule interval after `MAINTENANCE_LOCAL_TIME`, Europe/Madrid, an off-peak hour outside the slow hours of [s019 › Not verified](spikes/s019-pipeline-run-time-r2-reads.md#54-not-verified). Each task acts on the table's state, not on the date, so the next day does what a missed one left.
