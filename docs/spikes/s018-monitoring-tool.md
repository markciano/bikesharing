<!--
Spike doc template. A spike is a time-boxed investigation of one task: it reaches the decisions a task needs, by analysis where possible and with evidence only where an unknown would change the choice. Its output is knowledge (decisions, answers, a verdict, inputs for designs and ADRs); its code is throwaway and lives in spikes/<name>/.
Blocks: Questions (what we need to know), Method (how we find out), Steps, Findings (filled during execution), Conclusion (filled after the last step).
Sections marked Optional are kept only when they apply.
-->

# Spike: Monitoring tool

- **Task:** T060.9
- **ADRs:** [ADR-0023](../decisions/0023-storage-security-baseline.md), [ADR-0026](../decisions/0026-budget-shares-per-component.md), [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md), [ADR-0036](../decisions/0036-log-convention-across-components.md), [ADR-0042](../decisions/0042-data-quality-classes-and-severity.md)
- **Code:** none; every decision was taken at framing, with no run

## Status

<!-- State: Draft 📝 · Ready 🎬 · Running 🔄 · Concluded ✅.
Phase: the blocks and the review completed.
Started / Finished: UTC dates of the first step executed and of the Conclusion.
Current step: the step being executed, or —. -->

- State: Draft 📝
- Phase: [x] Questions · Method, Steps and Steps review: not applicable · [ ] Conclusion
- Started: — · Finished: —
- Current step: —

## 1. Questions — what we need to know

### 1.1 Context

<!-- 2–4 sentences: the decisions this spike takes, which of them depend on evidence and why, and the spikes or designs it builds on. -->

Capture's logs live in R2 and the pipeline's will, queried with SQL from the owner's machine ([ADR-0036](../decisions/0036-log-convention-across-components.md)); nothing shows them as dashboards or alerts the owner, as [d007 › D4](../designs/d007-pipeline-design.md#d4-data-quality-in-four-classes) asks of T060.2 for failed runtime rules and indicators off target. This spike decides where the logs live, which tool shows and alerts on them, how events and quality indicators reach it, whether it takes over the heartbeat, and its security. Every decision was settled by documentation and analysis: the facts the documentation does not state for the chosen tool's free tier change no choice on their own, and T060.2 checks them when it sets up the account.

### 1.2 Decided at framing

#### D1. R2 as the record, the tool with a copy

Every component keeps its logs where [ADR-0036](../decisions/0036-log-convention-across-components.md) places them, in R2 with its retention, and the monitoring tool receives a copy of every event, following tiered storage: object storage is the cold archive and source of truth, the log tool the hot tier with a retention of its own. R2 keeps meeting what it already covers (N1–N3, N7), so the tool only has to add what is missing today (N4–N6), and it can be replaced without losing the record. How the copy reaches the tool is decided in D3.

- **What would reopen it:** a candidate in D2 within the free tier that reads R2 in place with dashboards and alerts, and wins the matrix.

Rejected:

- The tool reads R2 in place: a log tool indexes, alerts and drills down on what it ingests; querying files in R2 needs a query engine running somewhere, which adds maintenance and possibly cost (N5, N6).
- Pipeline and page log to the tool only, capture stays in R2: the pipeline would lose the SQL query across components (N2), and its run history would depend on the free tier's retention (N3).

