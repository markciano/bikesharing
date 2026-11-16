---
status: Accepted
date: 2026-11-16
---

# Catch-up in bounded batches, with failed batches set aside for redrive

## Context and problem statement

Capture writes bronze objects all day; the pipeline runs on a schedule ([ADR-0028](0028-modal-cron-as-pipeline-scheduler.md)) and turns them into silver and gold. The amount waiting for a run varies widely: one cadence's captures normally, everything captured so far on the first load, hours or days of captures after an outage of capture or of the platform. Some objects reach bronze late, after a run has covered their capture time.

A run has bounded memory and time on its platform, so it cannot always take everything waiting at once. A batch that fails a rule on the pipeline's own logic must not be committed, and a row that fails its column's schema is quarantined while the rest of its batch is committed ([ADR-0042](0042-data-quality-classes-and-severity.md)); fixing that logic, or accepting a provider's new value into a schema, takes a new code version.

Without a policy, a backlog either overflows a run, or drains too slowly, or leaves a gap that someone must reload by hand; and one faulty batch can freeze the page.

## Considered Options

### 1. Drain in bounded batches, with failed batches set aside

Each run processes every bronze object no run has processed yet, whatever its capture time, in batches bounded in objects and in bytes, oldest first, one after another until none is left or its time budget is spent; then it ends, leaving the rest for the next run, following the drain mode of bounded micro-batches (e.g. Spark's `AvailableNow` trigger). Each batch is audited and committed as it ends. A batch that fails on reading, writing or the platform stays pending for the next run. A batch that fails a rule of severity error is set aside, following a dead-letter queue with redrive, and returns to pending when a new code version is deployed, as does each object with rows in quarantine.

- Pros:
  - Any backlog drains with the same code, in consecutive runs, and no run exceeds its memory or its time.
  - Late objects, returned batches and quarantined rows enter the next run with no manual step.
  - One faulty batch does not hold back the others.
- Cons:
  - A long backlog takes several runs, during which the page serves older data.
  - Batches set aside leave a gap in the history until the fix is deployed.

### 2. Drain, but stop at a batch that fails a rule

As option 1, but a batch that fails a rule of severity error stops processing until the code is fixed.

- Pros:
  - The history never has a gap: batches publish strictly in order.
- Cons:
  - One faulty object freezes the page until a fix is deployed.

### 3. One batch per run

Each run processes one bounded batch, the oldest pending, and ends.

- Pros:
  - Every run is short and predictable.
- Cons:
  - A backlog drains by one batch per cadence, which can take days after an outage.

### 4. A fixed window per run

Each run processes only the captures of its last cadence.

- Pros:
  - Simple: what a run reads follows from its start time.
- Cons:
  - An outage, or an object that arrives late, leaves a gap until a manual reload.

### 5. A separate first load, then unbounded incremental runs

A one-off load processes everything captured so far; each later run processes everything new, with no bound.

- Pros:
  - Normal runs need no batching.
- Cons:
  - Two code paths for the same transformation.
  - A long outage can still overflow a run's memory.

## Decision Outcome

**Chosen option:** 1. Drain in bounded batches, with failed batches set aside

Processing an object again adds only the rows silver and gold do not hold yet, and a run never starts while another is running, so scheduled runs wait while one drains and the cadence resumes by itself. A batch is processed from bronze as a whole, so nothing of a failed batch counts as done. An object larger than the byte bound on its own is set aside like a batch that fails a rule. A run takes no further batch once a fixed time budget, below its timeout, is spent, and ends well, following a graceful shutdown before a deadline; the timeout only catches a run that hangs. The bounds, the time budget and the timeout are set from the memory and run time measured in production.

Rationale: the amount waiting varies by orders of magnitude, so only bounded batches fit every case in a run's memory and time, and only draining them run after run clears a backlog without waiting one batch per cadence or a manual reload; ending at a budget keeps normal catch-up apart from a run that fails. Setting a failed batch aside follows from [ADR-0042](0042-data-quality-classes-and-severity.md): a fault in the project's own code keeps that batch off the page, but must not stop the batches that pass; the new code version that fixes it is what returns it, and the same version is what may accept a quarantined row, so that row's object returns too.

Why not the others:

- Option 2 lets one faulty object stop the page.
- Option 3 turns an outage of hours into a backlog of days.
- Option 4 needs a manual reload after every outage.
- Option 5 keeps two code paths and can still overflow.

**Scope:** the pipeline's processing of bronze into silver and gold, in every run. It does not cover the one-off load of the providers' historical archives, a separate source, nor how a late object changes values already derived from the objects around it, which each business process decides.

### Consequences

#### Positive

- **Self-healing:** after an outage, the next runs catch up with no manual step.
- **Bounded runs:** no amount of backlog overflows a run's memory or time.
- **Isolated faults:** a faulty batch removes only its own data from the page, until fixed.

#### Negative

- **Older data while draining:** during a long catch-up the page serves older data, and its age says so.
- **Gaps until a fix:** batches set aside and quarantined rows are missing from the history until a new code version returns them.
- **Processing state:** the pipeline keeps a record of which objects are processed or set aside, which must be rebuildable from bronze and the rows' lineage ([ADR-0043](0043-lineage-at-four-levels.md)).

## More information

- [d007 › D7](../designs/d007-pipeline-design.md#d7-catch-up-in-bounded-batches), [#1, #9, #10](../designs/d007-pipeline-design.md#22-decision-summary), and its threats TH1–TH3 in [D8](../designs/d007-pipeline-design.md#d8-pipeline-security-threats).
