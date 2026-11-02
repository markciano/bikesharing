---
status: Accepted
date: 2026-11-02
---

# Modal's Cron as the pipeline's scheduler

## Context and problem statement

The pipeline runs on Modal ([ADR-0027](0027-modal-as-execution-platform.md)) and must start on its own, with nobody at hand, at a cadence that is not chosen yet ([s010/P5](../spikes/s010-storage-table-format.md#production-inputs)). Something has to trigger each run.

- The trigger must not limit the cadence, and changing the cadence must be cheap.
- One person operates the solution, so every added component is one more to maintain and one more that can fail.
- Run times should stay predictable across deployments, since the owner redeploys whenever code changes.

## Considered Options

Each option is compared on the components it adds, its behaviour on redeploy and whether it detects a run that does not start.

### 1. Modal's `Cron`

The platform's native schedule, declared on the function with a cron expression.

- Pros:
  - adds no component;
  - fixed clock times, which do not move on redeploy;
  - the cadence is one line of code.
- Cons:
  - what happens to a missed run is not documented;
  - it is specific to the platform.

### 2. Modal's `Period`

The platform's native schedule, declared on the function as an interval.

- Pros:
  - adds no component;
  - the cadence is one line of code.
- Cons:
  - the interval restarts on redeploy, so run times move;
  - what happens to a missed run is not documented;
  - it is specific to the platform.

### 3. A Cloudflare Worker as an external trigger

A Worker with a Cron Trigger that starts the pipeline on Modal.

- Pros:
  - it could detect a run that does not start;
  - the schedule survives a change of execution platform.
- Cons:
  - one more component to maintain, with its own credentials;
  - one more point of failure between the clock and the run;
  - the pipeline would need an entry point callable from outside.

## Decision Outcome

**Chosen option:** 1. Modal's `Cron`.

It follows the pattern of using the platform's native scheduler: it meets the need with no added component, which matters most for a single operator, and it keeps run times fixed across deployments. Detecting a missed run does not need a different trigger, because the alerting decision covers any cause of a run that does not finish.

Why not the others:

- `Period`: its run times move on every redeploy, with no gain over `Cron`.
- A Cloudflare Worker: it adds a component and a point of failure, and it opens an entry point from outside that the pipeline otherwise does not need ([d002/R27](../designs/d002-requirements.md#requirements)).

**Scope:** What triggers the pipeline's scheduled runs. It does not choose the cadence or prevent two runs from overlapping, both in T040, and it does not cover how a missed run is detected, which belongs to the alerts ADR. Capture keeps its own trigger.

### Consequences

#### Positive

- **Nothing to run or maintain:** the schedule is declared with the code and deployed with it.
- **The cadence stays open:** T040 changes one line to set it.

#### Negative

- **Silent on missed runs:** Modal does not document what happens to one, so detecting it depends on a separate mechanism outside Modal.
- **Undefined overlap:** what happens to a scheduled tick while a run is active is not documented, so T040 has to prevent overlaps itself.
- **Tied to the platform:** moving to the fallback in [ADR-0027](0027-modal-as-execution-platform.md) replaces the schedule with the new platform's timer.
- **Plan limit:** Starter allows 5 deployed cron jobs. The pipeline needs one, so a future split into several schedules has little room.

## More information

- Decision at framing: [s012/D2](../spikes/s012-execution-target.md#d2-scheduler); outcome in [s012 Decisions to record](../spikes/s012-execution-target.md#54-decisions-to-record).
- Facts on schedules and plan limits: [Modal source card](../sources/modal.md); [Modal schedules](https://modal.com/docs/guide/cron).
