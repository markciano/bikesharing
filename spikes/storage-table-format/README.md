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
