# Spike: Execution target

- **Task:** T037
- **ADRs:** [ADR-0010](../decisions/archive/0010-ingestion-logic-separated-from-platform.md) (replaced by [ADR-0029](../decisions/0029-pipeline-code-architecture.md)), [ADR-0016](../decisions/0016-runtime-versions-pinned-per-component.md), [ADR-0023](../decisions/0023-storage-security-baseline.md), [ADR-0024](../decisions/0024-duckdb-as-processing-engine.md), [ADR-0025](../decisions/0025-sql-models-directed-by-python.md), [ADR-0026](../decisions/0026-budget-shares-per-component.md), [ADR-0027](../decisions/0027-modal-as-execution-platform.md), [ADR-0028](../decisions/0028-modal-cron-as-pipeline-scheduler.md), [ADR-0030](../decisions/0030-pipeline-logs.md), [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md)
- **Code:** `spikes/execution-target/`

## Status

- State: Concluded ✅
- Phase: [x] Questions · [x] Method · [x] Steps · [x] Steps review
- Started: 2026-11-02 · Finished: 2026-11-02
- Current step: —

## 1. Questions — what we need to know

### 1.1 Context

Storage (T035), engine and pipeline language (T036) are decided; this spike decides where the pipeline runs (D1, the central decision), what schedules it (D2), its threats and new requirements (D3), how processing logic is separated from the platform (D4) and how the pipeline logs and alerts the owner (D5). The refresh cadence is not chosen here: [s010 › P5](s010-storage-table-format.md#production-inputs) leaves it to T040, and R2's Class B operations limit it, not the machine. D2–D5 depend on D1.

### 1.2 Decided at framing

#### D1. Execution platform

Modal, on its Starter plan, runs the pipeline. It leads the matrix (8.10) and needs almost no maintenance, which weighs most because the owner has no spare time to keep a machine. Its cost stays at €0 while the $30 monthly credit covers it: at 1 vCPU and 4 GiB the credit pays for 540 hours a month, so runs of up to 7.5 minutes at a 10-minute cadence, or 3.75 minutes at 5 minutes. Above the credit, usage is billed. This depends on [Q1](#13-questions): if its Gate fails, Oracle Cloud Always Free replaces Modal and D2–D5 are reviewed.

What would change it: without the credit, Modal costs about €7.20 per month at 10 minutes, above N4's cut, so this decision is reviewed with the pipeline share of [ADR-0026](../decisions/0026-budget-shares-per-component.md). The cost itself is not a loss of service. N4's cut rests on runs of 2 minutes, an unmeasured estimate. With runs of 1 minute or less, Google Cloud Run jobs (about €1.37 per month at 10 minutes) and Fly.io Machines (about €2.28) would pass it, and they may also pass under an on-demand mode.

The cut also assumes 4 GB in every run, which is the worst case. With 2 GB, Fly.io Machines would pass at about €2.41 per month at 10 minutes.

`TODO(T040)`: if the first slice measures runs of 1 minute or less, or normal runs of 2 GB or less, or T040 chooses the on-demand mode, reopen this decision with Cloud Run and Fly.io as candidates. To measure it, the final log event of every run ([D5](#d5-pipeline-logs)) carries `duration_s` and `peak_memory_mb`, the latter from `ru_maxrss` (**#1**).

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

Modal's built-in `Cron` schedules the pipeline, following the pattern of using the platform's native scheduler. It adds no component, its fixed clock times do not move on redeploy, as `Period` intervals do, and the cadence T040 chooses is one line of code. Modal does not document what happens to a missed run, so [D5](#d5-pipeline-logs) covers detecting it.

Rejected: a Cloudflare Worker as an external trigger. It could detect a run that does not start, but it adds a component to maintain and a point of failure.

#### D3. Pipeline security

Five new requirements, R24–R28, and the other threats documented without a requirement. Threats are listed with STRIDE and controls follow least privilege, as in [s011 › D4](s011-engine-pipeline-language.md#d4-pipeline-security). The scope is where the pipeline runs: its account, secrets, deployment, network and spend. Facts on Modal gathered on 2026-11-02.

| # | Threat (STRIDE) | Impact | Control | Requirement |
|---|---|---|---|---|
| TH1 | Someone takes over the Modal account, or the GitHub account it logs in with (Spoofing) | Code runs with the pipeline's token, and spends on the owner's card | Two-factor authentication on the login; tokens with an expiry, kept outside the repository; no other workspace members | R24 |
| TH2 | The R2 token leaks from where the pipeline receives it (Information disclosure) | Same as a leaked credential in [ADR-0023](../decisions/0023-storage-security-baseline.md) | Injected from `modal.Secret`, encrypted at rest and stored in the US; never in the image or the repository; bounded by R15 and R17 | R25 |
| TH3 | Unreviewed code reaches production (Tampering) | Wrong or harmful code runs with the pipeline's token | Deploy only commits on `main`, which passed the PR's checks. The owner deploys, since Modal's CI service users are stated for Team and Enterprise | R26 |
| TH4 | Something calls the pipeline from outside (Spoofing, Denial of service) | Unplanned runs and cost | No web decorators: runs start only from the schedule or the owner's Modal client. This closes [s011 › TH10](s011-engine-pipeline-language.md#d4-pipeline-security) | R27 |
| TH5 | A loop or a bug spends beyond the budget (Denial of service) | The card is charged above R4 (denial of wallet); R23 bounds a single run, not the month | A spend limit on the platform; Modal stops workloads that would incur out-of-pocket charges. The pipeline catches up later (R11), and the visualization shows the age of the data (R7) | R28 |
| TH6 | A compromised dependency sends data or the token out (Information disclosure) | Same as TH2 | Accepted: outbound restrictions are documented for Modal's Sandboxes, not Functions; prevented by R20 and bounded by R15 and R17 | None |
| TH7 | Logs and payloads stay on Modal, in the US (Information disclosure) | Low: public feed data, and no credentials (R22) | Accepted | None |
| TH8 | Data leaks through DuckDB's temporary files ([s011 › TH9](s011-engine-pipeline-language.md#d4-pipeline-security)) (Information disclosure) | Low: public feed data, and no credentials (R22) | Accepted, closing s011 › TH9: each container runs in its own sandbox; encryption and wiping of its disk are not documented | None |
| TH9 | No way to tell who deployed what (Repudiation) | Low: there is one operator | Accepted: Modal keeps a deployment history, and `main` the code | None |
| TH10 | Modal has an outage or withdraws the credit (Denial of service) | The pipeline stops, or its cost rises | Covered by R7 and R11; cost by [D1](#d1-execution-platform); moving to the fallback is bounded by [D4](#d4-processing-logic-separated-from-the-platform) | None |
| TH11 | The heartbeat URL of [D5](#d5-pipeline-logs) leaks (Spoofing) | Low: false signals could hide a failure, and the visualization still shows the age of the data (R7) | Accepted: kept as a secret, as in TH2, and it gives access to nothing else | None |
| TH12 | A memory kill is retried without limit: Modal's [retries guide](https://modal.com/docs/guide/retries) states this for deployed apps and does not cover scheduled functions (Denial of service) | Credit spent with no progress, against the limited retries of R23 | Accepted, bounded by three controls: DuckDB's memory limit below the container's, so memory errors are raised rather than killed, though it does not cover all of the process's memory; the heartbeat alert of [D5](#d5-pipeline-logs), after which the owner stops the app; and the usage limit of R28 | None |

`TODO(T040)`: set DuckDB's memory limit, decide on a hard container limit (`memory=(request, limit)`; without one, usage above the request is billed, as Modal charges the higher of the two), cap what one run processes and leave the rest to the next, do not retry memory errors since they are permanent, and check in the first slice how Modal treats a memory kill of a scheduled function ([d002 › R23](../designs/d002-requirements.md#requirements)).

Requirements transferred to [d002 › Requirements](../designs/d002-requirements.md#requirements):

| R | Threat | Evidence |
|---|---|---|
| R24 | TH1 | [Modal workspaces](https://modal.com/docs/guide/workspaces): GitHub login; two-factor authentication on Modal itself is not documented |
| R25 | TH2 | [Modal Secrets](https://modal.com/docs/guide/secrets), [data residency](https://modal.com/docs/guide/data-residency) |
| R26 | TH3 | [Modal service users](https://modal.com/docs/guide/service-users) |
| R27 | TH4 | [Modal web endpoints](https://modal.com/docs/guide/webhooks): serving over HTTP uses web decorators |
| R28 | TH5 | [Modal budgets](https://modal.com/docs/guide/budgets); the owner found the usage and spend limits on the Starter plan's billing page on 2026-11-02 |

#### D4. Processing logic separated from the platform

A thin platform wrapper separates the logic from Modal. The `bikesharing` package holds the pipeline and exposes one entry point; a single module outside the package declares the image, secrets, schedule and resources with Modal's SDK, and calls that entry point. Moving to the fallback in [D1](#d1-execution-platform) replaces only that module.

No single name covers this design. It combines three established patterns:

- **Dependency Rule** (Clean Architecture): source dependencies point inward, so the platform module knows the package and never the reverse.
- **Humble Object** (xUnit Test Patterns): the part that is hard to test, here the platform declaration, holds no logic, so the logic can be tested without it.
- **Config and Backing Services** (Twelve-Factor App): configuration and credentials arrive as environment variables, and storage is an attached resource named by that configuration.

It is a subset of hexagonal architecture: the platform module is a driving adapter, and the package has no driven ports. Those rules define the design, and each has a check, so a deviation can be detected:

| # | Rule | Check |
|---|---|---|
| 1 | The package never imports `modal` | CI fails on the import |
| 2 | The platform module holds no SQL or data logic: only declarations and the call to the entry point | CI fails if the module imports `duckdb`; review for the rest |
| 3 | The package reads configuration and credentials only from environment variables | Review |
| 4 | The entry point runs without Modal, on a local path | A CI test runs the pipeline with Modal not installed |

`TODO(T040)`: add the checks of rules 1, 2 and 4 to CI, and place the platform module in the repository.

Rejected: **full hexagonal architecture** (ports and adapters on both sides), with an interface for storage and one adapter per technology.

- The processing logic is SQL ([ADR-0025](../decisions/0025-sql-models-directed-by-python.md)), so it would move into the adapter and leave the core almost empty.
- DuckDB already isolates storage: the same SQL reads from R2 or from a local path.
- The port would have one real implementation, and each new operation would touch the port, the real adapter and a fake one.
- A fake adapter does not run the SQL, where the main failures are expected, so the tests against DuckDB are still needed.

What would change it: a second real implementation behind the same interface, such as a second engine or a destination DuckDB cannot write to, or business rules in Python that grow beyond orchestration. Moving from the wrapper to ports then is a bounded refactor.

Recorded in [ADR-0029](../decisions/0029-pipeline-code-architecture.md), which explains the hexagonal alternative in full.

#### D5. Pipeline logs

The pipeline writes structured logs as an event stream (Twelve-Factor): JSON Lines on stdout, which Modal keeps for 1 day on Starter, in the US. Each run also uploads its events to R2 as one object, so the logs outlive Modal's retention and can be queried with SQL. An R2 lifecycle rule deletes these objects after 30 days.

- **Format:** every event carries `ts` (UTC), `level`, `run_id` and `event`. T040 sets the events and their own fields, and [T039](../tasks.md) applies this format to capture.
- **Place:** a prefix of the pipeline's own, with the UTC day in the key (`date=YYYY-MM-DD/<run_id>.jsonl`), so reading one day takes one read per run of that day. T040 sets the prefix. They stay apart from capture's `logs/`, which is permanent evidence under a bucket lock that would block the lifecycle rule, and which the pipeline must not be able to write to.
- **Cost:** with 10 KB per run, a deliberately high assumption, 30 days hold about 43 MB at 10 minutes and 86 MB at 5 minutes, under $0.002 per month. Writes are 0.4% and 0.9% of R2's free 1M Class A. With at most 8,640 objects and a read per run of the day queried, no compaction is needed.
- **Limit:** a run killed abruptly, by memory or by its time limit, uploads no object. Only Modal's 1-day copy remains.
- **Access:** SQL with DuckDB from the owner's machine, with a read-only token.

Rejected:

- **Modal's logs only:** nothing to build, but after a day there is no trace of why a run failed, nor any history of run duration, which T040 needs to check D1's reopening condition.
- **An external log service:** it adds an account, a secret and a component to maintain.

Alerts follow the heartbeat pattern (dead man's switch), with Healthchecks.io on its free plan: each run signals its start and its result, and the service emails the owner on a failure signal or when the expected signal does not arrive. This satisfies [d002 › R23](../designs/d002-requirements.md#requirements) and detects the missed runs of [D2](#d2-scheduler), whatever their cause. The monitor runs outside Modal, because a failed platform cannot report its own failure.

- **Detection time:** a failure signal alerts at once. A run that dies abruptly or never starts alerts after the period plus its grace time, about 20 minutes at a 10-minute cadence with 10 minutes of grace.
- **Signals:** they carry no body, so logs stay in R2. The signal URL is a secret, and the package signals only when that environment variable is set, as D4's rules 3 and 4 require.
- **Limit:** a run that ends well with no new data sends a success signal; [R7 and R8](../designs/d002-requirements.md#requirements) cover that case.
- **Not confirmed:** the service's minimum period. A secondary source states 60 seconds, enough for any cadence T040 can choose; it is checked when the monitor is created.

Rejected:

- **Modal's notifications alone:** only failed scheduled runs are documented, through Slack. Timeouts, memory kills and runs that never start are not documented as triggers. They can stay on as an extra, with nothing relying on them.
- **A Cloudflare Worker checking the age of the data:** it also covers every cause, but adds code to maintain and test.
- **Cronitor and Better Stack:** free plans of 5 and 10 monitors against Healthchecks.io's 20. Healthchecks.io is also open source and can be self-hosted, which leaves a way out.

### 1.3 Questions

Main question: can Modal's Starter plan give the pipeline the memory it needs?

- **Q1.** Does Modal's Starter plan accept a function that requests 4 GiB, and let it occupy that memory? Its [resources guide](https://modal.com/docs/guide/resources) enforces a maximum when the function is created, rejecting larger requests with `InvalidError`, without stating the figure or whether it depends on the plan. Unblocks D1. Gate: if not, Oracle Cloud Always Free replaces Modal.

### 1.4 Exit criteria

- **Standard:** weighted decision matrix, with a Gate on the winner only.
- **Timebox:** one owner session of up to one hour, ended by Q1's result.
- A function that requests 4 GiB is accepted and occupies at least 3 GB without failing — hard cut.

### 1.5 Out of scope

- The pipeline's mode and refresh cadence, and how the ≤ 5-minute freshness of R3 is reconciled with them ([s010 › P5](s010-storage-table-format.md#production-inputs)) — T040
- Which events the pipeline logs — T040
- Preventing two runs from overlapping: `max_containers` exists, and what happens to a scheduled tick while a run is active is not documented — T040
- The region containers run in: by default on global capacity, with `eu` at 1.15x, which lowers the 540 hours of [D1](#d1-execution-platform) to about 470; it affects run time against R2 and does not move logs ([Modal card](../sources/modal.md)) — T040
- Interruption: base prices are not the non-preemptible rate, which costs 3x, so a run may be interrupted and must be safe to run again — T040
- Modal's limits: usage $30 and spend $1, set by the owner on 2026-11-02. If the usage limit counts usage before credits, as documented, runs stop when the credit ends and nothing is charged; not tried. They may be raised, up to R28's limit — T040
- The size of catch-up batches, and where the one-off history load runs — T040
- The pipeline's end-to-end and post-deploy smoke tests, on paper in [testing-strategy](../testing-strategy.md) — T040
- Aligning capture's logs with the convention this spike sets for the pipeline: format and field names only; log objects from before the production start are deleted before the bucket lock is enabled ([ADR-0023](../decisions/0023-storage-security-baseline.md)), so only the new format remains — T039
- The fragmentation of capture's logs, one object per pass, and whether a compacted daily copy is worth it; the bucket lock keeps the originals — T039
- Whether capture's alert ([d002 › R8](../designs/d002-requirements.md#requirements)) uses the same heartbeat service as [D5](#d5-pipeline-logs) — T039
- How the pipeline's health is viewed beyond ad hoc SQL: a separate operations panel, for which Modal's OpenTelemetry integration and SDK metrics are to be evaluated (their plans and cost not checked), or a public status page with aggregated metrics; an admin role would add authentication where [d002 › R1](../designs/d002-requirements.md#requirements) asks for none — T038

### 1.6 Open questions

None.

## 2. Method — how we find out

### 2.1 Approach

| Variant | What it is | What it tells |
|---|---|---|
| Memory probe | One Modal function with `memory=4096` that allocates and writes 3.5 GiB, holds it for 60 seconds and prints its peak memory | Whether Starter accepts the request and lets the function occupy at least 3 GB (Q1) |

- **What runs where:** the owner launches it from the local machine with `modal run`, which creates a temporary app: nothing is deployed and nothing is scheduled. It uses the default region and a plain image, with no DuckDB, R2 access or secrets, since Q1 asks about the platform and not the pipeline.
- **Why 3.5 GiB:** it clears the 3 GB cut with margin and stays under the 4 GiB requested. The function writes to every page, so the memory is really occupied and not only reserved.
- **Evidence:** the peak from the kernel (`ru_maxrss` from `getrusage`), checked against the known allocation and, as an independent count, against the memory graph on Modal's dashboard. The `Vm*` lines of `/proc/self/status` are printed as they are, as support. **#1**
- **Reading the result:** `InvalidError` for the memory request on creation, a memory kill during the run, or a peak under 3 GB fails the Gate. A finished run with a peak of at least 3 GB passes it. Any other error, or a `peak_gb` of `null`, says nothing about Q1 and does not decide the Gate: the cause is fixed and the probe runs again.
- **Cost and tear-down:** about 2 minutes at about $0.0555 per hour, under $0.01 of the credit. The app stops when the run ends.

### 2.3 Decision log

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| 1 | [D1](#d1-execution-platform), [2.1 Approach](#21-approach), [Step 1](#step-1--write-the-memory-probe) | The peak is read from `ru_maxrss` (POSIX `getrusage`), not `VmHWM` | The first run failed with `AttributeError`: `/proc/self/status` in Modal's container has no `VmHWM` line | Step 2 |

### 2.4 File layout

```text
spikes/execution-target/
├── README.md        Question, setup and commands, what each script does, link to the report; How we got here (written at Conclusion)
├── memory_probe.py  The Modal function of the memory probe
├── .python-version  Pinned Python (ADR-0016)
├── pyproject.toml   The Modal SDK, pinned (ADR-0017)
└── uv.lock          Locked dependencies
```

## 3. Steps

### 3.1 Prerequisites

Nothing to install beyond `uv`, which brings Python and the Modal SDK into the spike's own environment.

- `uv` 0.13.5, installed with Homebrew: `uv --version`.
- A Modal account on the Starter plan, with its usage limit of $30 and spend limit of $1: see the billing page.
- Two-factor authentication on the GitHub account used to log in to Modal (R24): see GitHub's password and authentication settings.

### Step 1 — Write the memory probe

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `chore: add Modal memory probe for s012`
- **Model:** sonnet · medium

#### Scope

The probe of [2.1 Approach](#21-approach), in `spikes/execution-target/`: `memory_probe.py`, `.python-version`, `pyproject.toml`, `uv.lock` and `README.md`. Nothing outside that folder changes.

#### Reads

- [2.1 Approach](#21-approach) of this document: what the probe does and how its result is read.
- `spikes/storage-table-format/pyproject.toml`: the form of an earlier spike's pins.

#### Do

1. Write `.python-version` with `3.13.17`.
2. Write `pyproject.toml` with `requires-python = ">=3.13,<3.14"` and the single dependency `modal==1.6.3`.
3. Run `uv lock` to create `uv.lock`.
4. Write `memory_probe.py`, with:
   - a `modal.App` named `memory-probe`;
   - an image `modal.Image.debian_slim(python_version="3.13")`, with no extra packages;
   - one function `probe`, declared with `memory=4096` and `timeout=300`, with no retries, secrets, schedule or `region`;
   - in its body: allocate a `bytearray` of 3.5 GiB (3,758,096,384 bytes), write to every 4,096th byte so each page is occupied, wait 60 s, print the `Vm*` lines of `/proc/self/status` as they are, read `ru_maxrss` from `getrusage`, and print one JSON line with `allocated_bytes`, `peak_gb` (decimal: `ru_maxrss` is in KiB on Linux, so its value × 1,024 / 10^9; `null` if it is 0, which means not tracked) and `duration_s`. **#1**
5. Write `README.md`: the question, setup and commands, what the script does and a link to this report. How we got here is written at the Conclusion.

#### Check

`uv run python -m py_compile memory_probe.py` from `spikes/execution-target/` ends without error. The probe is not run: that is Step 2.

### Step 2 — Run the memory probe

- **Status:** ✅ done
- **Who:** Owner
- **Commit:** `docs: add memory probe result to s012`
- **Model:** —
- **Gate:** the function is accepted, finishes, and its peak is at least 3 GB → on `InvalidError` for the memory request, a memory kill or a peak under 3 GB, Oracle Cloud Always Free replaces Modal and D2–D5 are reviewed as a Follow-up of the Conclusion. Any other error does not decide the Gate ([2.1 Approach](#21-approach)).

#### Scope

The result of [Q1](#13-questions), written as F1 in [Findings](#4-findings). No other file changes.

#### Reads

None.

#### Do

1. Install the environment, from the repository root:

   ```bash
   cd spikes/execution-target
   uv sync
   ```

2. Create the Modal token. A browser opens to log in, and the token is stored in `~/.modal.toml`, outside the repository:

   ```bash
   uv run modal setup
   ```

3. Run the probe:

   ```bash
   uv run modal run memory_probe.py::probe
   ```

4. While it holds the memory, or right after it ends, open the run on Modal's dashboard and note the peak in its memory graph.
5. Once the run has decided the Gate, revoke the token in Modal's API token settings. T040 creates its own. After any other error, keep the token for the repeat run.
6. Report: the full output of step 3, including any error; the peak on the dashboard; and the credit spent, if the billing page shows it.

#### Check

- The output holds the JSON line with a numeric `peak_gb`, or an error that fails the Gate. Any other error, or a `peak_gb` of `null`, fails this Check, and the step runs again once the cause is fixed.
- In a finished run with a peak of at least 3 GB, `peak_gb` is between 3.76 (the allocation) and 4.3 (the 4 GiB requested), and the dashboard's peak is within 10% of `peak_gb`. If either fails, Q1 stays unanswered until the gap is explained.

### Step 3 — Conclusion

- **Status:** ✅ done
- **Who:** Owner + Claude
- **Commit:** `docs: conclude spike s012`
- **Model:** sonnet · medium

#### Scope

In this document: Production inputs with their destinations, Conclusion and Status. `docs/sources/modal.md`: the result of Q1, replacing its `TODO(T037)`. `spikes/execution-target/README.md`: How we got here. There is nothing to tear down: the app ends with the run and Step 2 revokes the token.

#### Reads

1. [1. Questions](#1-questions--what-we-need-to-know), including D1–D5 in Decided at framing.
2. [2.3 Decision log](#23-decision-log).
3. [4. Findings](#4-findings).

#### Do

1. Write Production inputs with a destination for each.
2. Write the Conclusion: answers, exit criteria, verdict, and D1–D5 in Decisions to record, with D4's ADR as `TODO(T037)` describes it.
3. If the Gate failed, record in Follow-ups that Oracle Cloud Always Free replaces Modal and that D2–D5 are reviewed.
4. Update `docs/sources/modal.md` and the README.
5. Run `grep -rn "TODO(T037)" docs` and, for each result other than this step's own text, state in Follow-ups how it is resolved.

#### Check

Q1 is answered, the exit criterion has a result, every P has a destination, and every `TODO(T037)` has a resolution.

## 4. Findings

### F1. Modal's Starter plan accepts a 4 GiB function and lets it occupy 3.822 GB

Step 2, 2026-11-02, output of `memory_probe.py`.

- The function with `memory=4096` was created without `InvalidError`, allocated 3,758,096,384 bytes, held them for 60 s and finished, with no memory kill: `duration_s` 60.6.
- `peak_gb` is 3.822, from `ru_maxrss`: above the 3 GB cut and inside the expected range of 3.76 to 4.3.
- `VmRSS` at the end of the hold is 3,732,536 KiB, which is also 3.822 GB.
- Consequence: Q1's Gate passes.

### F2. `/proc/self/status` in Modal's container has no `VmHWM` line

Step 2, 2026-11-02, output of `memory_probe.py` in two runs.

- The first run failed with `AttributeError` when looking for `VmHWM`, after the allocation and the hold. It says nothing about Q1.
- The `Vm*` lines the second run printed are only `VmSize`, `VmRSS` and `VmData`. `ru_maxrss` returned a value.
- Consequence: the peak is read from `ru_maxrss` (#1), here and in the pipeline (P1).

### F3. Modal's dashboard shows 3.54 GiB used, in line with `peak_gb`

Step 2, 2026-11-02, memory graph of the run on Modal's dashboard.

- The graph shows 4 GiB requested and 3.54 GiB used, flat through the hold.
- 3.54 GiB is 3.80 GB, about 0.5% below the `peak_gb` of F1 and inside the 10% tolerance.
- Consequence: an independent count confirms F1, and `ru_maxrss` is a valid source for P1.

### 4.1 Production inputs

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | `peak_memory_mb` in the run's final log event (D1) cannot be read from `VmHWM` in Modal's container: use the source that the memory probe validates | Step 2, #1 | T040's design: `peak_memory_mb` from `ru_maxrss` (F2, F3) |

## 5. Conclusion

Observed window: two runs of the memory probe on 2026-11-02, launched with `modal run` in the default region. The first ended on the `VmHWM` error of F2 and says nothing about Q1; the second gives the result.

### 5.1 Answers

- **Q1.** Yes. Starter accepts a function that requests 4 GiB, and the function occupied 3.822 GB for 60 s and finished (F1), which Modal's dashboard shows as 3.54 GiB (F3). The probe stopped at its planned 3.5 GiB allocation, so the last part of the 4 GiB was not occupied; it clears the 3 GB that [N2](#d1-execution-platform) needs.

### 5.2 Exit criteria

| Criterion | Kind | Result | Findings |
|---|---|---|---|
| A function that requests 4 GiB is accepted and occupies at least 3 GB without failing | Hard cut | Pass: accepted, 3.822 GB, finished | F1, F3 |

### 5.3 Verdict

Modal's Starter plan can give the pipeline the memory it is estimated to need, 3 GB at worst ([N2](#d1-execution-platform)). The Gate passed, so Modal stays as the execution platform and Oracle Cloud Always Free stays as the fallback.

### 5.4 Decisions to record

| D | Outcome | Why |
|---|---|---|
| D1 | Holds: Modal on the Starter plan, with Oracle Cloud Always Free as the fallback | It leads the matrix with 8.10, and the Gate on the winner passed (F1, F3) |
| D2 | Holds: Modal's `Cron` | It adds no component, and its fixed clock times do not move on redeploy |
| D3 | Holds: R24–R28, with the other threats documented without a requirement | STRIDE and least privilege: R24–R28 cover what needs a control, and the other threats are accepted with their reason |
| D4 | Holds: a thin platform wrapper, with its four rules | The logic is SQL and DuckDB already isolates storage, so ports would leave the core almost empty; a change of platform touches one module |
| D5 | Holds: JSON Lines on stdout, one object per run in R2 for 30 days, and heartbeat alerts with Healthchecks.io | Modal keeps logs for 1 day, and R2 keeps them for almost no cost; a heartbeat outside Modal detects runs that never start, which Modal does not document |

### 5.5 Not verified

- A deployed, scheduled function: the probe was a temporary app started by hand, so a limit that applies only to deployed apps would not show — the first deployment of T040 runs at the same memory request; the Gate's fallback applies if it is rejected.
- DuckDB's real memory use on Modal, and spilling to disk under [N2](#d1-execution-platform): the probe holds a plain allocation — a run could need more memory than the 3 GB estimated — the first slice of T040 measures it with `peak_memory_mb`.
- Occupying the full 4 GiB, and the plan's maximum memory: a request above 4 GiB could be rejected — T040 tries it again before raising the request.
- The reliability of `Cron` and what happens to a missed run: runs could be skipped with no notice from Modal — the heartbeat of [D5](#d5-pipeline-logs) detects them.
- How Modal retries a memory kill of a scheduled function (TH12): credit spent with no progress — the `TODO(T040)` in [D3](#d3-pipeline-security).
- Whether the usage limit stops runs before any charge: an unexpected charge — the $1 spend limit bounds it, and T040 checks it with Modal's limits in [1.5 Out of scope](#15-out-of-scope).
- Real run time, and the region: the credit may not cover it, and `eu` costs 1.15x — `duration_s` measures it, with D1's reopening condition.
- The minimum period of Healthchecks.io: it may not fit the chosen cadence — checked when the monitor is created.

### 5.6 Follow-ups

- ADRs to write, each in its own commit with its lines in `docs/architecture.md`: execution platform (D1), scheduler (D2), processing logic separated from the platform (D4, replacing ADR-0010, as its `TODO(T037)` describes), pipeline logs (D5) and pipeline alerts (D5). D3 takes no ADR: it is recorded as R24–R28 in [d002 › Requirements](../designs/d002-requirements.md#requirements), as s011 did with R19–R23.
- `TODO(T037)` resolutions:
  - [D4](#d4-processing-logic-separated-from-the-platform): resolved by D4's ADR.
  - `docs/architecture.md` › Architecture decisions: resolved by D4's ADR.
  - `docs/architecture.md` › Deployment view, processing: written in D1's ADR commit.
  - `docs/architecture.md` › Runtime view, main flows: written in the commit of the alerts ADR, once the schedule, logs and alerts are recorded.
  - `docs/sources/modal.md`: resolved in this step.
- No new tasks. Existing tasks pick up what this spike leaves them:
  - `TODO(T038)`: the item marked T038 in [1.5 Out of scope](#15-out-of-scope).
  - `TODO(T039)`: the items marked T039 in [1.5 Out of scope](#15-out-of-scope).
  - `TODO(T040)`: the items marked T040 in [1.5 Out of scope](#15-out-of-scope), and [4.1 Production inputs](#41-production-inputs).
- Tear-down: nothing is kept. The apps ended with their runs, and the owner revoked the token in Step 2.

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

Gathered by the `web-researcher` on 2026-11-02 for D5:

- Modal notifications and retries: <https://modal.com/docs/guide/slack-notifications>, <https://modal.com/changelog/per-app-and-per-environment-notification-preferences>, <https://modal.com/docs/guide/retries>
- Healthchecks.io plans, signals and self-hosting: <https://healthchecks.io/pricing/>, <https://healthchecks.io/docs/http_api/>, <https://healthchecks.io/docs/self_hosted/>
- Other heartbeat services: <https://cronitor.io/pricing>, <https://betterstack.com/pricing>, <https://betterstack.com/docs/uptime/cron-and-heartbeat-monitor/>
