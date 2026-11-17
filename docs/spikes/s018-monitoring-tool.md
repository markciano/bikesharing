<!--
Spike doc template. A spike is a time-boxed investigation of one task: it reaches the decisions a task needs, by analysis where possible and with evidence only where an unknown would change the choice. Its output is knowledge (decisions, answers, a verdict, inputs for designs and ADRs); its code is throwaway and lives in spikes/<name>/.
Blocks: Questions (what we need to know), Method (how we find out), Steps, Findings (filled during execution), Conclusion (filled after the last step).
Sections marked Optional are kept only when they apply.
-->

# Spike: Monitoring tool

- **Task:** T060.9
- **ADRs:** [ADR-0026](../decisions/0026-budget-shares-per-component.md), [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md), [ADR-0036](../decisions/0036-log-convention-across-components.md), [ADR-0042](../decisions/0042-data-quality-classes-and-severity.md)
- **Code:** `spikes/monitoring-tool/`

## Status

<!-- State: Draft 📝 · Ready 🎬 · Running 🔄 · Concluded ✅.
Phase: the blocks and the review completed.
Started / Finished: UTC dates of the first step executed and of the Conclusion.
Current step: the step being executed, or —. -->

- State: Draft 📝
- Phase: [ ] Questions · [ ] Method · [ ] Steps · [ ] Steps review · [ ] Conclusion
- Started: — · Finished: —
- Current step: —

## 1. Questions — what we need to know

### 1.1 Context

<!-- 2–4 sentences: the decisions this spike takes, which of them depend on evidence and why, and the spikes or designs it builds on. -->

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

Robust: no single unconfirmed fact changes the winner; all four failing together would tie it with New Relic at 4.00. No candidate reads R2 in place, so D1 stands. Facts gathered on 2026-11-17 from each vendor's pricing and documentation pages.

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

Each component sends its run's events to Grafana Cloud's Loki itself, over HTTP, at the moment it writes them to R2, following agentless push: there is no collector between the emitter and the tool. The capture Worker makes one more `fetch` per run, well within the subrequests of the Workers free plan, and spends no CPU time while it waits; the pipeline does the same when it uploads its run's object. A failed send does not change the run's outcome, since R2 holds the record (D1). Capture's alerts then do not depend on the pipeline running. The cost is one more secret in the Worker, covered in D7.

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

#### D`<N>`. `<Title of decision N>`

<!-- In this order, so the reader finds what matters first:
1. The decision and why, in one short paragraph. If it depends on a Q, name it and what happens if its Gate fails.
2. What would change it, and what would not, each with the action to take. Only when a later event could reopen it.
3. The options rejected and how robust the result is.
4. The evaluation behind it: the table or weighted matrix (needs, cuts, anchors and scores) if one was used. A security decision lists its threats in a table: `| # | Threat (STRIDE) | Impact | Control | Requirement |`, with IDs `TH1`, `TH2`… per document. -->

### 1.3 Questions

<!-- The main question, answered by the Verdict. Then Q1..Qn, each answerable with evidence.
"Observe only": things to note during the run with no dedicated effort. -->

Main question: `<one sentence>`

- **Q1.** `<question>`
- **Observe only:** `<item>`

### 1.4 Exit criteria

<!-- Fixed before the first run; a later change is recorded in the Decision log.
Derived from the standard that applies to this kind of question, named in the first line: e.g. DAMA data quality dimensions for a data source, a weighted decision matrix for a technology choice.
Each criterion is measurable and says whether it is a hard cut or a guide. The timebox says what ends the run. State whether one variant meeting the criteria is enough. -->

- **Standard:** `<standard or pattern applied>`
- **Timebox:** `<window, and what ends it>`
- `<criterion>` — `<threshold>` — hard cut | guide

### 1.5 Out of scope

<!-- Optional. What someone could expect this spike to answer and it will not, each item pointing to the task that covers it. -->

- Real user monitoring of the page: browser errors and load times sent to the tool; the page's health is measured from outside by a synthetic check (DQM10) — not planned
- The platforms' own logs: R2 access logs and the Cloudflare and Modal platform logs — not planned

## 2. Method — how we find out

### 2.1 Approach

<!-- The variants, options or probes compared, and what each one tells that the others do not. -->

| Variant | What it is | What it tells |
|---|---|---|
| | | |

