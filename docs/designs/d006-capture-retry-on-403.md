<!--
Design doc template. A design doc is the working document of one task: Spec (what and why), Plan (how), Steps (implementation), Close (what was delivered).
It is detailed enough that Code can implement it without making design decisions.
Sections marked Optional are kept only when they apply.
-->

# Design: Capture retry on 403

- **Task:** T059
- **ADRs:** `<ADRs this design must respect, or "none">`
- **New ADRs from this doc:** `<ADRs created during this design, or "none">`

## Status

<!-- State: Draft 📝 · Ready for implementation 🎬 · In progress 🔄 · Complete ✅.
Phase: the blocks and reviews completed.
Current step: the step being implemented, or —. -->

- State: Draft 📝
- Phase: [ ] Spec · [ ] Plan · [ ] Plan review · [ ] Steps · [ ] Steps review
- Current step: —

## 1. Spec — what and why

<!-- What the result does seen from outside, not how it is built. The test: if whoever uses the result would notice a change, it belongs here; if not, it belongs to the Plan. External systems and their data (feeds, fields) may be named. -->

### 1.1 Context

<!-- 2–4 sentences for a reader with no prior context: the problem or need and why it matters now; who or what uses the result; where things stand today, including any design or spike this builds on. No solution here: it starts in Decided at framing. For a correction: current vs expected behaviour and how to reproduce it. -->

Bicing answers HTTP 403 to about 1.3 per hour of the production Capture Worker's `station_status` requests, and the Worker retries no failure ([d004 › D8](d004-bronze-data-capture.md#d8-capture-failure-behaviour)), so each 403 costs that minute's object. That leaves about 2% of the feed's minutes missing, against the 99.5% target of [d004 › D6](d004-bronze-data-capture.md#d6-capture-completeness-target); AMBici is at 100%. Spike s014 showed that the 403s go on with production alone, that each one costs a single minute, and that a request a few seconds later usually gets through ([s014 › Conclusion](../spikes/s014-bicing-403.md#5-conclusion)). This design changes the capture built in d004 accordingly.

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

#### D1. A 403 is retried once

