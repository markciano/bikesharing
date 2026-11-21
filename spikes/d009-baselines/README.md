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
