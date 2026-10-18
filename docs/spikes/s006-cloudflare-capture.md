# Spike — Cloudflare Workers + R2 as the real-time capture platform

## Status

- Completed
- Started:  2026-10-09 
- Finished: 2026-10-15 (V4 worker is running on Cloudflare)

## Questions

Main question: is Cloudflare Workers (Free plan, Cron Triggers) + R2 the definitive platform to capture the AMBici and Bicing GBFS feeds?

- **Q1.** Does the capturer stay within the Free plan's 10 ms CPU per cron invocation in the worst case (AMBici `free_bike_status`, 897 KB raw, every minute)?
- **Q2.** Is gzip compression what breaks that budget, and which variant avoids it: Python gzip, JS `CompressionStream`, or storing the origin's own gzip bytes?
- **Q3.** Is capture complete over the observation window (no gaps, no recurring `exceededCpu`), and does R2 usage match the estimate (~220k Class A operations/month)?
- **Q4.** Does the download to local with rclone from the R2 S3 endpoint work at no cost?
- **Observe only (no dedicated effort):** whether the platform logs are enough to diagnose problems during the run.

## Method

- Time-boxed spike; exit criteria are fixed before the first deploy:
  - Window: open-ended; the run is cut by the owner when the trends are clear enough for the production decision. Conclusions cover only the days observed; weekend coverage is not guaranteed (decided 2026-10-14; replaces the 7-day window of 2026-10-09).
  - Completeness: about 95 % of the expected captures per dynamic feed. It is a guide, not a hard cut: gaps at night weigh less than gaps by day (decided 2026-10-09).
  - Cost: €0 billed during the window, and R2 operations within the estimate (decided 2026-10-09).
  - Download: the daily download to local works on every day of the run (decided 2026-10-14).
  - CPU is observed, not a criterion: a run killed for CPU is a lost capture, which completeness already counts. Typical and maximum `cpuTime` are recorded per variant to know the headroom (decided 2026-10-09).
  - It is enough that one variant meets the criteria.
  - Two capture variants run in parallel on the same feeds and window: V2 and V4 (decided 2026-10-14). V3 and V4 were dropped because the Worker `fetch` decodes the gzip body (F8, decided 2026-10-13). V4 was recovered when `passthrough` with `encodeResponseBody: 'manual'` kept the origin's gzip (F9).

  | Variant | Language | Mode | What it tells |
  |---|---|---|---|
  | V1 | Python | `compress`: Python `gzip` | Baseline: the local scripts ported as they are |
  | V2 | JS | `compress`: `CompressionStream` | Whether native compression fits |
  | V3 | Python | `passthrough` | Whether Python fits without compression work |
  | V4 | JS | `passthrough` with encodeResponseBody: 'manual' | Whether the Free plan fits at all (cheapest design) |

- One code base per language, each deployed once.
- One cron per variant (2 of the 5 the Free plan allows). Splitting the feeds across several invocations is deferred to the production design, and only if the winner has little CPU headroom. The spike measures the worst case without mitigation (decided 2026-10-12).
- Polling: the dynamic feeds every minute, the static feeds every hour, enough to detect incidents within the spike (decided 2026-10-12).
  - Dynamic: AMBici `station_status` and `free_bike_status`; Bicing `station_status`.
  - Static: every other feed, including Bicing `station_information`.
- Each variant captures every feed of both sources (decided 2026-10-12). The CPU limit applies per invocation, so the realistic worst case is a tick that fetches the dynamic and the static feeds together.
- The gzip compression level is a parameter within each variant, not a variant of its own.
- While the capture runs, the owner downloads the R2 files to local once a day with `rclone copy` from the R2 S3 endpoint. rclone copies only new files, verifies them and retries, with no code to write (decided 2026-10-12).
- Logs (decided 2026-10-09):
  - Each variant writes its own JSONL request log, as close as possible to a future production capture.
  - R2 has no append, so each invocation writes one small object, `logs/<date>/<ts>.jsonl`, with one line per request. The daily download joins them locally.
  - The platform logs (Workers Logs, 3-day retention) are observed during the daily review, with no dedicated effort.
- File layout (decided 2026-10-12). One folder per language, each with its own dependencies and one Wrangler config per Worker. Installed dependencies (`node_modules/`, `.venv/`) stay inside each folder and are ignored by Git.
- Analysis (decided 2026-10-14): a full recompute over data/ on every run, with outputs overwritten (no incremental state). Window from the latest first log ts across variants to the last log ts in either. Checks instead of tests: known arithmetic, independent counts and fault injection.
    - Step 7.1 choices (decided 2026-10-14):
    - A log's `ts` is taken from its file name (the same value as its lines' `ts`).
    - `invalid_gzip`: decompression fails. `invalid_json`: decompression works but `json` cannot parse the result. An invalid object counts as invalid, not as `missing`.
    - A valid dynamic object at a non-expected minute (minute 17 of an odd UTC hour) is not counted as captured. It is reported per feed as off-schedule.
    - A variant with no logs is left out of the window start, and the report says so.
    - Files under `raw/` not named `<ts>.json.gz` are ignored and counted in the report.
