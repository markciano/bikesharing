# Spike: Execution target

- **Task:** T037
- **ADRs:** [ADR-0010](../decisions/0010-ingestion-logic-separated-from-platform.md) (to be replaced), [ADR-0016](../decisions/0016-runtime-versions-pinned-per-component.md), [ADR-0023](../decisions/0023-storage-security-baseline.md), [ADR-0024](../decisions/0024-duckdb-as-processing-engine.md), [ADR-0025](../decisions/0025-sql-models-directed-by-python.md), [ADR-0026](../decisions/0026-budget-shares-per-component.md)
- **Code:** `spikes/execution-target/`

## Status

- State: Draft 📝
- Phase: [ ] Questions · [ ] Method · [ ] Steps · [ ] Steps review
- Started: — · Finished: —
- Current step: —

## 1. Questions — what we need to know

### 1.1 Context

Storage (T035), engine and pipeline language (T036) are decided; this spike decides where the pipeline runs (D1, the central decision), what schedules it (D2), its threats and new requirements (D3), how processing logic is separated from the platform (D4) and how the pipeline logs (D5). The refresh cadence is not chosen here: [s010 › P5](s010-storage-table-format.md#production-inputs) leaves it to T040, and R2's Class B operations limit it, not the machine. D2–D5 depend on D1.

### 1.2 Decided at framing

#### D1. Execution platform

Modal, on its Starter plan, runs the pipeline. It leads the matrix (8.10) and needs almost no maintenance, which weighs most because the owner has no spare time to keep a machine. Its cost stays at €0 while the $30 monthly credit covers it: at 1 vCPU and 4 GiB the credit pays for 540 hours a month, so runs of up to 7.5 minutes at a 10-minute cadence, or 3.75 minutes at 5 minutes. Above the credit, usage is billed. This depends on [Q1](#13-questions): if its Gate fails, Oracle Cloud Always Free replaces Modal and D2–D5 are reviewed.

What would change it: without the credit, Modal costs about €7.20 per month at 10 minutes, above N4's cut, so this decision is reviewed with the pipeline share of [ADR-0026](../decisions/0026-budget-shares-per-component.md). The cost itself is not a loss of service. N4's cut rests on runs of 2 minutes, an unmeasured estimate. With runs of 1 minute or less, Google Cloud Run jobs (about €1.37 per month at 10 minutes) and Fly.io Machines (about €2.28) would pass it, and they may also pass under an on-demand mode.

The cut also assumes 4 GB in every run, which is the worst case. With 2 GB, Fly.io Machines would pass at about €2.41 per month at 10 minutes.

`TODO(T040)`: if the first slice measures runs of 1 minute or less, or normal runs of 2 GB or less, or T040 chooses the on-demand mode, reopen this decision with Cloud Run and Fly.io as candidates.

Options rejected:

- **Oracle Cloud Always Free** (7.33) is the fallback: €0 and 12 GB, but the owner keeps the machine, and creating it can fail for lack of capacity.
- **GitHub Actions** (7.71) scores close to Modal, and one more point on reliability would tie them. It is not the fallback for two facts outside the matrix: its terms allow use "to develop and test your application(s)", with account suspension among the sanctions, and its documented delays and dropped runs do not support [d002 › R3](../designs/d002-requirements.md#requirements).
- **The owner's Mac** (3.71) loses runs while it is off or asleep.

Needs and hard cuts:

| # | Need | Source | Hard cut |
|---|---|---|---|
| N1 | Run Python and DuckDB with pinned code installed ahead of the run | [d002 › R20](../designs/d002-requirements.md#requirements), [ADR-0016](../decisions/0016-runtime-versions-pinned-per-component.md) | Not possible: out |
| N2 | Memory for a MERGE bounded to one day: about 0.8 GB on average, 3 GB at worst ([s011 › D1](s011-engine-pipeline-language.md#d1-processing-engine)) | [ADR-0024](../decisions/0024-duckdb-as-processing-engine.md) | Under 3 GB, plus disk to spill: out |
| N3 | Run every 5 minutes or less, and on demand, so the platform does not limit T040's cadence | [d002 › R3](../designs/d002-requirements.md#requirements), [s010 › P5](s010-storage-table-format.md#production-inputs) | Not possible: out |
| N4 | Cost within the pipeline's share | [d002 › R4](../designs/d002-requirements.md#requirements), [ADR-0026](../decisions/0026-budget-shares-per-component.md) | Above €4 per month: out |
| N5 | A known run limit, so T040 can size its catch-up batches to it | [d002 › R11](../designs/d002-requirements.md#requirements) | None: reported for each candidate, as an input for T040 |
| N6 | Component credentials outside logs and files | [d002 › R15, R22](../designs/d002-requirements.md#requirements) | No way to inject secrets: out |
| N7 | Failures with limited retries, a time limit and an alert | [d002 › R23](../designs/d002-requirements.md#requirements) | Scored |
| N8 | Pipeline logs: where they live, retention and access | [D5](#d5-pipeline-logs) | Scored |

Criteria:

| Criterion | Weight | What it measures |
|---|---|---|
| Operational load | 5 | Patches, outages and maintenance for one person |
| Schedule reliability | 4 | Whether runs start on time, with none skipped |
| Cost margin | 4 | How much of the €4 stays free |
| Portfolio value | 3 | How standard and demonstrable it is in a data engineering project |
| Observability and alerts | 3 | Covers N7 and N8 |
| Portability | 2 | How much changing platform costs |

Anchors (2 and 4 fall between them):

| Criterion | 1 | 3 | 5 |
|---|---|---|---|
| Operational load | The owner patches the OS and runtime and restarts the service by hand | The owner maintains an image or a machine with unattended updates | Fully managed: the owner only deploys code |
| Schedule reliability | Best effort: documented delays as long as the cadence, or skipped runs | Delays of a few minutes at peak, no skipped runs documented | Starts within a minute, and a missed run is detected or retried |
| Cost margin | Above €3 and up to €4 per month | Above €1 and up to €2 per month | €0 per month |
| Portfolio value | Runs only on the owner's machine, with nothing to show | A common platform, deployed by hand | A standard platform with deployment as code, and runs that can be shown |
| Observability and alerts | No retained logs or failure alerts: all to be built | Logs kept for days and a failure signal, with the alert or time limit still to be built | Logs kept 30 days or more, with failure alerts, time limits and retries built in |
| Portability | The code runs only on the platform's own runtime | A standard container, with platform-specific trigger and configuration | The same artefact runs unchanged locally, in CI and in production |

Cost reference: each candidate's platform cost is computed for every row below, in a 30-day month, with 4 GB of memory (N2's 3 GB plus margin) and runs of 2 minutes, an unmeasured estimate, and again at 4 minutes. N4's cut and the Cost margin score are judged at 10 minutes, the fastest 24/7 cadence that fits R2's gate ([s010 › P5](s010-storage-table-format.md#production-inputs)). A candidate that passes at 10 minutes but not at a faster cadence stays in, with its costs shown. The R2 bill is separate.

| Cadence | Runs per month | Hours per month at 2 min | Hours per month at 4 min |
|---|---|---|---|
| 1 min | 43,200 | 720 (runs overlap) | 720 (runs overlap) |
| 2 min | 21,600 | 720 | 720 (runs overlap) |
| 5 min | 8,640 | 288 | 576 |
| 10 min | 4,320 | 144 | 288 |
| 15 min | 2,880 | 96 | 192 |

Hard cuts applied, with platform cost per month in EUR (runs of 2 / 4 minutes; a single figure when both match). USD at 0.8982, the rate in the storage cost model of 2026-10-28. Prices gathered on 2026-11-02; Cloud Run's rates come from third-party sources.

| Candidate | Basis | 1–2 min | 5 min | 10 min | 15 min | Result |
|---|---|---|---|---|---|---|
| Oracle Cloud Always Free | Arm VM, 12 GB | 0 | 0 | 0 | 0 | Passes |
| Modal | 1 vCPU, 4 GiB, after the $30 monthly credit | 8.98 | 0 / 1.80 | 0 | 0 | Passes |
| GitHub Actions, public repository | 4 vCPU, 16 GB | Not possible: 5-minute minimum | 0 | 0 | 0 | Passes |
| Owner's Mac | M4 Pro, 24 GB; electricity not counted | 0 | 0 | 0 | 0 | Passes |
| Fly.io Machines | Shared 2 vCPU, 4 GB | 22.81 | 9.13 / 18.24 | 4.56 / 9.13 | 3.04 / 6.08 | Out: N4 |
| Hetzner CX23 | 2 vCPU, 4 GB; fixed price, VAT excluded | 5.49 | 5.49 | 5.49 | 5.49 | Out: N4 |
| Google Cloud Run jobs | 1 vCPU, 4 GiB, after the free tier | 55.84 | 19.53 / 43.73 | 7.42 / 19.53 | 3.39 / 11.45 | Out: N4 |
| Cloudflare Containers | `standard-1`, upper bound, with the $5 plan | 51.71 | 22.98 / 42.13 | 13.41 / 22.98 | 10.22 / 16.61 | Out: N4 |
| AWS Lambda | 4,096 MB, x86, us-east-1 | 149.22 | 56.09 / 118.18 | 25.05 / 56.09 | 14.70 / 35.40 | Out: N4 |
| Dagster+ Serverless | Compute only, without the $10 fee and credits | 388.02 | 155.21 / 310.42 | 77.60 / 155.21 | 51.74 / 103.47 | Out: N4 |
| Prefect Managed | Hobby: 500 minutes per month | Above the cap | Above the cap | Above the cap | Above the cap | Out: N1 (installs packages at run time) and N4 |
| Cloudflare Workers | 128 MB per isolate | — | — | — | — | Out: N1, N2 |

Scores of the candidates that pass (facts gathered on 2026-11-02, sources in [Sources](#6-sources)):

| Criterion (weight) | Modal | GitHub Actions, public repository | Oracle Cloud Always Free | Owner's Mac |
|---|---|---|---|---|
| Operational load (5) | 5: managed; the owner deploys the image and app code | 5: managed runners; the owner keeps the workflow and pins | 3: a VM the owner keeps with unattended updates | 1: the owner keeps the machine on, awake and updated |
| Schedule reliability (4) | 4: boots in about 1 s, scheduled functions notify on failure; missed runs not documented | 1: documented delays and dropped runs under load; user reports of delays of hours | 4: own timer on an always-on VM; continuity depends on capacity and idle reclamation | 1: runs are lost while the Mac is off or asleep |
| Cost margin (4) | 5: €0 within the $30 credit | 5: €0 | 5: €0 | 4: €0 on the platform; about €1 of electricity (estimate) |
| Portfolio value (3) | 3: deployment as code, on a less common platform, with a private dashboard | 4: standard and visible, though not a usual pipeline runner | 3: a common VM, with no view of runs | 1: nothing to show |
| Observability and alerts (3) | 3: timeouts, retries and failure notice built in; Starter keeps logs for 1 day | 4: logs for 90 days, timeouts and a notice to whoever last edited the schedule; retries are manual | 3: free monitoring, alarms and notifications; timeouts and retries to be built | 1: all to be built |
| Portability (2) | 3: the logic is plain Python, but a Modal app wrapper and SDK are mandatory | 4: plain code or a container, with a workflow file as trigger | 4: plain Python or a container, Arm only | 4: plain code, with a local scheduler as trigger |
| **Weighted score (out of 10)** | **8.10** | 7.71 | 7.33 | 3.71 |

#### D2. Scheduler

`TODO(T037)`: depends on D1.

#### D3. Pipeline security

`TODO(T037)`: depends on D1.

#### D4. Processing logic separated from the platform

`TODO(T037)`: replaces ADR-0010.

#### D5. Pipeline logs

`TODO(T037)`: depends on D1.

### 1.3 Questions

Main question: can Modal's Starter plan give the pipeline the memory it needs?

- **Q1.** Does Modal's Starter plan accept a function that requests 4 GiB, and let it occupy that memory? Its documentation enforces a maximum without stating the figure. Unblocks D1. Gate: if not, Oracle Cloud Always Free replaces Modal.

### 1.4 Exit criteria

- **Standard:** weighted decision matrix, with a Gate on the winner only.
- **Timebox:** one owner session of up to one hour, ended by Q1's result.
- A function that requests 4 GiB is accepted and occupies at least 3 GB without failing — hard cut.

### 1.5 Out of scope

- The pipeline's mode and refresh cadence, and how the ≤ 5-minute freshness of R3 is reconciled with them ([s010 › P5](s010-storage-table-format.md#production-inputs)) — T040
- Which events the pipeline logs — T040
- The size of catch-up batches, and where the one-off history load runs — T040
- The pipeline's end-to-end and post-deploy smoke tests, on paper in [testing-strategy](../testing-strategy.md) — T040
- Aligning capture's logs with the convention this spike sets for the pipeline: format and field names only; log objects from before the production start are deleted before the bucket lock is enabled ([ADR-0023](../decisions/0023-storage-security-baseline.md)), so only the new format remains — T039

### 1.6 Open questions

| Question | Notes |
|---|---|
| | |

## 2. Method — how we find out

### 2.1 Approach

| Variant | What it is | What it tells |
|---|---|---|
| | | |

### 2.3 Decision log

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|

### 2.4 File layout

```text
spikes/execution-target/
└── README.md        Question, setup and commands, what each script does, link to the report; How we got here (written at Conclusion)
```

## 3. Steps

### 3.1 Prerequisites

## 4. Findings

### 4.1 Production inputs

| P | Input | Origin | Destination |
|---|---|---|---|

## 5. Conclusion

### 5.1 Answers

### 5.2 Exit criteria

| Criterion | Kind | Result | Findings |
|---|---|---|---|

### 5.3 Verdict

### 5.4 Decisions to record

| D | Outcome | Why |
|---|---|---|

### 5.5 Not verified

### 5.6 Follow-ups

## 6. Sources

Gathered by the `web-researcher` on 2026-11-02 for D1:

- GitHub Actions terms: <https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features>
- GitHub Actions schedules, delays and dropped jobs: <https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule>
- GitHub Actions runners, limits and log retention: <https://docs.github.com/en/actions/reference/runners/github-hosted-runners>, <https://docs.github.com/en/actions/reference/limits>, <https://docs.github.com/en/organizations/managing-organization-settings/configuring-the-retention-period-for-github-actions-artifacts-and-logs-in-your-organization>
- User reports of delayed scheduled runs (third-party): <https://github.com/orgs/community/discussions/210625>, <https://github.com/orgs/community/discussions/201472>
- Modal pricing, billing and limits: <https://modal.com/pricing>, <https://modal.com/docs/guide/billing>, <https://modal.com/docs/guide/resources>
- Modal schedules, cold start, failure notice and existing images: <https://modal.com/docs/guide/cron>, <https://modal.com/docs/guide/cold-start>, <https://modal.com/docs/guide/managing-deployments>, <https://modal.com/docs/guide/existing-images>
- Oracle Always Free limits and idle reclamation: <https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm>
- Oracle Monitoring and Notifications: <https://docs.oracle.com/en-us/iaas/Content/Monitoring/Concepts/monitoringoverview.htm>, <https://docs.oracle.com/en-us/iaas/Content/Notification/Concepts/notificationoverview.htm>
- Candidates cut: <https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/>, <https://docs.fly.io/about/pricing>, <https://cloud.google.com/run/pricing>, <https://developers.cloudflare.com/containers/pricing/>, <https://developers.cloudflare.com/workers/platform/limits/>, <https://aws.amazon.com/lambda/pricing/>, <https://dagster.io/pricing>, <https://www.prefect.io/pricing>, <https://www.prefect.io/docs/v3/how-to-guides/deployment_infra/managed>