Capture retries a source request once when the source answers HTTP 403, on any source and for feeds and indexes alike; every other source failure keeps the no-retry rule of [d004 › D8](d004-bronze-data-capture.md#d8-capture-failure-behaviour), which this decision refines. With production alone, Bicing answers 403 to about 1.26 `station_status` requests per hour, never in two consecutive minutes, and a request a few seconds after a 403 usually gets through ([s014 › F1–F3](../spikes/s014-bicing-403.md#4-findings)): the 403 behaves as a transient rejection, unlike a source that is down. One rule for every source needs no per-source configuration and costs nothing where no 403 occurs, as on AMBici.

If the retries logged in production recover fewer 403s than Done when requires, the wait or the approach is revisited. A 403 on another source or feed needs no change.

Rejected:

- Retrying only Bicing `station_status`: a per-source special case that misses the same 403 on another feed.
- Also retrying 429, 5xx and network errors: at most about 0.2% of minutes (57 source failures in 22 days, d004 › D8), with no evidence that they recover within seconds; a timeout leaves no time to retry anyway.
- Checking the retry with a probe before the deploy: only a Cloudflare Worker reproduces production's conditions, so it would deploy the same change twice; the retry is checked in production instead (Done when).

#### D2. The retry waits 3–5 s at random

The retry starts after a uniform random wait of 3 to 5 s (backoff with jitter). 3–4 s is the only delay after a 403 that has been measured ([s014 › F3](../spikes/s014-bicing-403.md#f3-a-request-a-few-seconds-after-a-403-usually-gets-through)), and a limiter that counts requests over a window of a few seconds could reject a shorter wait. A longer wait costs little: it happens about 1.3 times per hour, and waiting uses no Worker CPU. The jitter spreads the retries across any window the limiter counts.

If the logged retries recover too few 403s (D1), the wait is the first thing revisited.

Rejected:

- A fixed 3 s wait: every retry would land at the same point of a fixed window.
- A wait below 3 s: not measured.

#### D3. One 60 s limit covers the retry

The 60 s limit of [d004 › D8](d004-bronze-data-capture.md#d8-capture-failure-behaviour) covers the whole request: first attempt, wait and retry (an overall deadline). No request lasts longer than it does today, and the retry still has about 54 s, against about 1 s for a successful response (p90 935 ms, [s014 › 5.5](../spikes/s014-bicing-403.md#55-production-inputs)).

Rejected:

- 60 s per attempt: a request could last about 125 s, twice D8's limit, for no gain, since a 403 arrives fast.

#### D4. A retry is logged as its own event

Each 403 that capture retries writes a `fetch_retried` event, at level `warning`, before the wait, with `source`, `feed` (null for an index), `status` and `latency_ms` of the first attempt, plus `headers`, every response header except `Set-Cookie`, and `body`, the first 1,000 bytes of the response body as text. The request's outcome is then logged as today, by `feed_captured`, `feed_failed`, `index_refreshed` or `index_rejected`, whose `status` and `latency_ms` are those of the last attempt; the existing events keep their fields and meaning ([d004 › D9](d004-bronze-data-capture.md#d9-capture-logs)). It extends D9's event table, and `warning` matches D9's level for a failure that does not affect the data.

The pass log then answers how many 403s each source gets per hour (the `fetch_retried` events) and how many the retry recovers (those followed in the same pass by `feed_captured` or `index_refreshed` for the same feed), which Done when measures. Who sends the 403 and what it keys on is unknown ([s014 › 5.4](../spikes/s014-bicing-403.md#54-not-verified)): `headers` and `body` can name the limiter or the wait it asks for (`Retry-After`), which the next step needs if the retry falls short, and a 403 that arrives in tens of milliseconds points to a limiter at the network edge, one of hundreds to the origin server. `Set-Cookie` is left out because it can carry a session token (OWASP Logging Cheat Sheet). At about 3 KB per event and about 940 403s per month, they add about 3 MB per month to D9's 30–35 MB.

A retry that succeeds:

```json
{"ts":"2026-11-12T10:15:36.120Z","level":"warning","event":"fetch_retried","source":"bicing","feed":"station_status","status":403,"latency_ms":85,"headers":{"content-type":"text/html","server":"…"},"body":"<html>…"}
{"ts":"2026-11-12T10:15:40.530Z","level":"info","event":"feed_captured","source":"bicing","feed":"station_status","status":200,"latency_ms":640,"bytes":48210,"attempts":1,"recompressed":false}
```

The common fields `component`, `version` and `run_id` are left out, and the values are illustrative. When the retry also fails, the second event is `feed_failed` with the retry's `status`, or with `status` null and `error_type` `timeout` if D3's limit runs out.

Rejected:

- Counting fetch attempts in `attempts`: D9 defines it as write attempts, so one field would carry two meanings.
- Two new fields in the four source events (fetch attempts and the first attempt's status): it changes four existing events with fields that are almost always empty.
- A fixed list of headers and no body: it needs to guess which headers name the limiter, which is what is unknown.
- Headers and body on every HTTP failure: it changes `feed_failed` and `index_rejected` with no open question to answer.

#### D5. Every source request identifies the project

Every source request, for feeds and indexes alike, sends `User-Agent: bikesharing-capture (+https://github.com/markciano/bikesharing)`: a product name and a contact link, as usual for automated clients of public APIs ([RFC 9110 › User-Agent](https://www.rfc-editor.org/rfc/rfc9110#name-user-agent)), so a source operator can identify the traffic and reach the project instead of blocking it. The link is the public repository; no personal contact is sent.

It ships in the same deploy as D1. It may change the 403 rate in either direction ([s014 › 5.4](../spikes/s014-bicing-403.md#54-not-verified)); Done when measures the 403s the retry does not recover, which does not depend on telling the two effects apart, and D4 logs any change.

Rejected:

- Sending it in a later deploy to measure each change's effect apart: a second deploy and measurement window for a result Done when does not need.

### 1.3 Requirements

<!-- Optional. The acceptance criteria, cited by number in the Test plan and the steps. They translate Decided at framing and cite the decision they come from; nothing is decided here.
One behaviour per requirement, verifiable, with a measurable threshold where one applies. Written in EARS:
- Ubiquitous: The <system> shall <response>.
- Event: When <trigger>, the <system> shall <response>.
- State: While <state>, the <system> shall <response>.
- Unwanted: If <condition>, then the <system> shall <response>.
- Optional: Where <feature is included>, the <system> shall <response>.
Only requirements specific to this task; project-wide rules (CLAUDE.md, ADRs) are not repeated. -->

- **R1** `<EARS statement>` (D`<N>`)

### 1.4 Done when

<!-- Optional. Only what closes this task and Requirements cannot express: operational actions, checks on real data, understanding. The general closing rule is checked in `.claude/skills/implement/review.md`. -->

- Over 48 h of production pass logs after the deploy, Bicing `station_status` requests whose retry also fails stay at or below 0.1 per hour, the hard cut of [s014 › Q1](../spikes/s014-bicing-403.md#13-questions). If not, the wait or the approach is revisited in a new task.

### 1.5 Out of scope

<!-- Optional. What someone could expect and will not be done, each item pointing to the task that covers it. -->

- `<item>` — TNNN

### 1.6 Open questions

<!-- Optional. The decisions still to take about the what, in dependency order. Each one closes as a decision in Decided at framing and leaves the table, so it is empty at Spec approval. Questions about the how are Plan decisions. -->

| OQ | Question | Depends on | Notes |
|---|---|---|---|
| OQ6 | What must not break | D1–D5 | d004 › D8 for other failures, the pass within its minute, write-once, d004's requirements |

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

<!-- Optional. Every requirement has at least one verification method (IADT: Inspection, Analysis, Demonstration, Test). Test is the default, at the lowest level that can verify the requirement. Another method only when no test can: Inspection for configuration or documents, Analysis for production data or measurements, Demonstration for behaviour observed end to end, such as a third-party service. -->

| R | Method | What is verified | Level |
|---|---|---|---|
| R1 | Test / Inspection / Analysis / Demonstration | | unit / integration / e2e; — for other methods |

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

<!-- Decisions made after the Plan was approved, including deviations from Scope approved by the owner. Oldest first; "None" is valid.
- #: `DI1`, `DI2`… (decision during implementation).
- Applies to: anchor link(s) to the design section the decision changes, or the path of a file outside the design.
- Decision and Reason: one line each; the content goes where it applies.
- Decided at: the step where it was decided (`Step N`).
-->

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| | | | | |
