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
| Auth | HTTP Basic on the OTLP endpoint, with the stack's OpenTelemetry instance ID `1928689` as user and an access policy token with the `logs:write` scope as password, one token per emitter; stack service account token for Terraform; Synthetic Monitoring access token |
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
| Dashboard template variables and data links are core Grafana features, not limited by plan | [Pricing](https://grafana.com/pricing/) | 2026-11-22 |
| The SLO app is offered on the Free tier, billed through the active series its SLOs generate | [Grafana SLO](https://grafana.com/products/cloud/slo/) | 2026-11-22 |
| Grafana-managed recording rules can query the stack's Loki and write their result to its Prometheus | Grafana Cloud console, new recording rule | 2026-11-22 |
| A scripted k6 check can request a URL and assert on its response, such as a `Last-Modified` header against the current time, with `check()`; it counts against the 100k API executions a month | [k6 scripted checks](https://grafana.com/docs/grafana-cloud/testing/synthetic-monitoring/create-checks/checks/k6/) | 2026-11-22 |
| An IRM integration of type Webhook can have a heartbeat: a missed interval opens an alert group | [Configure integrations](https://grafana.com/docs/grafana-cloud/alerting-and-irm/irm/integrations/configure-integrations/) | 2026-11-22 |
| The usage data source `grafanacloud-usage` holds the Free tier's use and limits: logs in `grafanacloud_org_logs_usage` and `grafanacloud_org_logs_included_usage`, synthetic check executions in `grafanacloud_org_sm_billable_check_executions` and `grafanacloud_org_sm_included_check_executions` | Grafana Cloud console, Explore on `grafanacloud-usage` | 2026-11-22 |

### Logs

| Fact | Evidence | Confirmed |
|---|---|---|
| Over OTLP, a log record's attributes, such as `event`, `system`, `feed` and `rule`, are stored as structured metadata, not as labels; only a fixed list of resource attributes, `service.name` among them, become labels, with dots as underscores; structured metadata is filtered after the stream selector (`{service_name="…"} \| event="…"`) | [Loki › OpenTelemetry](https://grafana.com/docs/loki/latest/send-data/otel/); a test record sent to the stack matched `{service_name="…"} \| event="…"` and not `{service_name="…", event="…"}` | 2026-11-22 |

### Security

| Fact | Evidence | Confirmed |
|---|---|---|
| An access policy can hold the `logs:write` scope alone, realm limited to one stack, with several tokens that are revoked one by one | Grafana Cloud console, Access Policies | 2026-11-22 |

### Alerting

| Fact | Evidence | Confirmed |
|---|---|---|
| The root notification policy must name a contact point, the default for alerts no other policy matches | [`grafana_notification_policy`](https://registry.terraform.io/providers/grafana/grafana/latest/docs/resources/notification_policy) | 2026-11-22 |
| Message templates have the functions `tz`, which converts a time to a time zone, and `date`, which formats it with a Go layout, e.g. `{{ .StartsAt \| tz "Europe/Madrid" \| date "2006-01-02 15:04 MST" }}` | [Template reference](https://grafana.com/docs/grafana/latest/alerting/configure-notifications/template-notifications/reference/) | 2026-11-22 |
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

- Does an alert group routed to an escalation chain with no steps enter IRM's list of alert groups, in the browser and the app, with no notification?
