---
status: Accepted
date: 2026-11-02
---

# Heartbeat alerts for the pipeline

## Context and problem statement

When a pipeline run fails, exceeds its time limit or never starts, the owner has to find out without looking for it ([d002/R23](../designs/d002-requirements.md#requirements)). A failure nobody hears about leaves the published data ageing with no one acting on it.

- A run can end in several ways: a controlled error, a time limit, a kill by memory, or no start at all because of a platform outage, the schedule or an exhausted credit.
- The platform documents a notice for failed scheduled runs, through Slack. It does not document timeouts, memory kills or runs that never start as triggers, nor what happens to a missed run ([ADR-0027](0027-modal-as-execution-platform.md), [ADR-0028](0028-modal-cron-as-pipeline-scheduler.md)).
- One person operates the solution, with a small budget and little time to maintain more components.

## Considered Options

Each option is compared on which of those endings it detects, what it adds to maintain and what it costs.

### 1. Heartbeat with an external monitor

Also known as a dead man's switch. Each run signals its start and its result to a monitor outside the platform, which alerts on a failure signal or when an expected signal does not arrive. Silence is what triggers it, so it needs no knowledge of the cause.

- Pros:
  - detects every ending, whatever the cause, including an outage of the platform;
  - a few lines of code and a free plan, with nothing to deploy.
- Cons:
  - one more account and one more secret, the signal URL;
  - a run that never starts is detected only after the expected period and its grace time.

### 2. The platform's notifications

The notices Modal sends for failed scheduled runs.

- Pros:
  - nothing to build or to add.
- Cons:
  - timeouts, memory kills and runs that never start are not documented as triggers;
  - documented through Slack, and whether a failed run sends email is not stated.

### 3. A scheduled check on the age of the data

A Cloudflare Worker with a Cron Trigger reads the age of the latest data in R2 and sends an email when it is too old.

- Pros:
  - detects every ending, and also a run that ends well with no new data;
  - runs outside the platform, on a provider the project already uses.
- Cons:
  - own code to write, test and maintain;
  - every failure is reported late, after the data has aged past the threshold.

## Decision Outcome

**Chosen option:** 1. Heartbeat with an external monitor, using Healthchecks.io on its free plan.

It is the only option that detects every ending listed in the Context with no code to maintain beyond the signals, and it costs €0. The monitor has to sit outside the platform, because a failed platform cannot report its own failure.

Among heartbeat services, Healthchecks.io offers 20 checks on its free plan, against 5 for Cronitor and 10 for Better Stack, with start and failure signals and email alerts. It is also open source and can be self-hosted, which leaves a way out.

Why not the others:

- The platform's notifications: they do not cover what [ADR-0028](0028-modal-cron-as-pipeline-scheduler.md) leaves to this decision. They can stay on as an extra, with nothing relying on them.
- A scheduled check on the age of the data: it covers every cause, but with more code to maintain and slower detection of ordinary failures.

**Scope:** How the pipeline's failures reach the owner. It does not cover capture's alert ([d002/R8](../designs/d002-requirements.md#requirements)), which T039 decides and may build on the same service, or the cost alert. The number of retries and the time limit belong to T040, which sends the failure signal once retries are exhausted.

### Consequences

#### Positive

- **One mechanism for every ending:** the owner receives the same kind of alert whatever went wrong, and looks up the cause in the pipeline's logs.
- **Fast on ordinary failures:** a failure signal alerts at once.
- **Independent of the platform:** the signals are plain HTTP calls, so they survive a move to the fallback.

#### Negative

- **Slower on silence:** a run that dies abruptly or never starts alerts after the period plus its grace time, about 20 minutes at a 10-minute cadence with 10 minutes of grace.
- **One more dependency:** if the monitor is down, a failure may go unnoticed, or a false alert may arrive. The visualization still shows the age of the data ([d002/R7](../designs/d002-requirements.md#requirements)).
- **One more secret:** whoever gets the signal URL could send false signals and hide a failure. It gives access to nothing else, and the risk is accepted ([s012/TH11](../spikes/s012-execution-target.md#d3-pipeline-security)).
- **Blind to empty success:** a run that ends well with no new data sends a success signal. [d002/R7, R8](../designs/d002-requirements.md#requirements) cover that case.
- **Minimum period not confirmed:** a secondary source states 60 seconds, enough for any cadence T040 can choose. It is checked when the monitor is created.

## More information

- Signals carry no body, so logs stay in R2 and leave for no other provider. The package signals only when the URL's environment variable is set, so it still runs without the monitor ([ADR-0029](0029-pipeline-code-architecture.md)).
- Decision at framing: [s012/D5](../spikes/s012-execution-target.md#d5-pipeline-logs); outcome in [s012 Decisions to record](../spikes/s012-execution-target.md#54-decisions-to-record).
- Facts on Modal's notifications: [Modal source card](../sources/modal.md).
- Heartbeat services: <https://healthchecks.io/pricing/>, <https://healthchecks.io/docs/http_api/>, <https://healthchecks.io/docs/self_hosted/>, <https://cronitor.io/pricing>, <https://betterstack.com/pricing>.
