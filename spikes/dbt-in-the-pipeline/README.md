# dbt in the pipeline

Does dbt fit the pipeline as the layer that builds and audits its SQL, with Python planning the batch and publishing it to Delta, and with its glue below the friction thresholds of the spike? Report, findings and verdict: [s017](../../docs/spikes/s017-dbt-in-the-pipeline.md).

## Prerequisites

- **uv 0.13.5**, which installs Python 3.13. Locked versions ([s017 › F1](../../docs/spikes/s017-dbt-in-the-pipeline.md#4-findings)): `dbt-core` 1.12.7, `dbt-duckdb` 1.11.1, DuckDB 2.0.0, `deltalake` 1.6.6.
- **An R2 API token with Object Read only,** scoped to the bronze bucket; nothing is written to R2.
- **One complete hour of bronze station status,** under `raw/<source>/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz`. The runs used bucket `bikesharing-bronze`, `bicing` / `station_status`, 2026-11-16, 10 UTC: 60 objects.

## Setup

Every command runs from this folder.

```bash
uv sync
cp .env.example .env   # fill R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT, R2_BUCKET
mkdir out              # dbt-duckdb does not create its database's folder (F2)
```

Below, `<vars>` is the window:

```text
--vars '{"source": "bicing", "feed": "station_status", "date": "2026-11-16", "hour": "10"}'
```

`dbt_project/` is the one dbt project of the three checks: `profiles.yml` points `dbt-duckdb` at `out/scratch.duckdb`, with `httpfs` and an S3 secret for R2 built from `.env`.

## A. Build on DuckDB 2.0

Evidence for D1 and D2: do `dbt-core` 1.12 and `dbt-duckdb` 1.11 build, on DuckDB 2.0 and with no patch, a model that reads only the bronze objects of a window passed through `var()`, with an enforced contract, a runtime rule as a test with its severity, and a quarantine model?

- **Input:** the hour of bronze, read from R2.
- **Models** (`dbt_project/models/staging/`):
  - `base_probe_read.sql` reads the window's objects with `read_json` on a path built from `var()`, unnests the stations and keeps their fields uncast, with the capture time and object key.
  - `stg_probe.sql` keeps the rows whose required fields cast to non-null values; `stg_probe_quarantine.sql` keeps the rest, with the first field that failed.
  - `stg_probe.yml` sets the enforced contract of `stg_probe`, `not_null` on `station_id` with severity `error`, and `accepted_values` on `is_renting` with severity `warn`, its values from the var `accepted`.

```bash
uv run --env-file .env dbt build --project-dir dbt_project --profiles-dir dbt_project <vars>
# The warn rule failing: is_renting accepts only true
uv run --env-file .env dbt build --project-dir dbt_project --profiles-dir dbt_project --vars '{"source": "bicing", "feed": "station_status", "date": "2026-11-16", "hour": "10", "accepted": [true]}'
uv run --env-file .env dbt show --project-dir dbt_project --profiles-dir dbt_project <vars> --inline "select (select count(*) from {{ ref('stg_probe') }}) as rows, (select count(*) from {{ ref('stg_probe_quarantine') }}) as quarantined"
```

- **Output:** the first build ends `PASS=5 WARN=0 ERROR=0`; 60 objects and 32,700 rows read, all in `stg_probe` and none in quarantine. The second ends `PASS=4 WARN=1 ERROR=0` and the build still succeeds. The DDL in `dbt_project/target/run/` lists each column with its contract type and `not null` (F3–F6).
- **Run time:** about 2–3 s per build.

## B. Shell glue

Evidence for D1 and D4: does a Python shell invoke the build through `dbtRunner`, read each node's result as values, record dbt's events in a callback and MERGE the scratch table into Delta as Arrow, and what does dbt add to a run's time and memory?

- **Input:** the hour of bronze, read from R2; A's dbt project.
- **Script:** `shell_glue/run_batch.py`.
  - `--mode dbt` runs `dbt build` through `dbtRunner`, writes every event the callback receives to `out/events.jsonl` and prints each node's status, failures, rows affected and execution time as JSON.
  - `--mode baseline` runs, with no dbt, the SQL that `dbt compile` wrote to `dbt_project/target/compiled/`, in a fresh `out/baseline.duckdb`, and counts each data test's rows.
  - Both modes then MERGE `stg_probe` into the local Delta table `out/delta/stg_probe`, on station and capture time, and print its row count.
  - It imports from dbt only `dbt.cli.main`. Its size for the guide is 71 lines of code, without blank lines, comments and `--mode baseline`.

```bash
uv run --env-file .env dbt compile --project-dir dbt_project --profiles-dir dbt_project <vars>
# Three times each mode, to take the median
uv run --env-file .env /usr/bin/time -l python shell_glue/run_batch.py --mode dbt --source bicing --feed station_status --date 2026-11-16 --hour 10
uv run --env-file .env /usr/bin/time -l python shell_glue/run_batch.py --mode baseline --source bicing --feed station_status --date 2026-11-16 --hour 10
# Once, with the warn rule failing
uv run --env-file .env /usr/bin/time -l python shell_glue/run_batch.py --mode dbt --source bicing --feed station_status --date 2026-11-16 --hour 10 --accepted true
grep -nE "^(from|import) dbt" shell_glue/run_batch.py
```

- **Output:** every node appears with its status and failures; with `--accepted true`, `accepted_values` returns `warn` with 1 failure. `delta_rows` is 32,700 after every run. `out/events.jsonl` holds `NodeStart` and `NodeFinished` per node, and `LogModelResult` and `LogTestResult`; dbt-duckdb reports no rows affected (F7–F11).
- **Cost of dbt, median of three:** +0.95 s of real time and +36.4 MB of maximum resident set size against the baseline (F12).
- **Run time:** about 2–3 s per run.

## C. Unit tests

Evidence for D3: do dbt unit tests run on `dbt-duckdb`, passing and failing as written, and how long does the suite take locally?

- **Input:** no bronze. The mocked rows of `base_probe_read` take its column types from `out/scratch.duckdb`, so A's build runs first.
- **Tests:** `dbt_project/models/staging/stg_probe_unit.yml`.
  - `stg_probe_keeps_valid_rows_typed` passes two valid stations through `stg_probe`.
  - `stg_probe_quarantine_keeps_malformed_row_with_failed_field` sends a station with no docks count to quarantine.
  - `stg_probe_fails_on_purpose_wrong_vehicle_count` expects a wrong vehicle count, so it fails.

```bash
uv run --env-file .env /usr/bin/time -l dbt test --select test_type:unit --project-dir dbt_project --profiles-dir dbt_project <vars>
```

- **Output:** `PASS=2 WARN=0 ERROR=1 ... TOTAL=3`; the failure shows the diff of the failing value as expected→actual (`6→5`) and the path of the test's compiled SQL (F13).
- **Run time:** about 1.5 s, dbt's start-up included (F14).
