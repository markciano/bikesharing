# Storage and table format spike (s010)

Question: does the own lakehouse on R2 with Delta Lake (D1–D7) hold within the project's €10/month budget (d002 R4) and R2's quotas?

Report: [s010-storage-table-format.md](../../docs/spikes/s010-storage-table-format.md)

## Setup

```bash
uv sync --locked
cp .env.example .env
```

Fill `.env` (ignored by Git). Usual local values:

| Variable | Value |
|---|---|
| `R2_ACCOUNT_ID` | Cloudflare account ID |
| `R2_TEST_BUCKET` | Name of the scoped test bucket (created by the owner) |
| `R2_TEST_ACCESS_KEY_ID`, `R2_TEST_SECRET_ACCESS_KEY` | Token scoped to the test bucket only |
| `R2_PROD_BUCKET` | Name of the production bucket, used only to check the token cannot reach it |
| `R2_LOCKED_PREFIX` | Prefix covered by the test lock rule |
| `CF_ANALYTICS_API_TOKEN` | Token with Account Analytics Read only, for the R2 metrics query of step 7 |
| `PROXY_URL` | `http://127.0.0.1:8080` |
| `PROXY_CA_CERT` | `~/.mitmproxy/mitmproxy-ca-cert.pem` |

## Python version

`.python-version` pins `3.13.17`; `requires-python` is `>=3.13`.

The step 1 did not define the version. `3.13.17` was kept because it passed the step 1 Check and was the latest 3.13 patch available in uv. The production Python is not fixed yet: T036 decides it, and the spike's results (operations per commit, bytes per row, costs) do not depend on it. To change it, edit only `.python-version`, run `uv lock` if `requires-python` moves, and re-run `uv sync --locked`.

## Commands

### `delta_probe.py gate` — D4 hard cut (step 2)

```bash
uv run python delta_probe.py gate           # against R2, with the test token from .env
uv run python delta_probe.py gate --local   # against a temporary local table, no request to R2
```

Writes `station_status` rows of both providers from the local capture copy (`../cloudflare-capture-spike/data/V4/raw/`) to a fresh table, `s3://<R2_TEST_BUCKET>/<run_id>/station_status`, with `run_id` the run's UTC start time. Requests go directly to R2, without the proxy. Checks, in order; the run stops at the first failure:

- `write`: 10 append commits, one per captured minute, each from a fresh table handle.
- `merge`: 3 MERGE commits (upsert on `source`, `station_id`, `last_reported`).
- `concurrent`: two stale MERGEs on the same partition, then two stale appends. A stale MERGE that raises a conflict is retried once on a fresh handle. Both pairs are compared with a serial run of the same commits.

Appends write only keys not yet seen in the window; MERGEs take each minute's full rows (s010 decision log #32). Options: `--day` (default: the first full captured day), `--start` (UTC `HH:MM`, default `00:00`), `--minutes` (default and minimum 17).

Output: a summary table on the console and one JSON line per check in `output/probe-<run_id>.jsonl` (`output/local/` with `--local`): UTC start and end, result, table version, commit latencies in ms and, for `concurrent`, which outcome each pair had.

### `r2_proxy.py` — request counter (step 4)

```bash
uv run mitmdump -s r2_proxy.py   # listens on 127.0.0.1:8080; the first run creates ~/.mitmproxy/
```

Logs every request to `output/proxy-<UTC start>.jsonl`, one JSON line each: UTC time, host, bucket, key, method, path, query, status, request and response bytes, duration, and the S3 operation with its R2 class (`A`, `B`, `free`, or `unknown` for operations the R2 source card does not name, such as `DeleteObjects`). Only the probe process trusts the mitmproxy CA, through each client's own settings: `proxy_url` and `proxy_ca_certificate` (PEM content) for `deltalake` and Polars, `Config(proxies=...)` and `verify` for `boto3`. DuckDB's delta extension cannot use the proxy (s010 F6).

### `delta_probe.py full` — counted run (step 4)

```bash
uv run python delta_probe.py full           # against R2, through the proxy; prints its run_id
uv run python delta_probe.py full --local   # against a temporary local table, no request to R2
```

