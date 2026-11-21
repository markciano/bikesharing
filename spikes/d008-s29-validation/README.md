# d008 Step 29: independent validation of the station stock

Question: does `silver/station_stock`, as the drain writes it, hold what the bronze objects publish?
The runtime rules (DQR1, DQR2, DQR13, DQR14) check structure and counts; this check re-derives the values from bronze with its own code, and is evidence for the production checks of [d008 › Step 29](../../docs/designs/d008-pipeline-platform-and-walking-skeleton.md#step-29--production-rollout).

## Prerequisites

- Python and dependencies: the pipeline's locked environment, run with `uv run --directory pipeline`.
- `.env` at the repository root with the owner's bronze read pair (`BRONZE_R2_*`) and the lakehouse read pair (`LAKEHOUSE_READ_R2_*`, a read-only R2 token on `bikesharing-lakehouse`).

## station-stock-matches-bronze

- **Question:** do the table's counts, values, nulls and local calendar keys match bronze?
- **Inputs:** `silver/station_stock` of `bikesharing-lakehouse`, pinned at its latest Delta version when the run starts, and the `raw/<system>/station_status/` objects of `bikesharing-bronze`. Nothing is written to R2.
- **What the script does:** `validate_station_stock.py` validates the window of captures added since the last run without a failure (the first run, or `--full`, validates everything) with four checks:
  1. Per day and system, bronze's objects and stations against the table's captures and rows, for the first and last day of the window and for 2026-10-25 when inside it (`--all-days` takes every day).
  2. A sample of captures compared station by station on nine fields: 15 random per system, spread over the parts of the day, plus edge cases (stations out of service, zero vehicles, the capture with the fewest stations).
  3. Nulls and ranges over every row of the window, including TR8 and TR9, and the shape of `code_version`.
  4. `local_date` and `local_minute` of every capture against Europe/Madrid, and the DST day, 2026-10-25, once the table has loaded it.
- **Output:** a report on screen, saved as `out/report-<UTC time>.txt`, with one `PASS`, `FAIL` or `SKIP` per check and the details of every failure; `out/requests.log` adds one line per run with its requests to bronze, to subtract from R2's metrics in Do 5. The exit code is 1 if a check failed. The watermark `state.json` moves only after a run with no failure.
- **Commands:**

  ```bash
  uv run --directory pipeline python ../spikes/d008-s29-validation/station-stock-matches-bronze/validate_station_stock.py
  uv run --directory pipeline python ../spikes/d008-s29-validation/station-stock-matches-bronze/validate_station_stock.py --full
  uv run --directory pipeline python ../spikes/d008-s29-validation/station-stock-matches-bronze/validate_station_stock.py --self-test
  ```

  `--seed N` repeats a sample, `--sample N` changes the random captures per system, `--no-save` leaves the watermark, and `--local-lakehouse` with `--local-bronze` run it against local folders.
- **Run time:** seconds to a few minutes. The first run reads the whole table and about 1,440 bronze objects per system and day of check 1 (three days at most); later runs read only what is new.
