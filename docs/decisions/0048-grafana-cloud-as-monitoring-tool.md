---
status: Accepted
date: 2026-11-18
---

# Grafana Cloud as the monitoring tool

## Context and problem statement

Capture and the pipeline write their logs to object storage, queried with SQL from the owner's machine ([ADR-0036](0036-log-convention-across-components.md)). Reading them means writing a query each time, and nothing tells the owner when something goes wrong unless they look.

- The owner must learn of a failed runtime rule of either severity and of a quality indicator off its target without looking for it ([d007 › D4](../designs/d007-pipeline-design.md#d4-data-quality-in-four-classes)).
- The age of the files the page serves has to be measured from outside the pipeline, since the pipeline cannot measure it while it is not running (d007 › D4, DQM10).
- The running cost limit is small and has no share for monitoring ([d002 › R4](../designs/d002-requirements.md#requirements), [ADR-0026](0026-budget-shares-per-component.md)), so the tool has to fit a free tier.
- One person operates the solution, often from a phone, with little time to maintain more components.
- The log volume is small: a few hundred megabytes a month at most.

## Considered Options

Each option is a managed service on its free tier, compared by weighted decision matrix after hard cuts on ingest over HTTP, a query across components, dashboards with drill-down, alerts, cost and two-factor authentication. The criteria were dashboards, alerts, metrics and service level objectives, synthetic checks, heartbeats, configuration as code, phone use, retention and OTLP ingest ([s018 › D2](../spikes/s018-monitoring-tool.md#d2-monitoring-tool)).

### 1. Grafana Cloud

Loki for logs, with Grafana dashboards, alerting, synthetic monitoring and a mobile app, on its Free tier.

- Pros:
  - dashboards with drill-down from a chart to its logs, and deploy markers;
  - alerts to the mobile app, with grouping, silences and resolved notices;
  - synthetic checks often enough to measure the age of the published files;
  - dashboards, alert rules and checks managed as code with an official Terraform provider;
  - a free volume far above the project's.
- Cons:
  - a 14-day free retention;
  - some features are not stated for the Free tier by its documentation, such as service level objectives and template variables.

### 2. New Relic

A full observability platform on its free edition, with a log API, dashboards, alerts and a mobile app.

- Pros:
  - the largest free volume, with alerts to email, chat and the mobile app;
  - configuration as code with an official Terraform provider.
- Cons:
  - its free synthetic checks run far less often than the age of the published files needs;
  - no heartbeat monitor, only an alert on missing signals.

### 3. Better Stack

Logs with uptime and heartbeat monitors on its free plan.

- Pros:
  - native heartbeats with a grace period.
- Cons:
  - a 3-day free retention;
  - its mobile app shows incidents, not dashboards.

### 4. Axiom

Log ingest and query with dashboards and monitors on its free plan.

- Pros:
  - the longest free retention.
- Cons:
  - no synthetic checks and no service level objectives;
  - no two-factor authentication of its own on the free plan, only through sign-in with an identity provider.

## Decision Outcome

**Chosen option:** 1. Grafana Cloud, on its Free tier.

It answers each force of the Context: dashboards replace writing a query each time, alerts reach the owner's phone without looking, a synthetic check measures the published files from outside, and the Free tier covers the volume many times over at no cost. It scored highest in the matrix, and no single unconfirmed fact changes the result. Alerts reach the owner as push notifications in the Grafana mobile app.

Why not the others:

- New Relic: its free synthetic checks cannot measure the age of the published files at the rate it needs.
- Better Stack: three days of retention and no dashboards on the phone.
- Axiom: it cannot measure the published files from outside.

**Scope:** The tool that shows the logs as dashboards and alerts the owner, and the channel of its alerts. It does not cover where logs are stored or how events reach the tool ([s018 › D1](../spikes/s018-monitoring-tool.md#d1-r2-as-the-record-the-tool-with-a-copy), D3, D4); the heartbeat, which stays apart ([ADR-0031](0031-heartbeat-alerts-for-the-pipeline.md)); or which events and indicators alert and how they are routed, set in T060.2.

### Consequences

#### Positive

- **Health at a glance:** the owner sees each component's runs, warnings and errors without writing a query, including from a phone.
- **Failures come to the owner:** alerts arrive as push notifications, and say when the problem is resolved.
- **Configuration under review:** dashboards, alert rules and checks can live in the repository as code.

#### Negative

- **One more account and provider:** logs leave for one more provider, and the account needs its own protection; the threats and controls are in [s018 › D8](../spikes/s018-monitoring-tool.md#d8-monitoring-tool-security-threats).
- **Short retention:** the tool keeps events for 14 days; older questions are answered from object storage with SQL.
- **Free tier facts not all confirmed:** some features the choice relies on are not stated for the Free tier; if two or more of them fail when the account is set up, the decision reopens with New Relic as the fallback.
- **Free tiers change:** a provider can change its free tier without notice; the record in object storage and a standard protocol keep a change of tool small ([s018 › D4](../spikes/s018-monitoring-tool.md#d4-otlp-over-http-with-json-encoding)).

## More information

- Decided at framing in [s018 › D2](../spikes/s018-monitoring-tool.md#d2-monitoring-tool) and [D5](../spikes/s018-monitoring-tool.md#d5-notifications-in-the-grafana-app), with the matrix, the scores and their sources.
- Free tier on 2026-11-17: 50 GB of logs a month with 14 days of retention, 3 users, 100k synthetic API test executions a month, and 3 IRM users for mobile push. The facts to check at account set-up are s018 › P1.
