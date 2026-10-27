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

Filled by later steps.
