# d009: baselines from production data

Question: what do weeks of production captures and runs show for the values the monitoring design sets from them? Each check is evidence for one decision of [d009](../../docs/designs/d009-monitoring.md).

## Prerequisites

- Python and dependencies: the pipeline's locked environment, run with `uv run --directory pipeline`.
- `.env` at the repository root with the lakehouse read pair (`LAKEHOUSE_READ_R2_*`, a read-only R2 token on `bikesharing-lakehouse`); checks that read bronze also need the bronze read pair (`BRONZE_R2_*`).

## volume-drop

- **Question:** which threshold, window and minimum of captures should DQR12's volume drop take? Evidence for [d009 › D6](../../docs/designs/d009-monitoring.md#d6-volume-drop-at-95-of-a-7-day-median).
- **Inputs:** `control/processed_objects` of `bikesharing-lakehouse`, one row per bronze object with its `station_count`, the same history the pipeline's `capture_volume` model reads. Nothing is written to R2.
- **What the script does:** `volume_drop.py` recomputes the rule for every `station_status` capture as `capture_volume` does, against the median of the system's captures in the window before it, the capture itself left out. It reports the station count per system and day, the ratio to the median, the captures flagged per threshold (98% to 50%) and per window (24 h and 7 days), each episode of consecutive flagged captures at 95% and 90%, the worst captures, the captures not evaluated per minimum, and the gaps over 1 h.
- **Output:** the report on screen, saved as `out/report-<UTC time>.txt`, in UTC.
- **Commands:**

  ```bash
  uv run --directory pipeline python ../spikes/d009-baselines/volume-drop/volume_drop.py
  uv run --directory pipeline python ../spikes/d009-baselines/volume-drop/volume_drop.py --self-test
  ```

  `--self-test` checks the window logic on synthetic captures.
- **Run time:** under 10 s for 5.5 weeks of captures.

## indicator-targets