- Two Workers in `js/`, one config file each, deployed with `npx wrangler deploy -c <file>` (Wrangler's standard for several Workers in one folder; decided 2026-10-14). Rejected: Wrangler environments in one file (meant for one script in several stages, not two scripts) and one Worker running both variants (mixes their `cpuTime`).
  
  ```
  spikes/cloudflare-capture-spike/
  ├── README.md                      Description of the spike
  ├── js/                            V2, V4
  │   ├── package.json               Dependencies (wrangler)
  │   ├── wrangler.v2.jsonc          Worker capture-v2
  │   ├── wrangler.v4.jsonc          Worker capture-v4
  │   ├── src/V2.js
  │   └── src/V4.js
  ├── analysis/
  │   ├── analyze_remote_capture.py  Step 7: lee data/ y sobrescribe output/
  │   └── output/                    Report and issues (ignored by git)
  └── data/                          Copy of bucket data (ignored by git)
      ├── V2/{raw,logs,state}/
      └── V4/{raw,logs,state}/
  ```

## Plan

Draft, pending the owner's approval. Code is throwaway and lives in `spikes/cloudflare-capture-spike/`.
Code makes no design decisions: if something is not specified here, it stops and asks in its report.

| # | Who | Step | Done when | Done |
|---|---|---|---|---|
| 1.1 | Owner | Activate R2 in the Cloudflare dashboard (requires a card) | R2 shows as active | ✅ |
| 1.2 | Owner | Create the bucket `bikesharing-capture-spike` | The bucket exists | ✅ |
| 1.3 | Owner | Usage alerts at 50 % of the free tier: two Usage Based Billing notifications, R2 Storage at 5 GB and R2 Class A operations at 500k | Alerts on | ✅ |
| 1.4 | Owner | Create an R2 API token, Object Read only, scoped to the bucket; save the access key, secret and endpoint in `.env` | Keys in `.env` | ✅ |
| 2.1 | Owner | In `js/`: `npm init -y`, `npm i -D wrangler` (local dev dependency), `npx wrangler login` (browser OAuth; token stays outside the repo) | `npx wrangler whoami` shows the account | ✅ |
| 2.2 | Code | Minimal Worker: `wrangler.jsonc` with an R2 binding to the bucket, and `src/V4.js` with a `fetch` handler that requests AMBici `free_bike_status` and Bicing `station_status` with `Accept-Encoding: gzip`, stores each body unchanged in R2 and returns status, `content-encoding` and bytes per feed | Code ready to run | ✅ |
| 2.3 | Owner | `npx wrangler dev --remote` (runs on Cloudflare, nothing stays deployed) and open the local URL once | The object is in the bucket || ✅ |
| 2.4 | Owner | Download both objects; check them with `file`, their size and `gunzip -t` | AMBici: status 200, feed body (not a challenge), valid gzip of ~45 KB. Bicing: valid gzip of ~10 KB (F1) → V3 and V4 go ahead. **Gate:** if it is ~897 KB of plain JSON, `fetch` decompressed: stop and re-decide V3/V4. Result in Findings | ✅ |
| 2.5 | Code | Variant of the smoke Worker: `put(key, res.body)` without reading the body; report status, `content-length` and the put result or error per feed | Code ready to run | ✅ |
| 2.6 | Owner | Run as 2.3; download and check as 2.4 | AMBici stored as valid gzip of ~45 KB → V3/V4 viable for AMBici. Bicing result recorded. Otherwise V3/V4 dropped | ✅ |
| 2.7 | Code | Smoke Worker variant V4-1 in `js/src/V4-1.js`, separate from `V4.js` (which stays untouched). For AMBici `free_bike_status` and Bicing `station_status`: `fetch(url, { headers: { 'Accept-Encoding': 'gzip' }, encodeResponseBody: 'manual' })`. Test A: `put(key, res.body)` without reading the body, in a `try/catch`. Test B, only if A fails: read `arrayBuffer()`, `put` those bytes under another key and report `byteLength`. Per feed, report status, `content-encoding`, `content-length`, result or error of A, and result of B. Keys: `V4-1/<source>/<feed>/passthrough.gz` (A), `V4-1/<source>/<feed>/buffered.gz` (B). Do not modify `package.json`, `package-lock.json`, `wrangler.jsonc` or the other files in `src/`; if the run needs a change in `wrangler.jsonc` (for example `main`), stop and report. The report states the exact command to run V4-1 | Code ready to run; the report gives the run command | ✅ |
| 2.8 | Owner | Run as 2.3, with the command from the 2.7 report; download the stored objects and check them as in 2.4 (`file`, size, `gunzip -t`). **Gate:** the option works if a stored object is a valid gzip of ~45 KB (AMBici) or ~10 KB (Bicing, F1), from A or from B. If the bytes are ~851 KB / ~267 KB (plain JSON), `encodeResponseBody` is ignored and V4 stays dropped. Result in Findings (F9) | AMBici and Bicing: valid gzip from A or B → V4 viable (A: streamed; B: buffered, no compression work either way). Plain JSON → V4 dropped for good | ✅ |
| 3.1 | Code | Capturer V2 in `js/src/V2.js`: `runPass({ now, includeStatic, includeDynamic })` fetches the feeds of both sources (dynamic when `includeDynamic`, static when `includeStatic`), compresses with `CompressionStream`, stores each in R2 under the V2 prefix and writes the JSONL log. The `gbfs.json` indexes are fetched on every pass (no `state/` yet). A `fetch` handler calls it with `Date.now()` and both flags true (the worst case) and returns a short JSON summary per feed. Do not modify `package.json`, `package-lock.json` or `wrangler.jsonc`; if one needs a change, stop and report | Code ready to run | ✅ |
| 3.2 | Owner | `npx wrangler dev --remote src/V2.js`, open the local URL once; download the objects and the log and check them as in 2.4 | All feeds of both sources stored as valid gzip (`gunzip -t`); one JSONL log with one line per request {"ts", "source", "feed", "status", "latency_ms", "bytes", "error"} | ✅ |
| 3.3 | Code | Only if 3.2 passes: scheduling on top of the verified pass. `scheduled` handler that calls `runPass` with the trigger's `scheduledTime` and applies the hourly alternation of the shared behaviour (static at minute 17; dynamic skipped at minute 17 in odd UTC hours); both indexes read and written in `<variant>/state/<source>_index.json` for cold starts. Do not touch `wrangler.jsonc`: the cron and the second Worker config are settled by the owner (open point in Method) | Code ready to deploy | ✅ |
| 4.1 | Code | Capturer V4 in `js/src/V4.js`, same pass as 3.1 (`runPass({ now, includeStatic, includeDynamic })`, same feeds, keys with the V4 prefix, same JSONL log and `fetch` handler). Difference: no compression. Each feed is fetched with `Accept-Encoding: gzip` and `encodeResponseBody: 'manual'` (F9), read with `arrayBuffer()` and stored unchanged with `put`, for every feed (no streaming). The `gbfs.json` indexes are fetched without the option, since they have to be parsed. Do not modify `package.json`, `package-lock.json` or `wrangler.jsonc`; if one needs a change, stop and report | Code ready to run | ✅ |
| 4.2 | Owner | `npx wrangler dev --remote src/V4.js`, open the local URL once; download the objects and the log and check them as in 3.2 | Same as 3.2, for V4: all feeds valid gzip; one JSONL log with one line per request | ✅ |
| 4.3 | Code | Only if 4.2 passes: scheduling on top of the verified pass, as 3.3, for V4 | Code ready to deploy | ✅ |
| 5.1 | Code | Create `js/wrangler.v2.jsonc` (`capture-v2`, `main` `src/V2.js`) and `js/wrangler.v4.jsonc` (`capture-v4`, `main` `src/V4.js`), each with exactly these keys: `name`, `main`, `compatibility_date` `2026-10-01` (same in both), `r2_buckets` (binding `BUCKET` to the bucket), `triggers.crons` `["* * * * *"]`, `workers_dev: false` and `preview_urls: false` (no public `fetch` route: a visit would trigger a full pass and spend Class A operations), `observability` with `enabled: true` and `head_sampling_rate: 1` (every invocation logged, for `cpuTime` and `exceededCpu`) (decided 2026-10-14). Do not modify `package.json`, `package-lock.json` or `src/` | Config ready to deploy | ✅ |
| 5.2 | Owner | Delete the smoke-run objects (steps 3–4) under `V2/` and `V4/`, including `state/` (F10); then `npx wrangler deploy -c wrangler.v2.jsonc` and `-c wrangler.v4.jsonc`; check the first hour, including minute 17 and the even/odd hour alternation (F11) | Objects appear under each variant's prefix; `cpuTime` is visible in Workers Logs | ✅ |
| 6 | Owner | Run: daily `rclone copy` and a daily look at Workers Logs (`cpuTime`, `exceededCpu`) | A download on every day of the run; CPU noted per variant per day |  |
| 7.1 | Code | Analysis base in `analysis/analyze_remote_capture.py`. Python 3, standard library only, no arguments. Paths are resolved from the script's location: input `../data/`, output `output/` (created if missing). Constants at the top: variants `V2`, `V4`; dynamic feeds `ambici/station_status`, `ambici/free_bike_status`, `bicing/station_status`. Works with any amount of data, including less than one UTC day; if there are no logs, the report says so and the script exits without error. **Window:** start = the latest of each variant's earliest log `ts`; end = the latest log `ts` in either variant; whole minutes, inclusive, UTC. **Expected** per variant and dynamic feed: every minute in the window except minute 17 of odd UTC hours. **Captured:** `<variant>/raw/<source>/<feed>/<YYYY-MM-DD>/<ts>.json.gz` exists, decompresses with `gzip` and parses with `json`. Every raw object in the window, dynamic and static, is validated; objects outside the window are not analysed, only counted. **Outputs**, overwritten on every run. `output/report.md` has a header with the window start and end, its minutes and the run time (all UTC), then: (a) completeness per variant × dynamic feed: expected, captured and % over the window, per UTC day (days only partly in the window marked as partial), and missing per UTC hour of day (0–23); (b) invalid objects per variant × feed and kind; objects outside the window per variant × feed and UTC day. `output/issues.csv` has the columns `variant,source,feed,ts,kind,detail`, sorted in that column order; kinds in this step: `missing`, `invalid_gzip`, `invalid_json` (detail: the exception message). Same commit: add `analysis/output/` to the `.gitignore` that already ignores `data/` (if none does, stop and report). Do not modify `js/` or `data/` | Code ready to run | ✅ |
| 7.2 | Owner | From the spike root run `python3 analysis/analyze_remote_capture.py`, then make four checks. (1) Arithmetic: the expected count per dynamic feed equals the window minutes minus the minute-17 passes of odd UTC hours inside the window. (2) Independent count: for one variant, one dynamic feed and one UTC day, find data/<variant>/raw/<source>/<feed>/<day> -name '*.json.gz' \| wc -l equals captured + invalid + off-schedule + outside the window for that day in the report. (3) Fault injection: move one dynamic object from inside the window to `/tmp`, overwrite another with `echo x > <file>`, run again: `missing` +1 and `invalid_gzip` +1 in the report and in `issues.csv`; then `rclone copy` (restores both), delete the `/tmp` copy, run again: back to the previous figures. (4) The first hour after deploy shows no gaps (F12) | All four checks pass | ✅ |
| 7.3 | Code | Extend the same script with the rest of the analyses. **(c) Reconciliation** from every `<variant>/logs/<YYYY-MM-DD>/<ts>.jsonl` in the window. Logs and objects are matched by source, feed and UTC minute, not by the exact `ts` (passes run at second 47; expected minutes have second 00). In `issues.csv`, `ts` is the exact `ts` of the object or log line when one exists, and the expected minute (second 00) otherwise. A `status` that is neither null nor 200 → `http_error` (detail: the status). An `error` with a null `status` → `fetch_error` (detail: the error). A line with status 200 for a non-`gbfs` feed and no object at its key → `log_without_object`. A raw object in the window with no line for its source, feed and `ts` → `object_without_log`. A window minute with no log file → `missing_log`. A line that cannot be parsed → `invalid_log` (detail: the file). `gbfs` lines feed only `http_error` and `fetch_error`. The report gives, per variant: log files, lines, and count per kind. Log files outside the window are not analysed, only counted, per variant and UTC day. **(d) Static feeds:** for every minute-17 pass in the window, the number of static objects per variant × source, reported as a distribution (objects per pass → number of passes). Plus: minute-17 passes in odd hours that have any dynamic object (expected 0; taken from the off-schedule count of 7.1, not recomputed); minute-17 passes in even hours that have all 3 dynamic objects (expected all); static objects at minutes other than 17 (expected 0). **(e) Class A writes**, estimated per variant as raw objects + log files + `state/` writes (one per `gbfs` line with status 200; if the capturers write `state/` under another condition, follow the code and say so in the report). Reported as the total over the window, the rate per day (total / window minutes × 1,440) against the F2 reference of 6,144 per variant per day (4 per minute + 16 per hour), and a 30-day projection for both variants against the 1M free. The report notes that the R2 dashboard is the authoritative figure. Same restrictions as 7.1. Same commit: create the spike README.md with a description of the spike and an “Analysis” section (what the script does, how to run it).| Code ready to run | ✅ |
| 7.4 | Owner | Run as in 7.2, then make three checks. (1) `find data/<variant>/logs -name '*.jsonl' \| wc -l` equals the log files in the report plus the logs outside the window. (2) For one UTC day, every static feed folder holds as many objects as there are minute-17 passes inside the window that day (`ls data/<variant>/raw/<source>/<feed>/<day> \| wc -l`), consistent with (d). (3) The report's Class A writes are in the order of the R2 dashboard figure for the same period; the dashboard is higher because it also counts the rclone listings and the deletes. | All three checks pass | ✅ | 
| 8 | Chat + owner | Findings and Conclusion against the exit criteria. After the last download, tear down V2 (`npx wrangler delete -c wrangler.v2.jsonc`). V4 keeps running as interim capture outside the spike, so no `wrangler logout` and the bucket stays (decided 2026-10-14) | Conclusion written; next ADRs named | ✅ |

Behaviour shared by both capturers:

- **One pass per invocation.** Dynamic feeds every minute; static feeds when the scheduled minute is 17, to avoid minute 0, when scheduled jobs tend to cluster (decided 2026-10-12). The time comes from the trigger's `scheduledTime`, in UTC.
- **Feed URLs of both sources** come from their `gbfs.json`, which is fetched hourly with the static feeds. They are kept in memory and persisted to `<variant>/state/<source>_index.json` for cold starts. The two `gbfs.json` URLs are constants at the top of the code (no environment variables): AMBici `https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_bs/gbfs.json`, Bicing `https://barcelona.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json`. Feed URLs are resolved from the indexes, never hardcoded.
- **Object keys:** `<variant>/raw/<source>/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz`.
- **Timestamps:** everything is UTC, following the ADR 0005. Object keys, date folders and log fields are all derived from a single `now` (epoch ms) per pass, formatted as `YYYYMMDDTHHMMSSZ` in keys. No local-time getters or methods.
- **Logs:** one `<variant>/logs/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.jsonl` per invocation, one line per request, with exactly these fields in this order: {"ts", "source", "feed", "status", "latency_ms", "bytes", "error"} (decided 2026-10-13). `ts` is the pass timestamp, UTC, `YYYYMMDDTHHMMSSZ` (the value used in the object keys); `source` is `ambici` or `bicing`; `feed` is the feed name, and the `gbfs.json` index fetches keep their own line with feed `gbfs`. `bytes` is the size of the object written to R2; on `gbfs` lines, which write no object, it is the size of the response body received (decided 2026-10-14). The variant is not a field: it is the log's key prefix. No `url` or `key`. Each feed is fetched and stored independently, so one failure does not stop the others.
- **Static feeds alternate by hour**. At minute 17 of each UTC hour the pass fetches the static feeds; in even UTC hours it also fetches the dynamic feeds, and in odd UTC hours it skips the dynamic ones. The skipped dynamic captures will be excluded from analysis.
- **latency_ms** is the time from sending the request until the body is fully read
- **Index refresh policy**. Each source's index is refreshed in the minute-17 pass, held in memory and persisted to `<variant>/state/<source>_index.json`. On a cold start it is read from `<variant>/state/`; if `<variant>/state/` has no index, it is fetched in that pass (even if it is not minute 17) and persisted. The `gbfs` log line is written only when the index is fetched, so step 7 must not expect one per pass.
- **Index refresh failure**. If a refresh fails, the last known index (memory or `state/`) is kept and the error is logged on the `gbfs` line. If there is no index at all, that source is not captured in that pass and the fetch is retried in the next one.

### Others

#### Commands used in 3.2 and 4.2

- Run the Worker on Cloudflare without deploying it (terminal 1) 
  ```
  cd spikes/cloudflare-capture-spike/js
  npx wrangler dev --remote src/<file_name>.js 
  ```
- Trigger ONE pass (terminal 2); summary per feed: status, bytes, error. Stop with Ctrl+C
  ``` 
  curl -s http://localhost:8787 | python3 -m json.tool
  ```
- List and download the variant's objects from R2
  ```
  rclone ls r2:bikesharing-capture-spike  # list objects
  rclone copy r2:bikesharing-capture-spike data  # root to root folder
  ```

#### Workers commands

- Deploy workers
  ``` 
  cd spikes/cloudflare-capture-spike/js
  npx wrangler deploy -c wrangler.v2.jsonc
  npx wrangler deploy -c wrangler.v4.jsonc
- Command to delete workers
  ```
  npx wrangler delete -c wrangler.vN.jsonc # N = {v2, v4}
  ```


## Findings

**F1. Payload size per request (median, raw / gzip)**, from the source spikes, section 7a:

| Source | Feed | Raw | Gzip |
|---|---|---|---|
| AMBici | `free_bike_status` | 897 KB | 51 KB |
| AMBici | `station_information` | 80 KB | 10.6 KB |
| AMBici | `station_status` | 53 KB | 2.3 KB |
| Bicing | `station_information` | 516 KB | 45.7 KB |
| Bicing | `station_status` | 268 KB | 10.3 KB |
| Bicing | `system_pricing_plans` | 11 KB | 0.7 KB |

Every other feed is under 5 KB raw. The platform benchmark estimated ~0.5 MB for `free_bike_status`; the measured size is almost double.

**F2. R2 usage during the spike (estimated from F1):**

| | Per variant | 4 variants | 2 variants (V2, V4) |
|---|---|---|---|
| Storage per day | ~93 MB | ~370 MB | ~185 MB |
| Storage, 7 days | ~0.65 GB | ~2.6 GB (26 % of the 10 GB free) | ~1.3 GB (13 %) |
| Writes (Class A), 7 days | ~43k | ~172k (17 % of the 1M free per month) | ~86k (9 %) |

- Storage is driven by the three dynamic feeds every minute; static feeds and logs add ~2 MB/day.
- Writes: 4 per minute (3 dynamic feeds + 1 log) plus ~16 per hour (static feeds + Bicing index). Class A is R2's billing category for write and list operations.

**F3. Compression level:** the local scripts call `gzip.open` without `compresslevel`, which defaults to level 9, the most CPU-intensive.

**F4. Porting the local scripts:**

- `http_get` uses `urllib.request`, which is not confirmed in Python Workers; it is rewritten with `workers.fetch`.
- `write_gzip_atomically` is replaced by an R2 `put`, which writes the whole object or nothing.
- `FeedCatalog` (Bicing) only parses the small `gbfs.json` index and ports unchanged.

**F5. The AMBici origin serves gzip on request** (owner's `curl` with `Accept-Encoding: gzip` on `free_bike_status`, 2026-10-09 17:34 UTC):

- Response headers: `content-encoding: gzip`, `content-length: 45013`. The compressed body is ~45 KB versus 897 KB raw.
- The origin sits behind Cloudflare (`server: cloudflare`, `cf-ray`) and sets a `__cf_bm` bot-management cookie. A Worker is not challenged (F8).

**F6. Static feeds barely change** (owner, from the source spikes):

- Over the two days of local capture, the static feeds did not change.
- Only the dynamic feeds need 1-min polling. In production the rest could be fetched once a day.
- Bicing `station_information` changes a little, but not enough to need 1-min polling.

**F7. The Bicing origin also serves gzip on request** (owner's `curl` with `Accept-Encoding: gzip`, 2026-10-12):

- Both `station_status` and `station_information` answer `HTTP/2 200` with `content-encoding: gzip`.
- No `content-length` header was returned, so the compressed size could not be read from the headers.
- `server: envoy`, with no `set-cookie`: Bicing is not behind Cloudflare and sets no bot-management cookie.
- Passthrough (V3, V4) would need the Worker `fetch` to hand over the compressed bytes. It does not (F8).


**F8. Worker `fetch` decompresses the gzip body** (Plan step 2.3, 2026-10-12, `wrangler dev --remote`, `Accept-Encoding: gzip`):

| Source | Feed | Status | `content-encoding` | Bytes read |
|---|---|---|---|---|
| AMBici | `free_bike_status` | 200 | gzip | 851,394 |
| Bicing | `station_status` | 200 | gzip | 267,692 |

- The bytes match the raw sizes (F1), not the gzip ones: the runtime decodes the body, and the header still says `gzip`.
- AMBici answers 200 with the feed: the Worker is not challenged by bot management.
- Confirmed on the stored objects (Plan step 2.4): `file` reports JSON data, same byte counts, `gunzip -t` fails (not in gzip format). Passthrough as designed is not viable.
- Streaming the body to R2 without reading it (Plan step 2.6) fails for both feeds: `Provided readable stream must have a known length`, even though AMBici sends `content-length: 50939`. The stream is decoded too. V3 and V4 dropped (decided 2026-10-13), V4 reopened after F9; V3 stays dropped.”

**F9. `encodeResponseBody: 'manual'` makes `fetch` deliver the origin's gzip** (Plan steps 2.7–2.8, 2026-10-13, `wrangler dev --remote`, `Accept-Encoding: gzip`, option set in the outgoing `fetch` `RequestInit`; not documented, found in the `@cloudflare/workers-types` typings):

| Source | Feed | Test | Result | Stored | `gunzip -t` |
|---|---|---|---|---|---|
| AMBici | `free_bike_status` | A (`put(key, res.body)`) | OK, `content-length: 47634` | 47,634 B (inflates to ~809 KB) | OK |
| Bicing | `station_status` | A | Fails: `known length` (no `content-length`, F7) | none | |
| Bicing | `station_status` | B (`arrayBuffer()` then `put`) | OK, `byteLength: 11771` | 11,771 B (inflates to ~268 KB) | OK |

- The stored bytes are the origin's compressed ones (~47.6 KB and ~11.8 KB, in line with F1), not the decoded ones (F8: ~851 KB, ~267 KB). The option works.
- Different from `Response.encodeBody`, which only affects what the Worker sends out.
- AMBici can be streamed, because its `content-length` now matches the bytes. Bicing needs a buffered read (`arrayBuffer()`), since the origin sends no `content-length`; reading the compressed bytes costs no compression work.
- Consequence for the design: V4 needs no compression level (F3 does not apply) and handles ~19× fewer bytes than V2 on AMBici. Its CPU cost is not measured yet.
- Open point: whether the runtime does hidden CPU work when the option is set. Only the `cpuTime` of the 7-day run will tell.

**F10. `wrangler dev --remote` writes `state/` objects at startup, with no request**
- Observation (step 3.3, 2026-10-13): starting `wrangler dev --remote` with no request writes `V2/state/` objects (one or both sources) with no log and no raw objects. Reproduced twice; the orphan `system_hours` object of step 3.2 is probably the same effect. Likely an invocation at startup that is cut off mid-pass. Not seen in production (cron). Not blocking. Consequence: smoke-run cleanup before step 5 must include `V2/state/`.
- Reproduced with V4 (step 4.3, 2026-10-14): `wrangler dev --remote --test-scheduled src/V4.js` wrote both `V4/state/` indexes before any request. Cleanup before step 5 must include `V4/state/` too.

**F11. With `wrangler dev --remote`, a scheduled run cannot be given a simulated time** (step 4.3, 2026-10-14, `--test-scheduled`):
- `/cdn-cgi/handler/scheduled` returns Cloudflare error 1042; `/__scheduled?cron=*+*+*+*+*` works.
- The `time` parameter is ignored: `scheduledTime` is the real time.
- Verified on V4 at normal minutes: 4 passes, 3 dynamic feeds each, all valid gzip, one log per pass, no `gbfs` lines (index read from `state/`, then kept in memory).
- Not verified: minute 17 (static feeds, index refresh) and the even/odd hour alternation. They are checked in the first hours of step 5.

**F12. First hour in production: every pass completes, but only V4's dynamic-only passes fit the 10 ms CPU limit** (step 5.2, 2026-10-14, Workers Logs)
- Both Workers run every minute from the cron, all invocations `scheduled`; one log and the dynamic objects per minute under `V2/` and `V4/`.
- `cpuTimeMs` per pass:

  | Pass | V4 | V2 |
  |---|---|---|
  | Dynamic only (3 feeds) | 4–10 | 18–25 |
  | Minute 17, odd UTC hour (static only) | 23 | 36 |
  | Minute 17, even UTC hour (static + dynamic) | 24 | 48 |

- `outcome: ok` on 100 % of invocations: the Free plan's 10 ms limit is not enforced per invocation for now. Not something to rely on.
- V4's CPU grows with the number of feeds (~1 ms per fetch + `put`), not with their size; V2 adds the compression cost on top.
- Not checked: the number of static objects per minute-17 pass (step 7).

**F13. From the fourth hour, the 10 ms CPU limit is enforced on V2; V4 is unaffected** (step 7.2, 2026-10-14, Workers Logs and the step 7.1 report)
- Every `capture-v2` invocation from 13:50 to 15:25 UTC ends with `outcome: exceededCpu`, `cpuTimeMs: 10` (e.g. `wallTimeMs: 175`). Every `capture-v4` invocation is `ok`.
- The pass is cut mid-way, so some feeds of a pass are stored and others are not: V2 misses 92, 96 and 84 of 289 expected captures (`ambici/station_status`, `ambici/free_bike_status`, `bicing/station_status`), all between 13 and 15 UTC. V4 misses 1 (`bicing/station_status`, 11 UTC) : HTTP 524 at 11:42 UTC on the same pass in both variants, logged as such.
- Open: whether V4's minute-17 passes (23–24 ms, F12) will also be cut.

**F14. V4 captures every expected dynamic object but one; V2 loses about 30 %** (step 8, 2026-10-15, step 7 report; window 2026-10-14T10:51Z–22:09Z, 679 minutes, 673 expected per dynamic feed)

| Variant | `ambici/station_status` | `ambici/free_bike_status` | `bicing/station_status` |
|---|---|---|---|
| V2 | 467 (69.4 %) | 460 (68.4 %) | 482 (71.6 %) |
| V4 | 673 (100 %) | 673 (100 %) | 672 (99.9 %) |

- V2's gaps fall in 13–15 and 17–19 UTC, when `exceededCpu` cuts its passes (F13). V4's single gap is the HTTP 524 at 11:42 UTC (F13), logged as `http_error` in both variants.
- No invalid objects in either variant: every stored object decompresses and parses.
- Logs: V4 has one log per minute (679) and no mismatch with the objects. V2 has 215 minutes without a log and 30 objects without a log line: a pass cut for CPU stores some feeds and never writes its log.
- Static feeds: V4 stores 7 objects per source in all 11 minute-17 passes, and all 3 dynamic objects in its 5 even-hour ones. V2 stores no static objects in 4 of the 11 passes.

**F15. V4 stays at €0 and never ends with `exceededCpu`, although its minute-17 passes exceed 10 ms** (owner, Workers Logs and R2 dashboard, 2026-10-14 22:18 UTC)

- V4 `cpuTime`: typical 5 ms, maximum 28 ms, average of the maxima 20 ms. The passes above 10 ms are the minute-17 ones (F12). Why they are not cut while V2's are is not documented.
- R2 dashboard, whole bucket since creation (smoke runs, rclone listings and deletes included): Class A 6.15k, Class B 15.6k, storage 66 MB, 4.67k objects. Billed: €0.
- Class A estimated by the report: V4 6,097 per day against the F2 reference of 6,144; 30-day projection 182,916 for V4 alone (18 % of the 1M free). The dashboard is above the report's 4,862 for both variants, as expected (step 7.4).

**F16. The daily download works at no cost** (step 6, 2026-10-14)

- `rclone copy` from the R2 S3 endpoint, with the read-only token, downloaded every new object on each run; the downloads are part of F15's Class B and €0.
- Only one UTC day observed so far.

## Conclusion

Observed window: 2026-10-14T10:51Z–22:09Z (679 minutes, one weekday, no weekend).

**Answers**

- **Q1.** V4: yes in practice. Typical `cpuTime` is 5 ms; minute-17 passes reach 23–28 ms but have never been cut (F12, F15). V2: no, its passes are cut from the fourth hour (F13).
- **Q2.** Yes, compression is what breaks the budget: V2 spends 18–25 ms on a dynamic-only pass against V4's 4–10 ms (F12). Storing the origin's gzip (V4, F9) avoids it. Python `gzip` (V1) and Python passthrough (V3) were not tested (F8).
- **Q3.** V4: yes. Capture is 100 %, 100 % and 99.9 % per dynamic feed, with no `exceededCpu` (F14, F15). R2 usage is in line with the estimate: ~6.1k Class A per day for V4, ~183k per month (F15).
- **Q4.** Yes: the daily `rclone copy` works, €0 billed (F16).
- **Logs (observe only).** Workers Logs were enough to find V2's `exceededCpu` and the HTTP 524 (F13). V4's JSONL logs reconcile one to one with its objects (F14). The 3-day retention of Workers Logs requires a daily look.

**Exit criteria**

| Criterion | V2 | V4 |
|---|---|---|
| Completeness, ~95 % per dynamic feed | ❌ 68–72 % | ✅ 99.9–100 % |
| €0 billed, R2 operations within the estimate | ✅ | ✅ |
| Daily download works | ✅ | ✅ |
| CPU (observed, not a criterion) | 18–48 ms; cut from 13:50 UTC | typical 5 ms, max 28 ms; never cut |

**Verdict.** V4 meets every exit criterion and V2 does not. Cloudflare Workers (Free plan, Cron Triggers) + R2, with V4 (JS, passthrough with `encodeResponseBody: 'manual'`), is the platform for real-time capture of AMBici and Bicing. Not verified:

- Minute-17 passes run at 23–28 ms, above the 10 ms limit. They have not been cut, but the enforcement rule is not documented (F12, F13). Mitigation: split the feeds across several crons (Method).
- `encodeResponseBody: 'manual'` is not documented (F9). If the runtime stopped honouring it, objects would be stored decoded and the analysis would report them as `invalid_gzip`.
- Weekends and runs longer than one day.

V4 keeps running after the spike closes, as interim capture outside the spike; data after the window are not part of these conclusions. V2 is torn down.

**Inputs for the production design**

- consider Wrangler `vars` for the index URLs and the static-feed minute.
- index `bytes` is measured with string length, not bytes: read `arrayBuffer()` and use `byteLength`.
- no timeout on `fetch`: add `AbortSignal.timeout`.
- the log `put` is not guarded: a failure loses the log and the summary.
- index entries without `name` or `url` are not validated.
- `latency_ms` is null on errors and non-2xx responses: define the rule.
- the index refresh is tied to `includeStatic` in the spike; in production the static feeds will not be tied to the index, so decouple them.
- consider to set downloading freq for static json

## Sources

- Platform benchmark, October 2026. [s005-benchmark-data-capture.md](s005-benchmark-data-capture.md)
- AMBici source spike, section 7 (Volume). [ambici.md](s001-ambici-realtime-capture.md#7-volume-1)
- Bicing source spike, section 7 (Volume). [bicing.md](s002-bicing-realtime-capture.md#7-volume)