| N | Need | Origin |
|---|---|---|
| N1 | Capture's logs stay permanent evidence in bronze, under the bucket lock | [ADR-0023](../decisions/0023-storage-security-baseline.md), ADR-0036 |
| N2 | One SQL query across the logs of all components; DQM11 reads capture's logs | ADR-0036, [d007 › D4](../designs/d007-pipeline-design.md#d4-data-quality-in-four-classes) |
| N3 | A failed pipeline run can be investigated days later, with the history of `duration_s` and `peak_memory_mb`: 30 days at least | [ADR-0030](../decisions/archive/0030-pipeline-logs.md), [ADR-0027](../decisions/0027-modal-as-execution-platform.md) |
| N4 | Dashboards with drill-down, and alerts close to the event | This spike's hard cuts |
| N5 | Within free tiers | [d002 › R4](../designs/d002-requirements.md#requirements), [ADR-0026](../decisions/0026-budget-shares-per-component.md) |
| N6 | Little to maintain for a single operator | ADR-0027, ADR-0030 |
| N7 | Logs hold no credentials | [d002 › R22](../designs/d002-requirements.md#requirements) |

#### D2. Monitoring tool

Grafana Cloud on its Free tier is the monitoring tool, chosen by weighted decision matrix with 4.55 out of 5 against 4.00 for New Relic. It leads on dashboards, synthetic checks (DQM10) and heartbeats, and covers the alerts, SLOs, configuration as code and the phone use the project asks for, within 50 GB of logs a month, 250 times the estimated volume.

- **What would change it:** four scores rest on facts the documentation does not state for the Free tier: template variables and data links (C1), the SLO app and Loki recording rules (C3), a scripted k6 check that asserts a file's age (C4), and the IRM heartbeat (C5). T060.2 checks them when it sets up the account. If two or more fail, the decision reopens with New Relic as the fallback. One failing alone does not reopen it: it costs at most 20 of the 55 points of the margin.
- **What would not:** the free retention of 14 days, since R2 holds the record (D1).

Rejected:

- New Relic: 500 synthetic checks a month on its free edition allow one every 90 min at most, against the 15 min DQM10 needs; heartbeats only emulated.
- Better Stack: 3-day free retention, and its app shows incidents but not dashboards.
- Axiom: no synthetic check or SLOs, and alerts limited to Slack, Discord and email.
- Datadog: its free plan includes no logs (K5).
- Honeycomb: two triggers and no SLOs on its free plan, and no stated support for logs.

Robust: no single unconfirmed fact changes the winner; all four failing together would tie it with New Relic at 4.00. No candidate reads R2 in place, so D1 stands. Facts gathered on 2026-11-17 from each vendor's pricing and documentation pages (Sources).

Volume, worst case: 10 KB per run, deliberately high as in [ADR-0030](../decisions/archive/0030-pipeline-logs.md); capture every 5 min for two sources and the pipeline every 15 min ([d007 › D3](../designs/d007-pipeline-design.md#d3-continuous-mode-with-a-15-minute-cadence)) make about 670 runs a day, 7 MB a day, 200 MB a month.

Hard cuts:

| K | Cut | Origin |
|---|---|---|
| K1 | Receives JSON events over HTTP from the Worker and from Modal | D1 |
| K2 | Queries the logs of all components together, filtered by the common fields | ADR-0036 |
| K3 | Dashboards with saved views and drill-down, e.g. the daily count of `warn` and `error` leading to their logs | Owner |
| K4 | Alerts on log queries (failed runtime rules of either severity) and on indicators off their target | d007 › D4 |
| K5 | Free at the estimated volume with a 10× margin | d002 › R4, ADR-0026 |
| K6 | Managed service (SaaS): self-hosting needs an always-on machine, with its cost and maintenance | D1 › N5, N6 |
| K7 | Account with two-factor authentication: the tool's own, with an authenticator app (TOTP), or sign-in with GitHub with its two-factor authentication on, following delegated authentication (OIDC) | [d007 › D8](../designs/d007-pipeline-design.md#d8-pipeline-security-threats) |

Criteria and anchors:

| C | Criterion | Weight | 1 | 3 | 5 | Origin |
|---|---|---|---|---|---|---|
| C1 | Dashboards | 20 | Saved searches and basic charts only | Panels with charts over log queries, and drill-down links | 3, plus template variables and event markers (deploys) on charts | Owner, [ADR-0044](../decisions/0044-deployments-tagged-with-their-commit.md) |
| C2 | Alerts | 20 | Email only, one notification per firing | Email plus one push or chat channel, and a resolved notification | 3, plus push in a mobile app, grouping and silences | d007 › D4 |
| C3 | Metrics and SLOs | 15 | Counts at query time only, no stored series | Stored metrics, derived from logs or sent, with threshold alerts | 3, plus native SLO objects (target, error budget, burn rate) | d007 › D4 |
| C4 | Synthetic check | 10 | None in the free tier | HTTP status code only | Asserts on body or header (e.g. a file's age) every 15 min or less, free | d007 › D4 (DQM10) |
| C5 | Heartbeat | 10 | None in the free tier | Emulated by an alert on missing events for N minutes | Native cron monitor: ping URL, schedule, grace period, alert on missed or failed | [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md) |
| C6 | Configuration as code | 10 | UI only | JSON export and import by API | Official Terraform provider or declarative files for dashboards and alerts | Spec-driven development (CLAUDE.md) |
| C7 | Phone use | 5 | Desktop web only | Responsive web, usable for dashboards | Official app with dashboards and alerts | [s013 › D5](s013-visualization-tool.md) |
| C8 | Free retention | 5 | Under 7 days | 7 to 14 days | 30 days or more | D1: R2 holds the record |
| C9 | OTLP ingest | 5 | Proprietary API only | OTLP through a collector or agent | Native OTLP/HTTP endpoint for logs; the Worker cannot run a collector | ADR-0036 |

Hard cuts: Grafana Cloud, New Relic, Better Stack and Axiom pass; Axiom through sign-in with GitHub, since it has no two-factor authentication of its own on its free plan. Datadog fails K5. Honeycomb is not scored.

Scores (U: not stated for the free tier by the documentation):

| C | Weight | Grafana Cloud | New Relic | Better Stack | Axiom |
|---|---|---|---|---|---|
| C1 | 20 | 5 (U): panels over Loki, annotations; template variables and data links | 4 (U): facet linking, variables; deploy markers | 3: SQL dashboards; drill-down U | 4: charts, annotations |
| C2 | 20 | 5: email, Telegram, Slack, webhook, resolved notices; app push through IRM, 3 users free | 5: email, Slack, webhook, app push, closed notices | 4: email and Slack free; app push | 3: Slack, Discord, email |
| C3 | 15 | 4 (U): SLO app with no stated limit; recording rules | 4 (U): events-to-metrics, service levels | 3: metrics from logs; no SLOs | 2: monitors on queries only |
| C4 | 10 | 4 (U): 100k executions a month; regex on headers; a scripted k6 check could compute an age | 2: 500 checks a month, one every 90 min at most | 3: keyword and status every 3 min | 1: none |
| C5 | 10 | 4 (U): IRM heartbeat with an interval, grace not documented | 3: emulated by loss of signal | 5: 10 native heartbeats with grace | 3: emulated |
| C6 | 10 | 5: Terraform for dashboards, rules, contact points, synthetic checks, SLOs | 5: Terraform covers all | 4: two providers; log alerts U | 5: Terraform |
| C7 | 5 | 5: app with dashboards and alerts | 5: app with dashboards and alerts | 3: app for incidents only | 2 (U): not documented |
| C8 | 5 | 3: 14 days | 3: 8 days (some pages state 30) | 1: 3 days | 5: 30 days |
| C9 | 5 | 5: native OTLP/HTTP, plus JSON push to Loki | 4: native OTLP, protobuf | 4: OTLP; JSON U | 4: OTLP; JSON U |
| **Total** | | **4.55** | **4.00** | **3.45** | **3.15** |

#### D3. Each emitter sends its own copy

Each component sends its run's events to Grafana Cloud's Loki itself, over HTTP, at the moment it writes them to R2, following agentless push: there is no collector between the emitter and the tool. The capture Worker makes one more `fetch` per run, well within the subrequests of the Workers free plan, and spends no CPU time while it waits; the pipeline does the same when it uploads its run's object. A failed send does not change the run's outcome, since R2 holds the record (D1). Capture's alerts then do not depend on the pipeline running. The cost is one more secret in the Worker, covered in D8.

Rejected: the pipeline forwards capture's log objects from bronze to Loki in each run. It leaves the Worker unchanged and with no new secret, but capture's events would arrive up to 15 min late, and a stopped pipeline would also hide capture, coupling two failure domains that are independent today.

#### D4. OTLP over HTTP with JSON encoding

Both emitters send their events with OTLP over HTTP, the OpenTelemetry protocol, in its JSON encoding. ADR-0036 already follows OpenTelemetry's names, and the fallback tool of D2 also takes OTLP, so a change of tool changes the endpoint and the key, not the senders. JSON is one of the two encodings the OTLP specification defines, and lets the Worker send with a plain `fetch` and no protobuf library. How the common fields map to OTLP attributes and Loki labels is set in T060.2.

- **What would change it:** Grafana documents JSON over OTLP for low-traffic testing; the estimated 200 MB a month is low traffic. If Grafana rejects or throttles it, the pipeline moves to protobuf with the official OpenTelemetry SDK, and the Worker to Loki's push API, which takes JSON.

Rejected: Loki's own push API as the protocol for both. It is the most direct, with no caveat on JSON, but it is specific to Loki: a change of tool would rewrite the sending code of both components, with no gain the project needs at its volume.

#### D5. Notifications in the Grafana app

Every alert reaches the owner as a push in the Grafana mobile app, through IRM, with 3 users free on the Free tier. Which events and indicators alert, and how they are routed by severity, are set by T060.2; the SRE split between alerts that interrupt (page) and alerts reviewed later (ticket) is its starting point, carried as a production input.

#### D6. Quality indicators reach the tool by push

Grafana Cloud does not read the gold tables, for the reason D1 rejects reading R2 in place, so the values of the indicators the pipeline builds reach it in the events the pipeline sends (D3, D4); their history stays in gold. DQM10, the age of the published files, is measured from outside by a synthetic check that reads each file the page serves, following black-box monitoring: it sees what a visitor sees, including a file that failed its audit and was not deployed, a failed redeploy, or a stopped pipeline, none of which the heartbeat reports. DQM11 is built in the tool from capture's events within its 14-day retention; a longer window is queried with SQL over R2 (ADR-0036).

Whether the pipeline sends the indicators' values as log events or as metrics is set by T060.2; log events, with one signal and one path, are its starting point, carried as a production input. Which indicators are charted and their thresholds are also set there.

#### D7. The heartbeat stays on Healthchecks.io

The heartbeat of [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md) stays on Healthchecks.io, apart from the monitoring tool, following separate failure domains for alerting: the heartbeat reports when everything else is silent, and on Grafana Cloud an outage of the tool or its account would silence logs, alerts and heartbeat at once. ADR-0031 is unchanged.

Rejected: Grafana IRM's heartbeat. It would save an account and a secret and put every notification in one app (D5), but it would make one provider a single point of failure for alerting, and its grace period and its place in the Free tier are not documented (D2, C5).

#### D8. Monitoring tool security threats

One STRIDE pass covers what this spike adds, as [d007 › D8](../designs/d007-pipeline-design.md#d8-pipeline-security-threats) sets for each child: a Grafana Cloud account, a write token in each emitter, and logs leaving for one more provider. Repudiation is covered by R2 as the record (D1) and the `version` of every event (ADR-0036). Three controls rest on facts not checked yet, which T060.2 checks when it creates the account: tokens scoped to writing logs only, a stack in an EU region, and a Free tier that needs no payment method.

| # | Threat (STRIDE) | Impact | Control | Requirement |
|---|---|---|---|---|
| `TH1` | Spoofing: someone signs in to the owner's Grafana Cloud account | Logs read, alerts deleted or silenced | Two-factor authentication with TOTP (K7); the owner is the only user | d007 › D8 |
| `TH2` | Tampering: the write token of the Worker or of the pipeline leaks | False events hide a failure or add noise | One token per emitter, scoped to writing logs, so one is revoked without the other; kept as a Worker secret and a Modal secret, never in code; R2's record is unchanged (D1) | d007 › D8 |
| `TH3` | Information disclosure: logs leave for one more provider | What they hold is exposed | Logs hold no credentials (d002 › R22) and no visitor data (no real user monitoring); a stack in an EU region; only the owner reads them, with no public dashboards or shared snapshots | d002 › R22 |
| `TH4` | Denial of wallet: a leaked token floods the ingest | Cost, or the quota used up | No payment method on the account, so the Free tier stops at its limit and bills nothing; the token is revoked | d002 › R4 |
| `TH5` | Denial of service: Grafana Cloud is down | No logs or alerts in the tool | Capture and the pipeline do not depend on the send (D3); the heartbeat is apart (D7); R2 holds every event (D1) | d002 › R23 |

### 1.3 Questions

Main question: which tool shows the logs of capture and the pipeline as dashboards and alerts the owner, within free tiers, and how do events and quality indicators reach it?

No Q: triage left no unknown that only a run could settle (Context).

### 1.4 Out of scope

<!-- Optional. What someone could expect this spike to answer and it will not, each item pointing to the task that covers it. -->

- Real user monitoring of the page: browser errors and load times sent to the tool; the page's health is measured from outside by a synthetic check (DQM10) — not planned
- The platforms' own logs: R2 access logs and the Cloudflare and Modal platform logs — not planned

## 2. Conclusion

### 2.1 Verdict

<!-- The answer to the main question in 2–3 sentences. -->

Grafana Cloud on its Free tier shows and alerts on the logs of capture and the pipeline, while R2 stays their record: each component sends a copy of its run's events over OTLP/HTTP with JSON, and alerts reach the owner in the Grafana app. Quality indicators arrive in the pipeline's events, DQM10 is measured by a synthetic check from outside, and the heartbeat stays on Healthchecks.io as an independent failure domain.

### 2.2 Not verified

<!-- What the evidence does not cover, each with its risk and mitigation. "None" is valid. -->

- The Free tier features behind four scores of Grafana Cloud (D2: C1, C3, C4, C5) — a dashboard, an SLO or the DQM10 check needs a workaround — T060.2 checks them at account set-up; two or more failing reopen D2 with New Relic as the fallback
- The three account facts behind D8's controls: logs-write scoped tokens, an EU region, no payment method — a control is weaker than stated — T060.2 checks them at account set-up and adjusts D8's controls in its design
- JSON over OTLP at the project's volume (D4) — Grafana rejects or throttles it — the fallback in D4
- Facts gathered from vendor pages on 2026-11-17 — free tiers change without notice — R2 holds the record (D1) and OTLP keeps a change of tool to an endpoint and a key (D4)

### 2.3 Production inputs

<!-- Optional. What a later task must take into account when it builds, from any part of the spike: done when that task runs. Each one has a Destination: a design (with its task) with its `TODO(TNNN)` marker (CLAUDE.md › Pending items), or discarded with a reason. -->

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | At account set-up, check on the Free tier: template variables and data links, the SLO app, Loki recording rules, a scripted k6 check asserting a file's age, the IRM heartbeat; two or more failing reopen D2 | D2 | `TODO(T060.2): check Grafana Cloud Free tier features` |
| P2 | At account set-up, check: tokens scoped to writing logs, a stack in an EU region, no payment method needed; then apply the controls of TH1–TH5 | D8 | `TODO(T060.2): check and apply the monitoring security controls` |
| P3 | Route alerts by urgency, starting from the SRE split between page and ticket | D5 | `TODO(T060.2): route alerts by urgency` |
| P4 | Send the indicators' values as log events, unless the design shows a reason for metrics | D6 | `TODO(T060.2): choose the indicators' signal` |
| P5 | Map the common fields of ADR-0036 to OTLP attributes and Loki labels; a failed send never changes a run's outcome | D3, D4 | `TODO(T060.2): map log fields to OTLP and Loki` |

### 2.4 Records

<!-- Documents this spike updates before it closes: ADRs from Decided at framing (each in its own commit), architecture, requirements, source cards and new tasks agreed with the owner. A decision that updates no document has no row. Commit: "Done", or "Pending" until delivered; the spike closes when every row is Done. Production inputs are not repeated here. -->

| Output | From | Destination | Commit |
|---|---|---|---|
| [ADR-0048](../decisions/0048-grafana-cloud-as-monitoring-tool.md): Grafana Cloud as the monitoring tool | D2, D5 | `docs/decisions/` | Done |
| [ADR-0049](../decisions/0049-log-events-copied-to-monitoring-over-otlp.md): log events copied to the monitoring tool by each emitter over OTLP, extending ADR-0036 | D1, D3, D4 | `docs/decisions/` | Done |
| Architecture: the monitoring tool, the copy of log events and the alert path | D1–D7 | `docs/architecture.md`, the sections that name observability | Pending |

## 3. Sources

<!-- Optional. Earlier spikes, benchmarks and documentation used. -->

- Grafana Cloud: <https://grafana.com/pricing/>, <https://grafana.com/docs/grafana-cloud/send-data/otlp/send-data-otlp/>, <https://grafana.com/docs/grafana-cloud/observe-and-act/send-data/otlp/otlp-format-considerations/>, <https://grafana.com/docs/grafana-cloud/alerting-and-irm/irm/>, <https://grafana.com/docs/grafana-cloud/testing/synthetic-monitoring/create-checks/checks/http/>, <https://grafana.com/docs/grafana-cloud/platform/mobile-app/get-started/>, <https://grafana.com/whats-new/2026-06-02-mfa-in-grafana-cloud/>
- New Relic: <https://newrelic.com/pricing>, <https://docs.newrelic.com/docs/synthetics/synthetic-monitoring/using-monitors/monitor-limits/>, <https://docs.newrelic.com/docs/opentelemetry/best-practices/opentelemetry-otlp/>
- Better Stack: <https://betterstack.com/pricing>, <https://betterstack.com/docs/uptime/cron-and-heartbeat-monitor/>
- Axiom: <https://axiom.co/pricing>, <https://axiom.co/docs/reference/settings>
- Datadog: <https://www.datadoghq.com/pricing/>
- Honeycomb: <https://www.honeycomb.io/pricing>
