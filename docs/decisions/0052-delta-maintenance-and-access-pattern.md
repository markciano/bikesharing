---
status: Accepted
date: 2026-11-26
---

# Delta maintenance and access pattern for the pipeline's tables

## Context and problem statement

The pipeline keeps its silver tables and its control table in Delta on R2 ([ADR-0022](0022-delta-lake-for-silver-and-gold.md)). The control table records which bronze objects have been processed ([ADR-0045](0045-catch-up-in-bounded-batches.md)). Scheduled runs come every 15 minutes, so each table gains about 96 commits a day, and each batch adds at least one small data file. Opening a table replays its log from the last checkpoint. Reading a table costs requests per data file, whatever the file's size. R2 bills each request, and each request pays the network's round trip.

When nothing bounds what a run reads, a run's reads grow with everything processed so far. A run then gets slower and more expensive every day, and so does each batch of a catch-up. [s019](../spikes/s019-pipeline-run-time-r2-reads.md) measured this in production: about 12,000 GetObject per run, growing by about 1,500 a day. About 90% of them came from reading the control table in full, several times per run, while it gained one file per run and was never compacted.

Two forces constrain the answer:

- A run's MERGE rewrites files, so a compaction running at the same time conflicts with it.
- A catch-up writes many batches in a row, so files accumulate faster than in steady runs.

## Considered Options

### 1. Bounded access and maintenance inside the run

Each table is laid out and maintained for how it is read:

- it is opened once per run;
- it is partitioned by the range its readers filter by;
- each read and MERGE states that range;
- it is compacted inside the run without merging files within a range a reader prunes by;
- it is vacuumed within its history.

- Pros:
  - A run reads only what its window needs, so neither its requests nor its bytes grow with the history.
  - Maintenance follows the writes: a catch-up compacts as often as it writes, and nothing runs alongside the MERGE.
- Cons:
  - Each table needs its own partitioning, ranges and threshold, chosen from its readers.
  - Compaction adds time to the runs that trigger it.

### 2. Keep the current access

Every call opens its table, and reads the whole table where its query cannot be pruned. Nothing is compacted.

- Pros:
  - No change.
- Cons:
  - Reads, cost and run time grow with every run, with no limit.

### 3. Maintenance as a job apart from the run

A scheduled job compacts and vacuums the tables, for example once a day. The runs read as they do today.

- Pros:
  - The runs keep their code; maintenance lives in one place.
- Cons:
  - The job conflicts with a run's MERGE when both run at once.
  - Between two jobs, a catch-up accumulates files with no compaction.
  - Full reads still grow with the history, only more slowly.

### 4. No partitions, one compacted file

The control table is compacted into a single file whenever it reaches a threshold of small files, and read in full as today.

- Pros:
  - Few requests per read, and no partitioning to design.
- Cons:
  - Each read takes the whole history, so the bytes read and the memory grow without limit.
  - A system's latest capture still needs a full read.

## Decision Outcome

**Chosen option:** 1. Bounded access and maintenance inside the run

A run never starts while another is running ([ADR-0045](0045-catch-up-in-bounded-batches.md)), so a table opened once at the start stays valid across the run's calls, and is refreshed after its own writes. A table is partitioned by the range its readers filter by, such as a capture date. Each read and each MERGE states that range, so the engine skips other partitions and other files by their statistics in the log. A MERGE states the range explicitly when its join key alone does not narrow it, as when one batch's keys span several sources. A value that file statistics already hold, such as a source's latest capture, is read from the log, not from the data.

Compaction runs inside the run, after a batch that leaves a partition over a threshold of small files. It never merges files within the range a reader prunes by:

- A partition that its readers read whole is compacted by threshold.
- An active partition that a reader prunes within is left alone until it closes.
- Every closed partition is compacted once.

Every table is vacuumed within its history ([ADR-0021](0021-retention-per-layer.md)).

Rationale: the cost that grows is the number of files and commits a run touches, not the data it needs. This option is the only one that ties what a run reads to its own window, in steady runs and in each batch of a catch-up. Running maintenance inside the run removes the conflict with the MERGE, and makes compaction keep pace with the writes. Compacting only where no reader prunes keeps the pruning that bounds the reads.

Why not the others:

- Option 2 lets every run cost more than the one before.
- Option 3 conflicts with the MERGE and leaves a catch-up uncompacted.
- Option 4 bounds the requests but not the bytes: a run still reads the whole history.

**Scope:** every Delta table the pipeline writes and reads in its runs, silver and control, and gold when it becomes a Delta table. It does not cover bronze, which is plain objects ([ADR-0020](0020-bronze-as-captured-objects.md)), nor the retention periods themselves, set by [ADR-0021](0021-retention-per-layer.md).

### Consequences

#### Positive

- **Bounded runs:** a run's requests and bytes depend on its window, not on the history; a catch-up's cost per batch stays flat.
- **No second job:** maintenance needs no scheduler, and no lock against the runs.
- **One rule for every table:** a new table applies the same pattern, from how its readers filter.

#### Negative

- **Design per table:** each new table must name its readers' ranges, its partitioning and its compaction threshold. A wrong choice brings back full reads.
- **Uneven runs:** a run that compacts takes longer than one that does not.
- **Ranges in every call:** a read or MERGE that omits its range reads the whole table, silently. Only the request counts show it.

## More information

- [s019 › Verdict and Production inputs](../spikes/s019-pipeline-run-time-r2-reads.md#53-verdict): the measurements, the arithmetic of the effect, and how each table applies the pattern.
- Mechanisms at the time of writing, which may change with the library:
  - `deltalake` 1.7.0's streamed MERGE prunes target files with the source's statistics;
  - `optimize.compact` keeps file order;
  - scans prune whole files by partition values and log statistics;
  - `delta.checkpointInterval` is set per table ([s019 › Sources](../spikes/s019-pipeline-run-time-r2-reads.md#6-sources)).
