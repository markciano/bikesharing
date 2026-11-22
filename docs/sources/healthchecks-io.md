# Source card — Healthchecks.io (heartbeat monitor)

Facts about the external monitor that receives the heartbeats of capture and the pipeline, and the watchdog of Grafana's alerting ([ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md), [d009 › D13](../designs/d009-monitoring.md#d13-a-watchdog-outside-grafana-watches-its-alerting)). Living document: update it when something new is confirmed.

## Source

| | |
|---|---|
| Provider | Healthchecks.io |
| Service | Healthchecks.io on its free plan |
| Pricing page | <https://healthchecks.io/pricing/> |
| Licence | Commercial service; the software is open source and can be self-hosted |

## Access

| | |
|---|---|
| Endpoint | One signal URL per check, called over HTTP ([HTTP API](https://healthchecks.io/docs/http_api/)) |
| Format | Plain HTTP requests; the project's signals carry no body |
| Auth | The signal URL itself, kept as a secret; the console behind the owner's sign-in |
| Update frequency | Pricing page and documentation updated by Healthchecks.io |

## Facts

Facts about Healthchecks.io that the project relies on, one section per topic.

### Free plan

| Fact | Evidence | Confirmed |
|---|---|---|
| The free plan includes 20 checks | [Pricing](https://healthchecks.io/pricing/), [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md) | 2026-11-02 |
| Alerts are sent by email | [Pricing](https://healthchecks.io/pricing/), [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md) | 2026-11-02 |
| The software is open source and can be self-hosted, a way out if the service changes | [Self-hosted](https://healthchecks.io/docs/self_hosted/) | 2026-11-02 |

### Checks and signals

| Fact | Evidence | Confirmed |
|---|---|---|
| A check accepts start, success and failure signals, each at its own URL | [HTTP API](https://healthchecks.io/docs/http_api/), [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md) | 2026-11-02 |
| A check alerts on a failure signal at once, and when no signal arrives within its period plus its grace time | [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md) | 2026-11-02 |

## Open questions

- What is a check's minimum period? A secondary source states 60 s ([ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md)); checked when a check is created.
- Does a signal URL accept a POST with a body, as Grafana's webhook contact point sends for the watchdog ([d009 › Watchdog](../designs/d009-monitoring.md#watchdog))?