#### 2.1.1 Shared behaviour

<!-- Optional. Rules every variant follows (schedules, formats, key layouts, logs), stated once so the steps can cite them. -->

-

#### `<A>`. `<Title of variant, option or probe A>`

<!-- Detailed description -->

### 2.3 Decision log

<!-- It logs decisions about the method, before and during the run, including changes of course. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Column Applies to: anchor link(s) to the section where the decision is applied, named in one or two words (e.g. Q1, Probe A, File layout).
- Column Decided at: the Status phase where it was decided (Method, Steps), `<phase> review` when decided while reviewing that phase, or `Running step N` when decided during the run.
-->

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| `<N>` |  |  |  |  |

### 2.4 File layout

<!-- Every file and folder the spike creates, as a tree with its purpose in one line. Captured data and outputs are marked as ignored by Git. The README is always included. -->

```text
spikes/monitoring-tool/
├── README.md        Question, setup and commands, what each script does, link to the report
└── <file>           <purpose>
```

## 3. Steps
<!-- Each step is one reviewable result, touching at most 2–3 files.
- Status: where the step is: 💤 todo · 🎬 ready · 🔄 in progress · ⛔ blocked · ✅ done
- Who: Owner (manual actions: dashboards, accounts, deploys, runs, checks) or Claude (code and documents).
- Commit: only in a step that changes committed files: the proposed message, following the Git conventions in CLAUDE.md.
- Model: the model and effort the step's session runs with (e.g. sonnet · medium), or — when Who is Owner.
- Gate: optional. <condition> → <consequence if it fails: variants or steps dropped or re-decided>. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

### Step 1 — `<title>`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** following the Git conventions in CLAUDE.md.
- **Model:** `<model · effort>` (or —)
- **Gate:** `<condition>` → `<consequence>`

#### Scope

<!-- The result of the step. List the components and the files created or changed (code, tests, docs). A reviewer should know what the diff will contain from this section alone. -->

#### Reads

<!-- List of reads containing what to read (be specific with paragraph or line), what contains the read, and why it is interesting here.  -->

#### Do

<!-- Numbered actions in execution order, one verb each (write, implement, update, run). Every file named here must appear in Scope; add nothing Scope does not list. -->

#### Check

<!-- command/s or verification with a yes/no result. -->

## 4. Findings

<!-- Filled during the run, in the step that produces the evidence. One fact per finding: what was observed, the evidence (figures, tables) and its consequence for the spike. Numbering is never reused. An earlier finding is not rewritten to fit a later result; the later one says which finding it corrects. -->

### F1. `<one-line statement>`

Step N · YYYY-MM-DD · `<source of evidence>`

- `<evidence>`
- Consequence: `<for variants, steps or questions>`

## 5. Conclusion

<!-- Filled after the last step. Covers only the observed window. -->

Observed window: `<from–to, UTC; what it does not cover>`

### 5.1 Answers

- **Q1. Title** `<answer>` (FN)

### 5.2 Exit criteria

<!-- One result per criterion and variant. -->

| Criterion | Kind | Result | Findings |
|---|---|---|---|

### 5.3 Verdict

<!-- The answer to the main question in 2–3 sentences. -->

### 5.4 Not verified

<!-- What the evidence does not cover, each with its risk and mitigation. "None" is valid. -->

- `<item>` — `<risk>` — `<mitigation>`

### 5.5 Production inputs

<!-- Optional. What a later task must take into account when it builds, from any part of the spike: done when that task runs. Each one has a Destination: a design (with its task) with its `TODO(TNNN)` marker (CLAUDE.md › Pending items), or discarded with a reason. -->

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | | `<e.g. D1, #2, F3>` | |

### 5.6 Records

<!-- Documents this spike updates before it closes: ADRs from Decided at framing (each in its own commit), architecture, requirements, source cards and new tasks agreed with the owner. A decision that updates no document has no row. Commit: "Done", or "Pending" until delivered; the spike closes when every row is Done. Production inputs are not repeated here. -->

| Output | From | Destination | Commit |
|---|---|---|---|
| `<ADR, requirement, source card or task>` | `<e.g. D1, F3>` | `<document and section>` | `<Done, or Pending>` |

## 6. Sources

<!-- Optional. Earlier spikes, benchmarks and documentation used. -->

-
