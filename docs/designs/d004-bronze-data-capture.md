<!--
Design doc template. A design doc is the working document of one task: Spec (what and why), Plan (how), Steps (implementation), Close (what was delivered).
It is detailed enough that Code can implement it without making design decisions.
Sections marked Optional are kept only when they apply.
-->

# Design: Bronze data capture

- **Task:** T039
- **ADRs:** [ADR-0005](../decisions/0005-utc-for-all-stored-timestamps.md), [ADR-0006](../decisions/0006-raw-layer-keeps-source-responses-untouched.md), [ADR-0011](../decisions/0011-cloudflare-workers-r2-for-realtime-capture.md), [ADR-0012](../decisions/0012-collectors-decoupled-by-output-contract.md), [ADR-0018](../decisions/0018-medallion-architecture.md), [ADR-0020](../decisions/0020-bronze-as-captured-objects.md), [ADR-0021](../decisions/0021-retention-per-layer.md), [ADR-0023](../decisions/0023-storage-security-baseline.md), [ADR-0030](../decisions/0030-pipeline-logs.md), [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md)
- **New ADRs from this doc:** one for the bucket naming convention (D1), unless an existing ADR already covers it; [ADR-0030](../decisions/0030-pipeline-logs.md) is amended (D9)

## Status

<!-- State: Draft 📝 · Ready for implementation 🎬 · In progress 🔄 · Complete ✅.
Phase: the blocks and reviews completed.
Current step: the step being implemented, or —. -->

- State: Draft 📝
- Phase: [x] Spec · [ ] Plan · [ ] Plan review · [ ] Steps · [ ] Steps review
- Current step: —

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
| Hourly | `station_information` of each source |
| Daily | The other 12 static feeds: `system_information`, `system_pricing_plans`, `system_regions`, `vehicle_types` and `geofencing_zones` of each source, `system_hours` of AMBici, `gbfs_versions` of Bicing |

A change in a daily feed is recorded up to 24 h late, and two changes in one day keep only the last one.

If a daily feed starts changing more than once a day as a habit, move it to hourly. A daily feed that changes occasionally does not reopen this decision.

Rejected: every 2 days or weekly for the daily feeds. Weekly saves about 1.2 MB per year against bronze's roughly 2.9 GB per month, and delays a change by up to 7 days.

#### D4. Static feeds spread across passes

Each capture pass carries the dynamic feeds and at most one extra fetch, either a static feed, an index refresh (D5) or the heartbeat (D10), so dynamic feeds are captured every minute and no extra fetch adds to another's CPU time. [s006](../spikes/s006-cloudflare-capture.md) measured about 5 ms for a dynamic pass and 23–28 ms with the 16 feeds of a static pass, which estimates 1.5 ms per added feed and about 6.5 ms for a pass with one extra fetch. Extra fetches run at fixed, distinct minutes; 132 of the 1,440 daily passes carry one. While a source has no valid index, its passes fetch only that index, in place of its feeds and extras (D8), so they cost less than a normal pass.

CPU time can shift without any change of ours. During the spike's capture, median source latency moved from about 270 ms to 38 ms on 2026-10-29 at 22:07 UTC, and to about 145 ms on 2026-11-03 at about 08:00 UTC, while the average CPU per run rose from 2–3 ms to almost 5 ms; the only deployment was on 2026-10-14. Both shifts coincided with a change in the second at which the cron starts, which suggests a move of the Worker by Cloudflare; this is not confirmed. Passes with a static feed therefore keep a margin below the limit.

If passes with an extra fetch exceed the 10 ms limit in production, run them in their own executions.

Rejected: separate executions for static feeds from the start. They give the lowest peak, but add complexity and depend on Cloudflare starting two independent executions in the same minute, which is unverified.

#### D5. Hourly index refresh

Each source's index (`gbfs` feed) is refreshed once per hour, independently of the static feeds, at a different minute for each source. If a feed's URL changes, capture picks it up within an hour, which bounds the dynamic data lost. The size of both indexes did not change in 22 days of hourly reads, so the refresh rarely finds anything new, but its cost is small: 48 reads and 48 writes per day.

Rejected:

- Daily refresh: a changed URL could cost up to 24 h of dynamic data, which cannot be captured again.
- Daily refresh, and also on a feed's 404: it loses the least data, but adds logic that a brief 404 would trigger needlessly.

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

