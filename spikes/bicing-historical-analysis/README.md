# Bicing historical analysis (T005)

Throwaway analysis of the Bicing monthly archives of Open Data BCN (`ESTACIONS` = status, `INFORMACIO` = information), February to June and August 2026. One script implements the metrics of the [Analysis plan](../../docs/spikes/s004-bicing-historical-data.md#analysis-plan) and writes the evidence the spike report cites. The plan is the source of truth: the script makes no analysis decisions of its own, and any deviation is reported, not decided.

Status: `analyse_bicing_historical.py` implements the whole plan: common settings (extraction and conversion to Parquet, typed view, month window, duplicates), Verification › reconciliation (CSV vs Parquet rows, rows per snapshot before and after deduplication, rows dropped by deduplication), the 3b, 5b and 6d hand-checkable examples, metrics 1a–1c, the 2a input (`field_comparison.csv`), 3a–3d, 5b, 5c, 6a–6d, 7a, 7b and 8a–8j, and the `--only` option.

## Setup

Python 3.14.4 was used. From the repository root:

```sh
python3 -m venv spikes/bicing-historical-analysis/venv
source spikes/bicing-historical-analysis/venv/bin/activate
pip install -r spikes/bicing-historical-analysis/requirements.txt
```

`venv/` is ignored by Git. Extraction uses the macOS built-in `tar` (bsdtar/libarchive), which reads `.7z`; no `7z` binary is needed.

## Run

From the repository root, with the venv active:

```sh
python spikes/bicing-historical-analysis/analyse_bicing_historical.py
```

A run without `--only` rebuilds `work/` from the `.7z` archives, one month at a time (extract the CSV, convert it to Parquet with every column as text, delete the CSV), and then runs every metric. The CSV facts later metrics need (bytes, data rows, header line, inferred types) are stored in each Parquet file's key-value metadata.

Optional `--only <metric ids>` (for example `--only 1b,3a`) runs just those metrics over the Parquet files already in `work/`, for the review loop in the plan (run the planned metrics, review, then run only the added checks).

### How `--only` updates the evidence

The pattern is marked generated regions in Markdown, as used by terraform-docs, markdown-magic and cog.

- **Safe use:** `--only` is only for new blocks (checks added after first look) or for metrics whose code and dependencies have not changed. If shared code or a dependency changes, run the full script. The evidence the report cites always comes from one full run ([Analysis plan › Review loop](../../docs/spikes/s004-bicing-historical-data.md#common-settings), step 4).
- **`summary.md`:** every block is wrapped in invisible markers, `<!-- BEGIN metric:<id> -->` … `<!-- END metric:<id> -->`. With `--only`, the script replaces only the text between the markers of the metrics run; every other byte of the file stays as it is. Some metrics also own Verification blocks: 3a owns `3a.check` (snapshot reconciliation and month window), 3b owns `3b.example`, 5b owns `5b.example`, 6d owns `6d.example`; every metric that reads the deduplicated view (3a, 3b, 3c, 6a–6d, 8a–8j) rewrites `dedup.check`. `load` (CSV vs Parquet reconciliation) is written by full runs only, since only they extract the CSVs. A block not yet in the file (a check added after first look) is inserted after the nearest preceding block in the script's fixed order. A run without `--only` rewrites the whole file.
- **CSV files:** each has one owner and is rewritten only when that metric runs; otherwise it is not touched. `quality_cases.csv` is shared by the quality checks: it has a `check` column, and `--only` replaces only the rows whose `check` is one of the checks run, keeps the other rows as they are and keeps the file ordered by check. A run without `--only` rewrites it.

  | File | Owner |
  |---|---|
  | `header_check.csv` | 1a and 1c (either rewrites it) |
  | `field_profile.csv` | 1b |
  | `field_comparison.csv` | 2a (input) |
  | `snapshots.csv` | 3a |
  | `station_reporting.csv` | 3b |
  | `gaps.csv` | 5b |
  | `station_changes.csv` | 6c |
  | `station_match.csv` | 6d |
  | `quality_cases.csv` | 8a–8j (and any quality check added later), each owning the rows with its id in the `check` column |

- **Dependencies** are computed but not written: 3a, 3b, 5b, 5c and 7b read the snapshot times; 3b also takes the 5b threshold of each month; every metric in the deduplicated list above builds the deduplicated view; 6b and 8a read the `INFORMACIO` snapshots of every month (8a for the as-of `capacity`).
- **Errors, before anything is written:** an unknown id; a missing `summary.md` (run without `--only` first); a Parquet file missing from `work/`, or one without the stored CSV facts (run without `--only` first).

Metric ids implemented: 1a, 1b, 1c, 2a, 3a–3d, 5b, 5c, 6a–6d, 7a, 7b, 8a–8j.

## Inputs

| Input | Where | In Git |
|---|---|---|
| Monthly archives, one per month and series | `spikes/bicing-spike/historical-data/raw/2026_MM_<month name>_BicingNou_{ESTACIONS,INFORMACIO}.7z` | No (ADR-0009) |
| Real-time field profile (2a input) | `spikes/bicing-spike/analysis/field_profile.csv` | Yes |
| Last real-time `station_information` response of 2026-10-05 (6d) | `spikes/bicing-spike/realtime/raw/station_information/2026-10-05/<YYYYMMDDTHHMMSSZ>.json.gz` | No |

Working files: one Parquet file per month and series in `spikes/bicing-spike/historical-data/work/` (ignored by Git; rebuilt by every full run). The `.7z` archives are never modified (ADR-0006).

## Outputs

Written to `spikes/bicing-spike/historical-data/analysis/` and committed (small derived files): `summary.md`, `header_check.csv`, `field_profile.csv`, `field_comparison.csv`, `snapshots.csv`, `station_reporting.csv`, `gaps.csv`, `station_match.csv`, `station_changes.csv`, `quality_cases.csv`. `summary.md` ends with implementation notes (Python, duckdb and tar versions; conventions).

## Outline of `analyse_bicing_historical.py`

Configuration at the top: paths, months and series, timestamp and null/boolean tokens, the 3b counts, the real-time reference, the 6d settings and the quality checks with their definitions.

Each month and series is read from its Parquet file with DuckDB SQL; nothing is loaded whole into Python. Metrics over the deduplicated view run month by month (`INFORMACIO` first, so 8a can read the as-of capacity).

| Section | Plan metrics |
|---|---|
| Configuration, helpers and loading (extract, convert, key-value metadata) | Common settings, 7a input |
| Schema: header check, field profile, type stability | 1a, 1b, 1c |
| Snapshots and month window | 3a, Verification › reconciliation |
| Duplicates: the deduplicated typed view | Common settings › Duplicates, Verification › reconciliation |
| Freshness | 3b–3d |
| Coverage | 5b, 5c |
| Relation to the feed: `field_comparison.csv` | 2a input |
| Identity | 6a–6d |
| Quality | 8a–8j |
| Volume and load reconciliation | 7a, 7b, Verification › reconciliation |
| Summary: marked blocks, implementation notes | — |

1d (GBFS version), 2a/2b (field mapping), 5a (missing months) and 5d (range to real time) are done by Chat from the evidence, not by the script.
