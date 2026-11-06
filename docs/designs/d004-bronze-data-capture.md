<!--
Design doc template. A design doc is the working document of one task: Spec (what and why), Plan (how), Steps (implementation), Close (what was delivered).
It is detailed enough that Code can implement it without making design decisions.
Sections marked Optional are kept only when they apply.
-->

# Design: Bronze data capture

- **Task:** T039
- **ADRs:** [ADR-0005](../decisions/0005-utc-for-all-stored-timestamps.md), [ADR-0006](../decisions/0006-raw-layer-keeps-source-responses-untouched.md), [ADR-0011](../decisions/0011-cloudflare-workers-r2-for-realtime-capture.md), [ADR-0012](../decisions/0012-collectors-decoupled-by-output-contract.md), [ADR-0018](../decisions/0018-medallion-architecture.md), [ADR-0020](../decisions/0020-bronze-as-captured-objects.md), [ADR-0021](../decisions/0021-retention-per-layer.md), [ADR-0023](../decisions/0023-storage-security-baseline.md), [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md)
- **New ADRs from this doc:** [ADR-0035](../decisions/0035-cloud-resource-naming.md) (D1); [ADR-0036](../decisions/0036-log-convention-across-components.md) (D9), which supersedes [ADR-0030](../decisions/archive/0030-pipeline-logs.md); [ADR-0037](../decisions/0037-test-fixtures-per-component.md) (DL15), which supersedes [ADR-0009](../decisions/archive/0009-trimmed-source-samples-as-test-fixtures.md)

## Status

<!-- State: Draft 📝 · Ready for implementation 🎬 · In progress 🔄 · Complete ✅.
Phase: the blocks and reviews completed.
Current step: the step being implemented, or —. -->

- State: Ready for implementation 🎬
- Phase: [x] Spec · [x] Plan · [x] Plan review · [x] Steps · [x] Steps review
- Current step: —
- Next: Step 1 (`/implement d004`).

## 1. Spec — what and why

<!-- What the result does seen from outside, not how it is built. The test: if whoever uses the result would notice a change, it belongs here; if not, it belongs to the Plan. External systems and their data (feeds, fields) may be named. -->

### 1.1 Context

<!-- 2–4 sentences for a reader with no prior context: the problem or need and why it matters now; who or what uses the result; where things stand today, including any design or spike this builds on. No solution here: it starts in Decided at framing. For a correction: current vs expected behaviour and how to reproduce it. -->

