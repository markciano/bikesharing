# Source card — Modal (serverless compute)

Facts about the platform that runs the pipeline ([s012 › D1](../spikes/s012-execution-target.md#d1-execution-platform)). Living document: update it when something new is confirmed.

## Source

| | |
|---|---|
| Provider | Modal Labs |
| Service | Modal Functions on the Starter plan |
| Pricing page | <https://modal.com/pricing> |
| Licence | Commercial service; Modal's terms of service |

## Access

| | |
|---|---|
| Endpoint | Python SDK (`modal`) and CLI |
| Format | Python functions in containers, declared with the SDK |
| Auth | Modal API token; GitHub login to the workspace |
| Update frequency | Pricing page updated by Modal |

## Facts

| Fact | Evidence | Confirmed |
|---|---|---|
| Starter costs "$0 + compute" per month, with $30 of monthly credit | [Pricing](https://modal.com/pricing) | 2026-11-02 |
| Starter includes 3 seats, 100 containers of concurrency, 200 deployed apps, 5 deployed cron jobs, 1 TiB of monthly egress, region selection, and support through the community Slack only | [Pricing](https://modal.com/pricing) | 2026-11-02 |
| Starter excludes custom domains, static IP proxy, deployment rollbacks, environment-level budgets, RBAC and SSO | [Pricing](https://modal.com/pricing) | 2026-11-02 |
| Logs are kept for 1 day on Starter and 30 days on Team | [Pricing](https://modal.com/pricing) | 2026-11-02 |
| Function prices: $0.0000131 per core per second and $0.00000222 per GiB per second. One core is a physical core, equivalent to 2 vCPU; the minimum per container is 0.125 cores and 128 MiB | [Pricing](https://modal.com/pricing) | 2026-11-02 |
| Non-preemptible execution costs 3x base prices on all plans, and Sandboxes are billed at those rates | [Pricing](https://modal.com/pricing) | 2026-11-02 |
| At 1 vCPU and 4 GiB, a Function costs about $0.0555 per hour, so the $30 credit pays for about 540 hours a month | Calculated from the prices above | 2026-11-02 |
| CPU and memory are billed at the higher of the request and actual usage | [Resources](https://modal.com/docs/guide/resources) | 2026-11-02 |
| A maximum for CPU and memory is enforced when a Function is created, and larger requests are rejected with `InvalidError`. Neither the figure nor any dependence on the plan is documented | [Resources](https://modal.com/docs/guide/resources) | 2026-11-02 |
| `memory=(request, limit)` sets an optional hard limit, in MiB; a container that attempts to exceed it is killed | [Resources](https://modal.com/docs/guide/resources) | 2026-11-02 |
| Ephemeral disk defaults to 512 GiB per container, up to 3 TiB on request. Disk requests are billed by raising the memory request at a 20:1 ratio | [Resources](https://modal.com/docs/guide/resources) | 2026-11-02 |
| Containers run on global capacity by default, and inputs are routed through `us-east` | [Region selection](https://modal.com/docs/guide/region-selection) | 2026-11-02 |
| `region=` on the function decorator selects a region. Broad regions such as `eu` cost 1.15x and narrow ones such as `eu-west` cost 1.75x | [Region selection](https://modal.com/docs/guide/region-selection) | 2026-11-02 |
| Region selection does not move logs: stdout and stderr are stored in Modal's US data stores, and no way to keep them elsewhere is documented | [Data residency](https://modal.com/docs/guide/data-residency) | 2026-11-02 |
| Images and Secrets are stored in object storage in the US | [Data residency](https://modal.com/docs/guide/data-residency) | 2026-11-02 |
| Failed scheduled runs are notified through Slack, with no plan requirement stated. Email is offered for personal notifications, without stating which events it covers. Timeouts, memory kills and runs that never start are not documented as triggers | [Slack notifications](https://modal.com/docs/guide/slack-notifications), [changelog](https://modal.com/changelog/per-app-and-per-environment-notification-preferences) | 2026-11-02 |
| A memory kill counts as a container crash, and a deployed app retries it indefinitely with crash-loop backoff; scheduled functions are not covered | [Retries](https://modal.com/docs/guide/retries) | 2026-11-02 |

TODO(T037): add the result of [s012 › Q1](../spikes/s012-execution-target.md#13-questions), whether Starter accepts and lets a function occupy 4 GiB.
