# Free platform to capture Barcelona's GBFS feeds: recommendation (October 2026)

**My recommendation is Cloudflare Workers (Cron Triggers) + R2. It meets all five requirements with ample quota headroom and is permanently free, but with one condition: the real risk is the 10 ms CPU limit per invocation on the Free plan, not the quotas.** That is why I recommend writing the capture Worker so that it does not parse or recompress in Python, or writing it directly in JavaScript/TypeScript, and keeping Python/Spark for the downstream pipeline. As a fallback I propose an Oracle Cloud Always Free VM with cron/systemd and the scripts almost unchanged, accepting the risk of idle reclamation.

## TL;DR

- **Primary: Cloudflare Workers Cron + R2.** Quota-wise there is plenty of room everywhere: cron every minute, 100,000 requests/day (you will use \~1,500), R2 with 10 GB-month and 1M Class A operations/month (you will use \~22%), and free egress for downloading with rclone/S3 API. The weak point is the **10 ms of CPU per cron execution on the Free plan**. A Python Worker (Pyodide/WebAssembly) doing `json.loads` + `gzip.compress` on a \~0.5 MB `free_bike_status` is quite likely to exceed it. Solution: don't touch the payload in Python (streaming + native compression) or write the capturer in JS. This must be validated during the first week in Workers Logs.
- **Fallback: Oracle Cloud Always Free VM** (cron/systemd + 200 GB local disk + rsync/rclone-sftp; 10 TB/month free egress). Runs your stdlib Python without adaptation. The risks are that Oracle may reclaim "idle" Always Free VMs (according to its "Always Free Resources" documentation, when over 7 days CPU p95 and network are below 20%, and memory only on A1 shapes, which is exactly your case) and that it is less relevant in the job market. No other option is clearly better. GitHub Actions (5 min minimum, delays and dropped runs), Vercel Hobby (once a day), GCP and AWS (write operations on GCS/S3 exceed the free tier or depend on temporary credits) fall behind.
- **Logs:** Cloudflare observability on Free retains only **3 days** (200,000 events/day) and Logpush is not available on Free. **Keep your own JSONL request log in R2.** Since R2 does not support append, write one log object per invocation (`logs/<YYYY-MM-DD>/<ts>.jsonl`) and consolidate it when downloading. Required adaptation: replace the infinite loop with a `scheduled()` handler that does one pass per minute, decides static feeds with `minute % 15 == 0`, and caches the Bicing index.

## Key Findings

### 1. Cloudflare Workers + R2: detailed evaluation

| Aspect | Verified data (official docs, Oct. 2026) | Impact on your workload |
| --- | --- | --- |
| Minimum Cron interval | Every minute (`* * * * *`). Cannot fire more than once per minute. In UTC | ✅ Meets 1-min polling |
| Number of Cron Triggers | 5 per account (Free) vs 250 (Paid) | ✅ You need 1–2 |
| Cron change propagation | Up to 15 min | Minor; only on deploy |
| CPU per Cron Trigger (Free) | **10 ms** (Paid: 30 s if the interval is < 1 h) | ⚠️ **Main risk** (see below) |
| Wall time per cron | 15 min; waiting on `fetch()` does not count as CPU | ✅ Waiting on origins does not consume CPU |
| Requests/day (Free) | 100,000/day, reset at midnight UTC | ✅ 1,440 crons/day (≈1.5%) |
| Subrequests/invocation (Free) | 50 external + 1,000 to Cloudflare services (R2, KV…) | ✅ Normal tick: 3 fetch + 3 put. 15-min tick: \~20 fetch + \~20 put |
| Memory | 128 MB per isolate | ✅ Enough for a \~1 MB payload |
| Python Workers | **GA since 21-Sep-2026**; Pyodide (CPython → WebAssembly); cron supported in Python; R2 bindings from Python | ✅ Python is viable, but with higher CPU cost than JS |
| Stdlib | "The full Python Standard Library" except for a list of exclusions (curses, dbm, termios…). `gzip`/`zlib`/`json` are not excluded. `threading`/`multiprocessing` don't work. Filesystem is in-memory and ephemeral only | ✅ gzip available; ❌ no persistent disk |
| Outbound HTTP | The documented way is `from workers import fetch` (or `js.fetch` via FFI). Since GA, `requests`/`httpx` are routed through the Fetch API | ⚠️ `urllib.request.urlopen` **is not confirmed**; use `workers.fetch` |
| R2 free tier | 10 GB-month, 1M Class A/month, 10M Class B/month, **free** egress | ✅ \~220k Class A/month; 0.7–1.4 GB stored |
| Card for R2 | A payment method is required to activate the R2 subscription (confirmed in a HackerOne bug bounty report and in the Cloudflare community) | Acceptable per your requirements |
| Workers Logs (Free) | 200,000 events/day, **3 days** retention | ⚠️ Not usable as history; you need your own log |

