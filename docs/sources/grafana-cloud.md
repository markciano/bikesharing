# Source card — Grafana Cloud (monitoring)

Facts about the service where the owner sees how capture, the pipeline and the page run, and receives their alerts ([s018 › D2](../spikes/s018-monitoring-tool.md#d2-monitoring-tool), [ADR-0048](../decisions/0048-grafana-cloud-as-monitoring-tool.md)). Living document: update it when something new is confirmed.

## Source

| | |
|---|---|
| Provider | Grafana Labs |
| Service | Grafana Cloud on the Free tier: Loki for logs, Grafana Alerting, Synthetic Monitoring and IRM |
| Pricing page | <https://grafana.com/pricing/> |
| Licence | Commercial service; Grafana Labs' terms of service |

## Access

| | |
|---|---|
| Endpoint | `https://otlp-gateway-prod-eu-west-4.grafana.net/otlp/v1/logs`, the stack's OTLP/HTTP logs endpoint, for the events of capture and the pipeline; Grafana's Terraform provider (`grafana/grafana`) for alerting, IRM and Synthetic Monitoring ([ADR-0051](../decisions/0051-monitoring-configuration-as-code.md)) |
| Synthetic Monitoring | `https://synthetic-monitoring-api-eu-west-2.grafana.net`, the backend address the stack's Synthetic Monitoring config shows, for the provider's `sm_url` |
| Data sources | UIDs in the stack `bikesharing`: Loki `grafanacloud-logs`, Prometheus `grafanacloud-prom` (Synthetic Monitoring's results), usage `grafanacloud-usage` |
| Format | OTLP log records, JSON encoding ([ADR-0049](../decisions/0049-log-events-copied-to-monitoring-over-otlp.md)) |
| Auth | Access policy token with the `logs:write` scope for the OTLP copy, one per emitter; stack service account token for Terraform; Synthetic Monitoring access token |
| Update frequency | Pricing page and documentation updated by Grafana Labs |

## Facts

Facts about the Grafana Cloud services the project uses, one section per service or topic.

### Free tier

| Fact | Evidence | Confirmed |
|---|---|---|
| The Free tier includes 50 GB of logs a month, kept for 14 days | [s018 › D2](../spikes/s018-monitoring-tool.md#d2-monitoring-tool) | 2026-11-17 |
| The Free tier includes 100k synthetic check executions a month | [s018 › D2](../spikes/s018-monitoring-tool.md#d2-monitoring-tool) | 2026-11-17 |
| IRM is included in the Free tier, for at most 3 active IRM users, with community support | [IRM](https://grafana.com/products/cloud/irm) | 2026-11-22 |
| The Free tier needs no payment method: the project's account runs on it with none | Grafana Cloud console, billing page | 2026-11-22 |
| The project's stack runs in an EU region, Germany (`prod-eu-west-4`) | Grafana Cloud console, stack details | 2026-11-22 |

### Security

| Fact | Evidence | Confirmed |
|---|---|---|
| An access policy can hold the `logs:write` scope alone, realm limited to one stack, with several tokens that are revoked one by one | Grafana Cloud console, Access Policies | 2026-11-22 |

### Alerting

| Fact | Evidence | Confirmed |
|---|---|---|
| The root notification policy must name a contact point, the default for alerts no other policy matches | [`grafana_notification_policy`](https://registry.terraform.io/providers/grafana/grafana/latest/docs/resources/notification_policy) | 2026-11-22 |
| Grafana Alerting reaches IRM through a contact point of type Grafana IRM, on an IRM integration of type Grafana Alerting, with the built-in Alertmanager only; the alert's labels reach IRM's routes as `commonLabels` of the payload | [Connect Grafana Alerting](https://grafana.com/docs/grafana-cloud/observe-and-act/respond-to-incidents/integrations/grafana-alerting/connect/) | 2026-11-22 |

### IRM

| Fact | Evidence | Confirmed |
|---|---|---|
| A "Repeat escalation" step repeats an IRM escalation chain at most 5 times; a longer repetition needs more repeat steps, each with its own counter, and no step repeats without limit | [Escalation chains](https://grafana.com/docs/grafana-cloud/alerting-and-irm/irm/configure/escalation-routing/escalation-chains/) | 2026-11-22 |
| An escalation step marked important notifies through the user's important notification rules, which are set apart from the default ones | [Personal notification rules](https://grafana.com/docs/grafana-cloud/alerting-and-irm/irm/notify-responders/personal-notification-rules/) | 2026-11-22 |
| In the mobile app, important notifications override Do Not Disturb once allowed: on iOS, "Override DND for important" with Critical Alerts allowed; on Android, the Important channel set to override Do Not Disturb | [Push notifications](https://grafana.com/docs/grafana-cloud/alerting-and-irm/irm/mobile-app/push-notifications/) | 2026-11-22 |
| The Terraform provider manages IRM's integrations, routes and escalation chains with the stack's service account token, which needs `plugins.app:access`; only personal notification rules need an IRM API token | [Provider](https://registry.terraform.io/providers/grafana/grafana/latest/docs) | 2026-11-22 |

## Open questions

Checked when the owner creates the account ([d009 › Prerequisites](../designs/d009-monitoring.md#31-prerequisites)); each answer becomes a fact above.

- Does the Free tier offer template variables and data links, the SLO app, Loki recording rules, a scripted k6 check asserting a file's age, the IRM heartbeat and the usage data source ([s018 › P1](../spikes/s018-monitoring-tool.md#23-production-inputs))?
- Which of the OTLP attributes `event`, `system`, `feed` and `rule` does Grafana Cloud promote to Loki labels?
- Do message templates have the `tz` and `date` functions?
- Does an alert group routed to an escalation chain with no steps enter IRM's list of alert groups, in the browser and the app, with no notification?