Capture writes one log object per pass as JSON Lines, under `logs/date=<YYYY-MM-DD>/<run_id>.jsonl`, where `run_id` is the pass's capture time in the [ADR-0012](../decisions/0012-collectors-decoupled-by-output-contract.md) key format. The format follows [ADR-0030](../decisions/0030-pipeline-logs.md), which is amended to add two common fields for the whole project, with the owner's permission since nothing is built on it yet: `component` names the part of the system that wrote the event, following the practice of `service.name` in OpenTelemetry, and `version` identifies the deployed code of that component. Every event therefore carries `ts`, `level`, `component`, `version`, `run_id` and `event`, plus the fields of its event.

In capture, `component` is `capture` and `version` is the Worker's version ID.

| Event | Level | Own fields |
|---|---|---|
| `feed_captured` | `info` | `source`, `feed`, `status`, `latency_ms`, `bytes`, `attempts` |
| `feed_failed` | `error` | `source`, `feed`, `status`, `latency_ms`, `attempts`, `error_type`, `error` |
| `index_refreshed` | `info` | `source`, `status`, `latency_ms`, `bytes`, `unknown_feeds` |
| `index_rejected` | `error` | `source`, `status`, `latency_ms`, `error_type`, `error` |
| `heartbeat_sent` | `info` | `status`, `latency_ms` |
| `heartbeat_failed` | `warning` | `status`, `latency_ms`, `error_type`, `error` |

`attempts` counts write attempts, and is 0 when the source fails. `error_type` is one of `http`, `timeout`, `network`, `too_large`, `write` or `invalid_index`; the event tells whether it came from a feed, an index or the heartbeat. `level` is `info`, `warning` for a failure that does not affect the data, such as the heartbeat's, or `error`. `unknown_feeds` lists the feeds in the index that are not listed in D3, and is usually empty; a feed that the source removes makes the index invalid (D8).

These fields answer the following capture questions, the starting point for T042:

- Is the completeness target (D6) met, and which minutes are missing?
- Is a source degrading, or is a response size unusual?
- Are there duplicate or late passes, and does each object match a log line?
- Did a failure come from the source, a timeout or R2, and is R2 failing even when retries succeed?
- Which deployed code produced this data?
- Has a source added or removed a feed?

The objects under `raw/` are the record of what was captured, and the logs explain failures: a log write can fail after its data was stored (D8).

Questions that need the response's content, such as whether a source keeps returning HTTP 200 with frozen data, belong to the pipeline.

One object per pass meets D7's criteria. It costs about 30–35 MB per month and 43,200 writes (4.3% of R2's free Class A quota), and it adds no CPU beyond the write already measured. The pipeline reads only new objects once and consolidates them in the data quality table (T042); the originals stay under the bucket lock. Pipeline compute is unmeasured, so T042 validates it.

Rejected:

- Daily compaction in capture: reading 1,440 objects does not fit the 10 ms CPU limit.
- Logging failures only: it loses the latency and sizes of clean captures, which revealed the latency shifts and set the timeout in D8.
- Showing the origin only through a prefix in the event name (`capture.feed_captured`): it needs no ADR change, but mixes two meanings in one field and depends on a naming convention.

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
2. `V4/raw/` is copied up to the last pass before production's first captured minute (D2), so the copy adds no duplicates and no key can collide.
3. The copy is checked by object count per day and feed. If the counts differ, the copy is repeated: the lock is never enabled on an unchecked copy.
4. The bucket lock is enabled.
5. `capture-v4` is stopped, and the queries of D2 run on its complete logs.
6. `bikesharing-capture-spike` is emptied and deleted, together with `capture-v4` and its token, so no access to unused data remains (least privilege, as in [ADR-0023](../decisions/0023-storage-security-baseline.md)). A spike that needs a test bucket creates and removes its own, as [s010](../spikes/s010-storage-table-format.md) did.

The lock is enabled only after the check, as [ADR-0023](../decisions/0023-storage-security-baseline.md) requires, because under the lock a wrong copy can no longer be corrected; production's first hours stay unprotected until then.

Rejected:

- Stopping `capture-v4` before deploying production: it is simpler, but leaves a gap that grows if the deployment fails.
- Keeping the spike's bucket as a test bucket: its name breaks the convention of D1, and it keeps an old token alive.

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

### 1.4 Done when

<!-- Optional. Only what closes this task and Requirements cannot express: operational actions, checks on real data, understanding. The general closing rule is checked in `.claude/skills/implement/review.md`. -->

- `V4/raw/` is copied up to the switch cutoff and checked by object count before the bucket lock is enabled. (D2, D11)
- The bucket lock is enabled, and overwriting an existing object fails. (D11, TH4)
- The queries of D2 have run on the spike's complete logs. (D2)
- `bikesharing-capture-spike`, `capture-v4` and its token are deleted. (D11)
- The deployment token is scoped to the production Worker only. (TH6)
- Passes with an extra fetch stay below 10 ms of CPU in the first days of production. (D4)
- Each dynamic feed has a clean capture in at least 99.5% of the minutes of the first 7 days of production. (D6)