**R2 operations calculation.** At 1 min there are 3 dynamic GETs/min, i.e. 4,320 objects/day. Static feeds (\~15–18 feeds × 96 ticks) add \~1,450–1,730/day. With one log object per invocation that is 1,440/day more. In total ≈7,300 PUT/day ≈ **220,000 Class A/month, 22% of the free million**. ListObjects is also Class A in R2, but rclone lists 1,000 keys per call, so a biweekly download is a few hundred calls. Reads when downloading (\~100–200k GET) fit easily within the 10M Class B. Careful: according to the R2 pricing documentation, "if you have made one million and one operations, you will be billed for two million" (Class A overage costs $4.50/million), so the billing risk only appears if a bug multiplies writes.

**The 10 ms CPU problem.** This is the part that decides whether Python works or not:

- The official Workers limits page (updated 8-Oct-2026) says the average Worker uses \~2.2 ms per request and that workloads that "parse large payloads" typically use **10–20 ms**. A \~0.5 MB raw AMBici `free_bike_status` is exactly that case. This is my inference: 77.9 MB/day gzip ÷ 1,440 polls ≈ 54 KB gzip per minute for the two dynamic feeds, and JSON usually compresses \~10×. I could not download the feed to measure it.
- In Pyodide, `json.loads` + `gzip.compress` of \~0.5 MB run in WebAssembly, slower than native. **I found no published measurement** of Python Workers CPU on Free cron, nor of gzipping 1 MB in Workers.
- There are public issues of JS Workers on the Free plan with every-minute cron ending in `exceededCpu` (cpuTimeMs: 10) on cold isolates. It is not documented whether restoring the Python memory snapshot counts against those 10 ms. Cloudflare publishes an average cold start of 1.027 s wall time for a Python Worker with packages.
- The same Cloudflare limits page states that each isolate has "some flexibility" built in to occasionally exceed the limit, but that if it consistently exceeds it, execution is terminated.

