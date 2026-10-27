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

TODO: confirm the Python version before step 2. It was set provisionally in step 1 because the step did not define it. To check: (1) wheels for `deltalake`, `polars`, `duckdb` and `mitmproxy` on the candidate version, macOS arm64 (the owner's Mac runs the probes); (2) the Python version of the capture and deployment target (s009, d002), so the spike code stays close to what will run in production; (3) the support status of 3.13 versus 3.14. If it changes, edit only `.python-version`, run `uv lock` if `requires-python` moves, and re-run `uv sync --locked`.

## Commands

Filled by later steps.