- **Question:** which targets should DQM7, capture completeness, and DQM10, the age of the data the page serves, keep? Evidence for [d009 › D7](../../docs/designs/d009-monitoring.md#d7-capture-completeness-target-per-system) and [D8](../../docs/designs/d009-monitoring.md#d8-page-data-age-keeps-its-target).
- **Inputs:** read from R2, nothing written to it:
  - `control/processed_objects` of `bikesharing-lakehouse`: the `station_status` captures in the station stock, with the `run_id` of the run that processed each;
  - capture's pass logs, `logs/date=<YYYY-MM-DD>/<run_id>.jsonl` of `bikesharing-bronze`, one per pass;
  - the pipeline's run logs, `logs/pipeline/date=<YYYY-MM-DD>/<run_id>.jsonl` of `bikesharing-lakehouse`, kept for 30 days.
- **What the script does:** `indicator_targets.py`:
  - **DQM7:** for each system, every UTC minute from its first to its last processed capture, marked captured or not, a minute of two captures counted once. It reports the share of captured minutes per system and month against 99.5%, and the worst days. Each missed minute gets the cause its pass logged: the failure events of that minute (`feed_failed` of `station_status` or `index_rejected`, with status and error type), a capture logged but not processed, a pass with no `station_status` event, or no pass logged. Causes are ranked by missed minutes.
  - **DQM10:** for each `page_deployed`, its time minus each system's latest capture processed by the runs up to the deploying one, runs ordered by the time in their UUIDv7 `run_id`, and the oldest age a visitor meets, just before the next deployment. Steady state starts at the first deployment whose data is under 30 min old, after the runs that catch up on earlier captures. It reports the page's age (the older system) in steady state, the same ages from the latest capture instant `file_built` logs (`data_instant`) with their difference to the derived ones, together with the runs' outcome, `duration_s`, `peak_memory_mb` and the interval between runs, against one cadence plus one run.
  - Captures copied from V4 have no pass logs ([d004 › D2](../../docs/designs/d004-bronze-data-capture.md#d2-spike-data-moved-to-production)): their missed minutes show the cause `before capture logs`.
- **Output:** the report on screen, saved as `out/report-<UTC time>.txt`, in UTC.
- **Commands:**

  ```bash
  uv run --directory pipeline python ../spikes/d009-baselines/indicator-targets/indicator_targets.py
  uv run --directory pipeline python ../spikes/d009-baselines/indicator-targets/indicator_targets.py --self-test
  ```

  `--self-test` checks the minute count, the cause given to each missed minute and the UUIDv7 time on synthetic rows.
- **Run time:** about 5 min for two weeks of capture's logs, about 20 s per day, with progress per day.

## capture-gaps

- **Question:** which target should DQM11, the minutes with no capture of each feed split by cause, take? Evidence for [d009 › D9](../../docs/designs/d009-monitoring.md#d9-a-missed-minutes-cause-goes-to-whoever-can-act-on-it) and [D10](../../docs/designs/d009-monitoring.md#d10-a-target-on-captures-own-missed-minutes-only).
- **Inputs:** capture's pass logs, `logs/date=<YYYY-MM-DD>/<run_id>.jsonl` of `bikesharing-bronze`, from 2026-11-07, the first production pass; captures copied from V4 have no pass logs ([d004 › D2](../../docs/designs/d004-bronze-data-capture.md#d2-spike-data-moved-to-production)). Nothing is written to R2.
- **What the script does:** `capture_gaps.py` takes every UTC minute from the first to the last pass logged, for each dynamic feed of each source (`station_status` of both, `free_bike_status` of AMBici). A minute is captured when its pass logged `feed_captured` for the feed. Each missed minute gets its cause and its class by D9: provider for an HTTP error or a timeout on the feed (`feed_failed`) or its index (`index_rejected`); capture for a write failure, a pass with no event for the feed, or no pass logged; unclassified for any other error type, so a new one shows. It reports, per source, feed and class, the missed minutes per month, per day (median and worst) and per run of consecutive minutes.
- **Output:** the report on screen, saved as `out/report-<UTC time>.txt`, in UTC.
- **Commands:**

  ```bash
  uv run --directory pipeline python ../spikes/d009-baselines/capture-gaps/capture_gaps.py
  uv run --directory pipeline python ../spikes/d009-baselines/capture-gaps/capture_gaps.py --self-test
  ```

  `--self-test` checks the class given to each cause on synthetic events.
- **Run time:** about 5 min, about 20 s per day of logs, with progress per day.

## discovery

- **Question:** which alerts beyond the first pass of [d009 › D3](../../docs/designs/d009-monitoring.md#d3-alerts-on-symptoms-that-need-action) do the production events of capture and the pipeline call for? The inventory also lists the events, levels and fields of the observability catalog ([d009 › D5](../../docs/designs/d009-monitoring.md#d5-one-observability-catalog-built-here)).
- **Inputs:** read from R2, nothing written to it, each event read as a whole JSON object so that an unknown event or field shows:
  - capture's pass logs, `logs/date=<YYYY-MM-DD>/<run_id>.jsonl` of `bikesharing-bronze`, from 2026-11-07, the first production pass;
  - the pipeline's run logs, `logs/pipeline/date=<YYYY-MM-DD>/<run_id>.jsonl` of `bikesharing-lakehouse`, kept for 30 days.
- **What the script does:** `discovery.py` reports, per component and event:
  - the inventory: level, events, runs, days seen, first and last;
  - the fields each event carries, with how many of its events carry each;
  - the values of each field with at most 12 distinct values, with their counts, leaving out `ts` and `run_id`;
  - for every event not at level `info`, its count per day, days with none included: median, worst day and the days seen.
- **Output:** the report on screen, saved as `out/report-<UTC time>.txt`, in UTC.
- **Commands:**

  ```bash
  uv run --directory pipeline python ../spikes/d009-baselines/discovery/discovery.py
  uv run --directory pipeline python ../spikes/d009-baselines/discovery/discovery.py --self-test
  ```

  `--self-test` checks the field and value listing on synthetic events.
- **Run time:** about 5 min, about 20 s per day of capture's logs, with progress per day.