Same data and table layout as `gate`, on a window of 74 captured minutes, and a table created with `delta.checkpointInterval = 10`. Every commit opens a fresh table handle. Checks, in order: `write` (60 appends), `merge` (10), `concurrent` (as in `gate`), `optimize` (compaction), `vacuum` (a dry run with the 7-day default, then a run with zero retention). Against R2 it aborts before any request if `PROXY_URL` or `PROXY_CA_CERT` is empty.

Each check's line adds its operation windows (`ops`: each commit, load or vacuum, with its versions, JSON commits loaded, checkpoint, files and bytes added and removed, and, for MERGE, the files in the target partition) and a `measure` window, in which the probe reads the table's `_delta_log` to get Parquet bytes per row, `_delta_log` bytes per commit, checkpoints and bytes rewritten.

### `delta_probe.py extra` — reads, token and lock checks (step 4)

```bash
uv run python delta_probe.py extra --run-id <run_id> --skip duckdb              # counted, through the proxy
uv run python delta_probe.py extra --run-id <run_id> --only duckdb --no-proxy   # uncounted, after the R2 metrics query
```

Runs on the table `full` wrote and appends to its `output/probe-<run_id>.jsonl`. Checks: `polars` and `duckdb` read the table and match its row count; `token` checks that the test token cannot list, read or write `R2_PROD_BUCKET` (the write uses the key `s010-token-check/canary.txt`); `lock` writes a new object under `R2_LOCKED_PREFIX`, then checks that an overwrite and a delete of it fail. The object stays under the lock until the owner removes the lock rule. `--skip <check>` (repeatable) leaves a check out and `--only <check>` runs one alone. `--no-proxy` is accepted only with `--only`. With the proxy on, `duckdb` is refused: its log reads would bypass the proxy.

### `analyse_ops.py` — operations per check, commit and class (step 4)

```bash
uv run python analyse_ops.py --run-id <run_id> --proxy-log output/proxy-<UTC start>.jsonl
uv run python analyse_ops.py --run-id <run_id> --proxy-log <file> --r2-total <n>   # with the run window's R2 total
uv run python analyse_ops.py --synthetic   # self-check on generated logs in output/local/
```

Assigns each test-bucket request to a check by time window. Inside a check, a request goes to an operation window or else to the check's verification reads; requests in a measure window are the probe's own reads. Requests to other buckets are filtered out. Writes `output/ops-<run_id>-by-check.csv`, `-by-op.csv`, `-by-class.csv` and `output/analysis-<run_id>.json`. The operation windows of the `full` checks are marked as the ones C takes. A check with no proxied request is flagged, since its client bypassed the proxy. It also runs the analysis checks of s010 §2 A:

- known arithmetic: one data PUT and one log PUT per single-file append without a checkpoint;
- independent count: the proxy's total requests, failed ones included, within ±0.5% of R2's total over the run window (R2's metrics are sampled, s010 F14);
- fault injection: a 412 on a log PUT in each concurrent pair, then a retry or a conflict.

### `measure_volume.py` — measured volume (step 6)

```bash
uv run python measure_volume.py                         # full run: writes output/volumes.json
uv run python measure_volume.py --archive <file> [...]  # history archives alone, by file name; no volumes file
uv run python measure_volume.py --synthetic             # self-check on a hand-made sample in output/local/
```

Reads only the local copies, so it sends no request to R2:

- capture (`../cloudflare-capture-spike/data/V4/`): `raw/` objects, bytes and records per provider, feed and day (entries of the payload's main list, 1 for feeds without one), plus distinct (`station_id`, `last_reported`) records for `station_status`; `logs/` objects, bytes and writes per day; `state/` writes per day, derived as one per `gbfs` log line with no error (capture writes the index to `state/` after each successful fetch). The first and last captured days are dropped as incomplete.
- history (`../bicing-spike/historical-data/raw/*.7z`): per archive, streamed with `tar -xOf` and never extracted: `.7z` and uncompressed bytes, raw rows counted by a CSV parser with the quoted newlines it finds, distinct (`station_id`, `last_reported`) rows, snapshots (`last_updated`) per UTC day and rows of each day's first snapshot.

Output: a summary on the console (means per day for capture, one line per archive) and, in the full run, `output/volumes.json` with every per-day figure.

The full run takes about 2–3 minutes (capture about 1, history the rest) and prints each part only when it ends.
