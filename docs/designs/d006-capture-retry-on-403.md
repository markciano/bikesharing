<!--
Design doc template. A design doc is the working document of one task: Spec (what and why), Plan (how), Steps (implementation), Close (what was delivered).
It is detailed enough that Code can implement it without making design decisions.
Sections marked Optional are kept only when they apply.
-->

# Design: Capture retry on 403

- **Task:** T059
- **ADRs:** [ADR-0005](../decisions/0005-utc-for-all-stored-timestamps.md), [ADR-0006](../decisions/0006-raw-layer-keeps-source-responses-untouched.md), [ADR-0015](../decisions/0015-contract-tests-by-contract-kind.md), [ADR-0036](../decisions/0036-log-convention-across-components.md)
- **New ADRs from this doc:** [ADR-0039](../decisions/0039-retry-a-403-only-where-shown-transient.md)

## Status

<!-- State: Draft 📝 · Ready for implementation 🎬 · In progress 🔄 · Complete ✅.
Phase: the blocks and reviews completed.
Current step: the step being implemented, or —. -->

- State: Draft 📝
- Phase: [x] Spec · [x] Plan · [x] Plan review · [ ] Steps · [ ] Steps review
- Current step: —

## 1. Spec — what and why

<!-- What the result does seen from outside, not how it is built. The test: if whoever uses the result would notice a change, it belongs here; if not, it belongs to the Plan. External systems and their data (feeds, fields) may be named. -->

### 1.1 Context

<!-- 2–4 sentences for a reader with no prior context: the problem or need and why it matters now; who or what uses the result; where things stand today, including any design or spike this builds on. No solution here: it starts in Decided at framing. For a correction: current vs expected behaviour and how to reproduce it. -->

Bicing answers HTTP 403 to about 1.3 per hour of the production Capture Worker's `station_status` requests, and the Worker retries no source failure ([d004 › D8](d004-bronze-data-capture.md#d8-capture-failure-behaviour)), so each 403 costs that minute's object. That leaves about 2% of the feed's minutes missing, against the 99.5% target of [d004 › D6](d004-bronze-data-capture.md#d6-capture-completeness-target); AMBici is at 100%. Spike s014 showed that the 403s go on with production alone, that each one costs a single minute, and that a request a few seconds later usually gets through ([s014 › Conclusion](../spikes/s014-bicing-403.md#5-conclusion)). This design changes the capture built in d004 accordingly.

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

#### D1. A 403 from Bicing is retried once