### 1.5 Out of scope

<!-- Optional. What someone could expect and will not be done, each item pointing to the task that covers it. -->

- Calculating and storing completeness and other quality answers (D7), from the questions and fields in D9 — T042
- Quality checks capture does not make: repeated failures of a static feed or an index, and HTTP 200 with frozen data (D10) — T042
- Centralising quality rules and targets, such as D6's, in one place — T042

## 2. Plan — how

<!-- 2-3 sentences -->

### 2.1 Approach

<!-- Detailed plan organized by #### blocks.
Block `3. Steps` is written using this plan.
If some block contains `options considered`, include them with pros and cons.
-->

### 2.2 Decision summary

<!-- It logs decisions about the plan, including changes. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Applies to: anchor link(s) to the section where the decision is applied, named in one or two words.
- Decided at: the Status phase where it was decided (Plan, Steps), or `<phase> review` when decided while reviewing that phase.
- R: Requirement affected.
-->

| # | Applies to | Decision | Reason | R | Decided at |
|---|---|---|---|---|---|
| | | | | | |

### 2.3 Architecture

<!-- Optional. One diagram and 2–3 sentences. -->

### 2.4 File layout

<!-- Every file and folder the task creates or modifies, documents included, as a tree: (new) or (modified), and its purpose or change in one line. A task that adds a component also lists its CI job in `.github/workflows/ci.yml` (recipe in `.claude/rules/code/ci.md`), and its version files, manifest and lockfile (`.claude/rules/code/dependencies.md`). -->

TODO(T039): list `docs/decisions/0030-pipeline-logs.md` (modified) to add `component` and `version` to its common fields (D9).

```text
<path>/
└── <file>      (new)        <purpose>
```

### 2.5 Components

<!-- Optional. One subsection per component. The contract is exact, in the component's own language, never pseudocode. -->

#### `<ComponentName>`

- **Responsibility:** `<one sentence>`
- **Location:** `path/to/file`
- **Contract:**

```python
```

### 2.6 Test plan

<!-- Optional. Every requirement has at least one test, at the lowest level that can verify it. -->

| R | Test concept | Level |
|---|---|---|
| R1 | | unit / integration / e2e |

### 2.7 Breaking changes

<!-- Optional. Shared models or interfaces this design changes, and how their dependants are handled. -->

| File | Why it breaks | Strategy |
|---|---|---|
| | | |

### 2.8 What does not change

<!-- Optional. Code or documents that must not be modified. Out of scope limits the what; this section limits the how. -->

-

## 3. Steps

<!-- Each step is one reviewable result and one commit, touching at most 2–3 files.
- Status: where the step is: 💤 todo · 🎬 ready · 🔄 in progress · ⛔ blocked · ✅ done
- Who: Owner (manual actions: dashboards, accounts, deploys, runs, checks) or Claude (code and documents).
- R: the requirements the step implements or tests, or —.
- Commit: the proposed message, following the Git conventions in CLAUDE.md.
- Model: the model and effort the step's session runs with (e.g. sonnet · medium), or — when Who is Owner. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

### Step 1 — `<Title>`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** following the Git conventions in CLAUDE.md, including `<dNNN.sN - >` at the begining of the message, for the design and the step number.
- **R:** R1, R3 (or —)
- **Model:** `<model · effort>` (or —)

#### Scope

<!-- The result of the step. List the components, the files created or changed (code, tests, docs), and the tests from the Test plan that cover it. A reviewer should know what the diff will contain from this section alone. -->

#### Reads

<!-- List of reads containing what to read (be specific with paragraph or line), what contains the read, and why it is interesting here.  -->

#### Do

<!-- Numbered actions in execution order, one verb each (write, implement, update, run). Every file named here must appear in Scope; add nothing Scope does not list. -->

#### Check

<!-- command/s or verification with a yes/no result. -->

## 4. Close

<!-- The record of what the task delivered, for whoever opens this design later. -->

### 4.1 Implemented

<!-- Component — what was delivered; tests passing. -->

### 4.2 Known gaps at close

<!-- What the task leaves undone or imperfect, each with the task that covers it: requirements not fully met, File layout items not delivered, TODOs citing this task. "None" is valid. -->

- `<gap>` — TNNN

### 4.3 Decisions taken during implementation

<!-- Decisions made after the Plan was approved: <decision> — <reason>. "None" is valid. -->
