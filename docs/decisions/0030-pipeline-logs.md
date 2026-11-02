---
status: Proposed
date: 2026-11-02
---

# Pipeline logs as structured events, kept in object storage for 30 days

## Context and problem statement

Each pipeline run leaves a record of what it did, and the owner reads it to find out why a run failed and how runs behave over time. A single operator may read it days after the run, so the record has to outlive the moment of the failure.

- The platform keeps stdout and stderr for 1 day on the chosen plan, in the US, and no way to keep them elsewhere is documented ([ADR-0027](0027-modal-as-execution-platform.md)).
- Whether the platform stays depends on measures taken from real runs: run time and memory.
- The data is public, but logs must not hold storage credentials ([d002/R22](../designs/d002-requirements.md#requirements)).
- The budget is small and R2 bills operations ([d002/R4](../designs/d002-requirements.md#requirements), [ADR-0026](0026-budget-shares-per-component.md)).
- Capture already writes log objects to bronze, as permanent evidence under a bucket lock ([ADR-0023](0023-storage-security-baseline.md)), and the pipeline must not write to bronze ([d002/R17](../designs/d002-requirements.md#requirements)).

## Considered Options

Each option is compared on how long the record lasts, how it can be queried, what it adds to maintain and what it costs.

### 1. Structured events on stdout, plus one object per run in R2

The pipeline writes JSON Lines to stdout, and each run also uploads its events to R2 as one object. A lifecycle rule deletes the objects after 30 days.

- Pros:
  - a failure can be investigated days later;
  - the history of runs can be queried with SQL, using the engine the project already has;
  - no new service or account, at almost no cost.
- Cons:
  - some code in the pipeline to upload the events;
  - a run killed abruptly uploads nothing.

### 2. The platform's logs only

The pipeline writes to stdout, and the platform keeps it for 1 day.

- Pros:
  - nothing to build, and no writes to R2.
- Cons:
  - after a day there is no trace of why a run failed;
  - no history of run time or memory.

### 3. An external log service

The pipeline sends its events to a managed logging service.

- Pros:
  - search, dashboards and retention built in;
  - events can arrive during the run, so an abrupt kill loses less.
- Cons:
  - one more account, secret and component to maintain, for one operator;
  - logs leave for one more provider.

## Decision Outcome

**Chosen option:** 1. Structured events on stdout, plus one object per run in R2.

It keeps the record for as long as a single operator needs it, with no new component, and it gives the measures that decide whether the platform stays. The cost is negligible against R2's free tier.

The base is a standard, logs as an event stream (The Twelve-Factor App), with one deliberate departure: that standard leaves storing logs to the environment, and here the run also uploads its own events, because the environment keeps them for only 1 day and offers no documented alternative on this plan.

Why not the others:

- The platform's logs only: 1 day is too short for one operator, and it leaves no history.
- An external log service: it adds a component to maintain, which is what the Context and [ADR-0027](0027-modal-as-execution-platform.md) seek to avoid.

**Scope:** The pipeline's logs: format, common fields, where they live and for how long. It does not cover which events exist and their own fields, or the exact prefix, both in T040; how alerts reach the owner, in its own ADR; or capture's logs, whose format T039 aligns with this one while they stay where they are.

### The convention

- **Format:** JSON Lines, one event per line.
- **Common fields:** every event carries `ts` (UTC, [ADR-0005](0005-utc-for-all-stored-timestamps.md)), `level`, `run_id` and `event`.
- **Final event of a run:** it also carries `duration_s` and `peak_memory_mb`, the measures that can reopen [ADR-0027](0027-modal-as-execution-platform.md).
- **Place:** one object per run in a prefix of the pipeline's own, with the UTC day in the key (`date=YYYY-MM-DD/<run_id>.jsonl`), outside bronze, so a bucket lock does not block the lifecycle rule and the pipeline needs no write access there.
- **Retention:** 30 days, by a lifecycle rule.
- **Access:** SQL with the engine from the owner's machine, with a read-only token.

### Consequences

#### Positive

- **Failures can wait:** the owner can investigate days later, and one object per run holds all its events, including the step that failed.
- **Measures for later decisions:** run time and peak memory stop being estimates.
- **A shared format:** capture can adopt it, so one query can read both.

#### Negative

- **Abrupt kills leave little:** a run killed by memory or by its time limit uploads no object, and only the platform's 1-day copy remains. The alerts still report the failure.
- **Upload is one more thing that can fail:** if R2 is unavailable, the object is lost along with the run's result; T040 makes sure a failed upload does not hide the run's real outcome.
- **Small files:** one object per run means one read per run queried, which the day in the key keeps bounded.
- **No dashboard:** reading logs takes a query. Whether the pipeline's health gets a view of its own is left to T038.

## More information

- Decision at framing: [s012/D5](../spikes/s012-execution-target.md#d5-pipeline-logs); outcome in [s012 Decisions to record](../spikes/s012-execution-target.md#54-decisions-to-record).
- Cost, with 10 KB per run as a deliberately high assumption: 30 days hold about 43 MB at a 10-minute cadence and 86 MB at 5 minutes, under $0.002 per month. Writes are 0.4% and 0.9% of R2's free 1M Class A per month. With at most 8,640 objects and one read per run of the day queried, no compaction is needed.
- `peak_memory_mb` comes from `ru_maxrss`, since the platform's container has no `VmHWM` ([s012/F2](../spikes/s012-execution-target.md#4-findings)).
- Facts on log retention and location: [Modal source card](../sources/modal.md).