Capture retries a Bicing request once when Bicing answers HTTP 403, for feeds and indexes alike; every other failure, and any failure on another source, keeps the no-retry rule of [d004 › D8](d004-bronze-data-capture.md#d8-capture-failure-behaviour), which this decision refines. With production alone, Bicing answers 403 to about 1.26 `station_status` requests per hour, never in two consecutive minutes, and a request a few seconds after a 403 usually gets through ([s014 › F1–F3](../spikes/s014-bicing-403.md#4-findings)): Bicing's 403 behaves as a transient rejection, unlike a source that is down. A 403 is otherwise a final rejection ([RFC 9110 › 403](https://www.rfc-editor.org/rfc/rfc9110#name-403-forbidden)), so the retry stays on the source where that behaviour has been observed; each source states in its configuration whether it retries a 403. **refines [d004 › D8](d004-bronze-data-capture.md#d8-capture-failure-behaviour)**

If the retries logged in production recover fewer 403s than Done when requires, the wait or the approach is revisited. If another source starts answering 403 (its `feed_failed` or `index_rejected` events with `status` 403), a new task checks whether its 403s follow Bicing's pattern before that source retries them.

Rejected:

- Retrying a 403 on every source: there is no evidence of a transient 403 elsewhere, and a 403 that is a real rejection, such as a block, would get twice the requests.
- Retrying only Bicing `station_status`: it misses the same 403 on Bicing's other feeds and its index.
- Also retrying 429, 5xx and network errors: at most about 0.2% of minutes (57 source failures in the spike's 22 days of logs, before the 403s began, d004 › D8), with no evidence that they recover within seconds; a timeout leaves no time to retry anyway.
- Checking the retry with a probe before the deploy: only a Cloudflare Worker reproduces production's conditions, so it would deploy the same change twice; the retry is checked in production instead (Done when).

#### D2. The retry waits 3–5 s at random

The retry starts after a uniform random wait of 3 to 5 s (backoff with jitter). 3–4 s is the only delay after a 403 that has been measured ([s014 › F3](../spikes/s014-bicing-403.md#f3-a-request-a-few-seconds-after-a-403-usually-gets-through)), and a limiter that counts requests over a window of a few seconds could reject a shorter wait. A longer wait costs little: it happens about 1.3 times per hour, and waiting uses no Worker CPU. The jitter spreads the retries across any window the limiter counts.

If the logged retries recover too few 403s (D1), the wait is the first thing revisited.

Rejected:

- A fixed 3 s wait: every retry would land at the same point of a fixed window.
- A wait below 3 s: not measured.

#### D3. One 60 s limit covers the retry

The 60 s limit of [d004 › D8](d004-bronze-data-capture.md#d8-capture-failure-behaviour) covers the whole request: first attempt, wait and retry (an overall deadline). No request lasts longer than it does today, and the retry still has about 54 s, against about 1 s for a successful response (p90 935 ms, [s014 › 5.5](../spikes/s014-bicing-403.md#55-production-inputs)). **refines [d004 › D8](d004-bronze-data-capture.md#d8-capture-failure-behaviour)**

Rejected:

- 60 s per attempt: a request could last about 125 s, twice D8's limit, for no gain, since a 403 arrives fast.

#### D4. A retry is logged as its own event

Each 403 that capture retries writes a `fetch_retried` event, at level `warning`, before the wait, with `source`, `feed` (null for an index), `status` and `latency_ms` of the first attempt, plus `headers`, the response headers except `Set-Cookie`, at most 50 with each value cut to 1,000 bytes, and `body`, the first 1,000 bytes of the response body as text, or null if the body cannot be read. The request's outcome is then logged as today, by `feed_captured`, `feed_failed`, `index_refreshed` or `index_rejected`, whose `status` and `latency_ms` are those of the last attempt; the existing events keep their fields and meaning ([d004 › D9](d004-bronze-data-capture.md#d9-capture-logs)). It extends D9's event table, and `warning` matches D9's level for a failure that does not affect the data. **extends [d004 › D9](d004-bronze-data-capture.md#d9-capture-logs)**

The pass log then answers how many 403s each source gets per hour (the `fetch_retried` events) and how many the retry recovers (those followed in the same pass by `feed_captured` or `index_refreshed` for the same feed), which Done when measures. Who sends the 403 and what it keys on is unknown ([s014 › 5.4](../spikes/s014-bicing-403.md#54-not-verified)): `headers` and `body` can name the limiter or the wait it asks for (`Retry-After`), which the next step needs if the retry falls short, and a 403 that arrives in tens of milliseconds points to a limiter at the network edge, one of hundreds to the origin server. `Set-Cookie` is left out because it can carry a session token (OWASP Logging Cheat Sheet). At typically about 3 KB per event and about 940 403s per month, they add about 3 MB per month to D9's 30–35 MB.

A retry that succeeds:

```json
{"ts":"2026-11-12T10:15:36.120Z","level":"warning","event":"fetch_retried","source":"bicing","feed":"station_status","status":403,"latency_ms":85,"headers":{"content-type":"text/html","server":"…"},"body":"<html>…"}
{"ts":"2026-11-12T10:15:40.530Z","level":"info","event":"feed_captured","source":"bicing","feed":"station_status","status":200,"latency_ms":640,"bytes":48210,"attempts":1,"recompressed":false}
```

The common fields `component`, `version` and `run_id` are left out, and the values are illustrative. When the retry also fails, the second event is `feed_failed` with the retry's `status`, or with `status` null and `error_type` `timeout` if D3's limit runs out.

Rejected:

- Counting fetch attempts in `attempts`: D9 defines it as write attempts, so one field would carry two meanings.
- Renaming `attempts` to say it counts writes: production logs already use the name, so the pipeline would accept both names for good; D9 states its meaning.
- Two new fields in the four source events (fetch attempts and the first attempt's status): it changes four existing events with fields that are almost always empty.
- A fixed list of headers and no body: it needs to guess which headers name the limiter, which is what is unknown.
- Headers and body on every HTTP failure: it changes `feed_failed` and `index_rejected` with no open question to answer.

#### D5. Every source request identifies the project

Every source request, for feeds and indexes alike, sends `User-Agent: bikesharing-capture (+https://github.com/markciano/bikesharing)`: a product name and a contact link, as usual for automated clients of public APIs ([RFC 9110 › User-Agent](https://www.rfc-editor.org/rfc/rfc9110#name-user-agent)), so a source operator can identify the traffic and reach the project instead of blocking it. The link is the public repository; no email address is sent. **extends [d004 › Source fetch](d004-bronze-data-capture.md#source-fetch)**

It ships in the same deploy as D1. It may change the 403 rate in either direction ([s014 › 5.4](../spikes/s014-bicing-403.md#54-not-verified)); Done when measures the 403s the retry does not recover, which does not depend on telling the two effects apart, and D4 logs any change.

Rejected:

- Sending it in a later deploy to measure each change's effect apart: a second deploy and measurement window for a result Done when does not need.

#### D6. What changes in d004's requirements, and what does not

D1–D5 change four requirements of [d004 › Requirements](d004-bronze-data-capture.md#13-requirements):

| d004 | Today | With this design |
|---|---|---|
| R7 | A source that takes longer than 60 s is abandoned | The 60 s limit covers the whole request, retry included (D3) |
| R8 | No source failure is retried | Unchanged, except a 403 from Bicing, which is retried once (D1) |
| R14 | `latency_ms` of the source's response | Unchanged, for the last attempt's response; the first attempt's goes in `fetch_retried` (D4) |
| R16 | The events and fields of D9 | Plus `fetch_retried` (D4) |

The rest of d004's requirements hold, including where the retry comes close:

- R4, at most one extra fetch per pass: a retry repeats the same fetch and is not an extra one.
- R1 and write-once: at most one object per feed and pass. The retry happens before the write, so the key comes from the pass as today.
- Pass duration: no request lasts longer than 60 s, so the longest pass does not change.
- R17–R20, heartbeat: the heartbeat is not a source request, so it is not retried and does not send D5's `User-Agent`; a retry can delay its signal, by no more than the 60 s limit allows today.
- R22, 10 MB limit: it applies to the retry's response too.
- R23, heartbeat URL kept out of logs: `headers` and `body` come from a source's response, never from the heartbeat.
- R2, R3, R5, R6, R9–R13, R15, R21 and R24: D1–D5 do not touch them.

#### D7. Security of the retry

D1–D5 add two things that cross the capture's boundary: data from a source's 403 response written to the pass log (D4), and a header sent to every source (D5). The log is written as JSON Lines through JSON serialisation, which escapes quotes, line breaks and control characters, so a response's content stays inside a string value and cannot forge a line or a field (OWASP, CWE-117). Its readers, the pipeline (T042) and any analysis, parse it as JSON and treat `headers` and `body` as untrusted text: never evaluated, rendered as HTML or followed as instructions. The pass logs stay under the bucket lock ([d004 › D9](d004-bronze-data-capture.md#d9-capture-logs)), so whatever a response puts in `headers` or `body` cannot be deleted. The residual risk is accepted: capture sends no secret to a source, whose APIs are public and unauthenticated, so no secret of the project can come back in a response, and a source's own session cookie is left out. Spoofing, repudiation and elevation of privilege are not affected: D1–D5 change no authentication, permission or Worker surface, and d004's R21 and R23 hold (D6).

| # | Threat (STRIDE) | Impact | Control | Requirement |
|---|---|---|---|---|
| TH1 | Tampering: a source writes `headers` and `body` into the pass log | Forged log lines, or oversized events | JSON serialisation; `body` cut to 1,000 bytes; at most 50 headers, each value cut to 1,000 bytes (D4); readers treat both as untrusted text (T042) | R6, R9 |
| TH2 | Information disclosure: a 403 response carries a session cookie | A source's session token stored for good in the locked logs | `Set-Cookie` is left out (D4) | R6 |
| TH3 | Information disclosure: the `User-Agent` identifies the project | Sources know who requests | Intended (D5): only the public repository's URL, no personal contact | R8 |
| TH4 | Denial of service against a source: retries multiply requests | More load on a source that already limits | Only on Bicing's 403s, at most one retry per request, after 3–5 s (D1, D2): never more than twice today's requests | R1, R2, R3 |

### 1.3 Requirements

<!-- Optional. The acceptance criteria, cited by number in the Test plan and the steps. They translate Decided at framing and cite the decision they come from; nothing is decided here.
One behaviour per requirement, verifiable, with a measurable threshold where one applies. Written in EARS:
- Ubiquitous: The <system> shall <response>.
- Event: When <trigger>, the <system> shall <response>.
- State: While <state>, the <system> shall <response>.
- Unwanted: If <condition>, then the <system> shall <response>.
- Optional: Where <feature is included>, the <system> shall <response>.
Only requirements specific to this task; project-wide rules (CLAUDE.md, ADRs) are not repeated. -->

- **R1** If Bicing answers a feed or index request with HTTP 403, then the capture shall retry the request once in the same pass. (D1, TH4)
- **R2** If a source request fails in a way R1 does not retry, or its retry fails, then the capture shall make no further attempt in the same pass. (D1, D6)
- **R3** When the capture retries a request, it shall wait a uniform random time between 3 and 5 s before the retry. (D2)
- **R4** If a source request, retry included, takes longer than 60 s, then the capture shall abandon it and log it as a failure. (D3, D6)
- **R5** When the capture retries a request, it shall log a `fetch_retried` event at level `warning`, before the wait, with `source`, `feed` (null for an index), and the first attempt's `status` and `latency_ms`. (D4, D6)
- **R6** The `fetch_retried` event shall carry `headers`, the first attempt's response headers except `Set-Cookie`, at most 50 with each value cut to 1,000 bytes, and `body`, the first 1,000 bytes of its response body as text, or null if the body cannot be read. (D4, TH1, TH2)
- **R7** When a retried request ends, the capture shall log its outcome in the event d004 › D9 lists for it, with the last attempt's `status` and `latency_ms`. (D4, D6)
- **R8** The capture shall send `User-Agent: bikesharing-capture (+https://github.com/markciano/bikesharing)` in every source request, and not in the heartbeat signal. (D5, D6, TH3)
- **R9** The capture shall serialise every log event as JSON, so that a response's content cannot add a line or a field to the pass log. (D7, TH1)

### 1.4 Done when

<!-- Optional. Only what closes this task and Requirements cannot express: operational actions, checks on real data, understanding. The general closing rule is checked in `.claude/skills/implement/review.md`. -->

- Over 48 h of production pass logs after the deploy, Bicing `station_status` requests whose retry also fails stay at or below 0.1 per hour, the hard cut of [s014 › Q1](../spikes/s014-bicing-403.md#13-questions). If not, the wait or the approach is revisited in a new task.
  - Owner check: list the bucket with `rclone lsf -R --fast-list r2:bikesharing-bronze/raw > spikes/cloudflare-capture-spike/analysis/output/prod-progress.txt`, then run `duckdb -f scratch/capture-progress.sql` to count the minutes without a Bicing `station_status` object. That count includes every failure, not only failed retries, so a result at or below the cut meets it; a result above it is split by the `fetch_retried` and `feed_failed` events of the pass logs.

## 2. Plan — how

<!-- 2-3 sentences -->

### 2.1 Approach

<!-- Detailed plan organized by #### blocks.
Block `3. Steps` is written using this plan.
If some block contains `options considered`, include them with pros and cons.
-->

The retry lives in the source fetch, which already owns the 60 s limit; the pass decides per source whether it applies and logs it. d004 is rewritten where its behaviour changes.

#### Source fetch

- `fetchFeed` owns the whole request: one `AbortSignal.timeout(timeoutMs)` covers the first attempt, the wait and the retry (D3). The result is the last attempt's, with that attempt's `status` and `latencyMs` (R7).
- When the first attempt answers 403 and the caller passes `retryOn403`, it reads the 403's headers and body, hands them to the caller's `onRetry`, waits `retryWait(limits, random)` and fetches again. A 403 without `retryOn403`, any other failure and a failed retry return as today (R2).
- `latencyMs` of a 403 is measured when its headers arrive, as for every HTTP failure; reading its body does not count.
- The wait listens to the same signal, so the deadline cuts it short: no request outlasts `timeoutMs` (R4).
- If the deadline runs out while reading the 403's body, during the wait or during the retry, the result is a `timeout` with `status` and `latencyMs` null (D4); a body cut short by the deadline is null in `fetch_retried`.
- Every source request sends `USER_AGENT` (D5). The heartbeat keeps its own fetch in `heartbeat.js`, so it never sends it (R8).

#### The 403's headers and body

- `headers`: the response headers as the Fetch API iterates them, names in lowercase and in sorted order, without `set-cookie`; the first 50, each value cut to its first 1,000 bytes (R6).
- `body`: read within `maxBytes` and the deadline, like any body; decompressed if it arrives as gzip, then cut to its first 1,000 bytes and decoded as UTF-8, with a character split at the cut replaced by U+FFFD. If the body cannot be read or decompressed, `body` is null.
- Bytes are cut, not characters, since the limit bounds the event's size (TH1).

#### Retry wait

- `retryWait(limits, random)` returns `retry403MinMs + random() × (retry403MaxMs − retry403MinMs)`, with `random` defaulting to `Math.random`: uniform over 3,000–5,000 ms in production (D2, R3).
- Tests pass small limits and a fixed `random`, as every limit of capture (`.claude/rules/code/testing.md`).

#### Pass and source setting

- Each source in `sources.js` has `retryOn403`: true for Bicing, false for AMBici ([ADR-0039](../decisions/0039-retry-a-403-only-where-shown-transient.md)).
- `captureFeed` and `refreshIndex` in `pass.js` pass the source's `retryOn403` and an `onRetry` that logs `fetch_retried` at `warning` through `pass.log`, so its `ts` is the time before the wait (R5). Its fields go in the order `source`, `feed` (null for an index), `status`, `latency_ms`, `headers`, `body`.
- The outcome events keep their code and take `status` and `latency_ms` from the result, which is the last attempt's (R7).

#### Documents

- d004 is rewritten to the current state where d006 changes it (#3), following the change links across documents of `.claude/rules/docs/decision-log.md`: D8, D9, R7, R8, R14 and R16 in its Spec; Source fetch, `sources.js` and `fetch.js` in its Plan, whose contract of `fetchFeed` and `LIMITS` moves to [`fetch.js`](#fetchjs).
- `.claude/rules/docs/decision-log.md` extends change links across documents (#3).
- `contracts/capture-logs.json` takes `fetch_retried` (#2).

### 2.2 Decision summary

<!-- It logs decisions about the plan, including changes. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Applies to: anchor link(s) to the section where the decision is applied, named in one or two words.
- Decided at: the Status phase where it was decided (Plan, Steps), or `<phase> review` when decided while reviewing that phase.
- R: Requirement affected.
-->

| # | Applies to | Decision | Reason | R | Decided at |
|---|---|---|---|---|---|
| 1 | [D1](#d1-a-403-from-bicing-is-retried-once), [ADR-0039](../decisions/0039-retry-a-403-only-where-shown-transient.md) | A 403 is retried per source, turned on by evidence; Bicing only (ADR-0039, deviation from RFC 9110 › 403) | The deviation stays where a transient 403 has been measured; a real refusal gets no extra requests | R1, R2 | Plan |
| 2 | [File layout](#23-file-layout), [Test plan](#25-test-plan) | `fetch_retried` joins the capture log contract `contracts/capture-logs.json`, with valid cases and one invalid case per rule of D4 (one file per contract, `.claude/rules/code/testing.md`) | Same log lines, format and object as the other events; the invalid cases give the pipeline's consumer tests the rules of TH1 and TH2 | R5, R6 | Plan |
| 3 | [d004 › D8](d004-bronze-data-capture.md#d8-capture-failure-behaviour), [D9](d004-bronze-data-capture.md#d9-capture-logs), [Requirements](d004-bronze-data-capture.md#13-requirements), `.claude/rules/docs/decision-log.md` | d004 is rewritten to the current state where d006 changes it, each changed section ending with a bold link to the d006 decision; change links extend across documents | d004 stays the source of truth for capture's behaviour (CLAUDE.md › Working rules); the rule extends the in-document change links | R1–R9 | Plan |

### 2.3 File layout

<!-- Every file and folder the task creates or modifies, documents included, as a tree: (new) or (modified), and its purpose or change in one line. A task that adds a component also lists its CI job in `.github/workflows/ci.yml` (recipe in `.claude/rules/code/ci.md`), and its version files, manifest and lockfile (`.claude/rules/code/dependencies.md`). -->

```text
.
├── .claude/rules/docs/
│   └── decision-log.md          (modified)  Change links across documents (#3)
├── capture/
│   ├── src/
│   │   ├── fetch.js             (modified)  Retry on 403 within one deadline, User-Agent, the 403's headers and body
│   │   ├── pass.js              (modified)  Passes each source's retryOn403 and logs fetch_retried
│   │   └── sources.js           (modified)  retryOn403 per source: Bicing only
│   ├── test/
│   │   ├── integration/
│   │   │   └── pass-failures.test.js (modified)  Passes with a 403 then a 200, two 403s, a 403 on AMBici
│   │   └── unit/
│   │       ├── fetch.test.js    (modified)  Retry, wait, deadline, headers and body for the log, User-Agent
│   │       ├── heartbeat.test.js (modified) The heartbeat sends no User-Agent of capture
│   │       └── sources.test.js  (modified)  Only Bicing retries a 403
│   └── vitest.config.js         (modified)  Routes for a 403 and an echo of the User-Agent; retry limits in TEST_LIMITS
├── contracts/
│   └── capture-logs.json        (modified)  fetch_retried cases (#2)
└── docs/
    ├── decisions/
    │   └── 0039-retry-a-403-only-where-shown-transient.md (new)  Per-source 403 retry (#1)
    └── designs/
        └── d004-bronze-data-capture.md (modified)  D8, D9, R7, R8, R14, R16, Source fetch, sources.js and fetch.js rewritten, linking to d006 (#3)
```

### 2.4 Components

<!-- Optional. One subsection per component. The contract is exact, in the component's own language, never pseudocode. -->

#### `fetch.js`

- **Responsibility:** fetches one source response within one deadline, retrying a 403 once when the caller asks, and returns the bytes to store or the failure to log.
- **Location:** `capture/src/fetch.js`
- **Contract:** `gunzipText` and the `FetchOk` and `FetchFailed` typedefs keep their contract.

```js
/** Sent in every source request; the heartbeat does not use it (d006 D5, Every source request identifies the project). */
export const USER_AGENT = "bikesharing-capture (+https://github.com/markciano/bikesharing)";

/** @type {Readonly<{ timeoutMs: number, maxBytes: number, retryDelayMs: number,
 *   heartbeatTimeoutMs: number, retry403MinMs: number, retry403MaxMs: number }>} */
export const LIMITS = Object.freeze({
  timeoutMs: 60_000,
  maxBytes: 10_000_000,
  retryDelayMs: 250,
  heartbeatTimeoutMs: 10_000,
  retry403MinMs: 3_000,
  retry403MaxMs: 5_000,
});

/**
 * @typedef {{ status: 403, latencyMs: number, headers: Record<string, string>,
 *             body: string | null }} Retried
 * The first attempt of a request about to be retried, for `fetch_retried`.
 */

/**
 * GET with `Accept-Encoding: gzip`, `User-Agent: USER_AGENT` and
 * `encodeResponseBody: "manual"`. One `AbortSignal.timeout(timeoutMs)` covers every
 * attempt and the wait. With `retryOn403`, a 403 calls `onRetry`, waits
 * `retryWait(limits, random)` and fetches once more. Never throws.
 * @param {string} url
 * @param {{ timeoutMs: number, maxBytes: number, retry403MinMs: number, retry403MaxMs: number }} limits
 * @param {{ retryOn403?: boolean, onRetry?: (retried: Retried) => void, random?: () => number }} [options]
 *   Defaults: `false`, a no-op, `Math.random`
 * @returns {Promise<FetchOk | FetchFailed>} The last attempt's result
 */
export async function fetchFeed(url, limits, options = {}) {}

/**
 * Uniform wait before a retry: `retry403MinMs + random() * (retry403MaxMs - retry403MinMs)`. Pure.
 * @param {{ retry403MinMs: number, retry403MaxMs: number }} limits
 * @param {() => number} [random] Default `Math.random`
 * @returns {number} Milliseconds
 */
export function retryWait(limits, random = Math.random) {}
```

The 403's `headers` and `body` for `Retried` are built by private functions of the module, as set in [The 403's headers and body](#the-403s-headers-and-body), and tested through what `fetchFeed` passes to `onRetry`.

#### `sources.js`

- **Responsibility:** unchanged; each source also states whether it retries a 403.
- **Location:** `capture/src/sources.js`
- **Contract:** `Source` gains one property; `SOURCES` sets it to `true` for `bicing` and `false` for `ambici`.

```js
/**
 * @property {boolean} retryOn403 Whether a 403 from this source is retried once
 *   (ADR-0039, Retry a 403 only on sources where it is shown to be transient)
 */
```

### 2.5 Test plan

<!-- Optional. Every requirement has at least one verification method (IADT: Inspection, Analysis, Demonstration, Test). Test is the default, at the lowest level that can verify the requirement. Another method only when no test can: Inspection for configuration or documents, Analysis for production data or measurements, Demonstration for behaviour observed end to end, such as a third-party service. -->

| R | Method | What is verified | Level |
|---|---|---|---|
| R1 | Test | `fetchFeed` with `retryOn403` makes a second request after a 403 and returns its result; a pass stores a Bicing feed and adopts a Bicing index whose first request got a 403 | unit, integration |
| R2 | Test | One request only after a 500, or after a 403 without `retryOn403`; two requests only after two 403s; only Bicing has `retryOn403`; a 403 on AMBici in a pass logs `feed_failed` with no retry | unit, integration |
| R3 | Test | `retryWait` returns `retry403MinMs` for `random` 0, the midpoint for 0.5, and stays below `retry403MaxMs` for a value just under 1 | unit |
| R4 | Test | With `retry403MinMs` above `timeoutMs`, a 403 ends in `timeout` with `status` and `latencyMs` null, no second request, and within `timeoutMs` plus a small margin, not after the wait | unit |
| R5 | Test | A pass with a retried 403 logs `fetch_retried` at `warning` before the outcome event, with the fields in order and `feed` null for an index; the contract's valid cases build their JSON Lines | integration, contract |
| R6 | Test | What `fetchFeed` passes to `onRetry`: `headers` without `set-cookie`, the first 50, a value cut to 1,000 bytes; `body` decompressed from gzip and cut to 1,000 bytes with U+FFFD on a split character; `body` null for corrupt gzip | unit |
| R7 | Test | After a 403 then a 200, `feed_captured` carries 200 and the retry's latency; after two 403s, `feed_failed` carries 403 | integration |
| R8 | Test | A source request sends `USER_AGENT`; the heartbeat request does not | unit |
| R9 | Test | The contract's valid case with quotes and a line break in `body` builds one line | contract |

The new routes in `vitest.config.js`: `forbidden` (always 403, with a `set-cookie`, more than 50 headers and a gzip body over 1,000 bytes), `forbidden-corrupt-gzip` (403 with a body that starts as gzip and is not), `forbidden-once` (403 on a path's first request, the fixture on the next, by the existing request counts), and `user-agent` (200 with the request's `User-Agent` as its body). `TEST_LIMITS` adds `retry403MinMs: 1` and `retry403MaxMs: 2`.

The cases added to `contracts/capture-logs.json` (#2):

- Valid: `fetch_retried` of a feed; `fetch_retried` of an index, `feed` null; `fetch_retried` with `body` null; `fetch_retried` whose `body` holds quotes and a line break; `fetch_retried` then `feed_captured` in one pass.
- Invalid, one rule each: `headers` holds `set-cookie`; `headers` with more than 50 entries; `body` over 1,000 bytes; a header value over 1,000 bytes; `status` other than 403; `headers` missing.

### 2.6 What does not change

<!-- Optional. Code or documents that must not be modified. Out of scope limits the what; this section limits the how. -->

- `capture/src/log.js`: events are already serialised with `JSON.stringify` (R9).
- `capture/src/heartbeat.js` and `capture/src/storage.js`: the heartbeat and the write retries keep their behaviour.
- `capture/test/contract/capture-logs.test.js`: it builds every valid case of the contract, so the new cases need no change to it.
- The existing events of d004 › D9: their fields and meaning.

## 3. Steps

<!-- Each step is one reviewable result and one commit, touching at most 2–3 files.
- Status: where the step is: 💤 todo · 🎬 ready · 🔄 in progress · ⛔ blocked · ✅ done
- Who: Owner (manual actions: dashboards, accounts, deploys, runs, checks) or Claude (code and documents).
- R: the requirements the step implements or tests, or —.
- Commit: the proposed message, following the Git conventions in CLAUDE.md.
- Model: the model and effort the step's session runs with (e.g. sonnet · medium), or — when Who is Owner. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

None.

### Step 1 — `fetch_retried` cases in the capture log contract

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `test: d006.s1 - add fetch_retried cases to the capture log contract`
- **R:** R5, R6, R9
- **Model:** sonnet · medium

#### Scope

`contracts/capture-logs.json` gains the `fetch_retried` cases listed in [Test plan](#25-test-plan) (#2): 5 valid and 6 invalid, each invalid case breaking one rule and stating its `reason`. The producer's contract test `capture/test/contract/capture-logs.test.js` builds every valid case unchanged ([What does not change](#26-what-does-not-change)), so it verifies R5's contract row and R9. No code changes: `log.js` already serialises any event.

#### Reads

- `contracts/capture-logs.json`, whole: the shape of the existing valid and invalid cases, which the new ones follow.
- `capture/test/contract/capture-logs.test.js`, whole: how a valid case is built and compared, to confirm it needs no change.
- d006 › [D4](#d4-a-retry-is-logged-as-its-own-event): the fields, their order, the limits on `headers` and `body`, and the example lines.

#### Do

1. Add the 5 valid cases: `fetch_retried` of a feed; of an index, with `feed` null; with `body` null; with quotes and a line break in `body`; `fetch_retried` then `feed_captured` in one pass, with `status` 200 and the retry's `latency_ms` in `feed_captured`. Fields in D4's order, after the common fields.
2. Add the 6 invalid cases, one rule each: `headers` holds `set-cookie`; `headers` with 51 entries; `body` of 1,001 bytes; a header value of 1,001 bytes; `status` 500; `headers` missing.
3. Run the contract test.

#### Check

- `npm test --prefix capture -- test/contract/capture-logs.test.js` passes, and its output lists the 5 new valid cases.
- The case with quotes and a line break in `body` builds exactly one JSON line (R9).

### Step 2 — `retryOn403` per source

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d006.s2 - state per source whether a 403 is retried`
- **R:** R2
- **Model:** sonnet · low

#### Scope

`capture/src/sources.js`: the `Source` typedef gains `retryOn403`, `true` for `bicing` and `false` for `ambici` ([sources.js](#sourcesjs), ADR-0039). `capture/test/unit/sources.test.js`: one test that only Bicing retries a 403 (Test plan R2, unit). Nothing reads the property yet; Step 8 does.

#### Reads

- d006 › [Components › sources.js](#sourcesjs): the property's JSDoc.
- `capture/src/sources.js`, the `Source` typedef and `SOURCES`: where the property goes.
- `capture/test/unit/sources.test.js`, whole: the style of the existing tests.

#### Do

1. Write the test `only Bicing retries a 403`, tagged `// Verifies d006 R2`, and run it red.
2. Add `retryOn403` to the typedef and to both sources in `SOURCES`.
3. Run the test file.

#### Check

- `npm test --prefix capture -- test/unit/sources.test.js` passes.

### Step 3 — `User-Agent` in every source request

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d006.s3 - identify the project in every source request`
- **R:** R8
- **Model:** sonnet · medium

#### Scope

`capture/src/fetch.js` exports `USER_AGENT` and sends it in every `fetchFeed` request, next to `Accept-Encoding: gzip` ([Components › fetch.js](#fetchjs), D5). `capture/vitest.config.js` adds the `user-agent` route, which answers 200 with the request's `User-Agent` as its body ([Test plan](#25-test-plan)). `capture/test/unit/fetch.test.js`: one test that a source request sends `USER_AGENT` (Test plan R8, first half). Feeds and indexes are both fetched through `fetchFeed`, so one test covers both.

#### Reads

- d006 › [Components › fetch.js](#fetchjs): `USER_AGENT` and its JSDoc.
- `capture/src/fetch.js`, `fetchFeed`: where the request headers are set.
- `capture/vitest.config.js`, the `outboundService` routes: how a route is declared.
- `capture/test/unit/fetch.test.js`, the first tests: how a route is reached.

#### Do

1. Add the `user-agent` route.
2. Write the test `sends the capture User-Agent to a source`, tagged `// Verifies d006 R8`, and run it red.
3. Add `USER_AGENT` and send it in `fetchFeed`.
4. Run the test file.

#### Check

- `npm test --prefix capture -- test/unit/fetch.test.js` passes.
- `grep -rn "bikesharing-capture (+" capture/src` finds only `fetch.js`.

### Step 4 — The heartbeat sends no capture `User-Agent`

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `test: d006.s4 - check that the heartbeat sends no capture User-Agent`
- **R:** R8
- **Model:** sonnet · low

#### Scope

`capture/test/unit/heartbeat.test.js`: one test that the heartbeat request does not carry `USER_AGENT` (Test plan R8, second half). `heartbeat.js` does not change ([What does not change](#26-what-does-not-change)), so the test passes at once: it guards against a later change that sends the heartbeat through `fetchFeed`.

#### Reads

- `capture/test/unit/heartbeat.test.js`, whole: how the existing tests observe the heartbeat request; the new test asserts on that same request.

#### Do

1. Write the test `does not send the capture User-Agent with the heartbeat`, tagged `// Verifies d006 R8`, comparing the request's `User-Agent` with the imported `USER_AGENT`.
2. Run the test file.

#### Check

- `npm test --prefix capture -- test/unit/heartbeat.test.js` passes.

### Step 5 — `retryWait` and the retry limits

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d006.s5 - add the random wait before a 403 retry`
- **R:** R3
- **Model:** sonnet · low

#### Scope

`capture/src/fetch.js`: `LIMITS` gains `retry403MinMs: 3_000` and `retry403MaxMs: 5_000`, and the pure function `retryWait` is exported ([Components › fetch.js](#fetchjs), [Retry wait](#retry-wait)). `capture/vitest.config.js`: `TEST_LIMITS` gains `retry403MinMs: 1` and `retry403MaxMs: 2`. `capture/test/unit/fetch.test.js`: the three `retryWait` tests of Test plan R3. Nothing calls `retryWait` yet; Step 6 does.

#### Reads

- d006 › [Components › fetch.js](#fetchjs): `LIMITS` and `retryWait`, contract and JSDoc.
- `capture/src/fetch.js`, `LIMITS`: where the new limits go.
- `capture/vitest.config.js`, `TEST_LIMITS`: where the test limits go.

#### Do

1. Write the tests `waits the minimum when random is 0`, `waits the midpoint when random is 0.5` and `waits less than the maximum when random is just below 1`, tagged `// Verifies d006 R3`, and run them red.
2. Add the limits and `retryWait` to `fetch.js`, and the test limits to `TEST_LIMITS`.
3. Run the test file.

#### Check

- `npm test --prefix capture -- test/unit/fetch.test.js` passes.

### Step 6 — Retry of a 403 within one deadline

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d006.s6 - retry a 403 once within the request deadline`
- **R:** R1, R2, R4
- **Model:** opus · high

#### Scope

`capture/src/fetch.js`: `fetchFeed` takes `options` (`retryOn403`, `onRetry`, `random`). One `AbortSignal.timeout(timeoutMs)` covers the first attempt, the wait and the retry. The wait listens to that signal, and the result is the last attempt's ([Source fetch](#source-fetch), [Components › fetch.js](#fetchjs)). In this step `onRetry` receives `status` and `latencyMs`, with `headers: {}` and `body: null` marked `TODO(T059): headers and body of the 403, built in d006 Step 7`. `capture/vitest.config.js` adds the routes `forbidden` (always 403, with a `set-cookie`, more than 50 headers and a gzip body over 1,000 bytes) and `forbidden-once` (403 on a path's first request, the fixture on the next, by the existing request counts). `capture/test/unit/fetch.test.js`: the unit tests of Test plan R1, R2 and R4.

#### Reads

- d006 › [Source fetch](#source-fetch) and [Components › fetch.js](#fetchjs): the behaviour and the contract of `fetchFeed` and `Retried`.
- `capture/src/fetch.js`, `fetchFeed`: the current timeout, the latency measure and the failure results.
- `capture/vitest.config.js`, the routes and the request counts: how the new routes are declared and how a test reads how many requests a path got.

#### Do

1. Add the routes `forbidden` and `forbidden-once`.
2. Write the tests, each tagged with the requirement it verifies, and run them red:
   - R1: with `retryOn403`, a 403 then the fixture makes two requests and returns the fixture's bytes with the second attempt's `status`; `onRetry` is called once, with `status` 403 and a number in `latencyMs`.
   - R2: one request after an existing 5xx route with `retryOn403`; one request after a 403 without `retryOn403`, returning the 403; two requests after two 403s, returning the second 403.
   - R4: with `retry403MinMs` and `retry403MaxMs` above `timeoutMs`, a 403 ends in `timeout` with `status` and `latencyMs` null, after one request, and within `timeoutMs` plus a small margin.
3. Implement the options, the single deadline and the abortable wait in `fetchFeed`, with the `TODO(T059)` above.
4. Run the full suite, since `fetchFeed`'s callers keep calling it without options.

#### Check

- `npm test --prefix capture` passes.
- `grep -rn "TODO(T059)" capture/src` finds exactly the one in `fetch.js`.

### Step 7 — The 403's headers and body for `onRetry`

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d006.s7 - pass the 403's headers and body to the retry log`
- **R:** R6
- **Model:** opus · medium

#### Scope

`capture/src/fetch.js`: private functions build `headers` and `body` of `Retried` as set in [The 403's headers and body](#the-403s-headers-and-body), replacing Step 6's `TODO(T059)`. A body cut short by the deadline gives `body` null ([Source fetch](#source-fetch)). `capture/vitest.config.js` adds the route `forbidden-corrupt-gzip` (403 with a body that starts as gzip and is not). `capture/test/unit/fetch.test.js`: the tests of Test plan R6, all through what `fetchFeed` passes to `onRetry`.

#### Reads

- d006 › [The 403's headers and body](#the-403s-headers-and-body): the rules for both fields.
- `capture/src/fetch.js`, the body reading within `maxBytes` and `gunzipText`: reused to read and decompress the 403's body.

#### Do

1. Add the route `forbidden-corrupt-gzip`.
2. Write the tests, tagged `// Verifies d006 R6`, and run them red: `headers` has no `set-cookie`; it holds exactly the first 50 names in sorted order; a long value is cut to 1,000 bytes; `body` is the gzip body decompressed and cut to 1,000 bytes, ending in U+FFFD where a character is split; `body` is null for `forbidden-corrupt-gzip`.
3. Implement the private functions and remove the `TODO(T059)`.
4. Run the test file.

#### Check

- `npm test --prefix capture -- test/unit/fetch.test.js` passes.
- `grep -rn "TODO(T059)" .` finds nothing.

### Step 8 — The pass logs `fetch_retried`

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d006.s8 - retry Bicing's 403s in the pass and log them`
- **R:** R1, R2, R5, R7
- **Model:** sonnet · medium

#### Scope

`capture/src/pass.js`: `captureFeed` and `refreshIndex` pass the source's `retryOn403` and an `onRetry` that logs `fetch_retried` at `warning` through `pass.log`, fields in D4's order. The outcome events keep their code ([Pass and source setting](#pass-and-source-setting)). `capture/test/integration/pass-failures.test.js`: the integration tests of Test plan R1, R2, R5 and R7. With this step, d006's code is complete.

#### Reads

- d006 › [Pass and source setting](#pass-and-source-setting) and [D4](#d4-a-retry-is-logged-as-its-own-event): the event, its fields and its order.
- `capture/src/pass.js`, `captureFeed` and `refreshIndex`: where `fetchFeed` is called and the outcome is logged.
- `capture/test/integration/pass-failures.test.js`, whole: how a source is pointed at a failing route and how the pass log is read.

#### Do

1. Write the tests, each tagged with the requirements it verifies, and run them red:
   - A Bicing feed whose first request gets a 403 is stored; the log has `fetch_retried` at `warning`, fields in order, before `feed_captured`, which carries 200 and the retry's `latency_ms` (R1, R5, R7).
   - A Bicing index whose first request gets a 403 is adopted; `fetch_retried` has `feed` null (R1, R5).
   - A Bicing feed with two 403s logs `fetch_retried` then `feed_failed` with `status` 403 (R2, R7).
   - An AMBici feed with a 403 logs `feed_failed` and no `fetch_retried` (R2).
2. Implement the options and `onRetry` in `captureFeed` and `refreshIndex`.
3. Run the full suite.

#### Check

- `npm test --prefix capture` passes.

### Step 9 — Merge and deploy

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** —
- **R:** —
- **Model:** —

#### Scope

Production capture running d006's code from `main`, deployed as in [d004 › Deployment](d004-bronze-data-capture.md#deployment). The PR with Steps 1–8 carries `Refs` to T059's issue, so the task stays open for the 48 h check of Step 10, which reaches `main` in a second PR that closes it.

#### Reads

- d004 › [Deployment](d004-bronze-data-capture.md#deployment), the deploy and smoke test paragraphs: the deploy command, the token and the smoke test.

#### Do

1. Push the branch, open the PR `T059: Capture retry on 403` with `Refs` to T059's issue, wait for the checks to pass, and merge it by rebase.
2. Update `main` locally and delete the local branch with `-D`.
3. From `capture/` on `main`, run `npm ci`, load the root `.env` with `set -a; source ../.env; set +a`, and run `npx wrangler deploy`.
4. Run the smoke test of d004 › Deployment on the first passes.
5. Note the deploy time in UTC, for Step 10.
6. Create the branch `t059-bicing-403-retry` again from the updated `main`, for Step 10's PR.

#### Check

- The PR merged with every check green.
- Each dynamic feed has a new object under `raw/` that passes `gunzip -t`, and the pass's log has `recompressed: false` and, in `version`, the active version shown by `npx wrangler deployments list`.

### Step 10 — 48 h check in production

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** `docs: d006.s10 - record the 48 h check of the 403 retry`, in Close
- **R:** —
- **Model:** —

#### Scope

The check of [Done when](#14-done-when) over the first 48 full hours after Step 9's deploy. The result is recorded in [Close](#4-close), and the PR that closes T059 carries it.

#### Reads

- d006 › [Done when](#14-done-when): the threshold and the owner check.

#### Do

1. After the 48 h, list the bucket with `rclone lsf -R --fast-list r2:bikesharing-bronze/raw > spikes/cloudflare-capture-spike/analysis/output/prod-progress.txt`.
2. Run `duckdb -f scratch/capture-progress.sql` and count the minutes without a Bicing `station_status` object in the window.
3. If the count divided by 48 is above 0.1, split it by the `fetch_retried` and `feed_failed` events of those passes' logs, and propose a new task with `/task` to revisit the wait or the approach.
4. Have Claude record the count, the rate per hour and, if needed, the new task, in Close.
5. Push and open the PR `T059: Capture retry on 403`, with `Closes` for T059's issue; once the checks pass, merge it by rebase.

#### Check

- The rate of minutes without a Bicing `station_status` object is at or below 0.1 per hour over the 48 h, or a new task exists for the gap and is named in Known gaps at close.

## 4. Close

<!-- The record of what the task delivered, for whoever opens this design later. -->

### 4.1 Implemented

<!-- Component — what was delivered; tests passing. -->

### 4.2 Known gaps at close

<!-- What the task leaves undone or imperfect, each with the task that covers it: requirements not fully met, File layout items not delivered, TODOs citing this task. "None" is valid. -->

- `<gap>` — TNNN

### 4.3 Decisions taken during implementation

<!-- Decisions made after the Plan was approved, including deviations from Scope approved by the owner. Oldest first; "None" is valid.
- #: `DI1`, `DI2`… (decision during implementation).
- Applies to: anchor link(s) to the design section the decision changes, or the path of a file outside the design.
- Decision and Reason: one line each; the content goes where it applies.
- Decided at: the step where it was decided (`Step N`).
-->

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| | | | | |
