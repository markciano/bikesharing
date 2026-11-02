---
status: Accepted
date: 2026-11-02
---

# Modal as the execution platform

## Context and problem statement

The pipeline is Python and DuckDB on a single node ([ADR-0024](0024-duckdb-as-processing-engine.md), [ADR-0025](0025-sql-models-directed-by-python.md)), and it needs somewhere to run unattended. The choice sets what the owner must maintain and how much of the budget stays free.

- One MERGE bounded to one day needs about 0.8 GB of memory on average and 3 GB at worst, plus disk to spill ([s011/D1](../spikes/s011-engine-pipeline-language.md#d1-processing-engine)).
- Code and its dependencies must be installed ahead of each run, with pinned versions ([d002/R20](../designs/d002-requirements.md#requirements), [ADR-0016](0016-runtime-versions-pinned-per-component.md)).
- The refresh cadence is not chosen yet, so the platform must allow runs every 5 minutes or less, and on demand, so that it does not limit that choice ([d002/R3](../designs/d002-requirements.md#requirements)).
- The pipeline's share of the budget is €4 per month ([ADR-0026](0026-budget-shares-per-component.md)).
- One person operates the solution and has no spare time to keep a machine.

## Considered Options

Every option passes five hard cuts first: it runs pinned Python and DuckDB, gives at least 3 GB of memory with disk to spill, allows the cadence above, can inject secrets, and costs at most €4 per month at a 10-minute cadence, with runs of 2 minutes and 4 GB. Fly.io Machines, Hetzner, Google Cloud Run jobs, Cloudflare Containers, AWS Lambda, Dagster+ Serverless, Prefect Managed and Cloudflare Workers fall at these cuts. The options left are scored on operational load, schedule reliability, cost margin, portfolio value, observability and alerts, and portability.

### 1. Modal, Starter plan

A managed serverless platform that runs Python functions in containers, with a monthly credit.

- Pros:
  - fully managed: the owner only deploys code;
  - €0 while the credit covers usage, with fast starts and built-in time limits and retries.
- Cons:
  - its SDK and an app wrapper are mandatory;
  - logs are kept for 1 day on this plan, and in the US;
  - a less common platform, and what happens to a missed run is not documented.

### 2. GitHub Actions, public repository

Scheduled workflows on managed runners.

- Pros:
  - managed, standard and visible, at €0;
  - logs kept for 90 days.
- Cons:
  - documented delays and dropped scheduled runs;
  - its terms allow use "to develop and test your application(s)", with account suspension among the sanctions.

### 3. Oracle Cloud Always Free

A free Arm virtual machine with 12 GB of memory, with a scheduler on it.

- Pros:
  - €0 and the most memory;
  - plain code or a container, with no SDK.
- Cons:
  - the owner keeps the machine and its updates;
  - creating it can fail for lack of capacity, and idle machines can be reclaimed.

### 4. The owner's Mac

A local scheduler on the owner's computer.

- Pros:
  - no platform cost and plenty of memory.
- Cons:
  - runs are lost while the Mac is off or asleep;
  - nothing to show, and every alert to build.

## Decision Outcome

**Chosen option:** 1. Modal on the Starter plan, with Oracle Cloud Always Free as the fallback.

Modal leads with 8.10 out of 10 because it needs almost no maintenance, which weighs most for a single operator with no spare time, and it costs €0 within its credit. Its one open unknown was memory, since the plan's maximum is not published: a probe confirmed that Starter accepts a function that requests 4 GiB and lets it occupy more than the 3 GB needed.

Why not the others:

- GitHub Actions (7.71): close on score, but its terms and its dropped scheduled runs rule it out for a production schedule, even as the fallback.
- Oracle Cloud Always Free (7.33): the owner would keep a machine, so it is the fallback rather than the first choice.
- The owner's Mac (3.71): it loses runs while it is off or asleep.

**Scope:** Where the pipeline's compute runs. It does not cover the scheduler, how the logic is separated from the platform, or logs and alerts, each in its own ADR. The region and the refresh cadence belong to T040, and capture and the visualization run elsewhere.

### Consequences

#### Positive

- **Almost nothing to maintain:** no operating system, runtime or machine for the owner to keep.
- **No platform cost at the expected usage:** the credit pays for about 540 hours a month at 1 vCPU and 4 GiB, which is runs of up to 7.5 minutes at a 10-minute cadence.
- **A bounded exit:** moving to the fallback touches only the platform layer.

#### Negative

- **Dependence on the credit:** without it, Modal costs about €7.20 per month at a 10-minute cadence, above the pipeline's share, and this decision is reviewed with [ADR-0026](0026-budget-shares-per-component.md). Above the credit, usage is billed, within the limits the owner sets.
- **Short log retention:** anything kept beyond 1 day must leave Modal.
- **Data in the US:** logs, images and secrets stay there whatever the region of the containers. The data is public and credentials stay out of logs.
- **The cost rests on an estimate:** runs of 2 minutes are not measured. With runs of 1 minute or less, normal runs of 2 GB or less, or an on-demand mode, Google Cloud Run jobs and Fly.io Machines could pass the cost cut, and this decision is reopened with them as candidates.
- **Evidence limited to one probe:** it was a temporary app with a plain allocation, not a deployed function running DuckDB. The first deployment of the pipeline checks it, and the fallback applies if the request is rejected.
- **Portfolio value is a judgement:** the platform is less common than the alternatives, with deployment as code but a private dashboard.

## More information

- Needs, cuts, costs per candidate, anchors and scores: [s012/D1](../spikes/s012-execution-target.md#d1-execution-platform); outcome in [s012 Decisions to record](../spikes/s012-execution-target.md#54-decisions-to-record).
- The memory probe: [s012 Findings](../spikes/s012-execution-target.md#4-findings).
- Facts on the plan, its prices and its limits: [Modal source card](../sources/modal.md).
