# Run time and R2 reads of the pipeline's scheduled runs

Why do the pipeline's scheduled runs get slower every day, and why do they read so many objects from R2? The first measurements, taken in T060.1's close, are the baseline of T077 and are recorded in [d008 › Close](../../docs/designs/d008-pipeline-platform-and-walking-skeleton.md#4-close): the run time, memory and platform's review in Implemented, and the run time's growth in Known gaps.

## Prerequisites

- **Window:** d008's cost window (DI15), from 03:00 UTC on 2026-11-21 to 03:00 UTC on 2026-11-23, set as constants in each script. Another window means changing `START`, `END` and `DAYS`.
- **Input data:** the runs' log objects, `bikesharing-lakehouse/logs/pipeline/date=YYYY-MM-DD/<run_id>.jsonl`, which a lifecycle rule deletes after 30 days (d008 › Observability); and Cloudflare's GraphQL Analytics API.
- **Credentials:**
  - `LAKEHOUSE_READ_R2_ACCESS_KEY_ID` and `LAKEHOUSE_READ_R2_SECRET_ACCESS_KEY` in `.env` at the repository root: a read-only R2 token on `bikesharing-lakehouse` (d008 › DI14).
  - `CF_ANALYTICS_API_TOKEN` in the shell's environment: a Cloudflare token with Account Analytics: Read only, loaded without echo or history with `read -s "CF_ANALYTICS_API_TOKEN?Token: " && export CF_ANALYTICS_API_TOKEN`.
- **Python and dependencies:** the pipeline's locked environment, run with `uv run --directory pipeline` from the repository root, so the commands below take paths relative to `pipeline/`.
- **Side effects:** every script only reads and prints aggregates; none writes to R2 or to disk, or prints a credential or a log line. The three log scripts make about 200 GetObject requests to `bikesharing-lakehouse` each, and none to `bikesharing-bronze`.

## Run time and memory

- **Question:** do the scheduled runs reach the thresholds that reopen ADR-0027: runs of 1 min or less, or normal runs of 2 GB or less ([d007 › Carried-over inputs](../../docs/designs/d007-pipeline-design.md#carried-over-inputs))?
- **Script:** `run-time-and-memory/run_stats.py` keeps the runs started in the window and prints their count, outcomes and versions, and the maximum, p95, median and minimum of `duration_s` and `peak_memory_mb` from `run_finished`, for all runs, the full sweeps and the incremental ones, with the five slowest.
- **Command:**

  ```bash
  uv run --directory pipeline python ../spikes/t077-run-time-and-r2-reads/run-time-and-memory/run_stats.py
  ```

- **Output (2026-11-23):** 192 runs, all `succeeded` on `df7225d`; `duration_s` median 128.5, p95 234.8, maximum 341.3; `peak_memory_mb` median 1,395, p95 1,558, maximum 2,428, the high-water mark of the container shared with the last run of stage 3.
- **Run time:** not recorded; the script prints it at the end.

## Time per phase

- **Question:** where does a run spend its time, and which phases grow over the window?
- **Script:** `time-per-phase/run_phases.py` derives each phase of a run from the timestamps of the events that open and close it (discovery, the wait before the first batch, batch work split into dbt's nodes and the rest, the gold file, the page's deployment, the tail) and prints the mean, median and p95 of each, the mean over the window's first and last 12 h, and the dbt nodes with the most time.
- **Command:**

  ```bash
  uv run --directory pipeline python ../spikes/t077-run-time-and-r2-reads/time-per-phase/run_phases.py
  ```

- **Output (2026-11-23):** of a mean run of 130.7 s, batch work outside dbt's nodes takes 66.3 s, discovery 37.2 s, the gold file 17.7 s, the page's deployment 8.0 s and dbt's nodes 1.0 s. From the first to the last 12 h, batch work grows from 44.4 to 84.8 s and the whole run from 105.9 to 158.0 s; the page's deployment stays at 7.8 s.
- **Run time:** not recorded; the script prints it at the end.

## Phases by hour

- **Question:** does the growth follow the day's partition, dropping at local midnight, or a factor common to the run?
- **Script:** `phases-by-hour/run_by_hour.py` takes discovery, batch work outside dbt's nodes and the gold file of each run, as in the previous check, and prints their mean per local date and hour (Europe/Madrid).
- **Command:**

  ```bash
  uv run --directory pipeline python ../spikes/t077-run-time-and-r2-reads/phases-by-hour/run_by_hour.py
  ```

- **Output (2026-11-23):** no drop at local midnight. The three phases rise and fall together hour by hour, up to twice as slow from 16:00 to 23:00, and rise from one early morning to the next.
- **Run time:** not recorded; the script prints it at the end.

## R2 operations and storage

- **Question:** how many operations of each type do the runs make on each bucket, and how fast does each bucket's storage grow?
- **Script:** `r2-operations-and-storage/r2_metrics.py` queries `r2OperationsAdaptiveGroups`, the query of [s010 › Step 5](../../docs/spikes/s010-storage-table-format.md#step-5--run-probe-a-and-verify-the-analysis), per action type and status, and `r2StorageAdaptiveGroups` at the window's first and last sample, for `bikesharing-bronze` and `bikesharing-lakehouse`. The operation metrics are sampled, so only totals compare ([s010 › F14](../../docs/spikes/s010-storage-table-format.md#4-findings)).
- **Command:**

  ```bash
  uv run --directory pipeline python ../spikes/t077-run-time-and-r2-reads/r2-operations-and-storage/r2_metrics.py
  ```

- **Output (2026-11-23):**

  | Bucket | GetObject | PutObject | ListObjects | Objects, first → last | Payload, first → last |
  |---|---|---|---|---|---|
  | `bikesharing-bronze` | 161,760 | 12,420 | 1,040 | 190,693 → 202,302 | 3.618 → 3.810 GB |
  | `bikesharing-lakehouse` | 1,263,034 | 993 | 3,783 | 1,290 → 2,253 | 0.187 → 0.202 GB |

  The query groups conditional PutObject with PutObject and reports ListObjectsV2 as ListObjects; no DeleteObjects ran in the window.
- **Run time:** not recorded; the script prints it at the end.
