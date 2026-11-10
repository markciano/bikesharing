# Spike: Bicing 403s on station_status

- **Task:** T059
- **ADRs:** none
- **Code:** none; the log queries are throwaway and not kept.

## Status

- State: Concluded ✅
- Phase: [x] Questions · [x] Method · [x] Steps · [ ] Steps review · [x] Conclusion
- Started: 2026-11-10 · Finished: 2026-11-10
- Current step: —

## 1. Questions — what we need to know

### 1.1 Context

Since production capture started, Bicing answers HTTP 403 to some `bicing/station_status` requests, about 1.2 per hour, and capture does not retry them ([d004 › D8](../designs/d004-bronze-data-capture.md#d8-capture-failure-behaviour)). At that rate the feed reaches about 98% of minutes, against the 99.5% target of [d004 › D6](../designs/d004-bronze-data-capture.md#d6-capture-completeness-target). The spike and production logs already show what triggered the 403s (D1); whether they stop with production alone is still unknown, and it decides whether capture changes.

### 1.2 Decided at framing

#### D1. The overlap of two Workers triggered the 403s; a retry waits for Q1

The 403s began when production and the spike Worker (capture-v4) started requesting the same feeds, and both Workers received them at the same rate during the overlap. Capture keeps D8 unchanged until Q1 shows whether the 403s stop with production alone. If Q1's Gate fails, the fix is decided in this spike's Conclusion.

What would change it: 403s at or below Q1's threshold close the task with no code change; above it, a retry after a 403 (or another fix) is decided with Q1's figures.

Rejected: adding a retry after a 403 now. Retry policies usually treat a 403 as non-retryable, and retrying against the protection that sends it could raise the rejection rate; the change would also alter D8 before knowing it is needed.

Evidence, from the spike Worker's logs (one line per request, 2026-10-14 to 2026-11-09) and production's pass logs (2026-11-07 to 2026-11-09):

| Period (UTC) | Worker | Minutes with a `station_status` 403 | Per hour |
|---|---|---|---|
| 2026-10-14 to 2026-11-06, spike Worker alone | capture-v4 | 3, all on 2026-10-18 16:13–16:19 | ~0 |
| 2026-11-07 10:19 to 2026-11-09 08:16, both Workers | capture-v4 | 60 | 1.2 |
| same | production | 57 | 1.2 |

- **Onset:** production's first pass ran at 2026-11-07 10:19:39 and capture-v4's first 403 came at 10:20:36. A change on Bicing's side would not match the start to the minute.
- **Not a block:** only 4 of those minutes have a 403 in both Workers, and the next minute usually succeeds. The pattern fits a rate limiter or bot protection rejecting single requests, not a blocked client.
- **From a layer in front of the API:** 403s take a steady 723 ms (p50) to 792 ms (p90), while Bicing's 200s in production spread from 396 ms (p50) to 935 ms (p90).
- **Index too:** the Bicing index refresh got a 403 four times in production; AMBici had none.
- **After the overlap:** the copied production logs hold only 78 passes after capture-v4 stopped, too few for a rate. From the objects listed, 4 of the 5 missing minutes on 2026-11-09 12:00–15:00 were 403s, 4–7 h after the stop.

### 1.3 Questions

Main question: Do Bicing's 403s on `station_status` stop now that production runs alone, or does capture need to handle them?

- **Q1.** What is the rate of Bicing `station_status` 403s per hour with production alone, over D6's 48 h window? Unblocks D1's retry decision. Gate: Q1's exit criterion.
- **Observe only:** whether 403s come in consecutive minutes, which bears on whether a retry within the pass would succeed; 403s on Bicing's index refresh.

### 1.4 Exit criteria

- **Standard:** SRE error budget, as set in D6: 99.5% allows 216 minutes of failures per 30-day month, about 0.3 per hour.
- **Timebox:** D6's window, 2026-11-09 12:00 to 2026-11-11 12:00 UTC; it ends with the measurement after the window closes, or earlier once the 403s counted exceed what the hard cut allows over the whole window. **#1**
- Bicing `station_status` 403s with production alone — at most 0.1 per hour (72 minutes per month, a third of the budget, leaving the rest for the ~78 minutes per month of other failures seen in the spike) — hard cut

## 2. Method — how we find out

### 2.1 Approach

| Variant | What it is | What it tells |
|---|---|---|
| A | Count of 403s per hour in production's pass logs over D6's window | Q1 |

#### A. 403 rate with production alone

A query over the window's pass logs counts the passes and the `feed_failed` and `index_rejected` events with `status` 403 for Bicing, per UTC hour and in total, and lists runs of consecutive minutes with a 403. Passes come from the distinct `run_id`.

### 2.3 Decision log

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| 1 | [Timebox](#14-exit-criteria) | Close the measurement on 2026-11-10 07:48 UTC, before the window ends | The 25 403s counted already exceed the 4.8 the hard cut allows in 48 h, so the rest of the window cannot change the result | Running step 2 |

### 2.4 File layout

None: the query runs from a scratch file and is not kept.

## 3. Steps

### 3.1 Prerequisites

None.

### Step 1 — Copy the window's production logs

- **Status:** ✅ done
- **Who:** Owner
- **Model:** —

#### Scope

Production's pass logs of the window, copied to `spikes/cloudflare-capture-spike/analysis/output/prod-logs/` (ignored by Git).

#### Do

1. Run:

   ```bash
   rclone copy -P r2:bikesharing-bronze/logs spikes/cloudflare-capture-spike/analysis/output/prod-logs --include "date=2026-11-{09,10}/**"
   ```

#### Check

The window's folders hold one log per pass, one pass per minute.

### Step 2 — Measure the 403 rate

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `docs: s014 - record the Bicing 403 rate with production alone`
- **Model:** opus · medium
- **Gate:** at most 0.1 403s per hour → T059 closes with no code change; above it → the fix is decided in the Conclusion.

#### Scope

Findings in this document. No other file.

#### Do

1. Run variant A's query over the window.
2. Write the findings.

#### Check

The pass count matches one pass per minute over the measured span, and the 403 count matches the passes with `"status":403` that `grep -rl` lists over the same folders.

## 4. Findings

### F1. Production alone gets 403s at the overlap's rate

Step 2 · 2026-11-10 · production pass logs, 2026-11-09 12:00:40 to 2026-11-10 07:48:39 UTC

- 1,189 passes over 19.8 h, with none missing; 25 of them have a Bicing `station_status` 403, or 1.26 per hour, against 1.2 per hour for each Worker during the overlap (D1). `grep -rl` lists the same 25 passes.
- No downward trend:

  | 6 h from (UTC) | Passes | 403s | Per hour |
  |---|---|---|---|
  | 2026-11-09 12:00 | 360 | 9 | 1.5 |
  | 2026-11-09 18:00 | 360 | 9 | 1.5 |
  | 2026-11-10 00:00 | 360 | 5 | 0.83 |
  | 2026-11-10 06:00 | 109 | 2 | 1.1 |

- No 403 on Bicing's index refresh in the span.
- Consequence: Q1's hard cut allows at most 4.8 403s in the 48 h window, so it fails whatever the rest of the window brings (**#1**). The fix is decided in the Conclusion.

### F2. Each 403 costs a single minute

Step 2 · 2026-11-10 · production pass logs, same span as F1

- No two consecutive minutes have a `station_status` 403; the next pass always gets the feed.
- Consequence: a 403 is not a block of the client; the cost of each one is one missing minute.

### F3. A request a few seconds after a 403 usually gets through

Step 2 · 2026-11-10 · spike Worker and production logs of the overlap, 2026-11-07 10:19 to 2026-11-09 08:16 UTC

- capture-v4 requested `station_status` at second 36 of each minute and production about 3–4 s later. Of the 60 minutes in which capture-v4 got a 403, production got no 403 in 56 (93%).
- Consequence: one retry a few seconds after a 403 would recover most of them. At F1's rate it would leave about 1.26 × 4 / 60 ≈ 0.08 403s per hour, below Q1's 0.1. Whether a retry from the same Worker invocation behaves like a request from a second Worker is not shown.

## 5. Conclusion

Observed window: production alone from 2026-11-09 12:00:40 to 2026-11-10 07:48:39 UTC (19.8 h), and the overlap of both Workers from 2026-11-07 10:19 to 2026-11-09 08:16 UTC. It does not cover the last 28 h of D6's window (**#1**), nor whether the rate changes over weeks.

### 5.1 Answers

- **Q1. 403 rate with production alone** 1.26 per hour, the overlap's rate, with no downward trend; each 403 costs a single minute (F1, F2).

### 5.2 Exit criteria

| Criterion | Kind | Result | Findings |
|---|---|---|---|
| Bicing `station_status` 403s with production alone at most 0.1 per hour | Hard cut | Fails: 1.26 per hour; even with no further 403 the window would end at 0.52 per hour | F1 |

### 5.3 Verdict

The 403s do not stop with production alone, so capture handles them. Every request identifies the project in its `User-Agent`, and a 403 is retried once after a random wait of 3–5 s, within the request's single 60 s timeout; the retry is logged even when it succeeds. From F3, this should leave about 0.08 403s per hour, below the 0.1 that Q1 set.

### 5.4 Not verified

- A retry from the same Worker invocation behaves like a request from a second Worker (F3) — the retry recovers fewer 403s than expected — the logged retries show its success rate; if it falls short, revisit the wait.
- Waits below 3 s — none; they are not used.
- Who sends the 403 and what it keys on — a `User-Agent` may change the rate in either direction — the logged retries and 403s show any change after the deploy.

### 5.5 Production inputs

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | Every source request sends `User-Agent: bikesharing-capture (+https://github.com/markciano/bikesharing)` | Verdict | d006 (T059) |
| P2 | An HTTP 403 from any source, on a feed or an index, is retried once after a uniform random wait of 3–5 s (backoff with jitter); other failures keep D8's no-retry rule. The wait starts at 3 s because 3–4 s is the only delay measured (F3), and a limiter counting requests over a window of a few seconds could reject a shorter one; a longer wait costs little, since it happens about 1.3 times per hour and waiting uses no Worker CPU | F1, F2, F3 | d006 (T059) |
| P3 | One 60 s timeout covers the whole request, retry included (an overall deadline above the attempts), so no request lasts more than D8's 60 s; the retry still has about 54 s, against about 1 s for a 200 (p90 935 ms) | Verdict | d006 (T059) |
| P4 | A retried request is logged with `attempts: 1` and the first attempt's status, even when the retry succeeds, so the 403 rate stays measurable | Verdict | d006 (T059) |

### 5.6 Records

None.