**Conclusion:** a "naive" Python Worker (parsing JSON + recompressing with Python's `gzip`) has a **high risk** of failing intermittently precisely with AMBici `free_bike_status`. There are three designs that mitigate the risk, from most to least recommended:

1. **Capturer in JS/TS** (still free) with `fetch` → `body.pipeThrough(new CompressionStream("gzip"))` → `env.BUCKET.put()`. Native compression, without going through Python. Python/Spark stay for bronze→silver→gold, which is where employers look.
2. **"Don't touch the payload" Python Worker**: no `json.loads`, and compress with `CompressionStream` via FFI instead of Python's `gzip`. Doing it with CompressionStream from Python **is neither documented nor measured**, so it has to be tested.
3. **Reduce the load**: 5-min polling, or remove `free_bike_status` from the 1-min cycle, which brings it down to \~24 MB/day.

If none of this fits, the Workers Paid plan ($5/month) gives 30 s of CPU. It is no longer free, but it is the cheap escape hatch.

### 2. Comparison of alternatives

| Option | Granularity / reliability | Storage and operations | Logs | Card / billing risk | Portfolio relevance | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| **Cloudflare Workers Cron + R2** | 1 min, reliable | R2: 10 GB, 1M Class A, egress 0 | 3 days (Free) | Card for R2; Workers Free hard-stops; R2 bills overages | Medium-high (serverless + S3-compatible object storage) | **Primary** |
| **Oracle Always Free VM** | 1-min cron on the VM; your scripts as-is | 200 GB block volume; Object Storage 20 GB but only **50,000 API requests/month** (not enough for one PUT per file; enough for an hourly tar) | Your own, on disk | Card; idle reclamation | Medium-low | **Fallback** |
| GCP e2-micro Always Free | 1-min cron on the VM | 30 GB disk; GCS free only 5 GB and **5,000 Class A/month**, aggregated across us-west1, us-central1 and us-east1 (Google Cloud "Storage pricing" page) | Cloud Logging 50 GiB/project, 30 days | Billing account mandatory; egress beyond the free quota → cents | High (GCP) | Viable, almost free |
| GCP Cloud Run + Cloud Scheduler + GCS | Scheduler 1 min; 3 free jobs per billing account | GCS: 190k writes ≫ 5,000 free Class A → **billed** | 50 GiB / 30 days | Small but real billing risk | High | Not free as-is |
| AWS Lambda + EventBridge + S3 | 1 min | Lambda always free (1M req, 400k GB-s); S3 since Jul-2025 via credits ($100 + up to $100; the Free plan closes after 6 months) | CloudWatch | Free plan: account closes at the end; Paid plan: billed | Very high | Not free long-term |
| GitHub Actions (cron) | **5 min minimum**; delays at peak hours; queued jobs may be **dropped**; according to GitHub Docs, in public repos scheduled workflows are automatically disabled after **60 days** without activity | Artifacts not suitable; needs R2/B2 separately | Run logs | Free on public repo | Medium | Worse than Cloudflare |
| Vercel Hobby cron | **Once a day**, with ±59 min precision | — | — | — | — | Ruled out |
| Backblaze B2 (storage only) | — | 10 GB free; free uploads; free egress up to 3× stored | — | Card | Medium | Good complement, not a platform |
| Azure Functions / Deno Deploy / Netlify / Supabase | Not verified in this session | — | — | — | — | See Caveats |

**Why no alternative wins:**

- **GitHub Actions** guarantees neither the interval nor the execution. GitHub Docs document it like this: "scheduled events can be delayed during periods of high load… high load times include the start of every hour. If the load is sufficiently high enough, some queued jobs may be dropped". For a time series you will present to employers, random gaps are a visible defect.
- **GCP**: the GCS free tier (5,000 Class A/month, aggregated across us-west1, us-central1 and us-east1 according to the Google Cloud "Storage pricing" page) is 38 times smaller than your writes. You would have to bundle (hourly tar), which breaks your one-object-per-response layout.
- **AWS**: new accounts since 15-Jul-2025 get credits and a 6-month Free plan that closes the account. Only Lambda remains "always free"; storage does not.
- **Oracle**: it is the most "free" in resources (VM + 200 GB + 10 TB egress), but your workload is exactly what Oracle calls idle in its "Always Free Resources" documentation (CPU p95 < 20% and network < 20% over 7 days). Oracle warns by email and *stops* the instance (it can be restarted). Upgrading the account to Pay-As-You-Go avoids reclamation according to Oracle's own email, but introduces billing risk.

### 3. Logs: are the platform's logs enough?

**No.** Workers Logs on Free: 200,000 events/day and 3 days retention. Your volume would be \~1,440 invocation logs plus \~6,000 `print()` per day, which fits comfortably. Cloudflare announces that from **1-Dec-2026** Workers Logs will move to "Cloudflare Observability pricing". A secondary source cites for Free "0.5 GB per day" and "seven days of retention", but I have not verified it on the official page. In any case, 3–7 days don't cover your 1–2 week download cycle. `wrangler tail` is real-time only. **Keep the JSONL request log written by the script itself in R2** (including failures: status, latency, bytes, error), one object per invocation. In addition, the platform logs remain as a short-term diagnostic layer: cpuTime, `exceededCpu`, exceptions.

## Details

### Required script adaptations (high level)

- **Loop → handler.** `class Default(WorkerEntrypoint): async def scheduled(self, controller, env, ctx)`, with one pass per invocation and no `sleep`.
- **Static feeds every 15 min.** Use a single cron `* * * * *` and decide with `minute(scheduledTime) % 15 == 0`. You can also use two crons (`* * * * *` and `*/15 * * * *`) and branch on `controller.cron`, knowing that at minute 0/15/30/45 both fire. So that the 1-min tick doesn't carry all the static work within the same CPU budget, you can offset the static feeds (e.g. `minute % 15 == 7`).
- **Bicing index.** Cache the URLs from `gbfs.json` in a module variable (the isolate *may* survive between invocations, but it is not guaranteed) and persist them in R2 (`state/bicing_index.json`): rewritten every 15 min and read on cold start. That is about \~43k Class B/month, within quota.
- **No filesystem.** Write directly with `env.BUCKET.put("raw/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz", body)`. You keep your layout and UTC timestamps.
- **JSONL log.** Accumulate one line per request in memory and write a single `logs/<date>/<ts>.jsonl` object at the end of the handler, ideally with `ctx.waitUntil`. Catch exceptions per feed so that one failure doesn't take down the rest.
- **CPU cost.** Avoid `json.loads` of the payload. If you need metadata (`last_updated`), extract it from the headers or store the raw body. Measure `cpuTime` in Workers Logs for 7 days before considering the system good.

### High-level architecture (no setup steps)

Cron Trigger (1 min, UTC) → Worker (JS or Python) → `fetch` of the GBFS feeds → gzip → R2 binding (`raw/…`, `logs/…`, `state/…`) → every 1–2 weeks `rclone copy`/`sync` from the R2 S3 endpoint to local (free egress) → deletion in R2 (`rclone delete` or a lifecycle rule; deleting in R2 does not consume quota in any relevant way) → local Spark: bronze (raw) → silver (normalized) → gold.

## Recommendations

1. **Start with Cloudflare Workers + R2.** Activate R2 with a card and set up billing/usage alerts in the dashboard.
2. **Prototype the worst case first** (AMBici `free_bike_status` at 1 min) and watch `cpuTime`/`exceededCpu` for 3–7 days.
   - If there are recurring failures with Python, move the capturer to JS/TS with `CompressionStream` and keep Python for processing.
   - If you'd rather not leave Python, lower `free_bike_status` to 5 min.
3. **Keep your JSONL request log in R2.** It is your source of truth about capture completeness and, in addition, an excellent "data quality" table for the portfolio (gaps, latencies, HTTP errors).
4. **Fallback:** Oracle Always Free VM with your current scripts under systemd and download via rsync. Watch for Oracle's "idle" emails. If you care more about market relevance than a few cents, consider GCP e2-micro instead of Oracle.
5. **Don't use** GitHub Actions as the main scheduler (gaps, 5 min, automatic disabling after 60 days without activity in public repos according to GitHub Docs), nor Vercel Hobby (daily).

## Caveats

- **Not verified in this session:** the real size of AMBici's `free_bike_status` (estimated at \~0.5 MB from your figures); whether `urllib.request` works in Python Workers; whether restoring the Pyodide snapshot counts against the 10 ms; the CPU cost of `CompressionStream` called from Python; and the limit of 3 Cron Triggers *per Worker* on Free, which comes from secondary sources (the official doc gives 5 per account).
- **Imminent change:** Workers Logs pricing changes on 1-Dec-2026. Review it before that date.
- **Backblaze B2:** there is contradictory information. The old help page gives 2,500 free Class B and C transactions per day. 2026 sources cite the current pricing page: Class A/B/C free since 1-May-2026 and only Class D (event notifications) with a daily quota. Check the official page if you use it.
- **GitHub Actions:** the Actions terms of use have historically restricted using it as generic compute unrelated to the software project. I could not re-verify it; it is another reason not to base the capture on Actions.
- **Azure Functions, Deno Deploy, Netlify and Supabase** were not verified against current documentation in this session. I don't include them as candidates because none of them combines 1-min cron, free object storage with hundreds of thousands of writes per month, and S3-compatible download better than Cloudflare.
- **Oracle Always Free:** reclamation *stops* the instance, it does not delete it (according to Oracle emails cited by users). Even so, it causes gaps in the series.

## Sources

1. [Cloudflare Cron Triggers Not Firing? Limits & the Fix](https://runhooks.app/blog/cloudflare-workers-cron-triggers-limits/)
2. [--- description: Enable your Worker to be executed on a schedule.](https://developers.cloudflare.com/workers/configuration/cron-triggers/index.md)
3. [Limits](https://developers.cloudflare.com/workers/platform/limits)
4. [Cloudflare Workers Pricing: Free vs Paid (2026)](https://www.anygen.io/showcase/cloudflare-workers-pricing/index.html)
5. [Pricing · Cloudflare Workers docs](https://developers.cloudflare.com/workers/platform/pricing/)
6. [Chapter 3: Workers: The Core Compute Primitive](https://architectingoncloudflare.com/chapter-03/)
7. [Cloudflare Python Workers: Production ASGI & Connection Management](https://www.sitepoint.com/asgi-microservices-on-cloudflare-python-workers/)
8. [How Python Workers Work · Cloudflare Workers docs](https://developers.cloudflare.com/workers/languages/python/how-python-workers-work/)
9. [Python Workers are now generally available](https://blog.cloudflare.com/python-workers-ga/)
10. [Cron triggers are now supported in Python Workers · Changelog](https://developers.cloudflare.com/changelog/post/2025-04-22-python-worker-cron-triggers/)
11. [Python Workers Reach GA on Cloudflare, with Questions about Cold Starts and Upstream Maintenance - InfoQ](https://www.infoq.com/news/2026/09/cloudflare-python-workers-ga/)
12. [Fetch · Cloudflare Workers docs](https://developers.cloudflare.com/workers/runtime-apis/fetch/)
13. [Standard Library](https://developers.cloudflare.com/workers/languages/python/stdlib/)
14. [--- title: Pricing](https://developers.cloudflare.com/r2/pricing/index.md)
15. [Cloudflare Workers and Pages Pricing: What It Really Costs](https://blog.blazingcdn.com/en-us/cloudflares-pricing-for-developers-a-closer-look-at-workers-pages)
16. [Cloudflare Public Bug Bounty disclosed on HackerOne: Bypass R2...](https://hackerone.com/reports/2170559)
17. [Why using R2 free tier involves giving card info? - Billing - Cloudflare Community](https://community.cloudflare.com/t/why-using-r2-free-tier-involves-giving-card-info/945179)
18. [Workers Logs](https://developers.cloudflare.com/workers/observability/logs/workers-logs/)
19. [github.com](https://github.com/dom96/pycloud)
20. [Every-minute cron ticks are killed by the Workers Free 10 ms CPU limit on cold isolates since 1.1.0 — scheduled work is lost overnight · Issue #3858 · emdash-cms/emdash](https://github.com/emdash-cms/emdash/issues/3858)
21. [Keep the every-minute cron under the Free plan's 10 ms CPU limit by pichnarin-c137 · Pull Request #204 · itsupan/sns](https://github.com/itsupan/sns/pull/204)
22. [Python Workers redux: fast cold starts, packages, and a uv-first workflow](https://blog.cloudflare.com/python-workers-advancements/)
23. [Python cold start improvements · Changelog](https://developers.cloudflare.com/changelog/post/2025-12-08-python-cold-start-improvements/)
24. [Workers - Python cold start improvements - Changelog - Cloudflare Community](https://community.cloudflare.com/t/workers-python-cold-start-improvements/865416)
25. [blog.cloudflare.com](https://blog.cloudflare.com/author/dominik/rss)
26. [Cloudflare Workers Limits 2026: Free vs Paid Plan Guide](https://markaicode.com/benchmarks/cloudflare-workers-scalability-benchmark/)
27. [Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
28. [Oracle Cloud Always Free Tier — Grokipedia](https://grokipedia.com/page/Oracle_Cloud_Always_Free_Tier)
29. [GCP Free Tier Complete Guide 2026 — Every Free Service, Real Limits, and Hidden Costs](https://agentdeals.dev/gcp-free-tier-2026)
30. [Cloud Scheduler pricing](https://cloud.google.com/scheduler/pricing)
31. [AWS Free Tier in 2026: what a new account gets](https://codemithra.com/aws-free-tier-2026-avoid-charges/)
32. [AWS Free Tier now offers \$200 in credits and 6-month free plan to explore AWS at no cost](https://aws.amazon.com/about-aws/whats-new/2025/07/aws-free-tier-credits-month-free-plan/)
33. [Usage & Pricing for Cron Jobs](https://vercel.com/docs/cron-jobs/usage-and-pricing)
34. [Backblaze B2 Pricing: 2026 Cost Guide](https://www.zerobuffer.io/blogs/backblaze-b2-pricing)
35. [Backblaze B2 Cloud Storage: 10 GB Storage Free](https://freetier.co/directory/products/backblaze-b2-cloud-storage)
36. [AWS Free Tier in 2026: What Changed, What's Still Free, and What Will Surprise You](https://infratally.com/articles/aws-free-tier-2026/)
37. [Cloudflare sweep 2026-08-25 to 2026-10-08, part 2 of 2: changelog, blog, releases, pricing and incidents against our surfaces · Issue #42 · TheColliery/.github](https://github.com/TheColliery/.github/issues/42)
38. [Python Worker Examples · Cloudflare Workers docs](https://developers.cloudflare.com/workers/languages/python/examples/)
39. [Scheduled Handler · Cloudflare Workers docs](https://developers.cloudflare.com/workers/runtime-apis/handlers/scheduled/)
40. [Scheduled Handler](https://docs.cloudflare.com/workers/runtime-apis/handlers/scheduled/)
41. [Bindings (env) · Cloudflare Workers docs](https://developers.cloudflare.com/workers/runtime-apis/bindings/)
42. [Understanding B2 Pricing Structure](https://help.backblaze.com/hc/en-us/articles/217667478-Understanding-B2-Pricing-Structure)
43. [Oracle OCI will randomly shut your instances down, which is super annoying. I st...](https://news.ycombinator.com/item?id=36008957)
44. [Compute instance idle? — Cloud Customer Connect](https://community.oracle.com/customerconnect/discussion/663398/compute-instance-idle)
