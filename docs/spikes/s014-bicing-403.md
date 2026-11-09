<!--
Spike doc template. A spike is a time-boxed investigation of one task: it reaches the decisions a task needs, by analysis where possible and with evidence only where an unknown would change the choice. Its output is knowledge (decisions, answers, a verdict, inputs for designs and ADRs); its code is throwaway and lives in spikes/<name>/.
Blocks: Questions (what we need to know), Method (how we find out), Steps, Findings (filled during execution), Conclusion (filled after the last step).
Sections marked Optional are kept only when they apply.
-->

# Spike: Bicing 403s on station_status

- **Task:** T059
- **ADRs:** none
- **Code:** none; the log queries are throwaway and not kept.

## Status

<!-- State: Draft 📝 · Ready 🎬 · Running 🔄 · Concluded ✅.
Phase: the blocks and the review completed.
Started / Finished: UTC dates of the first step executed and of the Conclusion.
Current step: the step being executed, or —. -->

- State: Draft 📝
- Phase: [ ] Questions · [ ] Method · [ ] Steps · [ ] Steps review · [ ] Conclusion
- Started: — · Finished: —
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
- **Timebox:** D6's window, 2026-11-09 12:00 to 2026-11-11 12:00 UTC; it ends with the measurement after the window closes.
- Bicing `station_status` 403s with production alone — at most 0.1 per hour (72 minutes per month, a third of the budget, leaving the rest for the ~78 minutes per month of other failures seen in the spike) — hard cut

## 2. Method — how we find out

### 2.1 Approach

| Variant | What it is | What it tells |
|---|---|---|
| A | Count of 403s per hour in production's pass logs over D6's window | Q1 |

#### A. 403 rate with production alone

A query over the window's pass logs counts the passes and the `feed_failed` and `index_rejected` events with `status` 403 for Bicing, per UTC hour and in total, and lists runs of consecutive minutes with a 403. Passes come from the distinct `run_id`.

### 2.3 Decision log

None.

### 2.4 File layout

None: the query runs from a scratch file and is not kept.

## 3. Steps

### 3.1 Prerequisites

None.

### Step 1 — Copy the window's production logs

- **Status:** 💤 todo
- **Who:** Owner
- **Model:** —

#### Scope

Production's pass logs from 2026-11-09 to 2026-11-11, copied to `spikes/cloudflare-capture-spike/analysis/output/prod-logs/` (ignored by Git).

#### Do

1. After 2026-11-11 12:00 UTC, run:

   ```bash
   rclone copy r2:bikesharing-bronze/logs spikes/cloudflare-capture-spike/analysis/output/prod-logs --include "date=2026-11-{09,10,11}/**"
   ```

#### Check

The folders `date=2026-11-09` to `date=2026-11-11` hold one log per pass, about 1,440 per full day.

### Step 2 — Measure the 403 rate

- **Status:** 💤 todo
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

The window's pass count matches about 2,880 passes (48 h), and the 403 count matches a `grep -rc` of `"status":403` over the same folders.

## 4. Findings

<!-- Filled during the run, in the step that produces the evidence. One fact per finding: what was observed, the evidence (figures, tables) and its consequence for the spike. Numbering is never reused. An earlier finding is not rewritten to fit a later result; the later one says which finding it corrects. -->

## 5. Conclusion

<!-- Filled after the last step. Covers only the observed window. -->

Observed window: `<from–to, UTC; what it does not cover>`

### 5.1 Answers

- **Q1.** `<answer>` (FN)

### 5.2 Exit criteria

<!-- One result per criterion and variant. -->

| Criterion | Kind | Result | Findings |
|---|---|---|---|

### 5.3 Verdict

<!-- The answer to the main question in 2–3 sentences. -->

### 5.4 Not verified

<!-- What the evidence does not cover, each with its risk and mitigation. "None" is valid. -->

- `<item>` — `<risk>` — `<mitigation>`

### 5.6 Records

<!-- Documents this spike updates before it closes: ADRs from Decided at framing (each in its own commit), architecture, requirements, source cards and new tasks agreed with the owner. A decision that updates no document has no row. Commit: "Done", or "Pending" until delivered; the spike closes when every row is Done. Production inputs are not repeated here. -->

| Output | From | Destination | Commit |
|---|---|---|---|
| `<ADR, requirement, source card or task>` | `<e.g. D1, F3>` | `<document and section>` | `<Done, or Pending>` |
