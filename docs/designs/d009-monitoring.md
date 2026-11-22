<!--
Design doc template. A design doc is the working document of one task: Spec (what and why), Plan (how), Steps (implementation), Close (what was delivered).
It is detailed enough that Code can implement it without making design decisions.
Sections marked Optional are kept only when they apply.
Kind: a build task builds code or configuration and has every block. A document-only task delivers documents only, written during the Spec and the Plan, and has no Steps block. A parent is a document-only task with children (`TNNN.M`): it holds what its children share, and its Children section.
-->

# Design: Monitoring capture and pipeline

- **Task:** T060.2
- **Kind:** build
- **ADRs:** [ADR-0026](../decisions/0026-budget-shares-per-component.md), [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md), [ADR-0036](../decisions/0036-log-convention-across-components.md), [ADR-0048](../decisions/0048-grafana-cloud-as-monitoring-tool.md), [ADR-0049](../decisions/0049-log-events-copied-to-monitoring-over-otlp.md)
- **New ADRs from this doc:** `<ADRs created during this design, or "none">`

## Status

<!-- State: Draft 📝 · Ready for implementation 🎬 · In progress 🔄 · Complete ✅. A document-only task goes from Draft to Complete.
Phase: the blocks and reviews completed. A document-only task shows only Spec · Plan · Plan review.
Current: where work resumes (the step being implemented, or the block and section of the design; — when complete), plus only what the next session cannot derive from the document, such as an instruction from the owner. Nothing it can re-derive: options, recommendations, files to read, later sections. A document-only task names the section. -->

- State: Draft 📝
- Phase: [ ] Spec · [ ] Plan · [ ] Plan review · [ ] Steps · [ ] Steps review
- Current: Spec › Failure cases, every open question decided. D6 changes `capture_volume.sql`, the history window in `run.py`, their dbt unit tests, DQR12 in `data-quality.md` and d008 › D4; D7 changes DQM7 in `data-quality.md` and d004 › D6; D10 sets DQM11's target in `data-quality.md`: all planned in File layout. Evidence for OQ4, OQ5, OQ6 and OQ10 comes from DuckDB scripts in `spikes/d009-baselines/`, one subfolder per question, reading R2 from the owner's machine with the bronze and lakehouse read-only keys of `.env`. Parked for the Plan: one name for the warning level (D5), where the observability catalog lives (D5), the thresholds of ALR4, ALR7 and the heartbeat derived from the pipeline's cadence, so a change of cadence is one setting (D8); parked, to propose: a design-skill rule to explain each ID with an example in conversation.

## 1. Spec — what and why

<!-- What the result does seen from outside, not how it is built. The test: if whoever uses the result would notice a change, it belongs here; if not, it belongs to the Plan. External systems and their data (feeds, fields) may be named. -->

### 1.1 Context

<!-- 2–4 sentences for a reader with no prior context: the problem or need and why it matters now; who or what uses the result; where things stand today, including any design or spike this builds on. No solution here: it starts in Decided at framing. For a correction: current vs expected behaviour and how to reproduce it. -->

Capture, the pipeline and the page each write structured log events rich enough to be split by any of their fields ([ADR-0036](../decisions/0036-log-convention-across-components.md)), yet today the owner reads them only in R2 objects and in each platform's own logs. The owner learns only of runs that fail or never start, through the heartbeat ([ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md)), so a failed rule of severity warn, a batch set aside or an indicator off its target reaches the owner late ([d007 › D1](d007-pipeline-design.md#d1-build-by-vertical-slice)). This task makes Grafana Cloud, the tool chosen by [s018](../spikes/s018-monitoring-tool.md), the place where the owner sees how each component and each of its parts is running, and learns of what needs action through alerts. It builds on the copy of every event over OTLP set by [ADR-0049](../decisions/0049-log-events-copied-to-monitoring-over-otlp.md), on the scope set by [d007 › Children](d007-pipeline-design.md#16-children), and on the pipeline T060.1 runs in production.