The data pipeline needs a continuous, trustworthy record of the AMBici and Bicing feeds in the bronze layer. Today that record comes from the interim Worker `capture-v4`, left running by [s006](../spikes/s006-cloudflare-capture.md), which writes to the spike's bucket `bikesharing-capture-spike`. That deployment was built to answer the spike's questions, not for production: [s006 › Inputs for the production design](../spikes/s006-cloudflare-capture.md#inputs-for-the-production-design) lists its known gaps, and it captures every static feed in the same pass once per hour. Those passes reached 23–28 ms of CPU in the spike's window, against the 10 ms limit; the average per run has since stayed at or below 5 ms. This task replaces that Worker and that bucket with production capture.

### 1.2 Decided at framing

<!-- Optional. One heading per decision about what the result does. In this order, so the reader finds what matters first:
1. The decision and why, in one short paragraph.
2. What would change it, and what would not, each with the action to take. Only when a later event could reopen it.
3. The options rejected.
4. The artefact that fixes it, in whatever form the decision needs (e.g. a mapping table, a page map, a weighted matrix). An artefact that does not fit here or must outlive the design goes in its own file: the Plan decides where it lives and its format, File layout lists it, and this decision links to it.

A security decision lists its threats in this table, with IDs `TH1`, `TH2`… per document:

| # | Threat (STRIDE) | Impact | Control | Requirement |
|---|---|---|---|---|
| `TH1` | | | | |
-->

#### D1. Bronze bucket and key convention

Bronze lives in `bikesharing-bronze`, and the key layout of [ADR-0012](../decisions/0012-collectors-decoupled-by-output-contract.md) stays as it is. The first prefix names the kind of content, not the layer: the bucket already names the layer, and the bucket lock applies per prefix, so content with different lock rules needs its own prefix ([ADR-0023](../decisions/0023-storage-security-baseline.md)). A new source, such as a weather feed, goes under `raw/<source>/` and is covered by the existing lock rule.

The project-wide convention is that buckets are named `bikesharing-<content>`, and a layer prefix is used only when a bucket holds more than one layer. The lakehouse bucket is therefore `bikesharing-lakehouse`, with `silver/` and `gold/`. Static assets are not stored in a bucket, since they are published by redeploying ([ADR-0033](../decisions/0033-data-published-by-redeploying-static-assets.md)).

Rejected: sources at the bucket root (`<source>/…`). It shows the sources one level higher, but mixes them with the operational prefixes and needs one lock rule per source.

```text
bikesharing-bronze/
├── raw/<source>/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz   locked
├── logs/                                                         locked
└── state/                                                        not locked
```

#### D2. Spike data moved to production

`V4/raw/` is copied to `bikesharing-bronze` under `raw/`, without the `V4/` prefix, before the bucket lock is enabled. Bronze cannot be rebuilt and these responses cannot be captured again; they already meet the output contract ([ADR-0012](../decisions/0012-collectors-decoupled-by-output-contract.md)). `V4/logs/` and `V4/state/` are not copied: the log structure will change, and `state/` is rebuilt by capture. Copied objects therefore have no capture logs in production.

The spike logs are queried once before they are deleted, because they have only been analysed within the [s006](../spikes/s006-cloudflare-capture.md) window and can reveal unknown events.

Rejected: starting production with an empty bucket. It loses the captured responses that exist only in the spike's bucket.

#### D3. Feed cadence

This table lists every feed capture takes. The dynamic feeds are captured every minute, the cadence of the spike's capture. Each static feed is captured at the cadence its observed changes justify, because a change that is not captured cannot be recovered. Over 12.5 days of hourly captures (2026-10-14 to 2026-10-26), comparing the `data` field, `station_information` changed 68 times in Bicing and 4 times in AMBici; two other feeds changed once and the remaining ten never did. The GBFS `ttl` does not help: nearly every feed declares 60 s or 0 regardless of how often it changes.

| Cadence | Feeds |
|---|---|
| Every minute (dynamic) | `station_status` of each source, `free_bike_status` of AMBici |
| Hourly | `station_information` of each source; the index (`gbfs`) of each source, at its refresh (D5) |
| Daily | The other 12 static feeds: `system_information`, `system_pricing_plans`, `system_regions`, `vehicle_types` and `geofencing_zones` of each source, `system_hours` of AMBici, `gbfs_versions` of Bicing |

A change in a daily feed is recorded up to 24 h late, and two changes in one day keep only the last one.

If a daily feed starts changing more than once a day as a habit, move it to hourly. A daily feed that changes occasionally does not reopen this decision.

Rejected: every 2 days or weekly for the daily feeds. Weekly saves about 1.2 MB per year against bronze's roughly 2.9 GB per month, and delays a change by up to 7 days. **DL4**

#### D4. Static feeds spread across passes

Each capture pass carries the dynamic feeds and at most one extra fetch, either a static feed, an index refresh (D5) or the heartbeat (D10), so dynamic feeds are captured every minute and no extra fetch adds to another's CPU time. [s006](../spikes/s006-cloudflare-capture.md) measured about 5 ms for a dynamic pass and 23–28 ms with the 16 feeds of a static pass, which estimates 1.5 ms per added feed and about 6.5 ms for a pass with one extra fetch. Extra fetches run at fixed, distinct minutes; 132 of the 1,440 daily passes carry one. While a source has no valid index, its passes fetch only that index, in place of its feeds and extras (D8), so they cost less than a normal pass.

CPU time can shift without any change of ours. During the spike's capture, median source latency moved from about 270 ms to 38 ms on 2026-10-29 at 22:07 UTC, and to about 145 ms on 2026-11-03 at about 08:00 UTC, while the average CPU per run rose from 2–3 ms to almost 5 ms; the only deployment was on 2026-10-14. Both shifts coincided with a change in the second at which the cron starts, which suggests a move of the Worker by Cloudflare; this is not confirmed. Passes with a static feed therefore keep a margin below the limit.

If passes with an extra fetch exceed the 10 ms limit in production, run them in their own executions.

Rejected: separate executions for static feeds from the start. They give the lowest peak, but add complexity and depend on Cloudflare starting two independent executions in the same minute, which is unverified.

#### D5. Hourly index refresh

Each source's index (`gbfs` feed) is refreshed once per hour, independently of the static feeds, at a different minute for each source. If a feed's URL changes, capture picks it up within an hour, which bounds the dynamic data lost. The size of both indexes did not change in 22 days of hourly reads, so the refresh rarely finds anything new, but its cost is small: 48 fetches and up to 96 writes per day.

Each index response is stored under `raw/` like any feed, whether the index is valid or not, so its history, including a rejected index, can be rebuilt; only a valid index replaces the last one kept for capture (D8).

Rejected:

- Daily refresh: a changed URL could cost up to 24 h of dynamic data, which cannot be captured again.
- Daily refresh, and also on a feed's 404: it loses the least data, but adds logic that a brief 404 would trigger needlessly. **DL4**

#### D6. Capture completeness target

Each dynamic feed has a clean capture in at least 99.5% of the minutes of each calendar month, which allows 216 minutes of failures in a 30-day month. A minute is clean for a feed when an object of that feed is stored under `raw/` for that minute (D9). The first 7 days of production are checked against the same threshold; the monthly follow-up belongs to the data quality task (D7). Over 21 full days of the spike's capture (2026-10-15 to 2026-11-04), each feed reached 99.81–99.82%, or about 78 minutes per month, and fell below 99.5% on a single day. The target follows the SRE practice of an indicator with an objective and an error budget. Static feeds have no percentage, because one failure in a daily feed is a whole day without data; a failure there is handled as an individual event.

A missed month leads to reviewing its cause, with no automatic action. If capture stays well above the target for several months, raise the target.

Rejected:

- 99.9%: its 43-minute budget is below the failures already observed.
- 99%: its 432-minute budget could hide a real degradation.

#### D7. Quality questions answered from the pipeline

The pipeline answers quality questions, including completeness (D6), and capture only provides the data to answer them, because a derived figure can be rebuilt from the logs and calculating it in capture would add CPU. Capture's logs must allow an efficient answer, in Worker CPU, R2 storage and operations, and pipeline compute on Modal. Building the calculation and its storage belongs to the data quality task.

#### D8. Capture failure behaviour

Capture retries only what cannot be recovered in another way, using bounded retries, and records every failure. A failed fetch leaves no data yet, and the next scheduled capture brings a newer response; a failed write loses a response already fetched. Over 22 days of the spike's logs there were 57 source failures and 10 writes lost to R2 internal errors, out of 103,664 log lines.

| Event | Behaviour |
|---|---|
| A source takes longer than 60 s | The fetch is abandoned and logged as a failure. This keeps a hung request from losing the whole pass, and it would have dropped 11 valid responses in 22 days. |
| A source fails | No retry in the pass. The failure is logged and the next scheduled capture applies, so a change in a daily feed can be recorded up to 48 h late. |
| A data write fails | Up to 2 retries with a short wait. A key that already exists counts as written, not as a failure. |
| A log write fails | Up to 2 retries with a short wait. If it still fails, the error goes to the Workers logs. |
| An index refresh fails or returns an invalid index | Capture keeps the last valid index and logs the error. An index is valid when every entry has `name` and `url`, and it includes every feed listed in D3. |
| A source has no valid index yet, as on the first pass | Capture refreshes that source's index on every pass and fetches none of its feeds until the index is valid, an exception to D4. |

Each key is written once. Duplicate passes start at different seconds, so their keys differ; both objects are kept and the pipeline deduplicates them ([d002 › R13](d002-requirements.md#requirements)). In the unobserved case of two passes in the same second, the existing-key rule applies. `latency_ms` is recorded whenever the source responds, and is null only when no response arrives.

Rejected:

- Timeouts of 30 s (drops 35 valid responses with no CPU saving, since waiting uses no CPU) and no timeout (a hung request can lose the pass).
- Retrying source failures in the pass: it lengthens passes for little gain, since a source that is down usually stays down during the retries.
- Retrying failed static feeds in later passes: it adds state and logic for about 5 lost days per year across the daily feeds, which rarely change.
- Ignoring only the invalid index entry: the feed would stop being captured even with a known URL. Merging valid entries per feed would avoid that, but only helps when two index problems coincide, which was not observed.

#### D9. Capture logs

Capture writes one log object per pass as JSON Lines, under `logs/date=<YYYY-MM-DD>/<run_id>.jsonl`, where `run_id` is the pass's capture time in the [ADR-0012](../decisions/0012-collectors-decoupled-by-output-contract.md) key format. The format follows [ADR-0036](../decisions/0036-log-convention-across-components.md), one log convention for every component, which supersedes [ADR-0030](../decisions/archive/0030-pipeline-logs.md) to add two common fields: `component` names the part of the system that wrote the event, following the practice of `service.name` in OpenTelemetry, and `version` identifies the deployed code of that component. Every event therefore carries `ts`, `level`, `component`, `version`, `run_id` and `event`, plus the fields of its event.

In capture, `component` is `capture` and `version` is the Worker's version ID.

| Event | Level | Own fields |
|---|---|---|
| `feed_captured` | `info` | `source`, `feed`, `status`, `latency_ms`, `bytes`, `attempts`, `recompressed` |
| `feed_failed` | `error` | `source`, `feed`, `status`, `latency_ms`, `attempts`, `error_type`, `error` |
| `index_refreshed` | `info` | `source`, `status`, `latency_ms`, `bytes`, `attempts`, `recompressed`, `unknown_feeds` |
| `index_rejected` | `error` | `source`, `status`, `latency_ms`, `attempts`, `error_type`, `error` |
| `heartbeat_sent` | `info` | `status`, `latency_ms` |
| `heartbeat_failed` | `warning` | `status`, `latency_ms`, `error_type`, `error` |

`attempts` counts write attempts, and is 0 when the source fails. `error_type` is one of `http`, `timeout`, `network`, `too_large`, `write` or `invalid_index`; the event tells whether it came from a feed, an index or the heartbeat. `level` is `info`, `warning` for a failure that does not affect the data, such as the heartbeat's, or `error`. `unknown_feeds` lists the feeds in the index that are not listed in D3, and is usually empty; a feed that the source removes makes the index invalid (D8). `recompressed` is true when the response did not arrive as gzip and capture compressed it before storing; capture relies on an undocumented option to keep the source's gzip ([s006](../spikes/s006-cloudflare-capture.md), F9), so this flags a change in the source or the runtime.

These fields answer the following capture questions, the starting point for T042:

- Is the completeness target (D6) met, and which minutes are missing?
- Is a source degrading, or is a response size unusual?
- Are there duplicate or late passes, and does each object match a log line?
- Did a failure come from the source, a timeout or R2, and is R2 failing even when retries succeed?
- Which deployed code produced this data?
- Has a source added or removed a feed?
- Do responses still arrive as gzip, or is capture compressing them?

The objects under `raw/` are the record of what was captured, and the logs explain failures: a log write can fail after its data was stored (D8).

Questions that need the response's content, such as whether a source keeps returning HTTP 200 with frozen data, belong to the pipeline.

One object per pass meets D7's criteria. It costs about 30–35 MB per month and 43,200 writes (4.3% of R2's free Class A quota), and it adds no CPU beyond the write already measured. The pipeline reads only new objects once and consolidates them in the data quality table (T042); the originals stay under the bucket lock. Pipeline compute is unmeasured, so T042 validates it.

Rejected:

- Daily compaction in capture: reading 1,440 objects does not fit the 10 ms CPU limit.
- Logging failures only: it loses the latency and sizes of clean captures, which revealed the latency shifts and set the timeout in D8.
- Showing the origin only through a prefix in the event name (`capture.feed_captured`): it needs no ADR change, but mixes two meanings in one field and depends on a naming convention. **DL4** **DL7** **DL14**

#### D10. Capture heartbeat

Capture signals a heartbeat to Healthchecks.io once per hour, the service [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md) chose for the pipeline, which emails the owner when no signal arrives within the period plus 1 h of grace. The monitor sits outside Cloudflare, because a stopped Worker cannot report its own stop. The pass sends the signal only if it stored all three dynamic feeds listed in D3, so the signal means that data is being stored, not just that the Worker ran: an outage of R2 or of a source that lasts for hours also raises the alert. The goal is that capture never stays down for days unnoticed, which an alert within about 2 h meets, rather than a fast reaction. A failed signal does not affect capture, and is logged as `heartbeat_failed` (D9) without the signal URL (D12).

One failed signal does not alert, since the next one arrives within the grace. An outage shorter than about an hour may raise no alert, and shows in completeness (D6) instead. The signal costs nothing on Cloudflare's Free plan: it is an outgoing request from an existing pass.

What this alert does not cover: a static feed or an index failing repeatedly, and a source returning HTTP 200 with frozen data, both quality checks in T042; and CPU peaks, which the Worker cannot measure.

Rejected:

- Every minute or every 5 minutes: faster alerts than the owner can act on, at a higher CPU cost.
- Twice a day: the same cost as hourly, with alerts up to about 24 h late.
- A signal on every run, whatever it stored: it would miss a Worker that runs but stores nothing.

#### D11. Switch from spike capture to production

Production capture replaces `capture-v4` by running in parallel with it, so the switch leaves no gap in data that cannot be captured again. The overlap also tests production against the spike's capture, minute by minute. It doubles the requests to the sources for its duration, at one per feed and minute, which is accepted since no volume limit has been observed.

1. The production Worker is deployed and captures to `bikesharing-bronze` while `capture-v4` keeps capturing.
2. Once production has stored every feed at least once, `V4/raw/` is copied, for each source and feed, up to the last pass before that feed's first object in production (D2), so the copy leaves no gap, adds no duplicates and no key can collide.
3. The copy is checked by object count per day and feed. If the counts differ, the copy is repeated: the lock is never enabled on an unchecked copy.
4. The bucket lock is enabled.
5. `capture-v4` is stopped, and the queries of D2 run on its complete logs.
6. `bikesharing-capture-spike` is emptied and deleted, together with `capture-v4` and its token, so no access to unused data remains (least privilege, as in [ADR-0023](../decisions/0023-storage-security-baseline.md)). A spike that needs a test bucket creates and removes its own, as [s010](../spikes/s010-storage-table-format.md) did.

The lock is enabled only after the check, as [ADR-0023](../decisions/0023-storage-security-baseline.md) requires, because under the lock a wrong copy can no longer be corrected; production's first hours stay unprotected until then.

Rejected:

- Stopping `capture-v4` before deploying production: it is simpler, but leaves a gap that grows if the deployment fails.
- Keeping the spike's bucket as a test bucket: its name breaks the convention of D1, and it keeps an old token alive. **DL18**

#### D12. Capture security

One STRIDE pass over D1–D11 keeps the threats with a real chance or a lasting impact; the storage-wide baseline of [ADR-0023](../decisions/0023-storage-security-baseline.md) still applies. Bronze's lock makes some impacts permanent, so their controls act before the write. The response size limit leaves room for legitimate growth, such as a source publishing real geofencing zones, since the largest response observed is 57 KB.

| # | Threat (STRIDE) | Impact | Control | Requirement |
|---|---|---|---|---|
| `TH1` | Spoofing: an HTTP request triggers capture passes | Extra writes, CPU and duplicate data, kept forever under the lock | No HTTP handler in the production Worker; its public URL stays disabled | R21 |
| `TH2` | Denial of service: an oversized response | Storage kept forever under the lock, and its cost | Responses over 10 MB are rejected and logged | R22 |
| `TH3` | Information disclosure: the heartbeat URL ends up in a log | The secret cannot be deleted from a locked log | Errors of the heartbeat signal never include its URL | R23 |
| `TH4` | Tampering: the bucket lock is misconfigured | Bronze can be deleted or overwritten | After enabling it, overwriting an existing object is checked to fail | Done when |
| `TH5` | Spoofing: the heartbeat URL leaks | False signals hide an outage | Accepted, as in [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md); it gives access to nothing else | Accepted |
| `TH6` | Elevation of privilege: the deployment token leaks | Code that writes junk or alters `state/` is deployed | A deployment token scoped to this Worker only, held by the owner | Done when |

### 1.3 Requirements

<!-- Optional. The acceptance criteria, cited by number in the Test plan and the steps. They translate Decided at framing and cite the decision they come from; nothing is decided here.
One behaviour per requirement, verifiable, with a measurable threshold where one applies. Written in EARS:
- Ubiquitous: The <system> shall <response>.
- Event: When <trigger>, the <system> shall <response>.
- State: While <state>, the <system> shall <response>.
- Unwanted: If <condition>, then the <system> shall <response>.
- Optional: Where <feature is included>, the <system> shall <response>.
Only requirements specific to this task; project-wide rules (CLAUDE.md, ADRs) are not repeated. -->

- **R1** The capture shall store the response of each dynamic feed listed in D3 every minute in `bikesharing-bronze`, under the key layout of D1, except as R13 allows. (D1, D3, D4)
- **R2** The capture shall capture `station_information` of each source once per hour. (D3)
- **R3** The capture shall capture each of the 12 daily static feeds once per day. (D3)
- **R4** The capture shall make at most one extra fetch per pass (a static feed, an index refresh or the heartbeat), at fixed and distinct minutes, except as R13 allows. (D4, D5, D10)
- **R5** The capture shall refresh each source's index once per hour, at a different minute for each source, except as R13 allows. (D5)
- **R6** The capture shall fetch each feed from the URL in its source's last valid index. (D5)
- **R7** If a source takes longer than 60 s to return its complete response, then the capture shall abandon the fetch and log it as a failure. (D8)
- **R8** If a source fails, then the capture shall log the failure without retrying in the same pass. (D8)
- **R9** If a data or log write fails, then the capture shall retry it up to 2 times with a short wait. (D8)
- **R10** If a write finds its key already stored, then the capture shall count it as written. (D8)
- **R11** If a log write still fails after its retries, then the capture shall write the error to the Workers logs. (D8)
- **R12** If an index refresh fails or returns an invalid index, because an entry lacks `name` or `url` or a feed listed in D3 is missing, then the capture shall keep the source's last valid index and log the rejection. (D8)
- **R13** While a source has no valid index, the capture shall refresh that source's index on every pass and fetch none of its feeds. (D4, D8)
- **R14** The capture shall record `latency_ms` whenever the source responds, and leave it null only when no response arrives. (D8)
- **R15** The capture shall write one log object per pass under `logs/date=<YYYY-MM-DD>/<run_id>.jsonl`, whose events carry `ts`, `level`, `component`, `version`, `run_id` and `event`. (D9)
- **R16** The capture shall log the events and fields listed in D9, including `unknown_feeds`. (D7, D9)
- **R17** When the heartbeat pass has stored all three dynamic feeds listed in D3, the capture shall send the heartbeat signal. (D10)
- **R18** If the heartbeat pass has not stored all three dynamic feeds listed in D3, then the capture shall not send the heartbeat signal. (D10)
- **R19** If no signal arrives within 1 h plus 1 h of grace, then the monitor shall email the owner. (D10)
- **R20** If the heartbeat signal fails, then the capture shall continue unaffected and log the failure. (D9, D10)
- **R21** The production Worker shall run only from its cron trigger, with no HTTP handler, and its public URL shall stay disabled. (D12, TH1)
- **R22** If a response exceeds 10 MB, then the capture shall reject it and log the failure. (D12, TH2)
- **R23** The capture shall not include the heartbeat URL in any log or error. (D12, TH3)
- **R24** When an index refresh receives a successful response, the capture shall store it under `raw/<source>/gbfs/`, whether or not the index is valid. (D3, D5)

### 1.4 Done when

<!-- Optional. Only what closes this task and Requirements cannot express: operational actions, checks on real data, understanding. The general closing rule is checked in `.claude/skills/implement/review.md`. -->

- `V4/raw/` is copied up to the cutoff of each feed and checked by object count before the bucket lock is enabled. (D2, D11)
- The bucket lock is enabled, and overwriting an existing object fails. (D11, TH4)
- The queries of D2 have run on the spike's complete logs. (D2)
- `bikesharing-capture-spike`, `capture-v4` and its token are deleted. (D11)
- The probe's test bucket `bikesharing-t039-write-once` and the token `bikesharing-t039-completeness` are deleted. ([ADR-0035](../decisions/0035-cloud-resource-naming.md))
- The deployment token is scoped to the production Worker only. (TH6)
- Every pass stays below 10 ms of CPU over the first 3 full days of production, checked as in [Deployment](#deployment). (D4)
- Each dynamic feed has a clean capture in at least 99.5% of the minutes of the first 7 full UTC days of production, checked as in [Switch tooling](#switch-tooling). (D6)

### 1.5 Out of scope

<!-- Optional. What someone could expect and will not be done, each item pointing to the task that covers it. -->

- Calculating and storing completeness and other quality answers (D7), from the questions and fields in D9 — T042
- Quality checks capture does not make: repeated failures of a static feed or an index, and HTTP 200 with frozen data (D10) — T042
- Fixture entries chosen for variety of records (empty, full or out-of-service stations), which only code that reads them can use ([Fixtures](#fixtures)) — T040
- Citing the finding IDs of other documents with their source, such as s008's in `docs/testing-strategy.md` — T058
- Whether the pipeline gets a component folder of its own, like `capture/`, instead of `src/` and `tests/` at the root — T040
- Centralising quality rules and targets, such as D6's, in one place — T042

## 2. Plan — how

<!-- 2-3 sentences -->

### 2.1 Approach

<!-- Detailed plan organized by #### blocks.
Block `3. Steps` is written using this plan.
If some block contains `options considered`, include them with pros and cons.
-->

#### Component layout

Production capture is one Worker for both sources, since every pass carries the dynamic feeds of both and the heartbeat depends on all of them (D4, D10). It lives in `capture/`, named after its `component` in the logs (D9), and is written in JavaScript. The code follows *functional core, imperative shell*: the schedule, the source table, index validation and event building are pure functions; fetching, writing and signalling are a thin layer around them.

Sources are configuration: each entry in `sources.js` names its `kind`, and `adapters/<kind>.js` knows how that kind finds its feed URLs and validates its index (Adapter pattern). A new GBFS source adds one entry; a source that is not GBFS also adds an adapter. The heartbeat requires every dynamic feed in `sources.js`, not a fixed count.

Only `storage.js` accesses the bucket; `index-state.js` and `log.js` go through it. Only `worker.js` and `wrangler.jsonc` depend on the Workers runtime's entry point and trigger.

```text
capture/
├── .nvmrc                Pinned Node version
├── package.json          Dependencies and scripts
├── package-lock.json
├── wrangler.jsonc        Cron trigger, R2 binding, public URL disabled
├── vitest.config.js
├── scripts/
│   └── trim-fixtures.js  Fetches and trims the fixtures (Fixtures)
├── src/
│   ├── worker.js         Entry point: the `scheduled` handler only (R21)
│   ├── sources.js        Source table: id, kind, index URL and feeds by cadence (D3)
│   ├── adapters/
│   │   └── gbfs.js       Reads a GBFS index and validates it (D5, D8)
│   ├── schedule.js       Which extra fetch, if any, runs at each minute (D4, D5, D10)
│   ├── pass.js           One pass: dynamic feeds plus at most one extra fetch
│   ├── fetch.js          Source request with the 60 s timeout and 10 MB limit (D8, D12)
│   ├── index-state.js    Reads and stores each source's last valid index under `state/`
│   ├── storage.js        Object keys, write-once and retries; the only module that accesses the bucket (D1, D8)
│   ├── log.js            Pass events and the log object (D9)
│   └── heartbeat.js      Healthchecks.io signal (D10)
└── test/
    ├── unit/             <module>.test.js
    ├── integration/      The `scheduled` handler in workerd with in-memory R2
    ├── contract/         Producer side of the vectors in `contracts/`
    └── fixtures/         `<source>/<feed>.json` and `manifest.json` (ADR-0037)
```

Options considered:

- **One flat `capture/` folder, sources as configuration (chosen).** One code path for both sources; adding a source is mostly data.
- **`collector/` with one subfolder per source and a shared core.** Matches the earlier rule's guess, but adds structure to separate sources that share all their logic.

#### Pass schedule

`schedule.js` holds the calendar as an explicit table, keyed by the event's `scheduledTime` in UTC, not by the clock, so a late pass still makes its extra fetch. Each source's index refresh comes 5 minutes before its `station_information`, which then uses the refreshed URLs; minute `:00` carries no extra fetch.

| Minute of every hour | Extra fetch |
|---|---|
| `:07` | Bicing index |
| `:12` | Bicing `station_information` |
| `:22` | Heartbeat |
| `:37` | AMBici index |
| `:42` | AMBici `station_information` |

The 12 daily feeds run at minute `:52` of every even hour, alternating sources, so an outage of one hour costs at most one of them:

| Time (UTC) | Source | Feed |
|---|---|---|
| 00:52 | Bicing | `system_information` |
| 02:52 | AMBici | `system_information` |
| 04:52 | Bicing | `system_pricing_plans` |
| 06:52 | AMBici | `system_pricing_plans` |
| 08:52 | Bicing | `system_regions` |
| 10:52 | AMBici | `system_regions` |
| 12:52 | Bicing | `vehicle_types` |
| 14:52 | AMBici | `vehicle_types` |
| 16:52 | Bicing | `geofencing_zones` |
| 18:52 | AMBici | `geofencing_zones` |
| 20:52 | Bicing | `gbfs_versions` |
| 22:52 | AMBici | `system_hours` |

This gives 5 × 24 + 12 = 132 extra fetches per day (D4).

Options considered for the daily feeds:

- **One every 2 hours (chosen).** Source failures tend to cluster; an outage of one hour loses at most one daily feed.
- **All within one hour.** Equally readable, but an outage in that hour loses the day's daily feeds of the affected source.

#### Index state

Every pass reads each source's last valid index from `state/index/<source>.json`; the Worker keeps nothing in memory between passes (stateless processes, 12-factor). The object holds the validated form, independent of the adapter:

```json
{ "refreshed_at": "2026-11-06T10:07:00Z", "feeds": { "station_status": "https://…" } }
```

A refresh that returns a valid index overwrites it; a missing or unreadable object means the source has no valid index (D8). A valid index is adopted only once its response is stored under `raw/`: if that write or the write to `state/` fails after its retries, the refresh is logged as `index_rejected` with `error_type: write`, and the last valid index stays in use. So `index_refreshed` means stored, valid and in use, and the index in use is always in bronze. **DL13** This costs 2 reads per pass, about 86,400 per month, or 0.9% of R2's free Class B quota.

If R2 reads approach the free Class B quota, for example as sources are added, evaluate the in-memory cache below.

Options considered:

- **Read `state/` on every pass (chosen).** Always consistent with the last refresh, with no cache to test.
- **Memory first, `state/` as fallback, as in `capture-v4`.** Saves reads when the isolate is reused, but an isolate that misses the refresh minute keeps a stale index unless the cache also expires.

#### Write-once

`storage.js` writes every object under `raw/` and `logs/` as a conditional put, `onlyIf` with `If-None-Match: *` (RFC 9110 conditional requests): R2 writes only if the key holds nothing, as one atomic operation. A key that already holds an object counts as written (R10), and R2 signals it in two ways:

- **Without the bucket lock:** the put returns `null`.
- **Under the bucket lock:** the put throws, with the code only in the message (`The object is locked by the bucket policy. (10069)`).

So when a conditional put throws, `storage.js` checks the key with `head`: if an object is there, the write counts as done and is not retried; if not, or if `head` also fails, the attempt counts as failed and is retried (R9). This depends on no error code or message, and also covers a write that R2 stored but whose answer was lost. The `head` runs only on that error path. **DL17** Objects under `state/` are overwritten with a plain put.

The write-once probe ran on 2026-11-06 in the test bucket `bikesharing-t039-write-once`, with a lock rule on `locked/`, through the R2 binding in `wrangler dev` with the bucket connected remotely, and against Miniflare's in-memory R2, which the integration tests use (`spikes/cloudflare-capture-spike/js/src/probe-write-once.js`). Every object kept its first body. **DL9**

| Case | R2, no lock | R2, under the lock | Miniflare |
|---|---|---|---|
| Conditional put, new key | Writes | Writes | Writes |
| Conditional put, existing key (`Headers` or `etagDoesNotMatch: "*"`) | `null` | Throws `10069` | `null` |
| Plain put, existing key | — | Throws `10069` | — |

Miniflare answers as R2 without the lock; it does not simulate the lock, so the error path is tested with a fake binding ([Test plan](#26-test-plan)).

Options considered:

- **Conditional put, with `head` on error (chosen).** One atomic operation, and no dependency on the lock or on error messages.
- **Conditional put, reading `10069` in the message as "exists".** No extra operation, but it depends on the text of an error message; if the text changes, stored objects are logged as failed writes.
- **Plain put, reading the lock's error as "exists".** Before the lock is enabled a retry overwrites silently, and it depends on an error message.
- **`head`, then put.** Two operations per object, with a window in which two passes can both write the key.

#### Pass logs

`log.js` collects the pass's events in memory and `pass.js` writes them as one object in a `finally` block, so a pass that fails halfway still writes its log (D9).

| Field | Source |
|---|---|
| `run_id` | The pass's actual start, truncated to the second, in the [ADR-0012](../decisions/0012-collectors-decoupled-by-output-contract.md) key format; also the timestamp of the pass's data keys, so duplicate passes get distinct keys (D8) |
| `ts` | The event's time, ISO 8601 UTC with milliseconds |
| `component` | `capture` |
| `version` | `CF_VERSION_METADATA.id`, the version metadata binding |

The schedule uses `scheduledTime` and the keys use the actual start; the two differ by the seconds the cron starts late. If the log write still fails after its retries, its lines go to Workers Logs, enabled under `observability` in `wrangler.jsonc` (R11).

#### Source fetch

`fetch.js` requests every response with `Accept-Encoding: gzip` and `encodeResponseBody: "manual"`, which keeps the source's gzip bytes undecoded ([s006](../spikes/s006-cloudflare-capture.md), F9); those bytes are stored as received, with no compression work. The fetches of a pass run in parallel, since waiting uses no CPU.

- **Timeout:** `AbortSignal.timeout()` covers the whole response, body included (R7); its expiry is `timeout`. The duration is a parameter, 60 s in production, so tests use milliseconds. **DL9**
- **Size limit:** the body is read as a stream and the fetch is aborted once it exceeds 10 MB, measured on the bytes as received (R22); this is `too_large`. Bicing sends no `content-length`, so the header cannot be trusted for this.
- **A response that is not gzip:** a body whose first two bytes are not the gzip magic number `1f 8b` (RFC 1952) is compressed with `CompressionStream` before storing, and logged with `recompressed: true` (D9). The check reads the bytes, not `Content-Encoding`, so a runtime that stopped honouring `encodeResponseBody` would cost CPU instead of storing plain JSON under a `.json.gz` key (ADR-0012) under the lock. **DL7**
- **Index:** fetched like any feed, stored under `raw/` (R24), then decompressed in memory and validated by its adapter; the decompressed size has the same 10 MB limit.
- **`latency_ms`:** from the request to the end of reading the body, success or failure, once headers have arrived; `null` when none arrive (R14).

#### Tests and contracts

Shared contract vectors live in a top-level `contracts/` folder, owned by neither component; every CI job that reads them runs on any change to `contracts/**` ([ADR-0015](../decisions/0015-contract-tests-by-contract-kind.md)).

What local tests cannot verify, and what covers it (**DL9**, **DL21**):

| Gap | Covered by |
|---|---|
| Whether `encodeResponseBody: "manual"` keeps a source's gzip in workerd | The post-deploy smoke test ([Deployment](#deployment)); simulated sources serve gzip bytes without `Content-Encoding`, so no local test depends on it |
| Whether Miniflare's R2 answers a conditional put as R2 does | The write-once probe, run against both ([Write-once](#write-once)) |
| The bucket lock, which Miniflare does not simulate | The write-once probe and the overwrite check after enabling the lock (TH4) |
| The 60 s timeout, too long for a test | The duration is a parameter ([Source fetch](#source-fetch)) |
| CPU time against the 10 ms limit, unlike Cloudflare's locally | The CPU check of the first 3 days of production ([Deployment](#deployment)) |

Options considered:

- **Top-level `contracts/` (chosen).** Neutral ground for an agreement between two components.
- **Inside the producer, `capture/test/contracts/`.** Next to who defines it, but the pipeline would read inside another component's test folder.

#### Fixtures

`scripts/trim-fixtures.js` builds capture's fixtures from live responses ([ADR-0037](../decisions/0037-test-fixtures-per-component.md)). It runs on the local machine with Node, `npm run fixtures`, using only Node's built-in modules and `fetch`; it is run again when a source changes its format, and its output is committed.

- **Input:** for each source in `sources.js`, its index, then every feed the index lists for it, fetched once from the source.
- **Trimming:** the index is kept whole, since it is the only response capture parses. In every other feed, the list of entries under `data` (stations, vehicles, regions, plans, vehicle types, zones) keeps its first 3 entries, and everything else is kept as received; short lists stay whole. Capture stores feeds as opaque bytes, so which entries are kept changes no code path.
- **Output:** pretty-printed, uncompressed JSON at `test/fixtures/<source>/<feed>.json`, a name that does not change when the fixtures are regenerated. `vitest.config.js` compresses each fixture once, serves those bytes from `outboundService` and passes the same bytes to the tests as a binding, since tests run inside workerd and do not read the repository's files.
- **Provenance:** `test/fixtures/manifest.json` holds one entry per fixture, with `source`, `feed`, `url` and `captured_at` (ISO 8601 UTC), plus `attribution` for Bicing (see its source card); the script rewrites it with the fixtures.

Edge cases are not fixtures: an invalid index, a body that is not gzip, an oversized body, a timeout and the absence of `content-length` are built in memory by each test from a fixture. **DL16**

Options considered:

- **Live fetch, uncompressed JSON with stable names, first entries (chosen).** Current quirks, readable diffs, and tests that survive a regeneration.
- **The spike's local capture as input.** No request to the sources, but its responses get older with every regeneration.
- **The capture date in the file name.** Visible at a glance, but each regeneration renames the files the tests load.
- **Entries chosen for variety (empty, full, out of service).** Exercises nothing in capture, which does not read them; it belongs to the pipeline's fixtures.

#### Deployment

The owner deploys the Worker `bikesharing-capture` from the local machine with `npx wrangler deploy`, from an up-to-date `main`, once the PR with the code has merged. The results of the deployment, the switch and the production checks reach `main` in a second PR, which closes the task. **DL22** `wrangler.jsonc` sets:

| Key | Value | Why |
|---|---|---|
| `name` | `bikesharing-capture` | Project naming (D1) |
| `triggers.crons` | `["* * * * *"]` | One pass per minute (D3) |
| `r2_buckets` | binding `BUCKET` → `bikesharing-bronze` | The Worker reaches R2 through the binding, with no R2 token |
| `workers_dev`, `preview_urls` | `false`, set explicitly | No public URL (R21); `workers_dev` defaults to `true` |
| `version_metadata` | binding `CF_VERSION_METADATA` | The `version` log field ([Pass logs](#pass-logs)) |
| `observability.enabled` | `true` | Workers Logs, the fallback for a failed log write (R11) |

The heartbeat URL is a Worker secret, `HEARTBEAT_URL`, set with `wrangler secret put`, and never stored in a repository file (R23).

The deployment credential is an account-owned API token, `bikesharing-capture-deploy` ([ADR-0035](../decisions/0035-cloud-resource-naming.md)), scoped to Editor on this Worker only, with a one-year expiry, read by wrangler from `CLOUDFLARE_API_TOKEN` (least privilege, NIST SP 800-53 AC-6; TH6). Such a token can update a Worker but not create it, so the first deploy runs with `wrangler login`, and the owner then creates the token and runs `wrangler logout`. The first deploy with the token checks the two points Cloudflare's docs leave open: that Editor suffices for a Worker with an R2 binding, and for `workers_dev: false`; if either fails, the permission is widened only as far as needed, and recorded here.

After every deploy, the owner runs a smoke test on the first passes: each dynamic feed has a new object under `raw/` that passes `gunzip -t`, and the pass's log object exists with `recompressed: false` and the deployed version ID in `version`. It covers what local tests cannot, such as `encodeResponseBody` ([Tests and contracts](#tests-and-contracts)).

Over the first 3 full UTC days of production, the owner checks CPU time in the Workers Logs Query Builder, one full day at a time on the day after it, since the 3-day retention on the Free plan never holds the 3 full days at once: over every invocation of `bikesharing-capture` in that day, the max of `$workers.cpuTimeMs` is below 10 ms, and no invocation has the outcome `exceededCpu`. The max over every pass also bounds the passes with an extra fetch (D4). Close records the max of the 3 days and the time of the costliest pass. **DL19** **DL24**

Options considered for the CPU check:

- **Max per invocation in the Workers Logs Query Builder (chosen).** Exact for every pass; bound to the 3-day retention.
- **P99 of CPU time from the GraphQL Analytics API (`workersInvocationsAdaptive`).** Kept for at least 31 days, but its quantiles are sampled, as R2's were in [s010](../spikes/s010-storage-table-format.md) (F14), and leave the costliest 1% of passes, where those with an extra fetch fall, unchecked.

Options considered for the deployment credential:

- **Token scoped to this Worker (chosen).** A leak reaches only this Worker, and stops at expiry; available since Cloudflare's per-Worker permissions of September 2026.
- **`wrangler login` for every deploy.** Simplest, but keeps an account-wide permission on the local machine.

#### Switch tooling

The owner runs the switch of D11 from the local machine with rclone, as in [s006](../spikes/s006-cloudflare-capture.md), and one throwaway script next to the spike's analysis, `spikes/cloudflare-capture-spike/analysis/spike_raw_switch.py` (Python standard library only), with two commands.

The cutoff is per source and feed: the minute of that feed's first object in production. It is read from an `rclone lsf -R` listing of `bikesharing-bronze/raw/` taken before the first copy, since copied objects come first afterwards, and kept in a file that both commands read, so a repeated copy uses the same cutoffs.

- `keys`: writes the cutoffs file, then lists the keys under `V4/raw/` whose timestamp is earlier than their feed's cutoff, as paths relative to `V4/raw/`. It exits non-zero if a feed under `V4/raw/` has no object in production yet.
- `count`: compares the number of objects per day and feed under `V4/raw/` and under `bikesharing-bronze/raw/`, both before each feed's cutoff, from two `rclone lsf -R` listings, and exits non-zero on any difference.

The copy is server-side, from bucket to bucket: `rclone copy --files-from <keys> r2:bikesharing-capture-spike/V4/raw r2:bikesharing-bronze/raw`, so rclone verifies checksums and retries. The queries of D2 are `spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql`, run with DuckDB over the local copy of the spike's logs after a last `rclone copy` once `capture-v4` has stopped. Close records the cutoff of each feed, the counts per day and feed, and what the queries found.

The completeness check of D6 covers the 7 full UTC days that follow production's first day. It is `spikes/cloudflare-capture-spike/analysis/capture-completeness.sql`, run with DuckDB over an `rclone lsf -R` listing of `bikesharing-bronze/raw/` saved to a local file; no object is downloaded. For each source and dynamic feed, it counts the distinct minutes of the window with at least one object, read from the key's timestamp, divides them by 10,080, and flags any feed below 99.5%. Close records the window and the percentage of each feed.

rclone uses an R2 token, `bikesharing-t039-switch`, with Object Read & Write on `bikesharing-capture-spike` and `bikesharing-bronze`, deleted with the spike's bucket (D11). The completeness listing runs after that, with its own token, `bikesharing-t039-completeness`, with Object Read on `bikesharing-bronze` only ([ADR-0035](../decisions/0035-cloud-resource-naming.md)), deleted when the task closes. **DL18** **DL20**

Options considered:

- **rclone server-side copy and a small script (chosen).** A tool proven in the spike; the only new code filters and counts.
- **One Python script with `boto3`.** One piece, but its retries and verification must be written, for a one-off run.
- **rclone from the local copy to bronze.** Avoids the bucket-to-bucket copy, but uploads over 1.3 GB and trusts the local copy to be complete; the fallback if the server-side copy fails.

### 2.2 Decision log

<!-- It logs decisions about the plan, including changes. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Applies to: anchor link(s) to the section where the decision is applied, named in one or two words.
- Decided at: the Status phase where it was decided (Plan, Steps), or `<phase> review` when decided while reviewing that phase.
- R: Requirement affected.
-->

| # | Applies to | Decision | Reason | R | Decided at |
|---|---|---|---|---|---|
| DL1 | [Layout](#component-layout) | One Worker in `capture/`, sources as configuration with one adapter per kind; functional core, imperative shell | One code path for both sources, and a new source is mostly data | R1 | Plan |
| DL2 | [Schedule](#pass-schedule) | Daily feeds one every 2 hours at `:52`, alternating sources | An outage of one hour loses at most one daily feed | R3, R4 | Plan |
| DL3 | [Index state](#index-state) | Each pass reads the last valid index from `state/`, nothing kept in memory (stateless processes, 12-factor) | Always consistent, no cache to expire, about 0.9% of the free read quota | R6, R12, R13 | Plan |
| DL4 | [D3](#d3-feed-cadence), [D5](#d5-hourly-index-refresh), [D9](#d9-capture-logs) | Every index response is stored under `raw/`, valid or not; Spec change | Bronze keeps every captured response (ADR-0006, ADR-0020); +1% objects, compacted in silver | R24 | Plan |
| DL5 | [Write-once](#write-once) | Conditional put with `If-None-Match: *` under `raw/` and `logs/` (RFC 9110 conditional requests) | Atomic and independent of the lock and of error messages | R9, R10 | Plan |
| DL6 | [Write-once](#write-once) | R2's answers are probed before Plan approval, in a test bucket of their own | `storage.js` rests on verified behaviour; the spike's bucket still holds uncopied data and a running capture | R10 | Plan |
| DL7 | [D9](#d9-capture-logs), [Source fetch](#source-fetch) | Bodies that are not gzip by magic number are compressed and logged as `recompressed`; Spec change | Flags a change in the undocumented `encodeResponseBody` before it costs silent corruption | R16 | Plan |
| DL8 | [Tests](#tests-and-contracts) | Shared contract vectors in a top-level `contracts/` folder | A contract between two components belongs to neither | R1, R15 | Plan |
| DL9 | [Tests](#tests-and-contracts) | The write-once probe also runs against Miniflare's R2; the fetch timeout is a parameter | Integration tests rest on a verified simulator; the timeout is testable without waiting 60 s | R7, R10 | Plan |
| DL10 | [Deployment](#deployment) | Deploy with an account-owned token scoped to Editor on this Worker, one-year expiry; first deploy with `wrangler login` (least privilege, NIST SP 800-53 AC-6) | A leak reaches only this Worker | R21 | Plan |
| DL11 | [Switch tooling](#switch-tooling) | rclone server-side copy with a key list up to the cutoff, and a standard-library script that lists keys and compares counts **→ DL18** | Proven tool from s006; the only new code filters and counts | — | Plan |
| DL12 | [ADR-0035](../decisions/0035-cloud-resource-naming.md) | One naming pattern for every cloud resource, `bikesharing-<name>`: buckets by content, compute by component, tokens by component and purpose, temporary resources by task (resource naming conventions) | Cheap to fix while resources are few; buckets cannot be renamed | — | Plan |
| DL13 | [Index state](#index-state) | A valid index is adopted only once stored under `raw/` and `state/`; a failed write is `index_rejected` with `error_type: write` | `index_refreshed` keeps one meaning, and the index in use is always in bronze | R12, R24 | Plan |
| DL14 | [D9](#d9-capture-logs), [ADR-0036](../decisions/0036-log-convention-across-components.md) | The common fields come from a new ADR that supersedes ADR-0030, not from amending it; Spec change | Accepted ADRs are immutable (`.claude/rules/docs/adr.md`) | R15 | Plan |
| DL15 | [Layout](#component-layout), [ADR-0037](../decisions/0037-test-fixtures-per-component.md) | Fixtures in each component's tests, `capture/test/fixtures/` for capture; ADR-0037 supersedes ADR-0009 | Each component owns its test data, as it owns its code and tests (ADR-0016, ADR-0017) | — | Plan |
| DL16 | [Fixtures](#fixtures) | A Node script fetches live responses, keeps the index whole and the first 3 entries of each other feed, and writes uncompressed JSON with stable names and a provenance manifest | Current quirks and readable diffs; capture does not read feed entries, so choosing them adds nothing | — | Plan |
| DL17 | [Write-once](#write-once) | When a conditional put throws, `head` decides whether the object exists: if so it counts as written, otherwise the attempt is retried | Under the lock R2 throws instead of returning `null` (probe); `head` depends on no error message | R9, R10 | Plan |
| DL18 | [D11](#d11-switch-from-spike-capture-to-production), [Switch tooling](#switch-tooling) | The copy cutoff is per source and feed, the minute of its first object in production, read before the first copy (high-water mark per partition); Spec change **refines DL11** | No minute is lost, nothing is duplicated, and the count check compares like with like | — | Plan review |
| DL19 | [Deployment](#deployment) | CPU is checked as the max of `$workers.cpuTimeMs` over every invocation in the Workers Logs Query Builder, over the first 3 full days, with no `exceededCpu` outcome (IADT Analysis) **→ DL24** | Exact per pass, unlike the sampled quantiles of the GraphQL Analytics API | — | Plan review |
| DL20 | [Switch tooling](#switch-tooling) | The 7-day completeness check is a DuckDB query over a local `rclone lsf -R` listing of `raw/`, next to the switch tooling, with a temporary read-only token (IADT Analysis; least privilege, NIST SP 800-53 AC-6) | One credential path and a reproducible input for a one-off check that T042 replaces; the write token still goes with the spike's bucket | — | Plan review |
| DL21 | [Tests](#tests-and-contracts), [Test plan](#26-test-plan) | Simulated sources serve gzip bytes without `Content-Encoding`; `encodeResponseBody` is covered only by the post-deploy smoke test | Local tests rest only on verified behaviour; the gzip check reads the magic number, not the header | R1, R16 | Plan review |
| DL22 | [Deployment](#deployment) | Deploy only from `main`, after the code's PR merges (`Refs`); a second PR records the operational results and closes the task (GitHub Flow, deploy from the default branch) | Only reviewed code that passed CI reaches production, as for the pipeline (d002 › R24–R28), and no PR stays open for the 7-day check | — | Steps |
| DL23 | [Step 13](#step-13--ci-job) | Job `capture` behind a path filter (`dorny/paths-filter`); `ci-passed` fails only on `failure` or `cancelled`, so a filtered job passes (ADR-0013 path filter; "alls-green" aggregator) | A required aggregator that demands `success` blocks every PR that skips a filtered job | — | Steps review |
| DL24 | [Deployment](#deployment) | The CPU check queries each of the first 3 full days on the day after it, and takes the max of the 3 (IADT Analysis) **refines DL19** | The 3-day retention never holds the 3 full days at once, so a single query misses part of day 1 | — | Steps review |

### 2.3 Architecture

<!-- Optional. One diagram and 2–3 sentences. -->

One pass, started by the cron every minute. Each source is handled on its own, so a source without a valid index fetches only that index and does not hold back the other; the heartbeat and the log belong to the whole pass, and the log is written last, whatever happened before.

```mermaid
flowchart TD
    cron([Cron trigger,<br>every minute]) --> read[Read each<br>source's last<br>valid index<br>from state/]
    read --> valid

    subgraph each [For each source]
        valid{Index in<br>state/?}
        valid -- no --> refresh[Fetch and store<br>its index;<br>if valid, update<br>state/]
        valid -- yes --> dyn[Fetch and store<br>its dynamic<br>feeds]
        dyn --> extra{Extra fetch<br>for this source<br>at this minute?}
        extra -- index --> refresh
        extra -- static feed --> stat[Fetch and store<br>the static feed]
        extra -- none --> next([Source done])
    end

    refresh --> hbmin
    stat --> hbmin
    next --> hbmin
    hbmin{Heartbeat<br>minute?}
    hbmin -- no --> log
    hbmin -- yes --> hb{Every dynamic<br>feed of every<br>source stored?}
    hb -- yes --> signal[Send the<br>heartbeat to<br>Healthchecks.io]
    hb -- no --> skip[No signal]
    signal --> log
    skip --> log
    log[Write the<br>pass's log<br>object to logs/]

    classDef decision fill:#f3f4f6,stroke:#6b7280,color:#111827
    classDef r2 fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a
    classDef source fill:#dcfce7,stroke:#15803d,color:#14532d
    classDef external fill:#f3e8ff,stroke:#7e22ce,color:#581c87
    class cron,valid,extra,next,hbmin,hb,skip decision
    class read,log r2
    class refresh,dyn,stat source
    class signal external
```

Colours show what each box touches: grey, no I/O (the functional core); blue, R2 only; green, a source fetch stored in R2; purple, Healthchecks.io. The schedule decides the extra fetch ([Pass schedule](#pass-schedule)); every object goes through the write-once put of `storage.js` ([Write-once](#write-once)), and a failure at any box is logged and does not stop the rest of the pass (D8).

### 2.4 File layout

<!-- Every file and folder the task creates or modifies, documents included, as a tree: (new) or (modified), and its purpose or change in one line. A task that adds a component also lists its CI job in `.github/workflows/ci.yml` (recipe in `.claude/rules/code/ci.md`), and its version files, manifest and lockfile (`.claude/rules/code/dependencies.md`). -->

```text
.
├── CLAUDE.md                                  (modified) Project structure: `capture/` and `contracts/`
├── .env.example                               (modified) Variables grouped and documented; deploy and R2 token scopes
├── .claude/rules/code/
│   ├── cloudflare-worker.md                   (modified) `paths:` to `capture/**`; contract tests; TODO removed
│   └── testing.md                             (modified) `contracts/**` in `paths:`; TODO removed
├── .github/workflows/ci.yml                   (modified) Job `capture` and final job `ci-passed`; TODO removed
├── capture/                                   (new) Production capture Worker, as in Component layout
│   ├── .nvmrc                                 (new) Pinned Node version
│   ├── package.json                           (new) Manifest
│   ├── package-lock.json                      (new) Lockfile
│   ├── wrangler.jsonc                         (new) Worker configuration (Deployment), with `compatibility_date`
│   ├── vitest.config.js                       (new) Test configuration, sources through `outboundService`, fixtures compressed once and passed as bindings
│   ├── scripts/trim-fixtures.js               (new) Fetches and trims the fixtures (Fixtures)
│   ├── src/                                   (new) The modules of Component layout
│   └── test/
│       ├── unit/                              (new) One file per module
│       ├── integration/                       (new) The `scheduled` handler in workerd with in-memory R2
│       ├── contract/                          (new) Producer side of the vectors in `contracts/`
│       └── fixtures/                          (new) `<source>/<feed>.json` and `manifest.json` (Fixtures)
├── contracts/                                 (new) Shared contract vectors (Tests and contracts)
│   ├── bronze-keys.json                       (new) Object keys (ADR-0012, D1)
│   └── capture-logs.json                      (new) Log lines (D9)
├── docs/
│   ├── architecture.md                        (modified) Runtime view: pass schedule and one-pass diagram; completeness target (D6)
│   ├── testing-strategy.md                    (modified) Worker section paths to `capture/`; contract tests; smoke test (Deployment)
│   ├── decisions/
│   │   ├── 0023-storage-security-baseline.md  (modified) TODOs resolved by this design removed
│   │   ├── 0035-cloud-resource-naming.md      (new) Cloud resource naming (D1)
│   │   ├── 0036-log-convention-across-components.md (new) One log convention, with `component` and `version` (D9)
│   │   ├── 0037-test-fixtures-per-component.md (new) Fixtures in each component's tests (DL15)
│   │   ├── archive/0009-trimmed-source-samples-as-test-fixtures.md (moved) Superseded by ADR-0037
│   │   └── archive/0030-pipeline-logs.md      (moved) Superseded by ADR-0036
│   ├── sources/
│   │   ├── ambici.md                          (modified) Facts observed in the spike's capture that capture depends on
│   │   └── bicing.md                          (modified) Same; `OPEN_DATA_BCN_TOKEN`
│   └── spikes/
│       └── s012-execution-target.md           (modified) `TODO(T039)` removed: its items are resolved by D9 and D10
└── spikes/cloudflare-capture-spike/
    ├── README.md                              (modified) The switch script, the log queries, the completeness query and the probe
    ├── analysis/
    │   ├── capture-completeness.sql           (new) Completeness of the first 7 days of production (Switch tooling)
    │   ├── spike_raw_switch.py                (new) Key list up to the cutoff and count comparison (Switch tooling)
    │   └── spike-log-queries.sql              (new) The queries of D2
    └── js/
        ├── src/probe-write-once.js            (new) Write-once probe, run remotely against R2 and locally against Miniflare (Write-once)
        └── wrangler.probe.jsonc               (new) Probe configuration, bound to `bikesharing-t039-write-once`
```

The facts for the source cards are those of D3, D4, D5, D8 and D12 that capture depends on: how often each static feed changed, the GBFS `ttl` values, the stable index size, the latency shifts, Bicing's missing `content-length` and the largest response observed.

### 2.5 Components

<!-- Optional. One subsection per component. The contract is exact, in the component's own language, never pseudocode. -->

The modules of `capture/src/`, as in [Component layout](#component-layout). Contracts are JSDoc, the standard type annotation for JavaScript; the first three modules are the functional core and have no I/O.

#### `sources.js`

- **Responsibility:** The table of sources and the feeds each one captures by cadence (D3).
- **Location:** `capture/src/sources.js`
- **Contract:**

```js
/**
 * @typedef {object} Source
 * @property {string} id                 Source ID in object keys and logs: `ambici` or `bicing`
 * @property {string} kind               Adapter that reads its index: `gbfs`
 * @property {string} indexUrl           URL of the source's index (`gbfs` feed)
 * @property {readonly string[]} dynamic Feeds captured every pass (D3)
 * @property {readonly string[]} hourly  Feeds captured hourly (D3); the index is not a feed
 *                                       here: `indexUrl` names it and `schedule.js` its refresh
 * @property {readonly string[]} daily   Feeds captured daily (D3)
 */

/** @type {readonly Source[]} */
export const SOURCES;

/**
 * Every feed the source's index must list for it to be valid (D8): its dynamic,
 * hourly and daily feeds.
 * @param {Source} source
 * @returns {string[]}
 */
export function requiredFeeds(source);
```

#### `adapters/gbfs.js`

- **Responsibility:** Reads a GBFS index and validates it against the feeds its source requires (D8).
- **Location:** `capture/src/adapters/gbfs.js`; every adapter in `adapters/` exports the same function.
- **Contract:**

```js
/**
 * @typedef {{ ok: true, feeds: Record<string, string>, unknownFeeds: string[] }
 *         | { ok: false, error: string }} IndexResult
 * `feeds`: feed name → URL, for the required feeds only.
 * `unknownFeeds`: feeds in the index that are not required, sorted (D9).
 * `error`: why the index is invalid, for the `index_rejected` event.
 */

/**
 * Valid when the text parses as JSON, every feed entry has `name` and `url`,
 * and every required feed is listed. Never throws.
 * @param {string} text                Decompressed body of the index
 * @param {readonly string[]} required From `requiredFeeds(source)`
 * @returns {IndexResult}
 */
export function parseIndex(text, required);
```

#### `schedule.js`

- **Responsibility:** Decides the extra fetch, if any, of the pass scheduled at a given time ([Pass schedule](#pass-schedule)).
- **Location:** `capture/src/schedule.js`
- **Contract:**

```js
/**
 * @typedef {{ type: 'index', source: string }
 *         | { type: 'feed', source: string, feed: string }
 *         | { type: 'heartbeat' }} ExtraFetch
 */

/**
 * Reads the minute and hour in UTC of `scheduledTime`, never the clock, and looks
 * them up in the tables of Pass schedule.
 * @param {number} scheduledTime The event's `scheduledTime`, in ms since the epoch
 * @returns {ExtraFetch | null}  `null` when the minute carries no extra fetch
 */
export function extraFetch(scheduledTime);
```

#### `fetch.js`

- **Responsibility:** Fetches one source response and returns its gzip bytes as stored, or the failure ([Source fetch](#source-fetch)).
- **Location:** `capture/src/fetch.js`
- **Contract:**

```js
/** Production limits; tests pass their own (DL9). */
export const LIMITS = {
  timeoutMs: 60_000, maxBytes: 10_000_000, retryDelayMs: 250, heartbeatTimeoutMs: 10_000,
};

/**
 * @typedef {{ ok: true, status: number, latencyMs: number,
 *             body: Uint8Array, recompressed: boolean }} FetchOk
 * `body`: gzip bytes, as received or compressed by capture (`recompressed`).
 *
 * @typedef {{ ok: false, status: number | null, latencyMs: number | null,
 *             errorType: 'http' | 'timeout' | 'network' | 'too_large',
 *             error: string }} FetchFailed
 * `status`: null when no response arrived. `latencyMs`: null when no headers arrived (R14).
 * `http`: a status outside 200–299; its body is not stored.
 */

/**
 * GET with `Accept-Encoding: gzip` and `encodeResponseBody: "manual"`, aborted by
 * `AbortSignal.timeout(timeoutMs)` and once the body read exceeds `maxBytes`. Never throws.
 * @param {string} url
 * @param {{ timeoutMs: number, maxBytes: number }} limits
 * @returns {Promise<FetchOk | FetchFailed>}
 */
export async function fetchFeed(url, limits);

/**
 * Decompresses an index body for its adapter. Never throws.
 * @param {Uint8Array} gzipBytes
 * @param {number} maxBytes Limit on the decompressed size
 * @returns {Promise<{ ok: true, text: string } | { ok: false, error: string }>}
 */
export async function gunzipText(gzipBytes, maxBytes);
```

#### `storage.js`

- **Responsibility:** Builds object keys and writes them to the bucket with write-once and retries; the only module that calls the R2 binding ([Write-once](#write-once)).
- **Location:** `capture/src/storage.js`
- **Contract:**

```js
/**
 * The pass's start, truncated to the second, in the key format of ADR-0012.
 * @param {Date} start
 * @returns {string} `YYYYMMDDTHHMMSSZ`
 */
export function runIdOf(start);

/** @returns {string} `raw/<source>/<feed>/<YYYY-MM-DD>/<runId>.json.gz` (D1) */
export function rawKey(source, feed, runId);

/** @returns {string} `logs/date=<YYYY-MM-DD>/<runId>.jsonl` (D9) */
export function logKey(runId);

/** @returns {string} `state/index/<source>.json` */
export function stateKey(source);

/**
 * @typedef {{ ok: true, attempts: number }
 *         | { ok: false, attempts: number, error: string }} PutResult
 * `attempts`: write attempts made, 1 to 3.
 */

/**
 * Conditional put, `onlyIf` with `If-None-Match: *`, for keys under `raw/` and `logs/`.
 * A `null` answer counts as written (R10). If the put throws, `head(key)` decides: an
 * object there counts as written; otherwise the attempt failed (DL17). Up to 2 retries,
 * `retryDelayMs` apart (R9). Never throws.
 * @param {R2Bucket} bucket
 * @param {string} key
 * @param {Uint8Array | string} body
 * @param {{ retryDelayMs: number }} limits
 * @returns {Promise<PutResult>}
 */
export async function putOnce(bucket, key, body, limits);

/** Plain put, for keys under `state/`; same retries as `putOnce`. Never throws. */
export async function putState(bucket, key, text, limits);

/**
 * @param {R2Bucket} bucket
 * @param {string} key
 * @returns {Promise<string | null>} null when the object is missing or the read fails
 */
export async function getState(bucket, key);
```

#### `index-state.js`

- **Responsibility:** Reads and stores each source's last valid index under `state/`, through `storage.js` ([Index state](#index-state)).
- **Location:** `capture/src/index-state.js`
- **Contract:**

```js
/**
 * @typedef {object} IndexState
 * @property {string} refreshed_at          ISO 8601 UTC, the pass's start
 * @property {Record<string, string>} feeds Feed name → URL, from `parseIndex`
 */

/**
 * @param {R2Bucket} bucket
 * @param {string} sourceId
 * @returns {Promise<IndexState | null>} null when missing, unreadable or not an IndexState
 */
export async function readIndex(bucket, sourceId);

/**
 * @param {R2Bucket} bucket
 * @param {string} sourceId
 * @param {IndexState} state
 * @param {{ retryDelayMs: number }} limits
 * @returns {Promise<PutResult>}
 */
export async function writeIndex(bucket, sourceId, state, limits);
```

#### `log.js`

- **Responsibility:** Builds the pass's events and writes them as one log object ([Pass logs](#pass-logs)).
- **Location:** `capture/src/log.js`
- **Contract:**

```js
/**
 * @typedef {object} LogContext
 * @property {string} runId
 * @property {string} version `CF_VERSION_METADATA.id`
 */

/**
 * One event: `ts`, `level`, `component` (`capture`), `version`, `run_id` and `event`,
 * in that order, then `fields` (D9). Pure.
 * @param {LogContext} ctx
 * @param {Date} ts
 * @param {'info' | 'warning' | 'error'} level
 * @param {string} event  One of the events of D9
 * @param {Record<string, unknown>} fields Its own fields, in snake_case
 * @returns {Record<string, unknown>}
 */
export function buildEvent(ctx, ts, level, event, fields);

/** @returns {string} JSON Lines, one event per line, ending in a newline. Pure. */
export function toJsonl(events);

/**
 * `putOnce` to `logKey(runId)`. If it still fails, writes each line with `console.log`
 * and the write error with `console.error`, which reach Workers Logs (R11). Never throws.
 * @param {R2Bucket} bucket
 * @param {string} runId
 * @param {Record<string, unknown>[]} events
 * @param {{ retryDelayMs: number }} limits
 * @returns {Promise<void>}
 */
export async function writeLog(bucket, runId, events, limits);
```

#### `heartbeat.js`

- **Responsibility:** Sends the Healthchecks.io signal (D10).
- **Location:** `capture/src/heartbeat.js`
- **Contract:**

```js
/**
 * GET to `url`, aborted by `AbortSignal.timeout(heartbeatTimeoutMs)`, 10 s in production
 * as in Healthchecks.io's examples. The body is read and discarded within the same
 * timeout, so the timeout covers the whole response and no connection is left open.
 * Never throws.
 * `error` is built from the error's name and message with every occurrence of `url`
 * removed, so no result carries the URL (R23).
 * @param {string} url `HEARTBEAT_URL`
 * @param {{ heartbeatTimeoutMs: number }} limits
 * @returns {Promise<
 *   { ok: true, status: number, latencyMs: number }
 * | { ok: false, status: number | null, latencyMs: number | null,
 *     errorType: 'http' | 'timeout' | 'network', error: string }>}
 */
export async function sendHeartbeat(url, limits);
```

#### `pass.js`

- **Responsibility:** Runs one pass, as in [Architecture](#23-architecture), and writes its log whatever happens.
- **Location:** `capture/src/pass.js`; it maps each `kind` to its adapter.
- **Contract:**

```js
/**
 * @typedef {object} PassDeps
 * @property {R2Bucket} bucket
 * @property {string} heartbeatUrl
 * @property {string} version
 * @property {readonly Source[]} [sources] Default `SOURCES`
 * @property {typeof LIMITS} [limits]      Default `LIMITS`
 * @property {() => Date} [now]            Default `() => new Date()`
 */

/**
 * `runId` comes from `now()` at the start; the extra fetch from `scheduledTime`.
 * An index refresh adopts a valid index only once stored under `raw/` and `state/` (DL13).
 * Sources run in parallel, and so do the fetches within a source. The log is written in
 * `finally`. Never throws.
 * @param {number} scheduledTime
 * @param {PassDeps} deps
 * @returns {Promise<void>}
 */
export async function runPass(scheduledTime, deps);
```

#### `worker.js`

- **Responsibility:** The Worker's entry point: the `scheduled` handler only, with no `fetch` handler (R21).
- **Location:** `capture/src/worker.js`
- **Contract:**

```js
/**
 * @typedef {object} Env
 * @property {R2Bucket} BUCKET                     `bikesharing-bronze`
 * @property {string} HEARTBEAT_URL                Worker secret (R23)
 * @property {{ id: string }} CF_VERSION_METADATA  Version metadata binding
 */

export default {
  /**
   * @param {ScheduledController} controller
   * @param {Env} env
   * @param {ExecutionContext} ctx
   */
  async scheduled(controller, env, ctx) {
    await runPass(controller.scheduledTime, {
      bucket: env.BUCKET,
      heartbeatUrl: env.HEARTBEAT_URL,
      version: env.CF_VERSION_METADATA.id,
    });
  },
};
```

### 2.6 Test plan

<!-- Optional. Every requirement has at least one verification method (IADT: Inspection, Analysis, Demonstration, Test). Test is the default, at the lowest level that can verify the requirement. Another method only when no test can: Inspection for configuration or documents, Analysis for production data or measurements, Demonstration for behaviour observed end to end, such as a third-party service. -->

Integration tests run the `scheduled` handler in workerd with in-memory R2 and the sources served by `outboundService` from fixtures, or `runPass` with its dependencies where a test needs a fixed time, `LIMITS` in milliseconds and bytes, or a request count. Each simulated source serves its fixture as compressed once by `vitest.config.js` ([Fixtures](#fixtures)), without `Content-Encoding`, so the bytes reach capture unchanged whatever the runtime does with `encodeResponseBody`; the stored object is compared with those same bytes, passed to the test as a binding, and a fixture served uncompressed exercises `recompressed`. Unit tests that need a failing bucket pass `storage.js` a fake binding, since the in-memory R2 cannot fail on demand.

| R | Method | What is verified | Level |
|---|---|---|---|
| R1 | Test | A pass stores each dynamic feed of each source under `rawKey`, with the fixture's bytes unchanged | integration |
| R1 | Test | `rawKey` and `runIdOf` produce the valid cases of `contracts/bronze-keys.json` | contract |
| R1 | Demonstration | Post-deploy smoke test: each dynamic feed has a new object that passes `gunzip -t` ([Deployment](#deployment)) | — |
| R2 | Test | Over the 1,440 minutes of a day, `extraFetch` returns each source's `station_information` 24 times, at `:12` and `:42` | unit |
| R3 | Test | Over the 1,440 minutes of a day, `extraFetch` returns each of the 12 daily feeds once | unit |
| R4 | Test | `extraFetch` returns an extra fetch at exactly 132 minutes per day, those of [Pass schedule](#pass-schedule); every hourly and daily feed in `SOURCES` appears in the schedule | unit |
| R4 | Test | A pass at a static feed's minute stores the dynamic feeds and that feed only | integration |
| R5 | Test | Over the 1,440 minutes of a day, `extraFetch` returns each source's index 24 times, at `:07` and `:37` | unit |
| R6 | Test | With an index in `state/` that points a feed to a new URL, the pass fetches that URL and stores its response | integration |
| R7 | Test | A source whose body stalls beyond `timeoutMs` is logged as `feed_failed` with `error_type: timeout`; the other feeds are stored | integration |
| R8 | Test | A source answering HTTP 500 is requested once in the pass and logged as `feed_failed` with `error_type: http` and `attempts: 0` | integration |
| R9 | Test | `putOnce` with a bucket that fails twice writes on the third attempt with `attempts: 3`; one that always fails returns `ok: false` with `attempts: 3` | unit |
| R10 | Test | `putOnce` with a bucket that answers `null` returns `ok: true`; with a bucket whose put throws and whose `head` finds the object, it returns `ok: true` after 1 attempt; whose `head` finds nothing, it retries | unit |
| R10 | Test | A pass whose key is already in R2 leaves the object unchanged and logs `feed_captured` | integration |
| R10 | Demonstration | Write-once probe against R2 and Miniflare's R2, with and without the lock ([Write-once](#write-once)) | — |
| R11 | Test | `writeLog` with a bucket that always fails writes each line with `console.log` and the error with `console.error` | unit |
| R12 | Test | `parseIndex` rejects text that is not JSON, an entry without `name`, an entry without `url`, and an index missing a required feed | unit |
| R12 | Test | A refresh with an invalid index, or whose write to `raw/` or `state/` fails, logs `index_rejected` and leaves `state/` unchanged (DL13) | integration |
| R13 | Test | With no index in `state/` for one source, the pass fetches only that source's index, even at that source's extra minute, and the other source's feeds are stored | integration |
| R14 | Test | `latency_ms` is a number for an HTTP 500 and for a body that times out after headers, and null for a network failure | integration |
| R15 | Test | Each pass writes one object at `logKey(runId)`, also when every data write fails; its lines carry the common fields | integration |
| R15 | Test | `buildEvent` and `toJsonl` produce the valid cases of `contracts/capture-logs.json` | contract |
| R16 | Test | Each event of D9 is logged with its fields: `unknown_feeds` for an index with an extra feed, `recompressed: true` for a fixture served without gzip | integration |
| R16 | Demonstration | Post-deploy smoke test: the pass's log has `recompressed: false` and the deployed version ID ([Deployment](#deployment)) | — |
| R17 | Test | At minute `:22` with every dynamic feed stored, the pass sends one request to the heartbeat URL and logs `heartbeat_sent` | integration |
| R18 | Test | At minute `:22` with one dynamic feed failed, the pass sends no request to the heartbeat URL | integration |
| R19 | Demonstration | With the check configured, no signal for 1 h plus the grace sends the owner an email | — |
| R20 | Test | A heartbeat answering HTTP 500, or failing on the network, logs `heartbeat_failed` at `warning`; the pass's data and log are stored | integration |
| R21 | Test | The default export of `worker.js` has `scheduled` and no `fetch` | unit |
| R21 | Inspection | `wrangler.jsonc` sets `workers_dev` and `preview_urls` to `false`; after deploy, the dashboard shows no public URL | — |
| R22 | Test | A body over `maxBytes` with no `content-length` is logged as `feed_failed` with `error_type: too_large` and nothing is stored; an index over `maxBytes` once decompressed is rejected | integration |
| R23 | Test | `sendHeartbeat` with a network error whose message contains the URL returns an `error` without it | unit |
| R23 | Test | After a failed heartbeat, the log object does not contain the heartbeat URL | integration |
| R24 | Test | A refresh that receives an invalid index stores it under `raw/<source>/gbfs/` | integration |

### 2.7 What does not change

<!-- Optional. Code or documents that must not be modified. Out of scope limits the what; this section limits the how. -->

- `capture-v4`, its code (`spikes/cloudflare-capture-spike/js/src/`, `wrangler.v4.jsonc`) and its configuration keep running unchanged until step 5 of D11 stops them: the overlap compares production against them.
- `bikesharing-capture-spike` is only read until step 6 of D11; nothing is written to or deleted from `V4/` before then, so the copy and its count check stay repeatable.
- The key layout of [ADR-0012](../decisions/0012-collectors-decoupled-by-output-contract.md) (D1): `contracts/bronze-keys.json` encodes it as it is.
- The rules of [ADR-0023](../decisions/0023-storage-security-baseline.md) and the choice of [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md); ADR-0023 only loses the TODOs this design resolves.
- The spike's package (`spikes/cloudflare-capture-spike/js/package.json` and its lockfile): the probe runs with the wrangler it already pins.

## 3. Steps

<!-- Each step is one reviewable result and one commit, touching at most 2–3 files.
- Status: where the step is: 💤 todo · 🎬 ready · 🔄 in progress · ⛔ blocked · ✅ done
- Who: Owner (manual actions: dashboards, accounts, deploys, runs, checks) or Claude (code and documents).
- R: the requirements the step implements or tests, or —.
- Commit: the proposed message, following the Git conventions in CLAUDE.md.
- Model: the model and effort the step's session runs with (e.g. sonnet · medium), or — when Who is Owner. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

On the local machine:

| Tool | Version | Used for | Verify |
|---|---|---|---|
| Node, through fnm | 26.12.1, as in the root `.nvmrc`, with npm 11.20.0 | `capture/`, wrangler, `trim-fixtures.js` | `node -v` and `npm -v` |
| rclone | 1.75.2, with the remote `r2` (provider Cloudflare) | Switch copy and listings ([Switch tooling](#switch-tooling)) | `rclone version` and `rclone listremotes` |
| DuckDB CLI | 2.0.0 | The queries of D2 and the completeness query | `duckdb --version` |
| Python | 3.14.4, standard library only | `spike_raw_switch.py` | `python3 --version` |

DuckDB and Python run only the one-off switch tooling, so they follow the local machine rather than the pipeline's versions ([s011](../spikes/s011-engine-pipeline-language.md)).

Accounts:

- A Cloudflare account with R2 enabled, the one that runs `capture-v4`.
- A Healthchecks.io account on the free plan ([ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md)). The check itself is created in a step.

The tokens of [Deployment](#deployment) and [Switch tooling](#switch-tooling) depend on the Worker and the bucket, so they are created in the steps.

### Step 1 — Scaffold `capture/`

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `build: d004.s1 - scaffold the capture Worker`
- **R:** R21
- **Model:** sonnet · medium

#### Scope

<!-- The result of the step. List the components, the files created or changed (code, tests, docs), and the tests from the Test plan that cover it. A reviewer should know what the diff will contain from this section alone. -->

The `capture/` component with its runtime pin, its manifest with the test and deploy tools locked, the Worker configuration of [Deployment](#deployment), and the test configuration that runs tests inside workerd. The only source file is the entry point `src/worker.js`, which `wrangler.jsonc` names as `main`, with an empty `scheduled` handler; Step 11 makes it run the pass. No tests yet.

- `capture/.nvmrc` (new): `26.12.1`, the same as the root `.nvmrc`.
- `capture/package.json` (new): `private`, ES modules, scripts `test` and `fixtures`; development dependencies `wrangler`, `vitest` and `@cloudflare/vitest-plugin`.
- `capture/package-lock.json` (new): written by npm.
- `capture/wrangler.jsonc` (new): every key of the Deployment table, plus `main` and `compatibility_date`.
- `capture/vitest.config.js` (new): the `cloudflareTest` plugin reading `wrangler.jsonc`; the simulated sources are added in Step 9.
- `capture/src/worker.js` (new): a default export with an empty `async scheduled()` and no `fetch` handler (R21).

Tests: none; R21's Inspection row of the Test plan is checked here on the file and again after deploy (Step 16).

#### Reads

<!-- List of reads containing what to read (be specific with paragraph or line), what contains the read, and why it is interesting here.  -->

- `.claude/rules/code/dependencies.md`, whole: where the runtime pin and the lockfile go, and how dependencies are added.
- `.claude/rules/code/cloudflare-worker.md` › Tools: the test packages to install.
- d004 › [Deployment](#deployment), the table: the keys and values of `wrangler.jsonc`.
- d004 › [Component layout](#component-layout), the tree: the paths `main` and the scripts point to.
- `spikes/testing-conventions/worker/vitest.config.js`, whole: the plugin's configuration as proven in [s008](../spikes/s008-testing-conventions.md).

#### Do

<!-- Numbered actions in execution order, one verb each (write, implement, update, run). Every file named here must appear in Scope; add nothing Scope does not list. -->

1. Write `capture/.nvmrc` with `26.12.1`.
2. Write `capture/package.json` with `"name": "bikesharing-capture"`, `"private": true`, `"type": "module"` and the scripts `"test": "vitest run"` and `"fixtures": "node scripts/trim-fixtures.js"`; no `engines`, since Node is pinned only in `.nvmrc`.
3. Run `npm install --save-dev wrangler vitest @cloudflare/vitest-plugin` in `capture/`, which writes the ranges and `package-lock.json`. If npm reports a peer conflict, install the `vitest` major that `@cloudflare/vitest-plugin` declares in its `peerDependencies`.
4. Write `capture/wrangler.jsonc` with `$schema` set to `./node_modules/wrangler/config-schema.json`, `main` set to `src/worker.js`, `compatibility_date` set to `2026-11-06`, and the keys of the Deployment table with their values; `workers_dev` and `preview_urls` are written explicitly as `false`.
5. Write `capture/vitest.config.js` with `defineConfig` and the `cloudflareTest` plugin, `wrangler: { configPath: "./wrangler.jsonc" }`, as in the s008 configuration, without `bindings` or `outboundService`.
6. Write `capture/src/worker.js` with a default export holding only an empty `async scheduled()`.

#### Check

<!-- command/s or verification with a yes/no result. -->

- `npm ci` in `capture/`, with `capture/.nvmrc` active, exits 0 and prints no `EBADENGINE` or peer dependency warning.
- `npx vitest run --passWithNoTests` in `capture/` exits 0, so the plugin starts workerd from `wrangler.jsonc` and builds `src/worker.js`.
- `git status` shows only the six files of Scope as new, and `node_modules/` is ignored.
- `wrangler.jsonc` holds each key of the Deployment table with its value, and `workers_dev` and `preview_urls` are `false` (R21, Inspection).

### Step 2 — Contract vectors

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `test: d004.s2 - add the bronze key and capture log contract vectors`
- **R:** R1, R15
- **Model:** sonnet · medium

#### Scope

The two shared contracts of [Tests and contracts](#tests-and-contracts), as golden test vectors in the format of `.claude/rules/code/testing.md` › Contracts between components. No code: the producer tests that read them come in Steps 5 and 6, and the `invalid` cases serve the consumers (T040, T042).

- `contracts/bronze-keys.json` (new): object keys under `raw/` and `logs/` (ADR-0012, D1, D9).
  - `contract`: one line naming both layouts.
  - `valid`: cases with `name`, `kind` (`raw` or `log`), `captured_at` (ISO 8601 UTC, may carry milliseconds), `run_id`, `source` and `feed` (only for `raw`), and `key`. At least the five valid cases of the s008 file; a `captured_at` with milliseconds, truncated and not rounded (`2026-10-18T12:00:03.987Z` → `20261018T120003Z`); the feed `gbfs`; a log key at midday and one just after midnight UTC.
  - `invalid`: cases with `key` and `reason`. At least the invalid cases of the s008 file, and for log keys: no `date=`, the extension `.json`, and a date folder that does not match the `run_id`.
- `contracts/capture-logs.json` (new): log lines (D9, [ADR-0036](../decisions/0036-log-convention-across-components.md)).
  - `contract`: one line naming the convention.
  - `valid`: cases with `name`, `inputs` (a list of `{ run_id, version, ts, level, event, fields }`) and `jsonl`, the exact expected text: one line per input, keys in the order `ts`, `level`, `component`, `version`, `run_id`, `event`, then the fields in the order of D9's table, ending in a newline. One case per event of D9; a `feed_failed` from a network failure, with `status` and `latency_ms` null; an `index_refreshed` with a non-empty `unknown_feeds`; and one case with two inputs.
  - `invalid`: cases with `line` and `reason`, each breaking one rule: no `component`; `ts` without milliseconds; `ts` with an offset other than `Z`; `level` `warn`; an event not in D9; an `error_type` not in D9; a `run_id` not in the key format; a field in camelCase; a `feed_captured` without `attempts`.

#### Reads

- `.claude/rules/code/testing.md` › Contracts between components: the file format.
- `spikes/testing-conventions/contract/collector-contract.json`, whole: the cases of s008 to reuse.
- d004 › D1, the tree; D9, the table and the paragraph after it: the keys, events, fields and allowed values.
- d004 › [Pass logs](#pass-logs), the table: the format of `run_id` and `ts`.

#### Do

1. Write `contracts/bronze-keys.json`.
2. Write `contracts/capture-logs.json`.

#### Check

- Both files parse: `node -e 'for (const f of process.argv.slice(1)) JSON.parse(require("fs").readFileSync(f))' contracts/*.json` exits 0.
- Each event of D9 has a valid case in `capture-logs.json`, and each invalid case in both files has a `reason` naming one rule.
- In `bronze-keys.json`, each valid `key` carries its `run_id` and the date of its `captured_at` in UTC.

### Step 3 — Source table and GBFS adapter

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d004.s3 - add the source table and the GBFS adapter`
- **R:** R12
- **Model:** sonnet · medium

#### Scope

The first two modules of the functional core, as in [Components](#25-components) › `sources.js` and `adapters/gbfs.js`.

- `capture/src/sources.js` (new): `SOURCES` with `ambici` and `bicing`, `kind: "gbfs"`, the index URL of each source card, and the feeds of D3 by cadence; `requiredFeeds`.
- `capture/src/adapters/gbfs.js` (new): `parseIndex`. It reads the entries from `data.feeds` (GBFS 3.0, Bicing) or `data.en.feeds` (GBFS 2.x, AMBici), as `listFeeds` does in `capture-v4`. The `gbfs` entry is neither required nor unknown.
- `capture/test/unit/sources.test.js` (new): `requiredFeeds` of each source is its dynamic, hourly and daily feeds, and none of them is `gbfs`; across `SOURCES` there are 3 dynamic and 12 daily feeds.
- `capture/test/unit/gbfs.test.js` (new): the R12 unit row of the Test plan; a valid index in each GBFS shape returns the required URLs and sorted `unknownFeeds`. Indexes are built in memory.

#### Reads

- d004 › D3, the table; D8, the index row: the feeds and the validity rule.
- d004 › [Components](#25-components), `sources.js` and `adapters/gbfs.js`: the contracts.
- `docs/sources/ambici.md` and `docs/sources/bicing.md`, the Index row: the index URLs.
- `spikes/cloudflare-capture-spike/js/src/V4.js`, `listFeeds` (lines 48–49): the two GBFS shapes.

#### Do

1. Write `capture/test/unit/sources.test.js` and `capture/test/unit/gbfs.test.js`, and run them to see them fail.
2. Implement `capture/src/sources.js` and `capture/src/adapters/gbfs.js` until they pass.

#### Check

- `npx vitest run test/unit/sources.test.js test/unit/gbfs.test.js` in `capture/` passes.
- `sources.js` and `gbfs.js` import nothing from the Workers runtime and do no I/O.

### Step 4 — Pass schedule

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d004.s4 - add the pass schedule`
- **R:** R2, R3, R4, R5
- **Model:** sonnet · medium

#### Scope

`extraFetch`, the calendar of [Pass schedule](#pass-schedule) as explicit tables.

- `capture/src/schedule.js` (new): the hourly table and the daily table, looked up by the UTC minute and hour of `scheduledTime`.
- `capture/test/unit/schedule.test.js` (new): the R2, R3, R4 (unit) and R5 rows of the Test plan; the heartbeat 24 times a day at `:22`; a `scheduledTime` some seconds into its minute returns that minute's extra fetch.

#### Reads

- d004 › [Pass schedule](#pass-schedule), both tables.
- d004 › [Components](#25-components), `schedule.js`.

#### Do

1. Write `capture/test/unit/schedule.test.js`, and run it to see it fail.
2. Implement `capture/src/schedule.js` until it passes.

#### Check

- `npx vitest run test/unit/schedule.test.js` in `capture/` passes.

### Step 5 — Write-once storage

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d004.s5 - add write-once storage with retries`
- **R:** R1, R9, R10
- **Model:** sonnet · high

#### Scope

`storage.js`, the only module that calls the R2 binding ([Write-once](#write-once)).

- `capture/src/storage.js` (new): `runIdOf`, `rawKey`, `logKey`, `stateKey`, `putOnce`, `putState`, `getState`.
- `capture/test/contract/bronze-keys.test.js` (new): the R1 contract row; every valid case of `contracts/bronze-keys.json`, through `runIdOf` and `rawKey` or `logKey` by `kind`.
- `capture/test/unit/storage.test.js` (new): the R9 and R10 unit rows; `putState` retries as `putOnce`; `getState` returns null for a missing key and for a read that throws. The bucket is a fake binding whose `put`, `head` and `get` the test sets, and `retryDelayMs` is 0.

#### Reads

- d004 › [Write-once](#write-once), whole: the conditional put, the two answers and the `head` on error.
- d004 › [Components](#25-components), `storage.js`.
- `.claude/rules/code/cloudflare-worker.md` › Unit tests and Contract tests.

#### Do

1. Write `capture/test/contract/bronze-keys.test.js` and `capture/test/unit/storage.test.js`, and run them to see them fail.
2. Implement `capture/src/storage.js` until they pass.

#### Check

- `npx vitest run test/contract/bronze-keys.test.js test/unit/storage.test.js` in `capture/` passes.
- Changing one valid `key` in `contracts/bronze-keys.json` by one character makes the contract test fail; the change is reverted.

### Step 6 — Pass logs

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d004.s6 - add the pass log`
- **R:** R11, R15
- **Model:** sonnet · medium

#### Scope

`log.js`, the events of D9 and the pass's log object ([Pass logs](#pass-logs)).

- `capture/src/log.js` (new): `buildEvent`, `toJsonl`, `writeLog`, writing through `putOnce` and `logKey`.
- `capture/test/contract/capture-logs.test.js` (new): the R15 contract row; every valid case of `contracts/capture-logs.json`, through `buildEvent` and `toJsonl`.
- `capture/test/unit/log.test.js` (new): the R11 unit row, with a fake bucket that always fails and `console.log` and `console.error` spied.

#### Reads

- d004 › D9, the table and the paragraph after it.
- d004 › [Pass logs](#pass-logs), the table.
- d004 › [Components](#25-components), `log.js`.

#### Do

1. Write `capture/test/contract/capture-logs.test.js` and `capture/test/unit/log.test.js`, and run them to see them fail.
2. Implement `capture/src/log.js` until they pass.

#### Check

- `npx vitest run test/contract/capture-logs.test.js test/unit/log.test.js` in `capture/` passes.

### Step 7 — Index state

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d004.s7 - add the index state`
- **R:** R12, R13
- **Model:** sonnet · medium

#### Scope

`index-state.js`, each source's last valid index under `state/` ([Index state](#index-state)). Its requirements are verified at pass level in Steps 11 and 12; this step tests the module.

- `capture/src/index-state.js` (new): `readIndex` and `writeIndex`, through `getState`, `putState` and `stateKey`.
- `capture/test/unit/index-state.test.js` (new): with the in-memory R2 of `wrangler.jsonc`, a written state reads back equal; `readIndex` returns null for a missing key, for text that is not JSON, and for JSON without `refreshed_at` or `feeds`.

#### Reads

- d004 › [Index state](#index-state), the first paragraph and the JSON.
- d004 › [Components](#25-components), `index-state.js`.

#### Do

1. Write `capture/test/unit/index-state.test.js`, and run it to see it fail.
2. Implement `capture/src/index-state.js` until it passes.

#### Check

- `npx vitest run test/unit/index-state.test.js` in `capture/` passes.

### Step 8 — Fixtures

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `test: d004.s8 - add the capture fixtures and their script`
- **R:** —
- **Model:** sonnet · medium

#### Scope

The script that builds capture's fixtures from live responses, and its first output ([Fixtures](#fixtures), [ADR-0037](../decisions/0037-test-fixtures-per-component.md)).

- `capture/scripts/trim-fixtures.js` (new): Node built-in modules and `fetch` only; for each source in `SOURCES`, its index and every feed the index lists; trimming and output as in Fixtures.
- `capture/test/fixtures/<source>/<feed>.json` (new): one file per fetched response; the index is `gbfs.json`.
- `capture/test/fixtures/manifest.json` (new): one entry per fixture with `source`, `feed`, `url` and `captured_at`, and `attribution` for Bicing.

#### Reads

- d004 › [Fixtures](#fixtures), whole.
- `docs/sources/bicing.md`: the attribution text.

#### Do

1. Write `capture/scripts/trim-fixtures.js`.
2. Run `npm run fixtures` in `capture/`.

#### Check

- Each source has `gbfs.json` and one file per feed its index lists, including every feed of `requiredFeeds`.
- `manifest.json` has one entry per fixture file, each with its four fields, and Bicing's with `attribution`.
- No list under `data`, other than in `gbfs.json`, has more than 3 entries.

### Step 9 — Simulated sources and source fetch

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d004.s9 - add the source fetch and the simulated sources`
- **R:** R7, R14, R16, R22
- **Model:** sonnet · high

#### Scope

The simulated sources every network test uses, and `fetch.js` ([Source fetch](#source-fetch)). These rows are verified at pass level in Step 12; this step tests the module.

- `capture/vitest.config.js` (modified), as described in the [Test plan](#26-test-plan) and [Fixtures](#fixtures):
  - each fixture compressed once with `gzipSync`, served by `outboundService` at the URL the manifest records for it, without `Content-Encoding`, and passed to the tests as a base64 binding;
  - fixed routes on `https://sim.test/`, built in memory from a fixture:
    - failures: `http-500`, `stall-body` (headers, then a body that never ends), `network-error` (the request throws), `plain-json` (a fixture uncompressed), `oversized` (a body larger than the tests' `maxBytes`, with no `content-length`);
    - indexes, each in the GBFS shape of its source: `invalid-index/<source>` (the fixture index without one required feed), `index-extra-feed/<source>` (with one entry not in `requiredFeeds`), `index-oversized/<source>` (gzip bytes that decompress beyond the tests' `maxBytes`);
    - `moved/<source>/<feed>`: that fixture's gzip bytes at a URL other than its own (R6);
    - heartbeat: `heartbeat` (HTTP 200) and `heartbeat-network-error` (throws an error whose message contains the request URL);
    - counter: every route counts the requests it receives by path, and `count/<path>` answers that count. A test that counts requests appends a suffix of its own to the route, `/<id>`, so counts do not mix across tests;
    - the routes are declared in one table, each with a one-line comment stating what it answers and the case it serves, so the file is the catalogue of simulated responses;
  - the binding `HEARTBEAT_URL` set to `https://sim.test/heartbeat/default`.
- `capture/src/fetch.js` (new): `LIMITS`, `fetchFeed`, `gunzipText`.
- `capture/test/unit/fetch.test.js` (new), with `LIMITS` in milliseconds and bytes: a fixture returns its gzip bytes unchanged with `recompressed: false`; `plain-json` returns gzip bytes with `recompressed: true`; `http-500`, `stall-body`, `network-error` and `oversized` return their `errorType`, with `status` and `latencyMs` as in R14; `gunzipText` rejects a body over `maxBytes` once decompressed.

#### Reads

- d004 › [Source fetch](#source-fetch), whole.
- d004 › [Tests and contracts](#tests-and-contracts), the table; the [Test plan](#26-test-plan), the paragraph before the table.
- d004 › [Components](#25-components), `fetch.js`.
- `spikes/testing-conventions/worker/vitest.config.js`, whole: `outboundService` and the fixture binding as proven in s008.
- `.claude/rules/code/cloudflare-worker.md` › Integration tests and Not covered by local tests.

#### Do

1. Update `capture/vitest.config.js` with the fixtures, the routes and the bindings.
2. Write `capture/test/unit/fetch.test.js`, and run it to see it fail.
3. Implement `capture/src/fetch.js` until it passes.

#### Check

- `npx vitest run` in `capture/` passes, the earlier steps' tests included.
- No test sends a request outside the simulated sources: `outboundService` answers any other URL with an error that fails the test.

### Step 10 — Heartbeat

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d004.s10 - add the heartbeat signal`
- **R:** R20, R23
- **Model:** sonnet · medium

#### Scope

`heartbeat.js`, the Healthchecks.io signal (D10).

- `capture/src/heartbeat.js` (new): `sendHeartbeat`.
- `capture/test/unit/heartbeat.test.js` (new): the R23 unit row, with `heartbeat-network-error`; `heartbeat/<id>` returns `ok: true`; `http-500` returns `errorType: "http"`; `stall-body` with `heartbeatTimeoutMs` in milliseconds returns `errorType: "timeout"`.

#### Reads

- d004 › D10, the first paragraph.
- d004 › [Components](#25-components), `heartbeat.js`.

#### Do

1. Write `capture/test/unit/heartbeat.test.js`, and run it to see it fail.
2. Implement `capture/src/heartbeat.js` until it passes.

#### Check

- `npx vitest run test/unit/heartbeat.test.js` in `capture/` passes.

### Step 11 — Pass and entry point

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d004.s11 - add the capture pass and the scheduled handler`
- **R:** R1, R4, R6, R10, R15, R17, R21
- **Model:** sonnet · high

#### Scope

`runPass` and the Worker's entry point, as in [Architecture](#23-architecture), tested on a normal pass.

- `capture/src/pass.js` (new): `runPass`, mapping each `kind` to its adapter.
- `capture/src/worker.js` (modified): the default export of [Components](#25-components) › `worker.js`, its `scheduled` handler now calling `runPass`.
- `capture/test/unit/worker.test.js` (new): the R21 unit row.
- `capture/test/integration/pass.test.js` (new): the integration rows of R1, R4, R6, R10, R15 (one object per pass, with the common fields) and R17. Each test seeds `state/` with `writeIndex` from the fixture indexes. A plain pass runs the `scheduled` handler; a test that needs a fixed time, small limits or a request count calls `runPass` with `now`, `limits` or a `heartbeatUrl` of its own, `heartbeat/<id>`, and reads requests at `count/heartbeat/<id>`. R6 seeds `state/` with the feed's URL set to `moved/<source>/<feed>`.

#### Reads

- d004 › [Architecture](#23-architecture), the paragraph and the diagram.
- d004 › [Index state](#index-state), the paragraph on adoption (DL13).
- d004 › [Components](#25-components), `pass.js` and `worker.js`.
- d004 › [Test plan](#26-test-plan), the rows of this step's R.

#### Do

1. Write `capture/test/unit/worker.test.js` and `capture/test/integration/pass.test.js`, and run them to see them fail.
2. Implement `capture/src/pass.js` and `capture/src/worker.js` until they pass.

#### Check

- `npx vitest run` in `capture/` passes.
- Only `storage.js` calls methods of the bucket: `grep -rn 'bucket\.' capture/src` matches only `capture/src/storage.js`.
- Only `worker.js` reads `env`: `grep -rn 'env\.' capture/src` matches only `capture/src/worker.js`.

### Step 12 — Pass failures

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `test: d004.s12 - cover capture pass failures`
- **R:** R7, R8, R12, R13, R14, R15, R16, R18, R20, R22, R23, R24
- **Model:** sonnet · high

#### Scope

The pass under every failure of D8, D10 and D12, at integration level.

- `capture/test/integration/pass-failures.test.js` (new): the integration rows of R7, R8, R12, R13, R14, R15 (the log is written when every data write fails), R16, R18, R20, R22, R23 and R24. Tests call `runPass` with `LIMITS` in milliseconds and bytes, and with sources or `state/` entries that point to the `sim.test` routes of Step 9: `invalid-index` for R12 and R24, `index-extra-feed` for R16, `index-oversized` for R22, and `http-500/<id>` with `count/http-500/<id>` for R8. A failing bucket is a proxy over the test's R2 binding that fails `put` for the prefixes a test chooses.
- `capture/src/pass.js` (modified, only if a test shows a gap): the fix that makes it pass. If the fix contradicts a decision or a contract of this design, the step stops and reports it.

#### Reads

- d004 › D8, the table; D9, the paragraph after the table; D12, the table.
- d004 › [Test plan](#26-test-plan), the rows of this step's R.

#### Do

1. Write `capture/test/integration/pass-failures.test.js`, and run it.
2. Update `capture/src/pass.js` for each failing test, if any.

#### Check

- `npx vitest run` in `capture/` passes.
- Every row of the Test plan with Method Test has a test in `capture/test/`: each row's R appears in a test name or in a comment of the test that verifies it.

### Step 13 — CI job

- **Status:** 💤 todo
- **Who:** Claude; the owner switches the ruleset's required check
- **Commit:** `ci: d004.s13 - add the capture job and the ci-passed aggregator`
- **R:** —
- **Model:** sonnet · medium

#### Scope

The CI job of the `capture` component and the aggregator that becomes the only required check (ADR-0013, `.claude/rules/code/ci.md`).

- `.github/workflows/ci.yml` (modified):
  - job `changes`, with `dorny/paths-filter` at its latest major, pinned by major tag as the other actions in `ci.yml`: one output `capture`, true when the PR touches `capture/**`, `contracts/**` or `.github/workflows/ci.yml` (ADR-0013 path filter; `ci.md`, contract inside the filter of every job that reads it);
  - job `capture`, with `needs: changes` and `if: needs.changes.outputs.capture == 'true'`, following the recipe of `ci.md` › Job per component: `working-directory: capture`, `actions/setup-node@v7` with `node-version-file: capture/.nvmrc`, `cache: npm` and `cache-dependency-path: capture/package-lock.json`, then `npm ci` and `npx vitest run`, the whole suite;
  - job `ci-passed`, with `needs: [changes, docs, capture]` and `if: always()`, whose only step fails if any job in `needs` has the result `failure` or `cancelled`; `skipped` passes, since a filtered job is skipped. Without `if: always()` it would be skipped when a job fails, and GitHub treats a skipped required check as passed;
  - the `TODO(T039)` comment removed.
- Ruleset of `main` (owner, outside the repository): required check `ci-passed` in place of `docs`.

#### Reads

- `.claude/rules/code/ci.md`, whole: the job recipe and the aggregator rule.
- `.github/workflows/ci.yml`, whole: the `docs` job and its action versions.

#### Do

1. Add the job `capture` to `.github/workflows/ci.yml`.
2. Add the job `ci-passed`, and remove the `TODO(T039)` comment.
3. The owner switches the ruleset's required check from `docs` to `ci-passed`, after the PR run of this commit shows `ci-passed`.

#### Check

- The PR run shows `changes`, `docs`, `capture` and `ci-passed` green, and the whole workflow takes less than 10 min.
- The step of `ci-passed` fails only on `failure` or `cancelled`, so a `capture` skipped by the filter passes (Inspection).
- The ruleset of `main` lists `ci-passed` as its only required check.
- `grep -rn "TODO(T039)" .github/` finds nothing.

### Step 14 — Documents

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `docs: d004.s14 - document production capture`
- **R:** —
- **Model:** sonnet · medium

#### Scope

The documents of File layout that describe the system and are not rule documents. Each change follows the rules of its document type (`.claude/rules/docs/architecture.md` for `architecture.md`).

- `docs/architecture.md` (modified):
  - § 6.1 Capture pass: rewritten for one pass of production capture: dynamic feeds every pass, at most one extra fetch at fixed minutes, the index read from `state/`, the heartbeat, and the log written last. It has the steps table and the diagram of d004 › [Architecture](#23-architecture), each row citing d004's decisions or ADRs.
  - § 10 Quality requirements: a row `QS18`, Completeness, normal operation, each dynamic feed has a clean capture in at least 99.5% of the minutes of each month, citing d004 › D6; the line `TODO(T039): capture completeness target.` removed.
- `docs/testing-strategy.md` (modified): in the Cloudflare Worker section, Where (item 4), "Node pinned in `package.json` `engines`" becomes "Node pinned in `.nvmrc`", as `.claude/rules/code/dependencies.md` sets; the rest of the section is checked against File layout and the Test plan, and any mismatch is fixed.
- `docs/sources/ambici.md` (modified), § Known characteristics, and `docs/sources/bicing.md` (modified), § Data quality notes (real time): the facts capture depends on, listed after File layout. These are: how often each static feed changed (D3), the GBFS `ttl` values (D3), the stable index size (D5), the latency shifts (D4), Bicing's missing `content-length` ([Source fetch](#source-fetch)) and the largest response observed (D12). Each fact goes to the card of its source, citing d004 or s006.
- `docs/spikes/s012-execution-target.md` (modified): the line with `TODO(T039)` (line 471) removed, since D9 and D10 resolve its items.

#### Reads

- `.claude/rules/docs/architecture.md`, whole.
- `docs/architecture.md` › 6.1 and 10.
- d004 › [Architecture](#23-architecture), [Pass schedule](#pass-schedule), D3, D4 (second paragraph), D5, D6, D12, and [Source fetch](#source-fetch) (size limit).
- `docs/testing-strategy.md` › Cloudflare Worker.
- `docs/sources/ambici.md` › Known characteristics; `docs/sources/bicing.md` › Data quality notes (real time).
- [s006](../spikes/s006-cloudflare-capture.md), only to find which feed and source gave a fact that d004 states without it, such as the largest response.
- `docs/spikes/s012-execution-target.md`, lines 225–235 and 465–475.

#### Do

1. Update `docs/architecture.md` § 6.1 and § 10.
2. Update `docs/testing-strategy.md`.
3. Update `docs/sources/ambici.md` and `docs/sources/bicing.md`.
4. Remove the `TODO(T039)` line from `docs/spikes/s012-execution-target.md`.

#### Check

- `grep -rn "TODO(T039)" docs/` finds only lines of d004.
- `grep -n "engines" docs/testing-strategy.md` finds nothing.
- Each new row and bullet in `architecture.md` and in the source cards cites its source.
- The Markdown lint hook reports no error on the five files.

### Step 15 — Switch tooling

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `chore: d004.s15 - add the switch and completeness tooling`
- **R:** —
- **Model:** sonnet · medium

#### Scope

The one-off tooling of [Switch tooling](#switch-tooling), next to the spike's analysis. It is throwaway code under `spikes/`, so `dependencies.md` does not apply; it runs with the Prerequisites' Python and DuckDB.

- `spikes/cloudflare-capture-spike/analysis/spike_raw_switch.py` (new), with the standard library only and `argparse`. Listings are `rclone lsf -R` output: one path per line, relative to the listed root, `<source>/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz`; lines ending in `/` are folders and are skipped.
  - `keys --prod <listing> --spike <listing> --cutoffs <file> --out <file>`: if `--cutoffs` does not exist, it writes it from `--prod`, as JSON mapping `<source>/<feed>` to the minute of that feed's first object, `YYYYMMDDTHHMM`. If it exists, it reads it unchanged. It then writes to `--out` every spike path whose timestamp is earlier than its feed's cutoff, and exits 1 if a feed under `--spike` has no cutoff.
  - `count --prod <listing> --spike <listing> --cutoffs <file>`: for each source, feed and day before the cutoff, it prints the object count in both listings and exits 1 on any difference.
- `spikes/cloudflare-capture-spike/analysis/capture-completeness.sql` (new), for DuckDB. Its inputs are two variables set at its top, the listing file and the first full UTC day of the window (`SET VARIABLE`). It reads the listing, keeps the dynamic feeds of D3 within the 7 days from that day, and counts per source and feed the distinct minutes with at least one object, from the key's timestamp. It prints `source`, `feed`, `minutes`, `pct` (minutes / 10,080) and `below_target` (`pct` < 99.5%).
- `spikes/cloudflare-capture-spike/README.md` (modified), § Layout and § Running it: the switch script, `spike-log-queries.sql`, the completeness query and the write-once probe (`js/src/probe-write-once.js`, `js/wrangler.probe.jsonc`), each with its command.

#### Reads

- d004 › [Switch tooling](#switch-tooling), whole; D11, the numbered list.
- d004 › D6, the first two sentences: what a clean minute is.
- `spikes/cloudflare-capture-spike/README.md` › Layout and Running it.
- `spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql`, the first lines: how the existing query reads its input.

#### Do

1. Write `spikes/cloudflare-capture-spike/analysis/spike_raw_switch.py`.
2. Write `spikes/cloudflare-capture-spike/analysis/capture-completeness.sql`.
3. Update `spikes/cloudflare-capture-spike/README.md`.

#### Check

Run in the scratchpad, with hand-written listings of two feeds over two days:

- `keys` writes the cutoffs and lists exactly the spike paths before each cutoff; run again after editing the production listing, it keeps the same cutoffs.
- `keys` exits 1 when the spike listing has a feed that the production listing lacks.
- `count` exits 0 on equal listings, and 1 after one line is removed from the production listing before the cutoff.
- `capture-completeness.sql` on a listing with one minute missing in one feed prints `minutes` 10,079 for that feed and 10,080 for the others.

### Step 16 — First deploy

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** — (only if the deployment token needed a wider permission: `docs: d004.s16 - record the deployment token permission`, in Deployment)
- **R:** R19, R21
- **Model:** —

#### Scope

Production capture running from `main`, monitored, with its scoped deployment token ([Deployment](#deployment), D10, D11 step 1). Before it starts, the PR with Steps 1–15 has merged by rebase, with `Refs #N` so the task stays open (DL22). From here on, the work runs on a new branch with the task's name, created from the updated `main`, which ends in the PR that closes the task.

- Cloudflare: bucket `bikesharing-bronze`, with no lock yet (D11 step 4); Worker `bikesharing-capture` with the secret `HEARTBEAT_URL`; account-owned API token `bikesharing-capture-deploy`, Editor on that Worker only, one-year expiry; R2 token `bikesharing-t039-switch`, Object Read & Write on `bikesharing-capture-spike` and `bikesharing-bronze`, used by rclone from here until Step 18.
- Healthchecks.io: check `bikesharing-capture`, period 1 h, grace 1 h, email to the owner.
- Local machine: `CLOUDFLARE_API_TOKEN` in `.env`; rclone remote `r2` switched to the switch token.
- Verified: R19 (Demonstration), R21 (Inspection after deploy), the smoke test after each deploy, and TH6.

#### Reads

- d004 › [Deployment](#deployment), whole.
- d004 › D10, the first paragraph; D11, steps 1–2.

#### Do

1. Create the bucket `bikesharing-bronze` in the Cloudflare dashboard, with no lock rule.
2. Create the R2 token `bikesharing-t039-switch`, and set it as the credentials of the rclone remote `r2`.
3. Create the Healthchecks.io check `bikesharing-capture` with a period of 1 min and a grace of 1 min. Send one signal with `curl` to its URL, and wait for the alert email (R19). Then set the period to 1 h and the grace to 1 h.
4. From `capture/` on the updated `main`, run `npm ci`, `npx wrangler login` and `npx wrangler deploy`.
5. Run `npx wrangler secret put HEARTBEAT_URL`, pasting the check's URL at the prompt. Until then, the passes at `:22` log `heartbeat_failed`.
6. Run the smoke test of Deployment on the first passes.
7. Create the API token `bikesharing-capture-deploy`, and store it in `.env` as `CLOUDFLARE_API_TOKEN`. Run `npx wrangler logout`, then, from `capture/`, load the root `.env` with `set -a; source ../.env; set +a` and run `npx wrangler deploy`, and repeat the smoke test.
8. If that deploy fails for lack of permission, widen the token only as far as the error names, and have Claude record the permission in Deployment.

#### Check

- The alert email of Do 3 arrived.
- After each deploy, each dynamic feed has a new object under `raw/` that passes `gunzip -t`, and the pass's log object exists with `recompressed: false` and the deployed version ID in `version` (smoke test).
- The Worker's dashboard shows no `workers.dev` route and no preview URLs (R21, Inspection).
- The deploy of Do 7 succeeded with `bikesharing-capture-deploy`, and the token's page lists only this Worker (TH6).
- After the first `:22` that follows Do 5, Healthchecks.io shows the check as up.

### Step 17 — Copy and lock

- **Status:** 💤 todo
- **Who:** Owner; Claude records the result in Close
- **Commit:** `docs: d004.s17 - record the copy of the spike's data`
- **R:** —
- **Model:** sonnet · medium

#### Scope

The spike's responses copied into production up to each feed's cutoff, checked, and bronze locked (D2, D11 steps 2–4, TH4). It starts once production has stored every feed at least once, at least 24 h after Step 16, since the daily feeds run once every 24 h. Listings and the cutoffs file go to `spikes/cloudflare-capture-spike/analysis/output/`, which Git ignores.

- Cloudflare: objects under `bikesharing-bronze/raw/` copied from `V4/raw/`; lock rules on `raw/` and `logs/` with no expiry ([ADR-0023](../decisions/0023-storage-security-baseline.md)).
- d004 › 4.1 Implemented (modified): the cutoff of each feed and the counts per day and feed.

#### Reads

- d004 › [Switch tooling](#switch-tooling), the first three paragraphs; D11, steps 2–4.
- `spikes/cloudflare-capture-spike/README.md` › Running it: the commands of Step 15.
- [ADR-0023](../decisions/0023-storage-security-baseline.md): the lock rules.

#### Do

1. From `spikes/cloudflare-capture-spike/`, save the listings: `rclone lsf -R r2:bikesharing-bronze/raw > analysis/output/prod-before.txt` and `rclone lsf -R r2:bikesharing-capture-spike/V4/raw > analysis/output/spike.txt`.
2. Run `keys` with `--prod analysis/output/prod-before.txt`, `--spike analysis/output/spike.txt`, `--cutoffs analysis/output/cutoffs.json` and `--out analysis/output/keys.txt`. If it exits 1, a feed is still missing in production: wait for it and repeat from Do 1.
3. Run `rclone copy --files-from analysis/output/keys.txt r2:bikesharing-capture-spike/V4/raw r2:bikesharing-bronze/raw`.
4. Save `rclone lsf -R r2:bikesharing-bronze/raw > analysis/output/prod-after.txt`, and run `count` with it, the spike listing and the cutoffs. If it exits 1, repeat Do 3 and this one; never go on to Do 5 with a difference.
5. Enable the bucket lock on `bikesharing-bronze` for the prefixes `raw/` and `logs/`, with no expiry.
6. Try to overwrite one existing object under `raw/` with `rclone rcat` and to delete it with `rclone deletefile`.
7. Give Claude the cutoffs and the output of `count`, for 4.1 Implemented.

#### Check

- `count` exits 0 before the lock is enabled.
- Both attempts of Do 6 fail, and the object still passes `gunzip -t` (TH4).
- After the lock, new objects keep arriving under `raw/` and `logs/`, and the next log objects show `feed_captured` with `attempts: 1`.

### Step 18 — Retire the spike

- **Status:** 💤 todo
- **Who:** Owner; Claude reads the query results and records them in Close
- **Commit:** `docs: d004.s18 - record the spike log queries`
- **R:** —
- **Model:** sonnet · medium

#### Scope

`capture-v4` stopped, its logs queried once, and every resource of the spike and of the probe deleted (D2, D11 steps 5–6, [ADR-0035](../decisions/0035-cloud-resource-naming.md)).

- Cloudflare: Worker `capture-v4`, bucket `bikesharing-capture-spike`, the spike's tokens, `bikesharing-t039-switch` and bucket `bikesharing-t039-write-once` deleted.
- d004 › 4.1 Implemented (modified): what the queries of D2 found; new findings that need work go to Out of scope as tasks.

#### Reads

- d004 › D2, the second paragraph; D11, steps 5–6.
- `spikes/cloudflare-capture-spike/README.md` › Running it.
- `spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql`, the header: how to run it.

#### Do

1. Delete the Worker `capture-v4` in the dashboard, which stops it; no local credential is needed, as `bikesharing-capture-deploy` reaches only `bikesharing-capture`.
2. From the spike root, run `rclone copy r2:bikesharing-capture-spike data` for the last logs.
3. From the repository root, run `duckdb -f spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql`, and give Claude its output.
4. Delete the bucket and its contents with `rclone purge r2:bikesharing-capture-spike`.
5. Delete the bucket `bikesharing-t039-write-once` in the dashboard.
6. Delete the spike's tokens and `bikesharing-t039-switch` in the dashboard.

#### Check

- The dashboard lists neither `capture-v4`, `bikesharing-capture-spike` nor `bikesharing-t039-write-once`, and no token of the spike or of T039 other than `bikesharing-capture-deploy`.
- `bikesharing-capture` keeps storing a new object per dynamic feed every minute.

### Step 19 — Production checks

- **Status:** 💤 todo
- **Who:** Owner; Claude records the results in Close
- **Commit:** `docs: d004.s19 - record the production checks`
- **R:** —
- **Model:** sonnet · medium

#### Scope

The two Done when checks on production data: CPU over days 1–3, and completeness over days 1–7 ([Deployment](#deployment), [Switch tooling](#switch-tooling), D4, D6). Day 1 is the first full UTC day after Step 16's deploy, since the day of the deploy is partial.

- Cloudflare: R2 token `bikesharing-t039-completeness`, Object Read on `bikesharing-bronze` only, created and then deleted.
- d004 › 4.1 Implemented (modified): the max CPU and the time of the costliest pass; the window and the percentage of each dynamic feed.

#### Reads

- d004 › [Deployment](#deployment), the CPU paragraph; [Switch tooling](#switch-tooling), the last two paragraphs.
- `spikes/cloudflare-capture-spike/README.md` › Running it: the completeness query.

#### Do

1. On each of days 2, 3 and 4, open the Query Builder for `bikesharing-capture` over the previous full UTC day. Read the max of `$workers.cpuTimeMs` with the time of that invocation, and the count of invocations with outcome `exceededCpu`.
2. On day 8, once day 7 has ended, create the token `bikesharing-t039-completeness`, and set it as the credentials of the rclone remote `r2`.
3. Save `rclone lsf -R r2:bikesharing-bronze/raw > spikes/cloudflare-capture-spike/analysis/output/prod-completeness.txt`.
4. Run `capture-completeness.sql` with that listing and day 1 as the first day of the window, and give Claude its output and the figures of Do 1.
5. Delete the token `bikesharing-t039-completeness`.

#### Check

- On each of the 3 days, the max of `$workers.cpuTimeMs` is below 10 ms, and no invocation has the outcome `exceededCpu`.
- `below_target` is false for every dynamic feed.
- The dashboard no longer lists `bikesharing-t039-completeness`.

## 4. Close

<!-- The record of what the task delivered, for whoever opens this design later. -->

### 4.1 Implemented

<!-- Component — what was delivered; tests passing. -->

### 4.2 Known gaps at close

<!-- What the task leaves undone or imperfect, each with the task that covers it: requirements not fully met, File layout items not delivered, TODOs citing this task. "None" is valid. -->

- `<gap>` — TNNN

### 4.3 Decisions taken during implementation

<!-- Decisions made after the Plan was approved: <decision> — <reason>. "None" is valid. -->
