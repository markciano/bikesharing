# Realtime capture analysis (T006)

Throwaway analysis of the AMBici and Bicing GBFS captures. One script, configured per system, that implements the metrics of the [Analysis plan](../../docs/spikes/s001-ambici-realtime-capture.md) and writes the evidence the two spike reports cite. The plan is the source of truth: the script makes no analysis decisions of its own, and any deviation is reported, not decided.

Status: `analyse_realtime_capture.py` implements the whole plan (parts 1–3): common settings (configuration, streamed loading, analysis window and grid, responses used, UTC conversion), Verification › reconciliation (including the `gaps.csv` check), the 4b, 5d and 6b hand-checkable examples, metrics 1a, 1b, 1d, 1e, 1f, 2c, 2d, the 2a input (`field_comparison.csv`), 3a–3d, 4a–4c, 5a–5d, 6a–6d, 7a–7c, 8a–8j, 9a–9d and 10a–10b (AMBici only), and the `--only` option.

## Setup

Python 3.14.4 was used. From the repository root:

```sh
python3 -m venv spikes/realtime-capture-analysis/.venv
source spikes/realtime-capture-analysis/.venv/bin/activate
pip install -r spikes/realtime-capture-analysis/requirements.txt
```

`.venv/` is ignored by Git.

## Run

From the repository root:

```sh
python spikes/realtime-capture-analysis/analyse_realtime_capture.py --system ambici|bicing|both
```

Optional `--only <metric ids>` (for example `--only 1d,3a`) runs just those metrics, for the review loop in the plan (run the planned metrics, review, then run only the added checks).

### How `--only` updates the evidence

The pattern is marked generated regions in Markdown, as used by terraform-docs, markdown-magic and cog.

- **Safe use:** `--only` is only for new blocks (checks added after first look) or for metrics whose code and dependencies have not changed. If shared code or a dependency changes, run the full script. The evidence the reports cite always comes from one full run ([Analysis plan › Review loop](../../docs/spikes/s001-ambici-realtime-capture.md#common-settings), step 4).
- **`summary.md`:** every metric section is wrapped in invisible markers, `<!-- BEGIN metric:<id> -->` … `<!-- END metric:<id> -->`. With `--only`, the script replaces only the text between the markers of the metrics run; every other byte of the file stays as it is, header and reconciliation included. Some metrics also own Verification blocks: 5d owns `5d.check` (the `gaps.csv` check) and `5d.example`, 4b owns `4b.example`, 6b owns `6b.example` (hand-checkable examples). A block not yet in the file (a check added after first look) is inserted after the nearest preceding block in the script's fixed order. A run without `--only` rewrites the whole file.
- **CSV files:** each has one owner and is rewritten only when that metric runs; otherwise it is not touched. `quality_cases.csv` is shared by the quality checks: it has a `check` column, and `--only` replaces only the rows whose `check` is one of the checks run, keeps the other rows as they are and keeps the file ordered by check. A run without `--only` rewrites it.

  | File | Owner |
  |---|---|
  | `field_profile.csv` | 1d |
  | `schema_changes.csv` | 1e |
  | `schema_violations.csv` | 1f |
  | `field_comparison.csv` | 2a (input) |
  | `content_changes.csv` | 3a |
  | `station_reporting.csv` | 3b |
  | `gaps.csv` | 5d |
  | `quality_cases.csv` | 8a–8j (and any quality check added later), each owning the rows with its id in the `check` column |

- **Dependencies** are computed but not written: `--only 3d` computes 3a (and the ttl values of 3c) internally and writes only the 3d block; 7c does the same with 7a; 6d uses the 2c ID set and 9a the 1d profile without writing them.
- **Errors, before anything is written:** an unknown id; a missing `summary.md` (run without `--only` first); a metric that needs both systems (2a input, 2c, 2d, 5d, 7c) without `--system both`; a metric that does not apply to the system chosen (9a–9d, 10a, 10b with `--system bicing`). With `--system both`, those AMBici-only metrics run for AMBici and Bicing is left untouched.

Metric ids implemented: 1a, 1b, 1d, 1e, 1f, 2a, 2c, 2d, 3a–3d, 4a–4c, 5a–5d, 6a–6d, 7a–7c, 8a–8j, 9a–9d, 10a, 10b.

## Inputs

| Input | Where | In Git |
|---|---|---|
| AMBici raw responses | `spikes/ambici-spike/raw/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz` | No |
| AMBici language copies | `spikes/ambici-spike/languages/<ca,es>/<feed>_<YYYYMMDDTHHMMSSZ>.json.gz` | No |
| AMBici request log | `spikes/ambici-spike/log/requests_<YYYY-MM-DD>.jsonl` | No |
| Bicing raw responses | `spikes/bicing-spike/realtime/raw/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz` | No |
| Bicing request log | `spikes/bicing-spike/realtime/log/requests_<YYYY-MM-DD>.jsonl` | No |
| Mac sleep/wake and `caffeinate` lines (plan 5d) | `inputs/pmset-sleep-wake-2026-10-03-to-2026-10-05.txt` | Yes |
| Official GBFS JSON Schemas (plan 1f) | `schemas/v2.3/`, `schemas/v3.0/`, pinned in `schemas/SOURCE.md` | Yes |

## Outputs

Written to `spikes/<system>-spike/analysis/` and committed (small derived files): `summary.md`, `field_profile.csv`, `schema_changes.csv`, `schema_violations.csv`, `content_changes.csv`, `station_reporting.csv`, `gaps.csv`, `quality_cases.csv`. Bicing also gets `field_comparison.csv`. The pinned schema commit is recorded in `summary.md` and `schema_violations.csv`.

## Outline of `analyse_realtime_capture.py`

Per-system configuration (one dict per system): paths of raw data, log and output; GBFS version; dynamic and static feeds; timestamp parser (epoch seconds for AMBici, RFC 3339 for Bicing); field names that differ between 2.3 and 3.0; which metrics apply (9 and 10 AMBici only).

Responses are streamed one at a time, never all loaded in memory. Metrics computed from the request log alone (5a–5d, 7a–7c) do not stream responses.

| Section | Plan metrics |
|---|---|
| Configuration and loading (log, responses) | all |
| Analysis window (common to both systems) | Common settings |
| Schema: feeds, versions, field profile, stability, compliance | 1a, 1b, 1d, 1e, 1f |
| Common model: ID collisions, feeds without equivalent, `field_comparison.csv` | 2c, 2d (input for 2a) |
| Freshness | 3a–3d |
| Sampling | 4a–4c |
| Reliability | 5a–5d |
| Identity | 6a–6d |
| Volume | 7a–7c |
| Quality | 8a–8j |
| `free_bike_status` (AMBici) | 9a–9d |
| Languages (AMBici) | 10a, 10b |
| Verification: reconciliation and hand-checkable examples | Verification |

1c (versions offered) and 2a/2b (field mapping) are done by Chat from the evidence, not by the script.

## Licence note

The files in `schemas/` come from MobilityData/gbfs-json-schema under the Apache License 2.0; the licence text is in `schemas/LICENSE`.