### 1.2 Decided at framing

<!-- Optional. One heading per decision about what the result does. In this order, so the reader finds what matters first:
1. The decision and why, in one short paragraph.
2. What would change it, and what would not, each with the action to take. Only when a later event could reopen it.
3. The options rejected.
4. The artefact that fixes it, in whatever form the decision needs (e.g. a mapping table, a page map, a weighted matrix). An artefact that does not fit here or must outlive the design goes in its own file: the Plan decides where it lives and its format, File layout lists it, and this decision links to it.

A security decision lists its threats in this table, with IDs `TH1`, `TH2`… per document:

| # | Threat (STRIDE) | Impact | Control | Requirement |
|---|---|---|---|---|
| `TH1` | | | | |
-->

#### D1. Every event of every level reaches Grafana

Every event capture and the pipeline write, of every level, reaches Grafana Cloud, following [s018 › D1](../spikes/s018-monitoring-tool.md#d1-r2-as-the-record-the-tool-with-a-copy): R2 is the record and Grafana the hot copy (tiered storage). The owner queries the last 14 days there, the Free tier's retention; older events stay in R2 and are queried with SQL ([ADR-0036](../decisions/0036-log-convention-across-components.md)). The page runs no code of its own, so it appears through the pipeline's deployment events and through the synthetic check that reads its files as a visitor does ([s018 › D6](../spikes/s018-monitoring-tool.md#d6-quality-indicators-reach-the-tool-by-push)). A new event, field or system, such as those later children add, reaches Grafana and its queries with no change to the sending, since queries and alerts select on the fields events carry, never on a closed list of systems or events.

- **What would change it:** an estimated volume close to the Free tier's 50 GB a month; today it is about 200 MB. Then the events of level `info` that no query or alert reads are the first left out.

Rejected: only events of level `warn` and `error`. It saves volume the project does not need, and leaves out the health of the runs that end well (durations, rows, memory) that the dashboards of T060.10 chart.

#### D2. The copy to Grafana never affects a run

Sending to Grafana affects capture and the pipeline as little as possible, following best-effort delivery to the hot copy while R2 holds the record ([s018 › D1, D3, TH5](../spikes/s018-monitoring-tool.md#d8-monitoring-tool-security-threats)). What must not break:

- A send that fails or is slow changes neither a run's outcome nor its heartbeat signal.
- What a run writes to R2 is unchanged: the send is a copy of the same events.
- Each send has a time limit, so neither capture's cadence nor the pipeline's run timeout depends on Grafana.
- The redaction of secrets of [d008 › Observability](d008-pipeline-platform-and-walking-skeleton.md#observability) applies to the copy as well.

Events that did not reach Grafana, while it was down or a send failed, stay only in R2: Grafana shows a gap for that period, and the owner queries it with SQL over R2 if needed. The loss in the copy is accepted.

Rejected: resending later from R2 what did not arrive. Grafana would be complete, but each component would keep state of what it sent, and Loki rejects events older than its configured limit, so the resend would not always succeed.

#### D3. Alerts on symptoms that need action

An alert fires on a symptom that needs an action from the owner, not on each error, following the SRE practice of alerting on symptoms with every alert actionable: capture's single source failures, 57 in 22 days, mostly recover on the next pass ([d004 › D8](d004-bronze-data-capture.md#d8-capture-failure-behaviour)). The list was checked against every event capture and the pipeline wrote in production, 14.6 days of capture and 1.5 days of the pipeline ([`spikes/d009-baselines/discovery/`](../../spikes/d009-baselines/discovery/)); thresholds come from those events or from the Plan, and each alert's urgency from OQ7.

| # | Situation | Source | Why |
|---|---|---|---|
| ALR1 | A runtime rule of severity error fails (`batch_failed`, `file_invalid`) | Pipeline | [d007 › D4](d007-pipeline-design.md#d4-data-quality-in-four-classes) |
| ALR2 | A runtime rule of severity warn fails (`schema_drift_field`, DQR12's volume drop) | Pipeline | d007 › D4 |
| ALR3 | The page's deployment fails (`page_deploy_failed`) | Pipeline | The page stops updating |
| ALR4 | A published file is older than its target (DQM10, synthetic check) | Page | What a visitor sees, whatever the cause |
| ALR5 | A feed has had no clean capture for too many minutes in a row (DQM11) | Capture | A sustained failure, not a single one |
| ALR6 | Capture burns its monthly error budget (DQM7, 99.5%) at a rate that would exhaust it | Capture | The standard SLO burn-rate alert |
| ALR7 | A run nears its time or memory limit (`duration_s`, `peak_memory_mb`) | Pipeline | Warns before the timeout or a memory kill ends runs ([ADR-0027](../decisions/0027-modal-as-execution-platform.md)) |
| ALR8 | A component sends no events to Grafana for N minutes | Both | The send is broken (D2) |
| ALR9 | Any other event of the warning level, such as `heartbeat_failed`, `log_upload_failed` or `stage_drained`, but `fetch_retried` | Both | Single warnings of low urgency; a retry that succeeds needs no action and one that fails is a `feed_failed`, while `fetch_retried` comes about 32 times a day |
| ALR10 | A provider's index lists a feed capture does not know (`unknown_feeds` of `index_refreshed`) | Capture | A change in the source for the owner to evaluate, which nothing else shows |
| ALR11 | A pass logs a cause of a missed minute that D9's table does not list | Capture | A new cause to classify (D9) |
| ALR12 | Grafana stops signalling the heartbeat service (watchdog) | Grafana | Every other alert runs in Grafana (D13) |

An indicator built by a later child reaches these alerts by adding its target to the mechanism ALR4–ALR6 prove, as [d007 › D1](d007-pipeline-design.md#d1-build-by-vertical-slice) sets (Out of scope).

#### D4. Alerts carry their own ID and the catalog IDs they check

Each alert is a citable item with a flat ID of its own, prefixed `ALR`, as `DQR` and `DQM` are in the data quality catalog ([docs › References](../../.claude/rules/docs/general.md)), so an alert that checks no catalog item, such as a failed deployment, is citable too. Each alert carries, as labels, the catalog IDs it checks, following the practice of labels on Prometheus and Grafana alerts: an alert that covers a class of items, such as every rule of severity error, takes the failing item's ID from the event itself, since each data test is named after its rule ([s017 › P5](../spikes/s017-dbt-in-the-pipeline.md#55-production-inputs)). The notification shows both, so the owner reaches the item in its catalog and filters its past firings in Grafana.

Threats are cited the same way once a project-wide threat catalog gives them global IDs (`THG`); until then an alert carries no threat ID, since `TH` IDs restart in each document (Out of scope).

A failed rule of severity error reaches the owner as, for example:

```text
[ALR1] A runtime rule of severity error failed
  Rule:      DQR13, the rows added do not match the items read from bronze
  Component: pipeline · system: bicing · version: 3f2a9c1
  Batch:     2026-11-21 10:00 UTC
  → link to that run's events in Grafana
```

Rejected: an alert named after the item it checks, with no ID of its own. It is simpler, but alerts on a deployment, a run's limits or a silent sender check no catalog item and would not be citable.

#### D5. One observability catalog, built here

This task absorbs T074 and builds the observability catalog: one document that holds, for every component, its log events with their level and own fields, the common fields of [ADR-0036](../decisions/0036-log-convention-across-components.md), the heartbeat checks, and the signals and alerts that read them, alerts included with their IDs (D4). It becomes the source the designs link to, following link, don't copy: d004 and d008 keep their decisions and link to it for the events. The task walks every event of capture and the pipeline to map them to Grafana and to find alerts, so the catalog is written once, from that walk. The level of a failure that does not affect the data is written `warning` by capture and `warn` by the pipeline; the catalog fixes one name for both. Where the catalog lives, and how a later component, such as the page in T041, adds its events, are settled in the Plan.

Rejected: T074 kept apart, after this task. This design would be shorter, but the events would be walked twice, and the alerts' IDs would have no place until T074.

#### D6. Volume drop at 95% of a 7-day median

DQR12 flags a capture of a system that lists fewer than 95% of the median number of stations of that system's captures in the 7 days before its capture instant; with fewer than 60 such captures, the rule is not evaluated. Over 5.5 weeks of production captures (2026-10-14 to 2026-11-21, 108,289 captures, no gap over 1 h), AMBici listed 236 or 237 stations, at most 0.4% below its median, while Bicing lost stations from its feed twice and recovered them: to 513 (5.5% below) for about 20 h from 2026-10-31, and to 504 (7.5% below, 41 stations) for about 38 h from 2026-11-10. The provisional 90% over 24 h flagged neither, and a 24 h median takes in a sustained drop after about 12 h; 95% over 7 days flags both for their whole length and nothing else ([`spikes/d009-baselines/volume-drop/`](../../spikes/d009-baselines/volume-drop/)). The longer baseline follows the volume monitors of data observability, whose baseline must not absorb the drop it measures. Each capture is judged on its own, so a drop of a few captures flags only those captures; the minimum of 60 captures holds, since it only applied to each system's first hour. **refines [d008 › D4](d008-pipeline-platform-and-walking-skeleton.md#d4-volume-drop-against-a-rolling-median)**

- **What would change it:** a legitimate change of the network above 5%, such as stations closed for good, which flags each capture for about 3.5 days, until the median takes the new count; the owner silences that episode. Several such changes would call for a shorter window.

Rejected: 95% over 24 h. It keeps the window and the history the run reads, but flags only the first 10 h of the November drop and misses the October one.

#### D7. Capture completeness target per system

DQM7 keeps its definition and takes one target per system: at least 99.5% of the minutes of each calendar month for AMBici and 97% for Bicing. Over the first 14.5 days of production capture (2026-11-07 to 2026-11-21), AMBici captured 99.9% of its minutes, losing 17 to scattered 5xx responses and timeouts, while Bicing captured 97.8%, losing 464, 98% of them to a 403 from the provider, almost always a single minute at a time, about 32 a day, worst day 97.15% ([`spikes/d009-baselines/indicator-targets/`](../../spikes/d009-baselines/indicator-targets/)). Each target sits just below what production shows, following the SRE practice of setting an SLO from measured performance and revising it, so ALR6 stays quiet in normal operation and fires when a system gets worse. The captures copied from V4 before 2026-11-07 do not count: another capture wrote them, with no pass logs to give the cause of a gap. **refines [d004 › D6](d004-bronze-data-capture.md#d6-capture-completeness-target)**

- **What would change it:** the first full calendar month of production, December 2026, with Bicing clearly above or below 97%: its target is revised with that month. If Bicing's 403 stops, Bicing returns to 99.5%.

Rejected: 99.5% for both, with the minutes lost to a 403 left out of DQM7. One target for both, but the indicator would no longer measure what is missing from the station stock, and whether a 403 is the provider's gap or capture's is what DQM11 splits.

#### D8. Page data age keeps its target

DQM10 keeps its target, at most one cadence plus one run ([d002 › R3](d002-requirements.md#requirements)), since production meets it: today one cadence is 15 min and a run lasts up to about 7 min, so about 22 min. Over 22.7 h of steady state (2026-11-21 03:03 to 2026-11-22 01:46 UTC, 93 deployments, the runs before it catching up on the weeks captured earlier), the oldest data a visitor met, just before the next deployment, was 16.8 min at the median and 19.6 min at most, measured from the latest capture instant each run's `file_built` logs; runs lasted 127 s at the median and 421 s at most, 15 min apart ([`spikes/d009-baselines/indicator-targets/`](../../spikes/d009-baselines/indicator-targets/)). These are the walking skeleton's figures, a baseline: runs grow as later children add models, and the target, stated relative to the cadence and the run, follows them without being rewritten, while ALR7 and ALR4 watch that growth. A target is kept when production meets it, following the SRE practice of D7. Where ALR4 sets its threshold is a Plan decision (D3).

- **What would change it:** runs that bring the oldest data a visitor meets above one cadence plus one run: the cadence or the run's duration is reviewed, not the target, since it is what the page promises its visitor.

#### D9. A missed minute's cause goes to whoever can act on it

DQM11 gives each minute with no capture of a feed to capture or to the provider by who can act on it, since the indicator exists to tell the owner when to act on capture and when to do nothing ([data-quality › Quality indicators](../data-quality.md#quality-indicators)), following the SRE practice of attributing an error to whoever can fix it. A minute captured but missing from the station stock is the pipeline's, not a capture gap, and stays out of DQM11.

| Cause the pass logs | Goes to |
|---|---|
| A response from the provider with no data: any HTTP error status, 403 and 404 included, on the feed (`feed_failed`) or on its index (`index_rejected`) | Provider |
| A timeout reaching the provider | Provider |
| A failure to write the response to R2 (`error_type` `write`) | Capture |
| No pass logged for the minute | Capture |
| A pass with no event for the feed | Capture |
| Any other cause, until this table lists it | Capture |

A cause the table does not list goes to capture, following the fail-safe default of giving the unknown to whoever can investigate it, and raises ALR11, so the owner adds it to this table and to the observability catalog (D5).

- **What would change it:** evidence that Bicing's 403 depends on how capture requests, such as the Cloudflare location the request leaves from (Hong Kong is suspected, not shown): the 403 then goes to capture, since capture can act on it. Timeouts that grow: whether capture's limit is too short is reviewed.

Rejected: the HTTP status class (RFC 9110), 4xx to capture as a client error and 5xx to the provider. It reads the status class as an attribution, and would give capture Bicing's 403, about 32 minutes a day the owner has decided not to act on.

#### D10. A target on capture's own missed minutes only

DQM11 takes a target on the minutes D9 gives to capture: at most 30 minutes per feed and calendar month. The minutes given to the provider are measured and shown with no target, since the owner takes no action on them and DQM7 already bounds their effect on completeness (D7). Over the first 14.6 days of production pass logs (2026-11-07 10:19 to 2026-11-22 01:39 UTC), each dynamic feed lost 6 or 7 minutes to capture, each a single minute and at most one a day: four passes the cron never ran, the same minutes for every feed, and passes logged with no event for any feed; about 10 minutes a month. The provider took 13 and 15 minutes from AMBici's two feeds and 486 from Bicing's, 481 of them a 403, 32 a day at the median; no run of missed minutes lasted over 5 minutes ([`spikes/d009-baselines/capture-gaps/`](../../spikes/d009-baselines/capture-gaps/)). The target sits at about three times that baseline, which comes from two weeks only, following the SRE practice of D7: a target on what the owner can fix, set from measured performance and revised.

- **What would change it:** the first full calendar month of production, December 2026, with a baseline clearly above or below about 10 minutes: the target is revised with that month.

Rejected: a target per class, the provider's included. It repeats DQM7's per-system target, and a target the owner cannot act on prompts no action.

#### D11. Pages for what waiting makes worse, tickets for the rest

Each alert is a page or a ticket, following the SRE split between alerts that interrupt and alerts reviewed later: a page when waiting makes the harm worse, because data is lost for good or a visitor already sees it; a ticket when the action can wait for days. Both reach the Grafana mobile app through IRM ([s018 › D5](../spikes/s018-monitoring-tool.md#d5-notifications-in-the-grafana-app)). A page notifies the owner on the phone until acknowledged; a ticket sends no notification and stays in the app's list of alerts until the owner closes it. Alerts notify at any hour.

| Alert | Urgency | Why |
|---|---|---|
| ALR4 | Page | A visitor sees stale data, whatever the cause |
| ALR5 | Page | A minute not captured is lost for good: bronze cannot be captured again |
| ALR6 | Page at a fast burn, ticket at a slow one | The SLO alert of the SRE Workbook, at several burn rates over several windows |
| ALR1 | Ticket | The batch is set aside and bronze keeps its data to process again; a page falling behind raises ALR4 |
| ALR2 | Ticket | A rule of severity warn blocks nothing |
| ALR3 | Ticket | A failed deployment that repeats ages the page and raises ALR4 |
| ALR7 | Ticket | An early warning, with margin before the limit |
| ALR8 | Ticket | R2 still holds the record (D2), and the heartbeat, on another provider, still reports stopped runs |
| ALR9 | Ticket | Single warnings of low urgency (D3) |
| ALR10 | Ticket | A change to evaluate, with no hurry |
| ALR11 | Ticket | A cause to classify, with no hurry: its minutes already count against capture (D10) |
| ALR12 | Page, by email from the heartbeat service | Every other alert is silent; it cannot go through Grafana (D13) |

Rejected: every alert a page. Simpler, but twelve alerts that interrupt alike lead to alert fatigue, which D3 avoids. Rejected as well: a ticket as a notification that does not insist; the owner reviews tickets in the app instead.

#### D12. No health script

The owner checks the health of capture, the pipeline and the page in Grafana, from the phone as well, over the last 14 days; anything older is queried with SQL over R2 from the owner's machine ([ADR-0036](../decisions/0036-log-convention-across-components.md)), which is investigation rather than a health check. This follows the tiered storage of D1: Grafana is the hot copy to operate with, R2 the record to investigate. No script of its own answers health questions, which closes the health script that could run from a phone ([s013 › P9](../spikes/s013-visualization-tool.md#55-production-inputs)).

Rejected: a health script run from a phone through a manual GitHub Actions run. It reaches the history from the phone, but GitHub would hold one more read key on R2, its summary would be public if the repository is, and it repeats what Grafana shows.

#### D13. A watchdog outside Grafana watches its alerting

Grafana keeps one alert, ALR12, that always fires and signals, every few minutes, a check of the heartbeat service of [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md), Healthchecks.io; when the signals stop, that service emails the owner. This follows the watchdog alert, a dead man's switch watched from outside: ALR8 and every other alert run inside Grafana, so a suspended account, a change to the Free tier or a broken notification setting would silence them all with no notice. The watchdog proves that Grafana evaluates rules and sends notifications; delivery from IRM to the phone is not watched. Its period and grace time are settled in the Plan with the other thresholds (D8). It takes one of the free plan's 20 checks.

Rejected: no watchdog. Nothing to add, but a silent Grafana goes unnoticed until the owner opens it, while capture keeps losing minutes for good (D11). Rejected as well: a scheduled script outside Grafana, such as a Cloudflare Worker with a Cron Trigger, that asks Grafana's API whether it evaluates its alerts. It checks the same, with code of its own to maintain and one more credential.

#### D14. The synthetic check confirms a failure from two of three probes

The synthetic check of ALR4 reads the page's files from three probe locations, and ALR4 fires only when at least two of them find a file too old or cannot read it. This follows synthetic monitoring's practice of confirming a failure from several locations before alerting: a file's age is the same from every location, so a single failing probe points to its own network, and ALR4 is a page (D11), which must be reliable for the owner to keep answering it. Each probe counts against the Free tier's 100k check executions a month ([s018 › C4](../spikes/s018-monitoring-tool.md#d2-monitoring-tool)): a check every 5 min from three probes takes 25,920 a month. The check's frequency is settled in the Plan with the other thresholds (D8).

Rejected: one probe. A third of the executions, but a network failure at that probe pages the owner while visitors see a fresh page.

### 1.3 Requirements

<!-- Optional. The acceptance criteria, cited by number in the Test plan and the steps. They translate Decided at framing and cite the decision they come from; nothing is decided here.
One behaviour per requirement, verifiable, with a measurable threshold where one applies. Written in EARS:
- Ubiquitous: The <system> shall <response>.
- Event: When <trigger>, the <system> shall <response>.
- State: While <state>, the <system> shall <response>.
- Unwanted: If <condition>, then the <system> shall <response>.
- Optional: Where <feature is included>, the <system> shall <response>.
Only requirements specific to this task; project-wide rules (CLAUDE.md, ADRs) are not repeated. -->

- **R1** `<EARS statement>` (D`<N>`)

### 1.4 Done when

<!-- Optional. Only what closes this task and Requirements cannot express: operational actions, checks on real data, understanding. The general closing rule is checked in `.claude/skills/implement/review.md`. -->

- `<extra condition>`

### 1.5 Out of scope

<!-- Optional. What someone could expect and will not be done, each item pointing to the task that covers it. -->

- Dashboards per component and per part of each, built on the events in Loki — T060.10
- Alerts on DQM5, DQM8 and DQM9: the child builds each indicator, adds its target to the alerts and reviews it — T060.8
- Alerts on DQM4, the same way — T060.3
- Alerts on quarantined rows, once the quarantine table exists — T060.5
- Targets of DQM1–DQM3, rows of the review table — T060.6
- A project-wide threat catalog with global IDs (`THG`), and the threat ID on the alerts that detect one — T073

### 1.6 Open questions

<!-- Optional. The decisions still to take about the what, in dependency order. Each one closes as a decision in Decided at framing and leaves the table, so it is empty at Spec approval. Questions about the how are Plan decisions. -->

| OQ | Question | Depends on | Notes |
|---|---|---|---|

## 2. Plan — how

<!-- 2-3 sentences -->

### 2.1 Approach

<!-- Detailed plan organized by #### blocks.
Block `3. Steps` is written using this plan. In a document-only task, Approach lists the main and supporting deliverables instead, each already written.
A block may end with `Options considered`, with pros and cons, only for a decision asked of the owner, and listing only alternatives a later reader could reasonably propose again; an option that merely shapes the choice is left out, and a decision with none such has no Options considered.
-->

#### Carried-over inputs

Inputs about the how, left to this task by earlier spikes and designs; each links to its origin, which holds the detail.

- **Free tier features:** at account set-up, check template variables and data links, the SLO app, Loki recording rules, a scripted k6 check asserting a file's age and the IRM heartbeat; two or more failing reopen s018's choice of tool ([s018 › P1](../spikes/s018-monitoring-tool.md#23-production-inputs)).
- **Security controls:** at account set-up, check tokens scoped to writing logs, a stack in an EU region and no payment method needed; then apply the controls of TH1–TH5 ([s018 › P2](../spikes/s018-monitoring-tool.md#23-production-inputs)).
- **Indicators' signal:** the indicators' values sent as log events, unless the design shows a reason for metrics ([s018 › P4](../spikes/s018-monitoring-tool.md#23-production-inputs)).
- **Field mapping:** the common fields of ADR-0036 mapped to OTLP attributes and Loki labels; a failed send never changes a run's outcome ([s018 › P5](../spikes/s018-monitoring-tool.md#23-production-inputs)).
- **Pipeline's copy over OTLP:** each run's events sent after the log upload, as ADR-0049 sets, with the monitoring tool's token as a Modal Secret of the scheduled function only ([d008 › Observability](d008-pipeline-platform-and-walking-skeleton.md#observability)).

### 2.2 Decision summary

<!-- It logs decisions about the plan, including changes. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Applies to: anchor link(s) to the section where the decision is applied, named in one or two words.
- Decided at: the Status phase where it was decided (Plan, Steps), or `<phase> review` when decided while reviewing that phase.
- R: Requirement affected.
-->

| # | Applies to | Decision | Reason | R | Decided at |
|---|---|---|---|---|---|
| | | | | | |

### 2.3 Architecture

<!-- Optional. One diagram and 2–3 sentences. -->

### 2.4 File layout

<!-- Every file and folder the task creates or modifies, documents included, as a tree: (new) or (modified), and its purpose or change in one line. A task that adds a component also lists its CI job in `.github/workflows/ci.yml` (recipe in `.claude/rules/code/ci.md`), and its version files, manifest and lockfile (`.claude/rules/code/dependencies.md`). -->

```text
<path>/
└── <file>      (new)        <purpose>
```

### 2.5 Components

<!-- Optional. One subsection per component. The contract is exact, in the component's own language, never pseudocode. -->

#### `<ComponentName>`

- **Responsibility:** `<one sentence>`
- **Location:** `path/to/file`
- **Contract:**

```python
```

### 2.6 Test plan

<!-- Optional. Every requirement has at least one verification method (IADT: Inspection, Analysis, Demonstration, Test). Test is the default, at the lowest level that can verify the requirement. Another method only when no test can: Inspection for configuration or documents, Analysis for production data or measurements, Demonstration for behaviour observed end to end, such as a third-party service. -->

| R | Method | What is verified | Level |
|---|---|---|---|
| R1 | Test / Inspection / Analysis / Demonstration | | unit / integration / e2e; — for other methods |

### 2.7 Breaking changes

<!-- Optional. Shared models or interfaces this design changes, and how their dependants are handled. -->

| File | Why it breaks | Strategy |
|---|---|---|
| | | |

### 2.8 What does not change

<!-- Optional. Code or documents that must not be modified. Out of scope limits the what; this section limits the how. -->

-

## 3. Steps

<!-- Build tasks only; a document-only task removes this block.
Each step is one reviewable result and one commit, touching at most 2–3 files.
- Status: where the step is: 💤 todo · 🎬 ready · 🔄 in progress · ⛔ blocked · ✅ done
- Who: Owner (manual actions: dashboards, accounts, deploys, runs, checks) or Claude (code and documents).
- R: the requirements the step implements or tests, or —.
- Commit: the proposed message, following the Git conventions in CLAUDE.md.
- Model: the model and effort the step's session runs with (e.g. sonnet · medium), or — when Who is Owner.
- Review: `code`, `security`, `code and security`, or `no`. A review goes on the step that completes a reviewable unit (a flow or action, usually built over several steps); the last code step has at least `code`. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

### Step 1 — `<Title>`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** following the Git conventions in CLAUDE.md, with the design and step ID first in the description: `<type>: dNNN.sN <description>`.
- **R:** R1, R3 (or —)
- **Model:** `<model · effort>` (or —)
- **Review:** `<code | security | code and security | no>`

#### Scope

<!-- The result of the step. List the components, the files created or changed (code, tests, docs), and the tests from the Test plan that cover it. A reviewer should know what the diff will contain from this section alone. -->

#### Reads

<!-- List of reads containing what to read (be specific with paragraph or line), what contains the read, and why it is interesting here.  -->

#### Do

<!-- Numbered actions in execution order, one verb each (write, implement, update, run). Every file named here must appear in Scope; add nothing Scope does not list. -->

#### Check

<!-- command/s or verification with a yes/no result. -->

## 4. Close

<!-- The record of what the task delivered, for whoever opens this design later. -->

### 4.1 Implemented

<!-- Component — what was delivered; tests passing. In a document-only task: Deliverable — what it holds. A parent also names the children's issues created at its close; this block is not updated as they progress, since their state lives in their issues and their own working documents. -->

### 4.2 Known gaps at close

<!-- What the task leaves undone or imperfect, each with the task that covers it and its `TODO(TNNN)` marker (CLAUDE.md › Pending items): requirements not fully met, File layout items not delivered, TODOs citing this task. "None" is valid. -->

- `<gap>` — TNNN

### 4.3 Decisions taken during implementation

<!-- Decisions made after the Plan was approved, including deviations from Scope approved by the owner. Oldest first; "None" is valid.
- #: `DI1`, `DI2`… (decision during implementation).
- Applies to: anchor link(s) to the design section the decision changes, or the path of a file outside the design.
- Decision and Reason: one line each; the content goes where it applies.
- Decided at: the step where it was decided (`Step N`).
-->

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| | | | | |
