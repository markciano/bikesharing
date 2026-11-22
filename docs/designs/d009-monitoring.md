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
- **New ADRs from this doc:** [ADR-0051](../decisions/0051-monitoring-configuration-as-code.md)

## Status

<!-- State: Draft 📝 · Ready for implementation 🎬 · In progress 🔄 · Complete ✅. A document-only task goes from Draft to Complete.
Phase: the blocks and reviews completed. A document-only task shows only Spec · Plan · Plan review.
Current: where work resumes (the step being implemented, or the block and section of the design; — when complete), plus only what the next session cannot derive from the document, such as an instruction from the owner. Nothing it can re-derive: options, recommendations, files to read, later sections. A document-only task names the section. -->

- State: Draft 📝
- Phase: [x] Spec · [x] Plan · [x] Plan review · [x] Steps · [ ] Steps review
- Current: Steps review.

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

Every event capture and the pipeline write, of every level, reaches Grafana Cloud, following [s018 › D1](../spikes/s018-monitoring-tool.md#d1-r2-as-the-record-the-tool-with-a-copy): R2 is the record and Grafana the hot copy (tiered storage). The owner queries the last 14 days there, the Free tier's retention; older events stay in R2 and are queried with SQL ([ADR-0036](../decisions/0036-log-convention-across-components.md)). The page runs no code of its own, so it appears through the pipeline's deployment events and through the synthetic check that reads its files as a visitor does ([s018 › D6](../spikes/s018-monitoring-tool.md#d6-quality-indicators-reach-the-tool-by-push)). A new event, field or system, such as those later children add, reaches Grafana and its queries with no change to the sending, since queries and alerts select on the fields events carry, never on a closed list of systems; the list of events lives in the observability catalog, which ALR9 and ALR14 read so that a new event is classified (D5).

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
| ALR6 | Capture burns its monthly error budget (DQM7, each system's target) at a rate that would exhaust it | Capture | The standard SLO burn-rate alert |
| ALR7 | A run nears its time or memory limit (`duration_s`, `peak_memory_mb`) | Pipeline | Warns before the timeout or a memory kill ends runs ([ADR-0027](../decisions/0027-modal-as-execution-platform.md)) |
| ALR8 | A component sends no events to Grafana for N minutes | Both | The send is broken (D2) |
| ALR9 | An event the observability catalog marks as actionable and no other alert covers, such as `heartbeat_failed`, `log_upload_failed` or `stage_drained` | Both | Single warnings of low urgency; `fetch_retried`, about 32 a day, is not actionable: a retry that succeeds needs no action and one that fails is a `feed_failed` |
| ALR10 | A provider's index lists a feed capture does not know (`unknown_feeds` of `index_refreshed`) | Capture | A change in the source for the owner to evaluate, which nothing else shows |
| ALR11 | A pass logs a cause of a missed minute that D9's table does not list | Capture | A new cause to classify (D9) |
| ALR12 | Grafana stops signalling the heartbeat service (watchdog) | Grafana | Every other alert runs in Grafana (D13) |
| ALR13 | Grafana's use nears a limit of its Free tier: logs a month, synthetic check executions | Grafana | Past a limit, Grafana drops events or stops checking, and D1 is reviewed |
| ALR14 | An event the observability catalog does not list reaches Grafana | Both | A new event to classify, which ALR9 would otherwise miss (D5) |
| ALR15 | A feed's minutes given to capture over the last 7 days exceed the 7-day share of DQM11's target | Capture | Scattered single minutes, which neither ALR5 nor ALR6 sees, would break the target unnoticed (D10) |

The limits and costs of Cloudflare and Modal are watched by each provider's own usage and budget notifications, set in its console.

An indicator built by a later child reaches these alerts by adding its target to the mechanism ALR4–ALR6 prove, as [d007 › D1](d007-pipeline-design.md#d1-build-by-vertical-slice) sets (Out of scope).

#### D4. Alerts carry their own ID and the catalog IDs they check

Each alert is a citable item with a flat ID of its own, prefixed `ALR`, as `DQR` and `DQM` are in the data quality catalog ([docs › References](../../.claude/rules/docs/general.md)), so an alert that checks no catalog item, such as a failed deployment, is citable too. Each alert carries, as labels, the catalog IDs it checks, following the practice of labels on Prometheus and Grafana alerts: an alert that covers a class of items, such as every rule of severity error, takes the failing item's ID from the event itself, since each data test is named after its rule ([s017 › P5](../spikes/s017-dbt-in-the-pipeline.md#55-production-inputs)). The notification shows both, so the owner reaches the item in its catalog and filters its past firings in Grafana.

Threats are cited the same way once a project-wide threat catalog gives them global IDs (`THG`); until then an alert carries no threat ID, since `TH` IDs restart in each document (Out of scope).

A failed rule of severity error reaches the owner as, for example:

```text
[FIRING] [ALR1] A runtime rule of severity error failed · DQR13
  pipeline · system: bicing · version: 3f2a9c1
  since 11:00 CET
  → rule in the catalog   → this alert   → events in Grafana
```

Its layout is set in [Notifications](#notifications). **#11**

Rejected: an alert named after the item it checks, with no ID of its own. It is simpler, but alerts on a deployment, a run's limits or a silent sender check no catalog item and would not be citable.

#### D5. One observability catalog, built here

This task absorbs T074 and builds the observability catalog: one catalog, a document with its machine-readable registry of events, that holds, for every component, its log events with their level and own fields, the common fields of [ADR-0036](../decisions/0036-log-convention-across-components.md), the heartbeat checks, and the signals and alerts that read them, alerts included with their IDs (D4). It becomes the source the designs link to, following link, don't copy: d004 and d008 keep their decisions and link to it for the events. The task walks every event of capture and the pipeline to map them to Grafana and to find alerts, so the catalog is written once, from that walk. The level of a failure that does not affect the data is written `warning` by capture and `warn` by the pipeline; the catalog fixes one name for both. Each event in the catalog states whether it needs an action from the owner, which ALR9 reads, and a design that adds or changes an event classifies it when it designs its logs; ALR14 catches an event no design classified. Where the catalog lives, and how a later component, such as the page in T041, adds its events, are settled in the Plan. **#2**

Rejected: T074 kept apart, after this task. This design would be shorter, but the events would be walked twice, and the alerts' IDs would have no place until T074.

#### D6. Volume drop at 95% of a 7-day median

DQR12 flags a capture of a system that lists fewer than 95% of the median number of stations of that system's captures in the 7 days before its capture instant; with fewer than 60 such captures, the rule is not evaluated. Over 5.5 weeks of production captures (2026-10-14 to 2026-11-21, 108,289 captures, no gap over 1 h), AMBici listed 236 or 237 stations, at most 0.4% below its median, while Bicing lost stations from its feed twice and recovered them: to 513 (5.5% below) for about 20 h from 2026-10-31, and to 504 (7.5% below, 41 stations) for about 38 h from 2026-11-10. The provisional 90% over 24 h flagged neither, and a 24 h median takes in a sustained drop after about 12 h; 95% over 7 days flags both for their whole length and nothing else ([`spikes/d009-baselines/volume-drop/`](../../spikes/d009-baselines/volume-drop/)). The longer baseline follows the volume monitors of data observability, whose baseline must not absorb the drop it measures. Each capture is judged on its own, so a drop of a few captures flags only those captures; the minimum of 60 captures holds, since it only applied to each system's first hour. **refines [d008 › D4](d008-pipeline-platform-and-walking-skeleton.md#d4-volume-drop-against-a-rolling-median)**

- **What would change it:** a legitimate change of the network above 5%, such as stations closed for good, which flags each capture for about 3.5 days, until the median takes the new count; the owner silences that episode. Several such changes would call for a shorter window.

Rejected: 95% over 24 h. It keeps the window and the history the run reads, but flags only the first 10 h of the November drop and misses the October one.

#### D7. Capture completeness target per system

DQM7 keeps its definition and takes one target per system: at least 99.5% of the minutes of each calendar month for AMBici and 97% for Bicing. Over the first 14.5 days of production capture (2026-11-07 to 2026-11-21), AMBici captured 99.9% of its minutes, losing 17 to scattered 5xx responses and timeouts, while Bicing captured 97.8%, losing 464, 98% of them to a 403 from the provider, almost always a single minute at a time, about 32 a day, worst day 97.15% ([`spikes/d009-baselines/indicator-targets/`](../../spikes/d009-baselines/indicator-targets/)). Each target sits just below what production shows, following the SRE practice of setting an SLO from measured performance and revising it, so ALR6 stays quiet in normal operation and fires when a system gets worse. The captures copied from V4 before 2026-11-07 do not count in this baseline: another capture wrote them, with no pass logs to give the cause of a gap. **refines [d004 › D6](d004-bronze-data-capture.md#d6-capture-completeness-target)**

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

DQM11 takes a target on the minutes D9 gives to capture: at most 30 minutes per feed and calendar month. The minutes given to the provider are measured and shown with no target, since the owner takes no action on them and DQM7 already bounds their effect on completeness (D7). Over the first 14.6 days of production pass logs (2026-11-07 10:19 to 2026-11-22 01:39 UTC), each dynamic feed lost 6 or 7 minutes to capture, each a single minute and at most one a day: four passes the cron never ran, the same minutes for every feed, and passes logged with no event for any feed; about 10 minutes a month. The provider took 13 and 15 minutes from AMBici's two feeds and 486 from Bicing's, 481 of them a 403, 32 a day at the median; no run of missed minutes lasted over 5 minutes ([`spikes/d009-baselines/capture-gaps/`](../../spikes/d009-baselines/capture-gaps/)). The target sits at about three times that baseline, which comes from two weeks only, following the SRE practice of D7: a target on what the owner can fix, set from measured performance and revised. ALR15 warns when a feed's minutes given to capture over the last 7 days, counted as ALR6 counts them, over the minutes capture's events reach Grafana, exceed the target's share for 7 days, 7 minutes, against at most 3 a week today: Grafana keeps 14 days of events and cannot add up a calendar month, so the alert follows a rolling window, and the month's value is queried with SQL over R2 ([ADR-0036](../decisions/0036-log-convention-across-components.md)), as [s018 › D6](../spikes/s018-monitoring-tool.md#d6-quality-indicators-reach-the-tool-by-push) sets. **#6** **#13**

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
| ALR13 | Ticket | Fires with margin before the limit |
| ALR14 | Ticket | An event to classify, with no hurry |
| ALR15 | Ticket | Capture getting worse on its own, which can wait for days |

Rejected: every alert a page. Simpler, but fifteen alerts that interrupt alike lead to alert fatigue, which D3 avoids. Rejected as well: a ticket as a notification that does not insist; the owner reviews tickets in the app instead.

#### D12. No health script

The owner checks the health of capture, the pipeline and the page in Grafana, from the phone as well, over the last 14 days; anything older is queried with SQL over R2 from the owner's machine ([ADR-0036](../decisions/0036-log-convention-across-components.md)), which is investigation rather than a health check. This follows the tiered storage of D1: Grafana is the hot copy to operate with, R2 the record to investigate. No script of its own answers health questions, which closes the health script that could run from a phone ([s013 › P9](../spikes/s013-visualization-tool.md#55-production-inputs)).

Rejected: a health script run from a phone through a manual GitHub Actions run. It reaches the history from the phone, but GitHub would hold one more read key on R2, its summary would be public if the repository is, and it repeats what Grafana shows.

#### D13. A watchdog outside Grafana watches its alerting

Grafana keeps one alert, ALR12, that always fires and signals, every few minutes, a check of the heartbeat service of [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md), Healthchecks.io; when the signals stop, that service emails the owner. This follows the watchdog alert, a dead man's switch watched from outside: ALR8 and every other alert run inside Grafana, so a suspended account, a change to the Free tier or a broken notification setting would silence them all with no notice. The watchdog proves that Grafana evaluates rules and sends notifications; delivery from IRM to the phone is not watched. Its period and grace time are settled in the Plan with the other thresholds (D8). It takes one of the free plan's 20 checks.

Rejected: no watchdog. Nothing to add, but a silent Grafana goes unnoticed until the owner opens it, while capture keeps losing minutes for good (D11). Rejected as well: a scheduled script outside Grafana, such as a Cloudflare Worker with a Cron Trigger, that asks Grafana's API whether it evaluates its alerts. It checks the same, with code of its own to maintain and one more credential.

#### D14. The synthetic check confirms a failure from two of three probes

The synthetic check of ALR4 reads the page's files from three probe locations, and ALR4 fires only when at least two of them find a file too old or cannot read it. This follows synthetic monitoring's practice of confirming a failure from several locations before alerting: a file's age is the same from every location, so a single failing probe points to its own network, and ALR4 is a page (D11), which must be reliable for the owner to keep answering it. Each probe counts against the Free tier's 100k check executions a month ([s018 › C4](../spikes/s018-monitoring-tool.md#d2-monitoring-tool)): a check every 5 min from three probes takes 25,920 a month. The check's frequency is settled in the Plan with the other thresholds (D8).

Rejected: one probe. A third of the executions, but a network failure at that probe pages the owner while visitors see a fresh page.

#### D15. Monitoring security threats

One STRIDE pass covers what this task adds to the tool that [s018 › D8](../spikes/s018-monitoring-tool.md#d8-monitoring-tool-security-threats) already covers (the account, the write tokens, logs on one more provider, a flooded ingest, an outage): the watchdog's signal and the notifications on the owner's phone. Repudiation is covered by R2 as the record (D1); alerts grant no permission, so there is no elevation of privilege.

| # | Threat (STRIDE) | Impact | Control | Requirement |
|---|---|---|---|---|
| `TH1` | Tampering: the watchdog's signal URL (ALR12) leaks | False signals keep the check green while Grafana is silent | The URL is kept only in Grafana's notification setting, never in code; it reaches that one check only and is rotated in Healthchecks.io; the risk is accepted as for the heartbeat ([s012 › TH11](../spikes/s012-execution-target.md#d3-pipeline-security)) | R37 |
| `TH2` | Information disclosure: a notification is read on a locked or lost phone | What fails and where is seen | Notifications carry IDs, system and version, never credentials or visitor data; their links lead to Grafana, behind sign-in with two-factor authentication (s018 › TH1) | R38 |

### 1.3 Requirements

<!-- Optional. The acceptance criteria, cited by number in the Test plan and the steps. They translate Decided at framing and cite the decision they come from; nothing is decided here.
One behaviour per requirement, verifiable, with a measurable threshold where one applies. Written in EARS:
- Ubiquitous: The <system> shall <response>.
- Event: When <trigger>, the <system> shall <response>.
- State: While <state>, the <system> shall <response>.
- Unwanted: If <condition>, then the <system> shall <response>.
- Optional: Where <feature is included>, the <system> shall <response>.
Only requirements specific to this task; project-wide rules (CLAUDE.md, ADRs) are not repeated. -->

- **R1** When capture or the pipeline writes a log event, of any level, the component shall send a copy of it to Grafana Cloud. (D1)
- **R2** The sending code of each component shall send every event with no list of the systems or events it sends. (D1)
- **R3** If a send to Grafana fails or reaches its time limit, then the component shall end the run with the same outcome and heartbeat signal as with a send that succeeds. (D2)
- **R4** The component shall write to R2 the same events whether or not the send to Grafana succeeds. (D2)
- **R5** If a send to Grafana has not ended within its time limit, set in the Plan, then the component shall abandon it. (D2)
- **R6** The component shall apply to the copy sent to Grafana the redaction of secrets of [d008 › Observability](d008-pipeline-platform-and-walking-skeleton.md#observability). (D2)
- **R7** When a runtime rule of severity error fails, Grafana shall raise ALR1 as a ticket, labelled with the rule's ID taken from the event. (D3, D4, D11)
- **R8** When a runtime rule of severity warn fails, Grafana shall raise ALR2 as a ticket, labelled with the rule's ID taken from the event. (D3, D4, D11)
- **R9** When the page's deployment fails, Grafana shall raise ALR3 as a ticket. (D3, D11)
- **R10** When at least two of the synthetic check's three probes find a published file older than DQM10's target, or cannot read it, Grafana shall raise ALR4 as a page. (D3, D8, D11, D14)
- **R11** When a feed has had no clean capture for more minutes in a row than ALR5's threshold, set in the Plan, Grafana shall raise ALR5 as a page. (D3, D11)
- **R12** When a system's DQM7 error budget burns at the fast burn rate set in the Plan, Grafana shall raise ALR6 as a page. (D3, D7, D11)
- **R13** When a system's DQM7 error budget burns at the slow burn rate set in the Plan, Grafana shall raise ALR6 as a ticket. (D3, D7, D11)
- **R14** When a pipeline run's `duration_s` or `peak_memory_mb` exceeds ALR7's share of its limit, set in the Plan, Grafana shall raise ALR7 as a ticket. (D3, D11)
- **R15** When a component has sent no event to Grafana for longer than ALR8's threshold, set in the Plan, Grafana shall raise ALR8 as a ticket. (D3, D11)
- **R16** When an event that the observability catalog marks as actionable, and that no other alert covers, reaches Grafana, Grafana shall raise ALR9 as a ticket. (D3, D5, D11)
- **R17** When an `index_refreshed` event lists `unknown_feeds`, Grafana shall raise ALR10 as a ticket. (D3, D11)
- **R18** When a pass logs a cause of a missed minute that D9's table does not list, Grafana shall raise ALR11 as a ticket. (D3, D9, D11)
- **R19** Grafana shall keep ALR12 always firing, signalling the heartbeat service once every period set in the Plan. (D13)
- **R20** If the heartbeat service receives no signal of ALR12 within its period and grace time, then the heartbeat service shall email the owner, at any hour. (D11, D13)
- **R21** When Grafana's use of a Free tier limit, logs a month or synthetic check executions, exceeds ALR13's threshold, set in the Plan, Grafana shall raise ALR13 as a ticket. (D3, D11)
- **R22** When an event that the observability catalog does not list reaches Grafana, Grafana shall raise ALR14 as a ticket. (D3, D5, D11)
- **R23** Each alert notification shall show the alert's ID and the catalog IDs it checks. (D4)
- **R24** Each alert notification shall link to the events in Grafana that raised it. (D4)
- **R25** The observability catalog shall list the common fields of [ADR-0036](../decisions/0036-log-convention-across-components.md), the heartbeat checks and, for every event of capture and the pipeline, its level, its own fields, whether it needs an action from the owner, and the alerts that read it. (D5)
- **R26** The observability catalog shall list every alert with its ID, the catalog IDs it checks and its urgency. (D4, D5, D11)
- **R27** The observability catalog shall give one name to the warning level of capture and the pipeline. (D5)
- **R28** When a capture of a system lists fewer than 95% of the median number of stations of that system's captures in the 7 days before its capture instant, the pipeline shall flag it under DQR12. (D6)
- **R29** While a system has fewer than 60 captures in the 7 days before a capture instant, the pipeline shall not evaluate DQR12 for that capture. (D6)
- **R30** The data quality catalog shall set DQM7's target to at least 99.5% of the minutes of each calendar month for AMBici and 97% for Bicing. (D7)
- **R31** DQM11 shall give each minute with no capture of a feed to the provider or to capture by the cause its pass logs, as D9's table sets. (D9)
- **R32** DQM11 shall leave out a minute captured but missing from the station stock. (D9)
- **R33** The data quality catalog shall set DQM11's target to at most 30 minutes given to capture per feed and calendar month, with no target on the minutes given to the provider. (D10)
- **R34** When a page other than ALR12 fires, Grafana shall notify the owner in the Grafana mobile app, at any hour, until the owner acknowledges it. (D11)
- **R35** When a ticket fires, Grafana shall add it to the app's list of alerts with no notification, until the owner closes it. (D11)
- **R36** Grafana shall show, over the last 14 days, the events of capture and the pipeline and the results of the synthetic check, in the browser and in the mobile app. (D1, D12)
- **R37** The watchdog's signal URL shall be kept only in Grafana's notification setting, never in code. (D15)
- **R38** Alert notifications shall carry no credentials and no visitor data. (D15)
- **R39** When a feed's minutes given to capture over the last 7 days, among the minutes capture's events reach Grafana, exceed 7, the 7-day share of DQM11's target, Grafana shall raise ALR15 as a ticket. (D3, D10, D11, #6, #13)
- **R40** Grafana shall show each feed's minutes given to the provider over the last 7 days, with no target. (D10, #6)
- **R41** Grafana's queries and alerts shall select events by the fields they carry, with no list of systems. (D1)
- **R42** While no event of capture has reached Grafana within ALR8's threshold, Grafana shall not raise ALR5 or ALR6. (D2, #10)
- **R43** If no heartbeat signal of capture arrives within 10 min plus 10 min of grace, then the heartbeat service shall email the owner; capture shall signal it from each pass whose scheduled minute is a multiple of 5, when that pass stored all three dynamic feeds. (#10)

### 1.4 Done when

<!-- Optional. Only what closes this task and Requirements cannot express: operational actions, checks on real data, understanding. The general closing rule is checked in `.claude/skills/implement/review.md`. -->

- When the owner creates the Grafana Cloud account, the three facts [s018 › D8](../spikes/s018-monitoring-tool.md#d8-monitoring-tool-security-threats) leaves unchecked are checked and recorded in Close: tokens scoped to writing logs only, a stack in an EU region, and a Free tier that needs no payment method.
- A test page rings on the owner's phone until acknowledged, and a test ticket appears in the app's list of alerts with no notification.
- With production data, after the merge: events of capture and of the pipeline reach Grafana, the watchdog's check is green in Healthchecks.io, and the synthetic check reads the page from its three probes.

### 1.5 Out of scope

<!-- Optional. What someone could expect and will not be done, each item pointing to the task that covers it. -->

- Dashboards per component and per part of each, built on the events in Loki — T060.10
- Alerts on DQM5, DQM8 and DQM9: the child builds each indicator, adds its target to the alerts and reviews it — T060.8
- Alerts on DQM4, the same way — T060.3
- Alerts on quarantined rows, once the quarantine table exists — T060.5
- Targets of DQM1–DQM3, rows of the review table — T060.6
- A project-wide threat catalog with global IDs (`THG`), and the threat ID on the alerts that detect one — T073
- The existing catalogs aligned with the reader's introduction every catalog opens with (#15) — T076

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

#### Grafana configuration

Grafana's alert rules, contact points, notification policies, synthetic check and watchdog are declared as code with Terraform and Grafana's official provider, and the owner applies them from the owner's machine, with Terraform's state kept there, ignored by Git ([ADR-0051](../decisions/0051-monitoring-configuration-as-code.md)). Each change is reviewed on a diff and checked in CI, and a lost or suspended account is recreated with one apply. Secrets, such as the watchdog's signal URL, enter as variables from `.env`, never in the code (R37). **#1**

#### Observability catalog

The observability catalog of D5 is a registry of events with its schema, and a document. `contracts/log-events.registry.json` is the registry, the single source of each event of every component: its component, level, own fields, whether it needs an action from the owner, and the alerts that read it by name. `contracts/log-events.schema.json`, a JSON Schema (draft 2020-12) that the registry names in `$schema`, fixes the shape of an entry, and the registry test validates the registry against it. The registry is reference data written in the repository and read by several components, not data one component sends another, so it has no test vectors ([ADR-0050](../decisions/0050-contract-tests-by-contract-kind-with-native-schemas.md) covers the latter). `docs/observability.md`, beside `docs/data-quality.md`, holds the rest: the common fields of ADR-0036, the heartbeat checks, the alerts with their IDs, the catalog IDs they check and their urgency, and how alerts on an error budget work; it links to the registry for the events, and an alert's row does not list them. Terraform reads the registry to build each alert's event selector from the events that list it; ALR9 takes the events with `needs_action` that list no alert, and ALR14 every event the registry does not hold, so no event list is written by hand. The tests of capture and the pipeline check that every event they write is registered, and Terraform's tests that every alert ID the registry lists is an alert it declares. **#2** **#14**

`docs/observability.md` opens as every catalog does ([docs › Catalogs](../../.claude/rules/docs/general.md)); its worked example follows one event from its registry entry to the alert that reads it and the notification on the owner's phone. **#15**

`docs/observability.md` also holds the LogQL query of each feed's minutes given to the provider over the last 7 days, run in Grafana's Explore (R40); Grafana's dashboards are designed in T060.10, which may turn the query into a panel. **#12**

A component, including a later one such as the page, adds its events to the registry in the design that designs its logs. `docs/observability.md` states the criterion by which an event needs an action from the owner; the registry test keeps an unclassified event from passing CI, and the path rule `.claude/rules/docs/observability.md`, scoped to the catalog's two files, holds the conventions for writing an entry, as `.claude/rules/docs/data-model.md` does for the data model. **#3**

#### Warning level

Every component writes `warn` for a failure that does not affect the data, OpenTelemetry's short severity name; capture, which wrote `warning`, changes to it, with its log contract. Capture's logs already in R2 keep `warning`, since logs are append-only, and the catalog records the version and date of the change, so that SQL over older logs accepts both. Capture's change is deployed no later than its sending to Grafana, so Grafana only receives `warn`. **#4**

#### Field mapping

Each event maps to an OTLP log record, and Grafana turns only fields with few values into Loki labels, following Loki's practice of low-cardinality labels; every other field stays as structured metadata, which queries filter on as well:

| ADR-0036 field | OTLP | Loki |
|---|---|---|
| `component` | resource `service.name` | label `service_name` |
| `version` | resource `service.version` | structured metadata |
| `ts` | `timeUnixNano` | the record's time |
| `level` | `severityText` and `severityNumber` (9 `info`, 13 `warn`, 17 `error`) | label `detected_level` |
| `event` | attribute | label |
| `system`, `feed`, `rule` | attributes | labels |
| `run_id` and every other own field | attributes | structured metadata |
| the JSON line | body | the line shown |

Which attributes Grafana Cloud promotes to labels is checked at account set-up with the Free tier features; an attribute that cannot be promoted stays as structured metadata, which queries and alerts filter the same way, only less fast.

Every component names the bike sharing system `system` in its log events, as the pipeline does and as GBFS names it ([ADR-0040](../decisions/0040-model-vocabulary-from-gbfs-3-0.md)); capture, which wrote `source`, changes its log events and its log contract with #4, while its code and bronze keys keep `source`. Capture's logs already in R2 keep `source`, and the catalog records the change as for #4. **#5**

#### Error budget alerts

ALR6 follows the SRE Workbook's multiwindow, multi-burn-rate alert, written as LogQL alert rules over capture's events. For each system and window, the error rate is one minus the minutes with a `feed_captured` over the minutes DQM7 counts in the window in which capture's events reach Grafana, those with any event of capture. A minute with no event of capture, whether a pass the cron never ran or a gap in Grafana's ingest, counts in no window: Grafana cannot tell the two apart, capture's heartbeat reports a capture that stores nothing (#10), and DQM7's monthly value over R2 counts every minute. The burn rate is that error rate over the system's budget, one minus its DQM7 target (D7). A level fires when both its windows exceed its burn rate: the long one shows the burn is serious, the short one that it is still going on.

| Level | Burn rate | Long window | Short window | Budget spent in the long window |
|---|---|---|---|---|
| Page | 14.4 | 1 h | 5 min | 2% |
| Page | 6 | 6 h | 30 min | 5% |
| Ticket | 1 | 3 d | 6 h | 10% |

A Terraform module builds the three levels from each system's target, so a new system or target is one variable; every window fits Grafana's 14 days. The budget left in the month is queried with SQL over R2, as DQM11's month is (#6). **#7** **#13**

- **What would change it:** a longer retention, from a paid plan, or many more SLOs: Grafana's SLO app then gives its budget view, with the same queries kept as Loki recording rules; the alert, its ID and its requirements are unchanged.

#### Thresholds

Each threshold is a formula over the settings it depends on, never a figure measured on the walking skeleton, so a change of cadence, time budget or container size changes every threshold that depends on it with no rewrite; the measured figures only show that each alert stays quiet today.

| Threshold | Formula | Today | Measured today |
|---|---|---|---|
| ALR4, age of a published file | cadence + time budget, DQM10's target (D8) | 22 min | 19.6 min at most |
| Synthetic check frequency | fixed, while the cadence is longer than it | 5 min | — |
| ALR7, run duration (`duration_s`) | 80% of the timeout | 480 s | 127 s at the median, 421 s at most, in steady state (D8) |
| ALR7, run memory (`peak_memory_mb`) | 80% of the container's memory, converted from Modal's MiB to the field's decimal MB | 3,436 MB | 2,472 MB at most |
| ALR8, pipeline silent in Grafana | 2 × cadence | 30 min | — |
| Pipeline's send time limit (R5) | fixed, one attempt | 10 s | — |
| ALR5, minutes in a row with no clean capture of a feed | fixed: capture's cadence is one pass a minute ([d004](d004-bronze-data-capture.md)) | over 10 | 5 at most, any cause |
| ALR8, capture silent in Grafana | fixed | 5 min with no event | — |
| Capture's send time limit (R5) | fixed, one attempt, as capture's heartbeat | 10 s | — |
| ALR13, logs of the month | 80% of the Free tier's 50 GB | 40 GB | about 200 MB a month (D1) |
| ALR13, synthetic check executions of the month | 80% of the Free tier's 100k | 80k | 25,920 a month (D14) |
| ALR12, watchdog signal | the watchdog policy's `repeat_interval` | 5 min | — |
| Watchdog check in Healthchecks.io | period and grace | 5 min and 10 min | — |

ALR4 fires at the target itself, since the target is what the page promises its visitor. ALR7 follows the practice of warning at 80% of a capacity limit, the timeout and the container's memory, which end a run. The time budget is not such a limit: a run stops taking batches there and finishes the one under way, so a run that catches up reaches it, as one steady-state run did at 421 s. Runs that grow towards the timeout as later children add models raise ALR7, which is the signal to review the cadence or the budget. ALR8 at two cadences lets one lost send go, since the copy is best-effort (D2); a run that never starts is reported by the heartbeat. The pipeline's send uses the per-attempt timeout of the heartbeat's pings ([d008 › Observability](d008-pipeline-platform-and-walking-skeleton.md#observability)). ALR5 at twice the longest run measured stays quiet in normal operation; on AMBici the fast burn of ALR6 fires first, so ALR5 serves Bicing, whose budget is larger, and the feeds DQM7 does not count. ALR8 at five passes with no event points to a broken send rather than a single failure, and is the window of R42. ALR13 warns at 80% of each Free tier limit, as ALR7 does, reading Grafana Cloud's usage data source; if the Free tier lacks it, which account set-up checks with the other Free tier features, Grafana Cloud's own usage notifications cover it, as for Cloudflare and Modal (D3). A Grafana that stops evaluating or notifying is reported by email in about 15 min, the grace covering one lost signal; the watchdog takes the third of Healthchecks.io's 20 free checks. **#8**

The pipeline's cadence, time budget, timeout and container memory live in one data file, `pipeline/src/bikesharing/core/run_settings.json`: the core parses it into typed settings and the shell reads it once, as the functional core and imperative shell set ([ADR-0046](../decisions/0046-functional-core-imperative-shell-for-the-pipeline.md)), for the run and for Modal's app and image files, which take the schedule, the timeout and the container memory from it; Terraform reads it with `jsondecode(file(...))`, so the pipeline and its thresholds change together. The period and grace of the heartbeat's check stay in Healthchecks.io's console, outside Terraform (ADR-0051), and the catalog states that a change of cadence also changes them there. **#9**

#### Synthetic check

ALR4's synthetic check is a scripted k6 check, as [s018 › P1](../spikes/s018-monitoring-tool.md#23-production-inputs) sets, that reads each file the page serves and measures its data's age as the time since its `data_instant`, the age of the data a visitor sees, which DQM10 measures (D8). A probe fails when that age exceeds ALR4's threshold, or when the file cannot be read or parsed. The file's `Last-Modified` header is not used: every run deploys, with or without new batches ([d008 › #19](d008-pipeline-platform-and-walking-skeleton.md#22-decision-summary)), so a stuck pipeline would redeploy old data under a fresh header. The files are a Terraform variable, today `latest-station-count.json` only; a child that publishes another file adds it.

#### Notifications

Every notification uses one message template of the project's own, managed by Terraform, since Grafana's default lists every label, annotation and value, which is long on a phone and cannot build links to the catalogs. The template reads only the alert's labels and annotations, never an event's body (R38), and its layout is stated in `docs/observability.md`:

```text
[FIRING] [ALR5] A feed has had no clean capture for too many minutes in a row
  capture · system: bicing · feed: station_status · version: 7f3c2a9
  14 minutes in a row · threshold: over 10 · since 11:12 CET
  → rule in the catalog   → this alert   → events in Grafana
```

- **First line:** the state, the alert's ID and summary, and the catalog IDs it checks, when it checks any (R23).
- **Second line:** where it happens: the component, system, feed and version, those the alert carries.
- **Third line:** the value that raised the alert and its threshold, when it has one, and since when, in Madrid's local time with its zone, `CET` or `CEST`, converted by the template's `tz` and `date` functions from the alert's UTC time; stored times stay in UTC. If account set-up finds those functions missing, the line shows UTC.
- **Links:** the section of `docs/data-quality.md` that holds the checked item (Runtime rules for a `DQR`, Quality indicators for a `DQM`), the alert's row in `docs/observability.md`, and Grafana's Explore on the events that raised it, filtered by their labels and time (R24). The links to the catalogs open the repository on GitHub, whose base URL is a Terraform variable.

The rule's text is not copied into the notification: the summary names the kind of failure, and the item is one tap away, so its text lives in its catalog only. **#11**

#### Watchdog

ALR12 is an alert rule whose condition always holds, with a notification policy of its own that sends it every 5 min, its `repeat_interval`, to a webhook contact point on the watchdog's check in Healthchecks.io, never through IRM (D13). That policy is the first in the tree and matches `alert_id = "ALR12"` with no `continue`, so the policy for pages never routes ALR12 to IRM, although it carries `urgency = "page"` as D11 sets. The check's URL enters Terraform as a sensitive variable from `.env` (R37).

#### Volume drop

DQR12 follows D6 in the model `capture_volume`: the median takes the captures of the 7 days before each capture instant, and a capture is flagged below 95% of it, with the minimum of 60 captures unchanged. The history the shell reads from `processed_objects` widens from 24 h to 7 days before the batch's first capture, about 20,000 rows, and the model's dbt unit tests take the new window and threshold. **refines [d008 › D4](d008-pipeline-platform-and-walking-skeleton.md#d4-volume-drop-against-a-rolling-median)**

#### Notification grouping

Notifications follow Alertmanager's grouping, which Grafana Alerting implements: an alert fires one instance per set of labels and stays firing while its condition holds, the notification policy groups instances by alert ID and system into one notification, repeats it every 4 h while it fires, Grafana's default `repeat_interval`, and sends one notice when it resolves. A page's repeats join its alert group in IRM, which notifies until the owner acknowledges it, so a failure that lasts hours pages once per alert and system.

#### Capture silence

Grafana cannot tell a capture that stores nothing from a capture whose send is broken: both reach it as no events. ALR5 and ALR6 are therefore evaluated only while capture's events reach Grafana, and a capture silent altogether raises ALR8 instead, so a broken send or an outage of Grafana's ingest never pages the owner for data that R2 holds, and its minutes count in no window of ALR6 or ALR15 once events return (#13). Whether data is being stored is checked from outside Grafana by capture's heartbeat, a dead man's switch that signals only when a pass stored all three dynamic feeds: capture signals it from the pass of every fifth minute, by the pass's scheduled time, so the Worker keeps no state between passes, and Healthchecks.io emails the owner when no signal arrives within a period of 10 min plus 10 min of grace, so a capture that stores nothing is reported in about 20 min. A single failed signal, such as one of Bicing's scattered 403s, is covered by the next ones within the grace. **#10** **refines [d004 › D10](d004-bronze-data-capture.md#d10-capture-heartbeat)**

#### Sending the copy

Each component sends its events over OTLP/HTTP with JSON encoding, as [ADR-0049](../decisions/0049-log-events-copied-to-monitoring-over-otlp.md) sets, in one request per pass or run, after writing them to R2 (D2):

- **Capture:** after the pass's log is written to R2 and its heartbeat sent, the Worker sends the pass's events inside `ctx.waitUntil`, aborted at the send's time limit. The token is a Worker secret.
- **Pipeline:** after the run's log is uploaded to R2 and its heartbeat pinged, the run sends its events, aborted at the send's time limit. The token is a Modal Secret of the scheduled function only ([d008 › Observability](d008-pipeline-platform-and-walking-skeleton.md#observability)).

A send that fails or reaches its limit is written to the platform's own logs, Workers Logs or stdout as `log_upload_failed` is, and changes nothing else: the R2 log is already written and the outcome and heartbeat signal are already set (R3–R5).

The copy is built from the same JSON lines written to R2, never serialized again, so each line reaches Grafana as the body of its record and the redaction each component applies before writing reaches the copy with no code of its own (R4, R6). The pipeline's copy also carries the events emitted after the upload, `log_upload_failed` and `heartbeat_failed`, which the R2 log cannot hold, so that ALR9 reads them; capture pings its heartbeat before writing its log, so its copy is the R2 log's lines.

### 2.2 Decision summary

<!-- It logs decisions about the plan, including changes. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Applies to: anchor link(s) to the section where the decision is applied, named in one or two words.
- Decided at: the Status phase where it was decided (Plan, Steps), or `<phase> review` when decided while reviewing that phase.
- R: Requirement affected.
-->

| # | Applies to | Decision | Reason | R | Decided at |
|---|---|---|---|---|---|
| 1 | [Grafana configuration](#grafana-configuration) | Grafana's alerting, synthetic check and watchdog as code with Terraform and Grafana's official provider, applied by the owner (Infrastructure as Code); [ADR-0051](../decisions/0051-monitoring-configuration-as-code.md) | Reviewed on a diff, checked in CI, recreated with one apply | R7–R22, R34, R35, R37 | Plan |
| 2 | [Observability catalog](#observability-catalog), [D5](#d5-one-observability-catalog-built-here) | The catalog's events in a machine-readable registry, `contracts/log-events.registry.json`, its single source, validated against its JSON Schema `contracts/log-events.schema.json`; `docs/observability.md` holds the rest and links to it (a registry as in OpenTelemetry's semantic conventions, validated by its schema as configuration files are) **→ #14** | Terraform and the components' tests read the same list; each fact lives in one place; a malformed entry fails CI | R16, R22, R25, R26 | Plan |
| 3 | [Observability catalog](#observability-catalog) | The criterion for classifying an event in `docs/observability.md`, enforced by the registry test, with a path rule for writing entries; no line in the design template (poka-yoke) | The test already blocks an unclassified event; the template would repeat it in every design | R16, R22, R25 | Plan |
| 4 | [Warning level](#warning-level) | `warn` for every component, OpenTelemetry's short severity name; capture changes from `warning`, and its logs in R2 are not rewritten (append-only logs) **refines [d004 › D9](d004-bronze-data-capture.md#d9-capture-logs)** | One name in queries from now on; the record stays as written | R27 | Plan |
| 5 | [Field mapping](#field-mapping) | `system` for the bike sharing system in every component's log events; capture changes from `source` in its logs only (one name per concept, as OpenTelemetry's semantic conventions, in ADR-0040's vocabulary) **refines [d004 › D9](d004-bronze-data-capture.md#d9-capture-logs)** | Queries by system cover every component with one field | R41 | Plan |
| 6 | [D10](#d10-a-target-on-captures-own-missed-minutes-only), [D3](#d3-alerts-on-symptoms-that-need-action) | ALR15 and the provider's minutes over a rolling 7 days in Grafana, from capture's events; DQM11's monthly value queried with SQL over R2 (alerts on rolling windows, SLO period measured from the durable store) **→ #13** | Grafana keeps 14 days; the pipeline needs no access to capture's logs | R39, R40 | Plan |
| 7 | [Error budget alerts](#error-budget-alerts) | ALR6 as LogQL alert rules built by a Terraform module, with the SRE Workbook's multiwindow, multi-burn-rate levels; not Grafana's SLO app **→ #13** | Fewer parts, every window within 14 days; moving to the SLO app later keeps the same queries | R12, R13 | Plan |
| 8 | [Thresholds](#thresholds) | The pipeline's thresholds as formulas over its cadence, time budget and container (ALR4 at DQM10's target, ALR7 at 80% of each limit, ALR8 at 2 cadences), a 5-minute synthetic check; capture's ALR5 over 10 minutes in a row and ALR8 at 5 min; each component's send limited to its heartbeat's timeout, 10 s; ALR13 at 80% of each Free tier limit; the watchdog signalling every 5 min to a check with 10 min of grace | Thresholds follow the pipeline as it grows and its cadence is tuned, with no rewrite; the others stay quiet at what production shows and warn with margin | R5, R10, R11, R14, R15, R19, R20, R21 | Plan |
| 9 | [Thresholds](#thresholds) | The pipeline's run settings in one JSON data file read by the pipeline and by Terraform (single source of truth, configuration as data) | A change of cadence is one edit; no copy to keep aligned | R10, R14, R15 | Plan |
| 10 | [Capture silence](#capture-silence) | ALR5 and ALR6 only while capture's events reach Grafana; a silent capture raises ALR8, and capture's heartbeat on every fifth pass, with 10 min of period and 10 min of grace, reports a capture that stores nothing (dead man's switch) **refines [d004 › D10](d004-bronze-data-capture.md#d10-capture-heartbeat)** | No page for a broken send; a dead capture reported in about 20 min instead of 2 h | R11, R12, R13, R15, R42, R43 | Plan |
| 11 | [Notifications](#notifications) | A message template of the project's own: alert ID, summary and checked IDs; where; the value against its threshold and since when, in Madrid's local time; then links to the item's catalog section, the alert's row and its events; no rule text copied (link, don't copy; actionable alerts show the value that fired) | Read on a phone, enough to tell a page from a wait; the item's text lives in its catalog only | R23, R24, R38 | Plan |
| 12 | [Observability catalog](#observability-catalog) | The provider's 7-day minutes as a LogQL query in `docs/observability.md`, run in Explore; no dashboard in this task (dashboards in T060.10) | Meets R40 with what Grafana ships, leaving every dashboard decision to the task that designs them | R40 | Plan |
| 13 | [Error budget alerts](#error-budget-alerts), [D10](#d10-a-target-on-captures-own-missed-minutes-only) | ALR6's and ALR15's windows count only the minutes with an event of capture in Grafana; a minute with none is left to capture's heartbeat and to SQL over R2 (an SLI over valid events, SRE Workbook) **refines #6** **refines #7** | A gap in Grafana's ingest pages no one for data R2 holds, and leaves no alert blind for days | R12, R13, R39 | Plan review |
| 14 | [Observability catalog](#observability-catalog) | Each registry event lists the alerts that read it by name; Terraform builds every alert's event selector from it, and ALR9 from the events with `needs_action` that list none; an alert's row in `docs/observability.md` lists no events (single source of truth) **refines #2** | No hand-written exclusion list for ALR9, and the link between alerts and events lives in one place | R16, R25 | Plan review |
| 15 | [Observability catalog](#observability-catalog) | Every catalog opens with what it holds and what for, how to read an entry, and one worked example, as a rule in `.claude/rules/docs/general.md`; `docs/observability.md` follows it, the existing catalogs are aligned in T076 (Diátaxis: reference with an explanatory entry point) | A reader new to the project understands the catalog without the designs | R25 | Plan review |

### 2.3 Architecture

<!-- Optional. One diagram and 2–3 sentences. -->

### 2.4 File layout

<!-- Every file and folder the task creates or modifies, documents included, as a tree: (new) or (modified), and its purpose or change in one line. A task that adds a component also lists its CI job in `.github/workflows/ci.yml` (recipe in `.claude/rules/code/ci.md`), and its version files, manifest and lockfile (`.claude/rules/code/dependencies.md`). -->

```text
.
├── CLAUDE.md                                   (modified)  Project structure: monitoring/ and the event registry in contracts/
├── .env.example                                (modified)  Empty Terraform variables: Grafana's tokens, the watchdog's check URL
├── .gitignore                                  (modified)  Terraform's state and .terraform/
├── .claude/
│   ├── settings.json                           (modified)  Allows monitoring's check command
│   └── rules/
│       ├── code/
│       │   ├── terraform.md                    (new)       Terraform language and monitoring component rules (#1)
│       │   ├── dependencies.md                 (modified)  Terraform row: versions.tf, .terraform.lock.hcl, .terraform-version
│       │   ├── ci.md                           (modified)  Terraform's setup and lockfile install in a component job
│       │   └── testing.md                      (modified)  monitoring/** in scope; the event registry, a reference document validated by its schema
│       └── docs/
│           ├── general.md                      (modified)  Catalogs open with what they hold, how to read an entry and a worked example (#15)
│           └── observability.md                (new)       Conventions for writing a catalog entry (#3)
├── .github/workflows/
│   └── ci.yml                                  (modified)  Job monitoring; the registry and its schema in the filters of capture, pipeline and monitoring
├── contracts/
│   ├── log-events.registry.json                (new)       Every component's events: component, level, own fields, needs action, alerts that read it (#2, #14)
│   ├── log-events.schema.json                  (new)       JSON Schema (draft 2020-12) of a registry entry (#2)
│   └── capture-logs.json                       (modified)  Vectors with warn and system (#4, #5)
├── monitoring/                                 (new)       Grafana Cloud configuration as code (#1)
│   ├── .terraform-version                      (new)       Terraform version pin
│   ├── .terraform.lock.hcl                     (new)       Provider lockfile
│   ├── versions.tf                             (new)       required_version range and Grafana's provider
│   ├── providers.tf                            (new)       Provider configuration from variables
│   ├── variables.tf                            (new)       Stack, tokens, watchdog URL (sensitive), GitHub base URL, published files, systems' targets
│   ├── locals.tf                               (new)       Reads the event registry and the pipeline's run settings; derives the thresholds (#8, #9)
│   ├── alert_rules.tf                          (new)       ALR rules, ALR12's watchdog rule included
│   ├── contact_points.tf                       (new)       Email, IRM and the watchdog's webhook
│   ├── notification_policies.tf                (new)       Grouping by alert ID and system, repeat intervals, the watchdog's policy
│   ├── message_template.tf                     (new)       The notification template resource (#11)
│   ├── templates/notification.tmpl             (new)       The notification layout (#11)
│   ├── synthetic_check.tf                      (new)       ALR4's scripted k6 check
│   ├── checks/published_file_age.js            (new)       k6 script: each published file's data age against ALR4's threshold
│   ├── modules/error_budget_alert/
│   │   ├── main.tf                             (new)       ALR6's three burn-rate levels for one system (#7)
│   │   └── variables.tf                        (new)       System and target
│   ├── tests/
│   │   └── alerting.tftest.hcl                 (new)       terraform test with a mocked provider
│   └── scripts/check-monitoring.sh             (new)       fmt -check, validate and test, as CI runs it
├── capture/
│   ├── package.json, package-lock.json         (modified)  @cfworker/json-schema, a JSON Schema validator that runs in workerd, as a dev dependency
│   ├── wrangler.jsonc                          (modified)  OTLP endpoint as a variable
│   ├── vitest.config.js                        (modified)  A simulated OTLP endpoint that answers 2xx and keeps each request's body for the tests to read
│   ├── src/
│   │   ├── otlp.js                             (new)       Builds the OTLP/HTTP JSON request from the pass's lines and sends it within its limit
│   │   ├── fetch.js                            (modified)  otlpTimeoutMs, 10 s, in LIMITS
│   │   ├── log.js                              (modified)  warn in the level type (#4); toLines serializes the events once, for the log and the copy
│   │   ├── schedule.js                         (modified)  The heartbeat at every minute that is a multiple of 5, by the pass's scheduled time (#10)
│   │   ├── pass.js                             (modified)  warn and system in the events it logs (#4, #5); sends the copy after the log and the heartbeat
│   │   └── worker.js                           (modified)  The send inside ctx.waitUntil; the token as a Worker secret
│   └── test/
│       ├── unit/otlp.test.js                   (new)       Request built from the lines; failed or late send changes nothing
│       ├── unit/log.test.js, unit/schedule.test.js (modified) warn and toLines; the heartbeat at every fifth minute
│       ├── integration/pass.test.js            (modified)  warn and system; the heartbeat at :05; order: log, heartbeat, copy
│       ├── integration/pass-failures.test.js   (modified)  warn and system
│       └── contract/log-events-registry.test.js (new)      Registry valid against its schema; every capture event registered
├── pipeline/
│   ├── modal_image.py                          (modified)  The monitoring token's Modal Secret; container memory and timeout from settings, and run_settings.json added to the image (#9)
│   ├── modal_app.py                            (modified)  That Secret on the scheduled function only; the schedule from the cadence in settings (#9)
│   ├── src/bikesharing/
│   │   ├── core/run_settings.json              (new)       Cadence, time budget, timeout and container memory (#9)
│   │   ├── core/settings.py                    (modified)  RunSettings and its pure parser; TIME_BUDGET moves into it
│   │   ├── core/events.py                      (modified)  otlp_send_failed, at warn, stdout only; log_upload_failed to stdout and the copy
│   │   ├── core/otlp_payload.py                (new)       Builds the OTLP/HTTP JSON request from the run's lines
│   │   ├── shell/event_log.py                  (modified)  lines(): every kept line, for the copy
│   │   ├── shell/otlp_exporter.py              (new)       Sends it within its limit, one attempt; raises on failure
│   │   ├── shell/run_settings.py               (new)       Reads run_settings.json once into RUN_SETTINGS
│   │   └── shell/run.py                        (modified)  Sends the copy after the log upload and the ping, a failure to stdout; OTLP target in the scheduled config; 7-day volume history (DQR12)
│   ├── dbt/models/silver/
│   │   ├── capture_volume.sql                  (modified)  7-day median, 95% threshold (DQR12)
│   │   └── silver.yml                          (modified)  capture_volume's unit tests for the new window and threshold
│   └── tests/
│       ├── unit/core/test_otlp_payload.py      (new)       Request built from the lines
│       ├── unit/core/test_settings.py          (new)       Settings parsed from data; invalid data rejected
│       ├── unit/core/test_events.py            (modified)  otlp_send_failed
│       ├── integration/test_event_log.py       (modified)  lines(): every kept line, in order
│       ├── integration/test_otlp_exporter.py   (new)       Failed or late send changes nothing
│       ├── integration/test_run.py             (modified)  Copy sent after the log upload and the ping, with log_upload_failed and heartbeat_failed
│       └── integration/test_log_events_registry_contract.py (new) Registry valid against its schema; every pipeline event registered
└── docs/
    ├── observability.md                        (new)       The catalog: introduction and worked example, common fields, heartbeat checks, alerts, error budgets, notification layout, the provider's minutes query (#2, #3, #11, #12)
    ├── data-quality.md                         (modified)  DQM7, DQM10, DQM11 and DQR12
    ├── architecture.md                         (modified)  Monitoring as a building block, and its deployment
    ├── testing-strategy.md                     (modified)  The monitoring component and the registry tests
    ├── decisions/
    │   └── 0051-monitoring-configuration-as-code.md (new)  Monitoring configuration as code with Terraform (#1)
    └── designs/
        ├── d004-bronze-data-capture.md         (modified)  Links to the catalog
        └── d008-pipeline-platform-and-walking-skeleton.md (modified) Links to the catalog
```

### 2.5 Components

<!-- Optional. One subsection per component. The contract is exact, in the component's own language, never pseudocode. -->

#### OTLP request mapping

Both components build the same OTLP/HTTP JSON `ExportLogsServiceRequest` from a pass's or run's JSON lines, following [Field mapping](#field-mapping):

- **Resources:** one `resourceLogs` per distinct `component` and `version`, in order of first appearance, with resource attributes `service.name` and `service.version`; one `scopeLogs` in each, with scope name the component.
- **Records:** one log record per line, in order: `timeUnixNano` from `ts`, as a decimal string; `severityText` the `level`, and `severityNumber` 9, 13 or 17; `body` the line itself as `stringValue`, never serialized again (R6).
- **Attributes:** every field of the line except `ts`, `level`, `component` and `version`, in the line's order: a string as `stringValue`, a boolean as `boolValue`, an integer as `intValue` (a decimal string), any other number as `doubleValue`, an array or object as `stringValue` with its JSON; a `null` field is left out.
- **Empty:** no lines, no request.

#### Capture's OTLP sender

- **Responsibility:** builds the pass's OTLP request from its lines and sends it once within its time limit, never throwing.
- **Location:** `capture/src/otlp.js`
- **Contract:**

```js
/**
 * @typedef {object} OtlpTarget
 * @property {string} endpoint `OTLP_ENDPOINT` variable: Grafana Cloud's OTLP/HTTP logs URL, ending in `/v1/logs`
 * @property {string} token    `OTLP_TOKEN` secret: the Basic credential, base64 of `<instance ID>:<token>`
 */

/**
 * @typedef {{ errorType: 'http' | 'timeout' | 'network', status: number | null, error: string }} OtlpSendFailed
 */

/** OTLP severity number of each level (OpenTelemetry Logs data model). */
export const SEVERITY_NUMBER = Object.freeze({ info: 9, warn: 13, error: 17 });

/**
 * The pass's `ExportLogsServiceRequest`, as the OTLP request mapping sets. Pure.
 * @param {string[]} lines The pass's JSON lines, as written to R2, without their newline
 * @returns {object}
 */
export function buildLogsRequest(lines) {}

/**
 * One POST of `buildLogsRequest(lines)` to `target.endpoint`, with `Authorization: Basic <token>`,
 * aborted by `AbortSignal.timeout(limits.otlpTimeoutMs)`, 10 s in production. Never throws.
 * @param {OtlpTarget} target
 * @param {string[]} lines
 * @param {{ otlpTimeoutMs: number }} limits
 * @returns {Promise<OtlpSendFailed | null>} `null` when Grafana answers 2xx, or when there are no lines
 */
export async function sendLogs(target, lines, limits) {}
```

- **Callers:** `log.js` exports `toLines(events)`, each event's `JSON.stringify`, and `writeLog` takes those lines; `pass.js` serializes the pass's events once and, after the log and the heartbeat, passes the same lines to `sendLogs` inside `ctx.waitUntil`. A failure is written to Workers Logs only, with `console.log`, as the event `otlp_send_failed` at `warn` with `error_type`; the pass's outcome does not change (R3–R5).

#### Pipeline's OTLP payload and exporter

- **Responsibility:** the core builds the run's OTLP request from its lines; the shell sends it once within its time limit and raises on any failure.
- **Location:** `pipeline/src/bikesharing/core/otlp_payload.py`, `pipeline/src/bikesharing/shell/otlp_exporter.py`
- **Contract:**

```python
# core/otlp_payload.py
SEVERITY_NUMBER: Final[Mapping[str, int]] = MappingProxyType(
    {"info": 9, "warn": 13, "error": 17}
)

def logs_request(lines: Sequence[str]) -> dict[str, Any]:
    """The run's ExportLogsServiceRequest, as the OTLP request mapping sets."""

# shell/otlp_exporter.py
@dataclass(frozen=True)
class OtlpTarget:
    endpoint: str  # OTLP_ENDPOINT: Grafana Cloud's OTLP/HTTP logs URL, ending in /v1/logs
    token: str  # OTLP_TOKEN: the Basic credential, base64 of <instance ID>:<token>

def send_logs(
    target: OtlpTarget, lines: Sequence[str], *, timeout_s: float = 10.0
) -> None:
    """One POST of logs_request(lines) with urllib; returns at once with no lines.

    Raises OSError on a non-2xx answer, a timeout or a network error.
    """
```

- **Callers:** `EventLog.lines() -> tuple[str, ...]` returns every kept line, in order; read after the heartbeat ping, it holds the lines `body()` uploaded followed by any `log_upload_failed` or `heartbeat_failed`. `scheduled_config` reads `OTLP_ENDPOINT` and `OTLP_TOKEN` into the run's configuration as an `OtlpTarget`; `one_off_config` sets none, so a one-off run sends nothing. `run` sends after the log upload and the heartbeat ping, and catches any exception as it does for the upload, emitting `otlp_send_failed(ts, *, error_type)` at `warn`, to stdout only; the outcome does not change (R3–R5).

#### Pipeline's run settings

- **Responsibility:** the core parses the run settings and checks them; the shell reads their file once (#9).
- **Location:** `pipeline/src/bikesharing/core/run_settings.json`, `pipeline/src/bikesharing/core/settings.py`, `pipeline/src/bikesharing/shell/run_settings.py`
- **Contract:**

```json
{ "cadence_min": 15, "time_budget_s": 420, "timeout_s": 600, "container_memory_mib": 4096 }
```

```python
# core/settings.py
@dataclass(frozen=True)
class RunSettings:
    cadence: timedelta
    time_budget: timedelta
    timeout: timedelta
    container_memory_mib: int

def parse_run_settings(data: Mapping[str, object]) -> RunSettings:
    """Parse the decoded run_settings.json.

    Raises ValueError when a key is missing or unknown, a value is not a
    positive integer, cadence_min does not divide 60, or the time budget is
    not below the timeout and the timeout below the cadence (d008 D6).
    """

def schedule_cron(settings: RunSettings) -> str:
    """The run's cron expression, "*/<cadence_min> * * * *"."""

# shell/run_settings.py
RUN_SETTINGS: Final[RunSettings]  # parse_run_settings of the file, read once at import
```

- **Callers:** `run.py` takes the time budget from `RUN_SETTINGS`, which replaces `settings.TIME_BUDGET`; `modal_image.py` sets `MEMORY_MIB` and `TIMEOUT_S` from it, and `modal_app.py` its schedule with `schedule_cron`, so `modal_one_off.py` keeps importing the same names unchanged.

#### Event registry schema

- **Responsibility:** fixes the shape of the event registry, which names it in `$schema`.
- **Location:** `contracts/log-events.schema.json`
- **Contract:**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "log-events.schema.json",
  "title": "Log events registry",
  "type": "object",
  "required": ["$schema", "events"],
  "additionalProperties": false,
  "properties": {
    "$schema": { "const": "./log-events.schema.json" },
    "events": { "type": "array", "minItems": 1, "items": { "$ref": "#/$defs/event" } }
  },
  "$defs": {
    "name": { "type": "string", "pattern": "^[a-z][a-z0-9]*(_[a-z0-9]+)*$" },
    "event": {
      "type": "object",
      "required": ["event", "component", "level", "fields", "needs_action", "alerts", "description"],
      "additionalProperties": false,
      "properties": {
        "event": { "$ref": "#/$defs/name" },
        "component": { "enum": ["capture", "pipeline"] },
        "level": { "enum": ["info", "warn", "error"] },
        "fields": {
          "type": "array",
          "uniqueItems": true,
          "items": {
            "$ref": "#/$defs/name",
            "not": { "enum": ["ts", "level", "component", "version", "run_id", "event"] }
          }
        },
        "needs_action": { "type": "boolean" },
        "alerts": {
          "type": "array",
          "uniqueItems": true,
          "items": { "type": "string", "pattern": "^ALR[1-9][0-9]*$" }
        },
        "description": { "type": "string", "minLength": 1 }
      }
    }
  }
}
```

- **Beyond the schema:** each pair of `component` and `event` appears once, which JSON Schema cannot express; the registry tests of capture and the pipeline check it with the other rules of [Observability catalog](#observability-catalog). A later component adds itself to the `component` enum.

#### Error budget alert module

- **Responsibility:** builds ALR6's three burn-rate levels for one system as one Grafana rule group (#7).
- **Location:** `monitoring/modules/error_budget_alert/`
- **Contract:**

```hcl
# variables.tf
variable "system" {
  description = "Bike sharing system the alert covers, as capture's events name it in `system`."
  type        = string
}

variable "target" {
  description = "The system's DQM7 target as a fraction; its budget is 1 - target."
  type        = number
  validation {
    condition     = var.target > 0 && var.target < 1
    error_message = "target is a fraction between 0 and 1."
  }
}

variable "folder_uid" {
  description = "Grafana folder that holds the rule group."
  type        = string
}

variable "loki_datasource_uid" {
  description = "Loki data source the queries run on."
  type        = string
}

# main.tf
locals {
  levels = {
    page_1h   = { urgency = "page", burn_rate = 14.4, long = "1h", short = "5m" }
    page_6h   = { urgency = "page", burn_rate = 6, long = "6h", short = "30m" }
    ticket_3d = { urgency = "ticket", burn_rate = 1, long = "3d", short = "6h" }
  }
}

resource "grafana_rule_group" "this" {
  # One rule per entry of local.levels.
}
```

- **Rules:** each rule fires when the error rate of [Error budget alerts](#error-budget-alerts) over the burn rate times `1 - var.target` holds in both its windows, and only while capture's events reach Grafana (#10). It carries the labels `alert_id = "ALR6"`, `system` and `urgency`, and the annotations the message template reads (#11). The module has no outputs; `alert_rules.tf` calls it once per system.

### 2.6 Test plan

<!-- Optional. Every requirement has at least one verification method (IADT: Inspection, Analysis, Demonstration, Test). Test is the default, at the lowest level that can verify the requirement. Another method only when no test can: Inspection for configuration or documents, Analysis for production data or measurements, Demonstration for behaviour observed end to end, such as a third-party service. -->

`terraform test` runs with a mocked provider: it verifies each rule's query, threshold, labels and routing as planned, not that Grafana evaluates them; that alerts fire and notify is shown by the demonstrations of [Done when](#14-done-when).

| R | Method | What is verified | Level |
|---|---|---|---|
| R1 | Test | A pass's request, and a run's, holds one record per line written to R2, of every level, in order; a run's request also holds the `log_upload_failed` and `heartbeat_failed` emitted after the upload | integration |
| R2 | Test | The request is built for a line of an event and a system the code has never seen, with no list consulted | unit |
| R3 | Test | With Grafana answering 500, stalling past the limit or unreachable, the pass's and the run's outcome and heartbeat signal equal those of a successful send, and the failure is written to Workers Logs or stdout as `otlp_send_failed` with its `error_type` | integration |
| R4 | Test | The R2 log is byte-identical with a send that succeeds and one that fails | integration |
| R5 | Test | A response that stalls past `otlpTimeoutMs`, or `timeout_s`, is aborted: capture returns `errorType: "timeout"`, the pipeline raises `OSError` | unit (capture), integration (pipeline) |
| R6 | Test | Each record's body is the line written to R2, a redacted secret included, never serialized again | unit |
| R7, R8 | Test | ALR1 and ALR2 select the failed rules' events by severity, take `rule` from the event as a label, and carry `urgency = "ticket"` | unit |
| R9 | Test | ALR3 selects the page's failed deployment event, as a ticket | unit |
| R10 | Test | The synthetic check runs every 5 min from three probes with ALR4's threshold from `locals.tf`, and ALR4 fires on two failing probes, as a page | unit |
| R10 | Demonstration | The k6 script passes on the page's live file and fails a probe with a threshold of 0 min, run from Grafana's synthetic check | — |
| R11 | Test | ALR5 counts minutes in a row with no clean capture per system and feed, fires over 10, as a page | unit |
| R12, R13 | Test | The module builds three rules per system with the burn rates and windows of [Error budget alerts](#error-budget-alerts), each threshold the burn rate times `1 - target`, the error rate over the minutes with an event of capture only, both windows required, the 1 h and 6 h levels as pages and the 3 d level as a ticket; a target outside (0, 1) is rejected | unit |
| R14 | Test | ALR7's thresholds derive from `run_settings.json`: 80% of the timeout and of the container's memory | unit |
| R15 | Test | ALR8 fires per component after 2 cadences for the pipeline and 5 min for capture with no event, as a ticket | unit |
| R16, R22 | Test | ALR9 selects the registry's events with `needs_action` and an empty `alerts`, ALR14 every event the registry does not list, both built from the registry; every alert ID in the registry is one Terraform declares | unit |
| R17 | Test | ALR10 selects `index_refreshed` events with a non-empty `unknown_feeds` | unit |
| R18 | Test | ALR11 selects a pass's missed-minute cause outside D9's table | unit |
| R19 | Test | ALR12's condition always holds, its policy repeats every 5 min to the watchdog's webhook contact point, and no other policy reaches it | unit |
| R20 | Inspection | The watchdog's check in Healthchecks.io has a 5 min period, 10 min of grace and the owner's email | — |
| R21 | Test | ALR13 fires at 40 GB of logs and 80k check executions a month, as a ticket | unit |
| R23 | Test | Every rule carries `alert_id` and the checked catalog IDs that the template reads | unit |
| R23, R24 | Demonstration | A test notification shows the alert's ID and checked IDs, and its links open the catalog section, the alert's row and the events in Grafana's Explore | — |
| R25 | Test | The registry is valid against its schema, each `component` and `event` pair appears once, and every event capture and the pipeline write is registered | contract |
| R25, R26 | Inspection | `docs/observability.md` opens with its introduction and worked example, and lists the common fields, the heartbeat checks, and every alert with its ID, checked IDs and urgency; the registry lists, for each event, the alerts that read it | — |
| R27 | Test | The registry's levels are `info`, `warn` and `error`, and capture's log contract vectors use `warn` | contract |
| R28, R29 | Test | `capture_volume`'s dbt unit tests flag a capture below 95% of the 7-day median and skip it with fewer than 60 captures in those 7 days | unit |
| R28 | Inspection | `_VOLUME_WINDOW` in `shell/run.py` is 7 days | — |
| R30, R33 | Inspection | `docs/data-quality.md` sets DQM7's targets, 99.5% for AMBici and 97% for Bicing, and DQM11's, at most 30 min a feed and month given to capture | — |
| R31, R32 | Inspection | DQM11's definition gives each cause to the provider or capture as D9's table sets, and leaves out a minute captured but missing from the station stock | — |
| R34, R35 | Test | Notification policies route `urgency = "page"` to the IRM contact point and `urgency = "ticket"` to the alert list with no notification | unit |
| R36 | Demonstration | Grafana's Explore, in the browser and the mobile app, shows events of capture and the pipeline, and the synthetic check's results, over the last 14 days | — |
| R37 | Test | The watchdog's URL is a `sensitive` variable with no default | unit |
| R37 | Inspection | No signal URL in the repository; `.env.example` holds it empty | — |
| R38 | Inspection | The template reads only the alert's labels and annotations, and no annotation holds an event's body | — |
| R39 | Test | ALR15 sums each feed's minutes given to capture over 7 days, among the minutes with an event of capture, and fires over 7, as a ticket | unit |
| R40 | Demonstration | The query in `docs/observability.md`, run in Explore, shows each feed's minutes given to the provider over the last 7 days, with no target | — |
| R41 | Test | Every rule's query groups by `system` and names no system, except ALR6's, which takes its system from the module's variable | unit |
| R42 | Test | Every ALR5 and ALR6 rule holds only while capture has events in Grafana within ALR8's threshold | unit |
| R43 | Test | Capture signals the heartbeat from a pass whose scheduled minute is a multiple of 5 and that stored the three dynamic feeds, and from no other pass | unit |
| R43 | Inspection | Capture's heartbeat check in Healthchecks.io has a 10 min period and 10 min of grace | — |

### 2.7 Breaking changes

<!-- Optional. Shared models or interfaces this design changes, and how their dependants are handled. -->

| File | Why it breaks | Strategy |
|---|---|---|
| `contracts/capture-logs.json` | Capture's `warning` level becomes `warn` (#4) and its `source` field becomes `system` (#5): the valid vectors stop meeting the contract | The vectors change with capture's code in one step; SQL over capture's logs in R2 from before the change accepts both names, as the catalog records |

### 2.8 What does not change

<!-- Optional. Code or documents that must not be modified. Out of scope limits the what; this section limits the how. -->

- `pipeline/modal_one_off.py`: no monitoring Secret and the same imports, so a one-off run sends nothing ([d008 › Observability](d008-pipeline-platform-and-walking-skeleton.md#observability)).
- Capture's code and bronze object keys keep `source`; only its log events change to `system` (#5).
- Capture's logs already in R2 are not rewritten (#4, #5).
- The checks of capture's and the pipeline's heartbeats stay in Healthchecks.io's console, outside Terraform (#9).

## 3. Steps

<!-- Build tasks only; a document-only task removes this block.
Each step is one reviewable result and one commit, touching at most 2–3 files.
- Status: where the step is: 💤 todo · 🎬 ready · 🔄 in progress · ⛔ blocked · ✅ done
- Who: Owner (manual actions: dashboards, accounts, deploys, runs, checks) or Claude (code and documents).
- R: the requirements the step implements or tests, or —.
- Commit: the proposed message, following the Git conventions in CLAUDE.md.
- Model: the model and effort the step's session runs with, fitted to the step: the lightest that does it well, never more than it needs nor less (e.g. sonnet · medium). For an Owner step, those of the session that guides the owner, or — when the owner works alone.
- Review: `code`, `security`, `code and security`, or `no`. A review goes on the step that completes a reviewable unit (a flow or action, usually built over several steps); the last code step has at least `code`. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

- **tenv**, the version manager that installs the Terraform release `monitoring/.terraform-version` pins and verifies its SHA256 and HashiCorp's PGP signature by default: `brew install tenv` (4.16.9 or later). Verify: `tenv --version`.
- **Terraform 1.17.1**, the pin of `monitoring/.terraform-version`, the latest patch released at least two weeks before it was chosen. Grafana's provider is `~> 4.54` in `versions.tf`, with 4.54.0 locked. Installed by tenv on first use. Verify: `terraform version` inside `monitoring/` prints `Terraform v1.17.1`.
- **Grafana Cloud account** on the Free tier, with its stack in an EU region and no payment method. Verify in the console: the stack's region and the billing page. Record both in Close (Done when).
- **Free tier features** checked at account set-up: template variables and data links, the SLO app, Loki recording rules, a scripted k6 check asserting a file's age, the IRM heartbeat and the usage data source ALR13 reads. Two or more missing reopen s018's choice of tool ([s018 › P1](../spikes/s018-monitoring-tool.md#23-production-inputs)). Record the outcome in Close.
- **Grafana credentials**, each with the narrowest scope that works:
  - a stack service account token for Terraform's alerting and IRM resources (the provider's `auth`), with the `plugins.app:access` permission IRM needs;
  - a Synthetic Monitoring access token for ALR4's check (the provider's `sm_access_token`), with the stack's Synthetic Monitoring URL;
  - an access policy token with the `logs:write` scope only, for the OTLP copy of capture and the pipeline.

  The first two and the URL go in `.env` as Terraform variables; the third stays with the owner until it is set as a Worker secret and a Modal Secret. Verify: each token is listed in the console with that scope and no other.
- **Grafana mobile app** with IRM, signed in to the owner's account, notifications allowed. Verify: IRM's test notification reaches the phone.

### Step 1 — Event registry and its schema

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d009.s1 add the log events registry and its schema`
- **R:** R25, R27
- **Model:** sonnet · medium
- **Review:** no

#### Scope

<!-- The result of the step. List the components, the files created or changed (code, tests, docs), and the tests from the Test plan that cover it. A reviewer should know what the diff will contain from this section alone. -->

The observability catalog's machine-readable half: every event of capture and the pipeline, with its level, own fields, whether it needs an action and the alerts that read it.

- `contracts/log-events.schema.json` (new): the schema of [Event registry schema](#event-registry-schema), as written there.
- `contracts/log-events.registry.json` (new): `$schema` `./log-events.schema.json` and one entry per event of capture and of the pipeline, `otlp_send_failed` of both included; levels `info`, `warn` and `error` only (R27); capture's events with `system`, never `source`.
- Tests: the contract rows of R25 and R27 run against these files from Step 5 (capture) and Step 15 (pipeline).

#### Reads

<!-- List of reads containing what to read (be specific with paragraph or line), what contains the read, and why it is interesting here.  -->

- [Event registry schema](#event-registry-schema), in this design: the schema to write and the rules beyond it (one entry per `component` and `event`).
- [Observability catalog](#observability-catalog) and [Warning level](#warning-level), in this design: what an entry holds and the single level name.
- [D3](#d3-alerts-on-symptoms-that-need-action) and [Thresholds](#thresholds), in this design: which alert reads which event, for `alerts`.
- `.claude/rules/docs/observability.md`: the conventions of an entry, `needs_action` and `description` included.
- [d004 › D9](d004-bronze-data-capture.md#d9-capture-logs): capture's events and their own fields.
- [d008 › Observability](d008-pipeline-platform-and-walking-skeleton.md#observability): the pipeline's events and their own fields.
- [Capture's OTLP sender](#captures-otlp-sender) and [Pipeline's OTLP payload and exporter](#pipelines-otlp-payload-and-exporter), Callers, in this design: `otlp_send_failed` and its field `error_type`.

#### Do

<!-- Numbered actions in execution order, one verb each (write, implement, update, run). Every file named here must appear in Scope; add nothing Scope does not list. -->

1. Write `contracts/log-events.schema.json` from [Event registry schema](#event-registry-schema).
2. Write `contracts/log-events.registry.json` with one entry per event of d004 › D9 and d008 › Observability, plus `otlp_send_failed` for each component, at `warn` with `error_type`; capture's `warning` becomes `warn` and `source` becomes `system`.
3. Set each entry's `alerts` from D3 and Thresholds, and its `needs_action` and `description` as `.claude/rules/docs/observability.md` sets.
4. Run `grep -rn "buildEvent(" capture/src` and `grep -n "^def " pipeline/src/bikesharing/core/events.py`, and confirm each event they show has its entry.

#### Check

<!-- command/s or verification with a yes/no result. -->

- A throwaway script in the session's scratchpad, run with `uv run --project pipeline python <script>`, validates the registry against its schema with `jsonschema` and finds no repeated pair of `component` and `event`: it prints `ok`.
- Every event Do 4 lists has an entry: yes/no.

### Step 2 — Observability catalog

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `docs: d009.s2 add the observability catalog`
- **R:** R25, R26
- **Model:** sonnet · medium
- **Review:** no

#### Scope

The catalog's document, and the designs that now link to it for the events.

- `docs/observability.md` (new), in this order:
  - the introduction every catalog opens with: what it holds and what for, how to read an entry, and one worked example that follows an event from its registry entry to the alert that reads it and the notification on the owner's phone (#15);
  - the common fields of [ADR-0036](../decisions/0036-log-convention-across-components.md), and the link to the registry for the events;
  - the criterion by which an event needs an action from the owner (#3);
  - the level and field names: `warn` and `system` for every component; capture's logs in R2 from before the change keep `warning` and `source`, with a `TODO(T060.2):` marker for the version and date of the change, recorded in Step 32;
  - the heartbeat checks: capture's (10 min plus 10 min of grace, R43), the pipeline's, and the watchdog's (R20);
  - the alerts ALR1–ALR15, one row each with its ID, the catalog IDs it checks and its urgency, and no list of events (R26);
  - how the error budget alerts work, the notification layout, and the LogQL query of each feed's minutes given to the provider over the last 7 days (R40).
- `docs/designs/d004-bronze-data-capture.md` (modified): D9 links to the catalog for the events.
- `docs/designs/d008-pipeline-platform-and-walking-skeleton.md` (modified): Observability links to the catalog for the events.
- Tests: the Inspection rows of R25 and R26.

#### Reads

- [D4](#d4-alerts-carry-their-own-id-and-the-catalog-ids-they-check), [D5](#d5-one-observability-catalog-built-here), [D11](#d11-pages-for-what-waiting-makes-worse-tickets-for-the-rest) and [D13](#d13-a-watchdog-outside-grafana-watches-its-alerting), in this design: the alerts' IDs, the catalog's content, urgency and the watchdog.
- [Observability catalog](#observability-catalog), [Error budget alerts](#error-budget-alerts), [Thresholds](#thresholds), [Notifications](#notifications), [Watchdog](#watchdog), [Capture silence](#capture-silence), [Warning level](#warning-level) and [Field mapping](#field-mapping), in this design: each section of the document.
- `.claude/rules/docs/general.md` › Catalogs and `.claude/rules/docs/observability.md`: how a catalog opens and how an entry is written.
- `contracts/log-events.registry.json`, from Step 1: the event the worked example follows, and the alert IDs the table must hold.

#### Do

1. Write `docs/observability.md` with the sections of Scope, in that order.
2. Update d004 › D9 and d008 › Observability to link to `docs/observability.md` for the events, keeping their decisions.

#### Check

- The lint hook reports no error on the three files.
- Every alert ID in the registry has a row in the alerts table, and every row's ID appears in the registry or in [Thresholds](#thresholds): yes/no.
- The Inspection rows of R25 and R26 in the [Test plan](#26-test-plan) hold: yes/no.

### Step 3 — Data quality catalog: DQM7, DQM10, DQM11

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `docs: d009.s3 set the targets of DQM7 and DQM11`
- **R:** R30, R31, R32, R33
- **Model:** sonnet · low
- **Review:** no

#### Scope

The indicators this design sets, in `docs/data-quality.md` (modified):

- DQM7: one target per system, at least 99.5% of the minutes of each calendar month for AMBici and 97% for Bicing (R30), read by ALR6.
- DQM10: its target unchanged, read by ALR4.
- DQM11: each missed minute given to the provider or to capture as D9's table sets, leaving out a minute captured but missing from the station stock (R31, R32); a target of at most 30 minutes given to capture per feed and calendar month, with no target on the provider's (R33), read by ALR15.
- Each row links to its decision in this design and to its alert in `docs/observability.md`.
- Tests: the Inspection rows of R30–R33.

#### Reads

- [D7](#d7-capture-completeness-target-per-system), [D8](#d8-page-data-age-keeps-its-target), [D9](#d9-a-missed-minutes-cause-goes-to-whoever-can-act-on-it) and [D10](#d10-a-target-on-captures-own-missed-minutes-only), in this design: the targets and DQM11's attribution table.
- `docs/data-quality.md`, rows DQM7, DQM10 and DQM11 of Quality indicators: the rows to change.

#### Do

1. Update the rows of DQM7, DQM10 and DQM11 in `docs/data-quality.md` as Scope sets.

#### Check

- The Inspection rows of R30, R31, R32 and R33 in the [Test plan](#26-test-plan) hold: yes/no.
- The lint hook reports no error.

### Step 4 — Capture: `warn` and `system`

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat!: d009.s4 log capture's warn level and system field`
- **R:** R27
- **Model:** sonnet · low
- **Review:** no

#### Scope

Capture's log contract and the events it writes take the single level name and field name, in one change ([Breaking changes](#27-breaking-changes)).

- `contracts/capture-logs.json` (modified): the valid vectors with `warn` and `system`; one invalid case with level `warning` and one with field `source`, each with its `reason`; one valid vector of `otlp_send_failed` at `warn` with `error_type`, the line capture writes to Workers Logs.
- `capture/src/log.js` (modified): the level type is `'info' | 'warn' | 'error'`.
- `capture/src/pass.js` (modified): every event's `source` field becomes `system`, and `warning` becomes `warn`, its comments included. Bronze keys and the code's own `source` keep their name ([What does not change](#28-what-does-not-change)).
- `capture/test/unit/log.test.js`, `capture/test/integration/pass.test.js`, `capture/test/integration/pass-failures.test.js` (modified): they expect `warn` and `system`.
- Tests: the contract row of R27, through `capture/test/contract/capture-logs.test.js`, unchanged, which reads the new vectors.

#### Reads

- [Warning level](#warning-level) and [Field mapping](#field-mapping), in this design: the two names and why.
- [d004 › D9](d004-bronze-data-capture.md#d9-capture-logs): capture's events and fields, already with the new names.
- `contracts/capture-logs.json` and `capture/test/contract/capture-logs.test.js`: how the vectors are written and read.

#### Do

1. Update `contracts/capture-logs.json` as Scope sets.
2. Update the three tests to expect `warn` and `system`.
3. Update `log.js` and `pass.js`.
4. Run `npm test --prefix capture`.

#### Check

- `npm test --prefix capture` passes.
- `grep -rn "warning" capture/src` finds no level, and every log field built in `pass.js` with `source.id` is named `system`: yes/no.

### Step 5 — Capture: registry contract test

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `test: d009.s5 check capture's events against the registry`
- **R:** R25, R27
- **Model:** sonnet · low
- **Review:** no

#### Scope

Capture's side of the event registry: the registry is valid, and it holds exactly the events capture writes.

- `capture/package.json`, `capture/package-lock.json` (modified): `@cfworker/json-schema` as a dev dependency, installed with `npm install --save-dev @cfworker/json-schema --prefix capture`, in its latest release at least two weeks old.
- `capture/test/contract/log-events-registry.test.js` (new), read by relative path as `capture-logs.test.js` reads its vectors:
  - the registry is valid against `contracts/log-events.schema.json`, draft 2020-12;
  - each pair of `component` and `event` appears once;
  - the registry's `capture` events and the events of the valid vectors of `contracts/capture-logs.json` are the same set, each with the same level.
- Tests: the contract rows of R25 and R27.

#### Reads

- `.claude/rules/code/testing.md` › Contracts between components: reference data validated against its schema by each component that reads it.
- [Event registry schema](#event-registry-schema) › Beyond the schema, in this design: what the schema cannot check.
- `capture/test/contract/capture-logs.test.js`: how a contract test reads a file in `contracts/`.

#### Do

1. Install `@cfworker/json-schema` as Scope sets.
2. Write `log-events-registry.test.js`.
3. Run `npm test --prefix capture -- test/contract/log-events-registry.test.js`.

#### Check

- `npm test --prefix capture` passes.
- With one `capture` entry removed from the registry, the test fails, and passes again once it is restored: yes/no.

### Step 6 — Capture: OTLP sender

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d009.s6 build and send capture's OTLP request`
- **R:** R1, R2, R5, R6
- **Model:** sonnet · medium
- **Review:** no

#### Scope

The module that turns a pass's lines into an OTLP request and sends it once, never throwing.

- `capture/src/otlp.js` (new): `SEVERITY_NUMBER`, `buildLogsRequest` and `sendLogs`, as [Capture's OTLP sender](#captures-otlp-sender) and [OTLP request mapping](#otlp-request-mapping) set; the time limit covers the whole response, body included, as in `heartbeat.js`.
- `capture/src/fetch.js` (modified): `otlpTimeoutMs: 10_000` in `LIMITS` and its typedef.
- `capture/vitest.config.js` (modified): a route `otlp` that answers 200 and keeps each request's body and `Authorization` header by path, read back through a route like `count`; the failures reuse `http-500`, `stall-body` and `network-error`.
- `capture/test/unit/otlp.test.js` (new): the request's resources, records and attribute types, a `null` field left out, no request with no lines, and the `Authorization` header; a line of an event and a system the code has never seen (R2); each body equal to its line, a redacted secret included (R6); `null` on 2xx, and `http` with its status, `timeout` with a small `otlpTimeoutMs` (R5) and `network` on each failure route.
- Tests: the unit rows of R2, R5 and R6.

#### Reads

- [OTLP request mapping](#otlp-request-mapping), [Capture's OTLP sender](#captures-otlp-sender) and [Field mapping](#field-mapping), in this design: the contract.
- `capture/src/heartbeat.js`: the pattern of a request that never throws and whose timeout covers the body.
- `capture/vitest.config.js`, `ROUTES` and the `count` route: where the new route goes and how a test reads it back.

#### Do

1. Add the `otlp` route to `vitest.config.js`.
2. Write `otlp.test.js`.
3. Add `otlpTimeoutMs` to `LIMITS`.
4. Implement `otlp.js`.
5. Run `npm test --prefix capture`.

#### Check

- `npm test --prefix capture` passes.
- Each test of a Test plan row is tagged `Verifies d009 R<n>`: yes/no.

### Step 7 — Capture: heartbeat at every fifth minute

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d009.s7 signal capture's heartbeat every fifth minute`
- **R:** R43
- **Model:** sonnet · low
- **Review:** no

#### Scope

The pass calendar signals the heartbeat at every minute that is a multiple of 5 ([Capture silence](#capture-silence)).

- `capture/src/schedule.js` (modified): the heartbeat at `:00`, `:05`, … `:55`, and no longer at `:22`; the other extra fetches unchanged.
- `capture/test/unit/schedule.test.js` (modified): the heartbeat at the 288 minutes a day that are multiples of 5 and at no other (R43); 396 extra fetches a day ([d004 › Pass schedule](d004-bronze-data-capture.md#pass-schedule)).
- `capture/test/integration/pass.test.js` (modified): the heartbeat's integration tests at `:05` instead of `:22`.
- Tests: the unit row of R43.

#### Reads

- [Capture silence](#capture-silence), in this design: the cadence and why it keeps no state.
- [d004 › Pass schedule](d004-bronze-data-capture.md#pass-schedule): the calendar, already updated.
- `capture/src/schedule.js` and `capture/test/unit/schedule.test.js`: the table to change and its tests.

#### Do

1. Update `schedule.test.js` and `pass.test.js`.
2. Update `schedule.js`.
3. Run `npm test --prefix capture`.

#### Check

- `npm test --prefix capture` passes.
- No minute carries two extra fetches: yes/no.

### Step 8 — Capture: the copy in the pass

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d009.s8 send capture's events to Grafana after each pass`
- **R:** R1, R3, R4
- **Model:** sonnet · medium
- **Review:** code and security

#### Scope

Each pass sends its lines to Grafana after its log and its heartbeat, and the send can never change the pass ([Sending the copy](#sending-the-copy)).

- `capture/src/log.js` (modified): `toLines(events)`, each event's `JSON.stringify`; `writeLog` takes those lines.
- `capture/src/pass.js` (modified): serializes the pass's events once; after the log and the heartbeat, passes the same lines to `sendLogs` inside the `waitUntil` it receives; a failure is written with `console.log` as `otlp_send_failed` at `warn` with `error_type`, and the pass's outcome does not change.
- `capture/src/worker.js` (modified): passes `OTLP_ENDPOINT`, `OTLP_TOKEN` and `ctx.waitUntil` to `runPass`.
- `capture/wrangler.jsonc` (modified): `OTLP_ENDPOINT` as a variable, the stack's OTLP logs URL from the owner's account set-up ([Prerequisites](#31-prerequisites)); `OTLP_TOKEN` stays a secret, set in Step 28.
- `capture/test/unit/log.test.js` (modified): `toLines`.
- `capture/test/integration/pass.test.js` (modified): the request holds one record per line written to R2, of every level, in order (R1); with the endpoint at `http-500`, `stall-body` or `network-error`, the outcome and the heartbeat equal those of a successful send, and `otlp_send_failed` reaches the console with its `error_type` (R3); the R2 log is byte-identical with a send that succeeds and one that fails (R4); the order is log, heartbeat, copy.
- Tests: the integration rows of R1, R3 and R4, capture's side.

#### Reads

- [Capture's OTLP sender](#captures-otlp-sender) › Callers and [Sending the copy](#sending-the-copy), in this design: where the send goes and what a failure does.
- [D2](#d2-the-copy-to-grafana-never-affects-a-run), in this design: the copy never affects a run.
- [d004 › `log.js`](d004-bronze-data-capture.md#logjs) and [`pass.js`](d004-bronze-data-capture.md#passjs): the contracts the change extends.
- `capture/src/pass.js` and `capture/src/worker.js`: the order of the log and the heartbeat, and how `runPass` receives its dependencies.

#### Do

1. Update `log.test.js` and `pass.test.js`.
2. Update `log.js`, `pass.js` and `worker.js`.
3. Add `OTLP_ENDPOINT` to `wrangler.jsonc`.
4. Run `npm test --prefix capture`.

#### Check

- `npm test --prefix capture` passes.
- `grep -rn "OTLP_TOKEN" capture` shows it only in `worker.js` and in no log, error or test fixture: yes/no.
- Each test of a Test plan row is tagged `Verifies d009 R<n>`: yes/no.

### Step 9 — Pipeline: run settings (core)

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d009.s9 parse the pipeline's run settings`
- **R:** —
- **Model:** sonnet · low
- **Review:** no

#### Scope

The run's cadence, time budget, timeout and memory in one data file, parsed and checked by the core (#9), so Terraform's thresholds and Modal read the same values.

- `pipeline/src/bikesharing/core/run_settings.json` (new): the values of [Pipeline's run settings](#pipelines-run-settings).
- `pipeline/src/bikesharing/core/settings.py` (modified): `RunSettings`, `parse_run_settings` and `schedule_cron`, as that contract sets; `TIME_BUDGET` stays until Step 10.
- `pipeline/tests/unit/core/test_settings.py` (new): the repository's `run_settings.json` parses; each invalid input is rejected with `ValueError` (a missing or unknown key, a value that is not a positive integer, a cadence that does not divide 60, a time budget not below the timeout, a timeout not below the cadence); `schedule_cron` gives `*/15 * * * *` for a cadence of 15.

#### Reads

- [Pipeline's run settings](#pipelines-run-settings), in this design: the contract.
- [d008 › D6](d008-pipeline-platform-and-walking-skeleton.md#d6-provisional-run-bounds): the bounds the parser checks.
- `pipeline/src/bikesharing/core/settings.py`: where the new items go.

#### Do

1. Write `test_settings.py`.
2. Write `run_settings.json`.
3. Implement the new items in `settings.py`.
4. Run `uv run --directory pipeline pytest tests/unit`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` passes.

### Step 10 — Pipeline: run settings wired in

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `refactor: d009.s10 read the run's bounds from the run settings`
- **R:** —
- **Model:** sonnet · medium
- **Review:** code

#### Scope

The run and the Modal app take their bounds from `run_settings.json`, with the values they have today, so the deployed behaviour does not change.

- `pipeline/src/bikesharing/shell/run_settings.py` (new): `RUN_SETTINGS`, the file parsed once at import.
- `pipeline/src/bikesharing/shell/run.py` (modified): the time budget from `RUN_SETTINGS`.
- `pipeline/src/bikesharing/core/settings.py` (modified): `TIME_BUDGET` removed.
- `pipeline/modal_image.py` (modified): `MEMORY_MIB` and `TIMEOUT_S` from `RUN_SETTINGS`; `run_settings.json` added to the image with `add_local_file`, at its path inside the package, since `add_local_python_source` leaves out non-Python files by default.
- `pipeline/modal_app.py` (modified): the schedule from `schedule_cron(RUN_SETTINGS)`.
- `pipeline/modal_one_off.py` keeps its imports unchanged ([What does not change](#28-what-does-not-change)).
- Tests: the existing tests, unchanged, pass with the same values.

#### Reads

- [Pipeline's run settings](#pipelines-run-settings) › Callers, in this design: who reads which value.
- `pipeline/modal_image.py`, the image's `add_local_*` calls and the constants; `pipeline/modal_app.py`, the schedule: what changes.
- `grep -rn "TIME_BUDGET" pipeline`: every use to replace.

#### Do

1. Write `shell/run_settings.py`.
2. Update `run.py` and remove `TIME_BUDGET` from `settings.py`.
3. Update `modal_image.py` and `modal_app.py`.
4. Run `bash pipeline/scripts/check-pipeline.sh`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` passes.
- `grep -rn "TIME_BUDGET\|= 4096\|= 600\|\*/15" pipeline/src pipeline/modal_image.py pipeline/modal_app.py` finds no value outside `run_settings.json`: yes/no.

### Step 11 — Pipeline: OTLP payload

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d009.s11 build the pipeline's OTLP request`
- **R:** R1, R2, R6
- **Model:** sonnet · low
- **Review:** no

#### Scope

The pure function that turns a run's lines into the OTLP request, the same mapping capture uses.

- `pipeline/src/bikesharing/core/otlp_payload.py` (new): `SEVERITY_NUMBER` and `logs_request`, as [Pipeline's OTLP payload and exporter](#pipelines-otlp-payload-and-exporter) and [OTLP request mapping](#otlp-request-mapping) set.
- `pipeline/tests/unit/core/test_otlp_payload.py` (new): resources, records and attribute types, a `null` field left out, an empty request with no lines; a line of an event and a system the code has never seen (R2); each body equal to its line, a redacted secret included (R6).
- Tests: the unit rows of R2 and R6, the pipeline's side.

#### Reads

- [OTLP request mapping](#otlp-request-mapping) and [Pipeline's OTLP payload and exporter](#pipelines-otlp-payload-and-exporter), in this design: the contract.
- `capture/test/unit/otlp.test.js`, from Step 6: the same cases, so both components map alike.

#### Do

1. Write `test_otlp_payload.py`.
2. Implement `otlp_payload.py`.
3. Run `uv run --directory pipeline pytest tests/unit`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` passes.

### Step 12 — Pipeline: OTLP exporter

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d009.s12 send the pipeline's OTLP request`
- **R:** R5
- **Model:** sonnet · low
- **Review:** no

#### Scope

The shell's one POST of the request, within its limit, raising on any failure.

- `pipeline/src/bikesharing/shell/otlp_exporter.py` (new): `OtlpTarget` and `send_logs`, as [Pipeline's OTLP payload and exporter](#pipelines-otlp-payload-and-exporter) sets, with `urllib`.
- `pipeline/tests/integration/test_otlp_exporter.py` (new): against a local HTTP server, a 2xx returns; a non-2xx, a response that stalls past a small `timeout_s` (R5) and a refused connection each raise `OSError`; no lines sends nothing; the request carries `Authorization: Basic <token>`.
- Tests: the integration row of R5.

#### Reads

- [Pipeline's OTLP payload and exporter](#pipelines-otlp-payload-and-exporter), in this design: the contract.
- `pipeline/src/bikesharing/shell/heartbeat.py` and its integration test: the pattern of a `urllib` request with a timeout, tested against a local server.

#### Do

1. Write `test_otlp_exporter.py`.
2. Implement `otlp_exporter.py`.
3. Run `uv run --directory pipeline pytest tests/integration`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` passes.

### Step 13 — Pipeline: the copy in the run

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d009.s13 send the pipeline's events to Grafana after each run`
- **R:** R1, R3, R4, R6
- **Model:** sonnet · medium
- **Review:** code and security

#### Scope

Each scheduled run sends its lines after its log upload and its heartbeat ping, and the send can never change the run ([Sending the copy](#sending-the-copy)).

- `pipeline/src/bikesharing/core/events.py` (modified): `otlp_send_failed(ts, *, error_type)` at `warn`, written to stdout only; `log_upload_failed` written to stdout and kept for the copy.
- `pipeline/src/bikesharing/shell/event_log.py` (modified): `lines()`, every kept line in order.
- `pipeline/src/bikesharing/shell/run.py` (modified): `scheduled_config` reads `OTLP_ENDPOINT` and `OTLP_TOKEN` into an `OtlpTarget`, and adds `OTLP_TOKEN` to the run's secrets, so the redaction of [d008 › Observability](d008-pipeline-platform-and-walking-skeleton.md#observability) covers it (R6); `one_off_config` sets no target; `run` sends after the upload and the ping, and catches any exception into `otlp_send_failed`, the outcome unchanged.
- `pipeline/tests/unit/core/test_events.py` (modified): `otlp_send_failed`.
- `pipeline/tests/integration/test_event_log.py` (modified): `lines()` holds every kept line, in order, `log_upload_failed` included.
- `pipeline/tests/integration/test_run.py` (modified): the request holds one record per line uploaded, then `log_upload_failed` and `heartbeat_failed` when they occur (R1); with the target failing or stalling, the outcome and the heartbeat equal those of a successful send, and `otlp_send_failed` reaches stdout with its `error_type` (R3); the uploaded log is byte-identical either way (R4); a one-off run sends nothing.
- Tests: the integration rows of R1, R3 and R4, the pipeline's side.

#### Reads

- [Pipeline's OTLP payload and exporter](#pipelines-otlp-payload-and-exporter) › Callers and [Sending the copy](#sending-the-copy), in this design: the order and what a failure does.
- [d008 › Observability](d008-pipeline-platform-and-walking-skeleton.md#observability): the redaction and the events written to stdout.
- `pipeline/src/bikesharing/shell/run.py`, `scheduled_config`, `one_off_config` and the log upload and ping in `run`: where the send goes.

#### Do

1. Update `test_events.py`, `test_event_log.py` and `test_run.py`.
2. Add `otlp_send_failed` to `events.py` and `lines()` to `event_log.py`.
3. Update `run.py`.
4. Run `bash pipeline/scripts/check-pipeline.sh`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` passes.
- A test shows `OTLP_TOKEN` redacted from a line that carries it: yes/no.
- Each test of a Test plan row is tagged `Verifies d009 R<n>`: yes/no.

### Step 14 — Pipeline: monitoring Modal Secret

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d009.s14 give the scheduled function the monitoring Secret`
- **R:** —
- **Model:** sonnet · low
- **Review:** security

#### Scope

The OTLP endpoint and token reach the scheduled function only.

- `pipeline/modal_image.py` (modified): `MONITORING_SECRET = ("bikesharing-pipeline-monitoring", ["OTLP_ENDPOINT", "OTLP_TOKEN"])`, named as the other Secrets.
- `pipeline/modal_app.py` (modified): that Secret in the scheduled function's `secrets`.
- `pipeline/modal_one_off.py` is not changed: a one-off run has no monitoring Secret ([What does not change](#28-what-does-not-change)).

#### Reads

- [Sending the copy](#sending-the-copy), in this design: the Secret of the scheduled function only.
- `pipeline/modal_image.py`, the Secret constants, and `pipeline/modal_app.py`, the function's `secrets`: the pattern to follow.

#### Do

1. Add `MONITORING_SECRET` to `modal_image.py`.
2. Add it to the scheduled function in `modal_app.py`.
3. Run `bash pipeline/scripts/check-pipeline.sh`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` passes.
- `grep -n "MONITORING_SECRET" pipeline/modal_one_off.py` finds nothing: yes/no.

### Step 15 — Pipeline: registry contract test

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `test: d009.s15 check the pipeline's events against the registry`
- **R:** R25, R27
- **Model:** sonnet · low
- **Review:** no

#### Scope

The pipeline's side of the event registry, as Step 5 is capture's.

- `pipeline/tests/integration/test_log_events_registry_contract.py` (new):
  - the registry is valid against `contracts/log-events.schema.json` with `jsonschema`'s draft 2020-12 validator;
  - each pair of `component` and `event` appears once;
  - the registry's `pipeline` events and the events `core/events.py` defines are the same set, each with the same level.
- Tests: the contract rows of R25 and R27, the pipeline's side.

#### Reads

- `.claude/rules/code/testing.md` › Contracts between components, and [Event registry schema](#event-registry-schema) › Beyond the schema, in this design.
- `pipeline/src/bikesharing/core/events.py`: how each event and its level are defined, to enumerate them.
- `capture/test/contract/log-events-registry.test.js`, from Step 5: the same checks.

#### Do

1. Write `test_log_events_registry_contract.py`.
2. Run `uv run --directory pipeline pytest tests/integration`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` passes.
- With one `pipeline` entry removed from the registry, the test fails, and passes again once it is restored: yes/no.

### Step 16 — Pipeline: DQR12 over 7 days at 95%

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d009.s16 judge capture volume against a 7-day median`
- **R:** R28, R29
- **Model:** sonnet · low
- **Review:** code

#### Scope

DQR12 follows D6, in the model, the history the shell reads, and the catalog, in one change ([Volume drop](#volume-drop)).

- `pipeline/dbt/models/silver/capture_volume.sql` (modified): the median over the 7 days before each capture instant; `drop` below 95% of it; `not_evaluated` with fewer than 60 captures, unchanged.
- `pipeline/dbt/models/silver/silver.yml` (modified): the model's unit tests for a capture below 95% of the 7-day median, one at it, and one with fewer than 60 captures in those 7 days.
- `pipeline/src/bikesharing/shell/run.py` (modified): `_VOLUME_WINDOW` is 7 days.
- `docs/data-quality.md` (modified): DQR12's row with 95% and 7 days, linking to [D6](#d6-volume-drop-at-95-of-a-7-day-median).
- Tests: the unit rows of R28 and R29, and the Inspection row of R28.

#### Reads

- [D6](#d6-volume-drop-at-95-of-a-7-day-median) and [Volume drop](#volume-drop), in this design: the values and where they apply.
- [d008 › Transformation in dbt](d008-pipeline-platform-and-walking-skeleton.md#transformation-in-dbt) › Volume drop: the model's columns and statuses.
- `pipeline/dbt/models/silver/capture_volume.sql` and its unit tests in `silver.yml`: what changes.

#### Do

1. Update the unit tests in `silver.yml`.
2. Update `capture_volume.sql` and `_VOLUME_WINDOW` in `run.py`.
3. Update DQR12's row in `docs/data-quality.md`.
4. Run `bash pipeline/scripts/check-pipeline.sh`.

#### Check

- `bash pipeline/scripts/check-pipeline.sh` passes.
- The Inspection row of R28 holds: yes/no.

### Step 17 — Monitoring: Terraform pin, provider and lockfile

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `build: d009.s17 pin Terraform and Grafana's provider`
- **R:** —
- **Model:** haiku · low
- **Review:** no

#### Scope

The `monitoring/` component's stack, as `.claude/rules/code/dependencies.md` sets for Terraform.

- `monitoring/.terraform-version` (new): `1.17.1` ([Prerequisites](#31-prerequisites)).
- `monitoring/versions.tf` (new): `required_version` as a compatibility range that includes 1.17.1, and `grafana/grafana` at `~> 4.54`.
- `monitoring/.terraform.lock.hcl` (new): written by `terraform providers lock` with the hashes of `darwin_arm64`, the owner's machine, and `linux_amd64`, CI's, 4.54.0 locked.
- `.gitignore` (modified): Terraform's state files and `.terraform/`.

#### Reads

- `.claude/rules/code/dependencies.md` and `.claude/rules/code/terraform.md`: the files and how the lockfile is written.
- [Prerequisites](#31-prerequisites), in this design: the versions.

#### Do

1. Write `.terraform-version` and `versions.tf`.
2. Run `terraform -chdir=monitoring providers lock -platform=darwin_arm64 -platform=linux_amd64`, the owner's Apple silicon machine and CI's.
3. Update `.gitignore`.

#### Check

- `terraform -chdir=monitoring version` prints `Terraform v1.17.1`: yes/no.
- `git status` shows no state file or `.terraform/` to commit: yes/no.

### Step 18 — Monitoring: provider, variables and check script

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `build: d009.s18 configure Grafana's provider and the monitoring checks`
- **R:** R37
- **Model:** sonnet · low
- **Review:** security

#### Scope

The provider configured from variables, secrets only from `.env`, and the check that CI runs.

- `monitoring/providers.tf` (new): the provider's `url`, `auth`, `sm_url` and `sm_access_token` from variables.
- `monitoring/variables.tf` (new): the variables of the File layout; the tokens and the watchdog's URL `sensitive` with no default (R37); the systems' DQM7 targets, the published files and the GitHub base URL with their defaults.
- `.env.example` (modified): each secret as an empty `TF_VAR_<name>`.
- `monitoring/scripts/check-monitoring.sh` (new): `terraform fmt -check -recursive`, `init -backend=false -lockfile=readonly`, `validate` and `test`, as CI runs them.
- `monitoring/tests/alerting.tftest.hcl` (new): `mock_provider "grafana"` and `command = plan`; the first run block checks that the watchdog's URL is `sensitive` with no default (R37).
- Tests: the unit row of R37.

#### Reads

- [Grafana configuration](#grafana-configuration), in this design: what Terraform manages.
- [Prerequisites](#31-prerequisites), in this design: the credentials and their scopes.
- `.claude/rules/code/terraform.md`: secrets, files and the test tool.

#### Do

1. Write `variables.tf` and `providers.tf`.
2. Update `.env.example`.
3. Write `check-monitoring.sh` and `alerting.tftest.hcl`.
4. Run `bash monitoring/scripts/check-monitoring.sh`.

#### Check

- `bash monitoring/scripts/check-monitoring.sh` passes.
- No token, URL or other secret value appears in `monitoring/` or `.env.example`: yes/no.

### Step 19 — Monitoring: locals

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d009.s19 derive the alerts' thresholds and event selectors`
- **R:** R14, R15, R16, R22
- **Model:** sonnet · medium
- **Review:** no

#### Scope

Every threshold and event list the rules use, derived from the registry and the run settings, so no rule holds a literal figure or a hand-written list.

- `monitoring/locals.tf` (new): the registry and `run_settings.json` read with `jsondecode(file(...))`; ALR7's thresholds at 80% of the timeout and of the container's memory (R14); ALR8's at 2 cadences for the pipeline and 5 min for capture (R15); the other thresholds of [Thresholds](#thresholds), each fixed one with its reason in a comment; each alert's event selector from the events that list it; ALR9's events with `needs_action` and no alert (R16), and ALR14's set of registered events (R22).
- `monitoring/tests/alerting.tftest.hcl` (modified): run blocks for each derived value.
- Tests: the unit rows of R14 and R15, and the part of R16 and R22 that builds the lists.

#### Reads

- [Thresholds](#thresholds) and [Observability catalog](#observability-catalog), in this design: each threshold and how the registry feeds the rules.
- `.claude/rules/code/terraform.md`: thresholds as named locals.
- `contracts/log-events.registry.json` and `pipeline/src/bikesharing/core/run_settings.json`: the data read.

#### Do

1. Write the run blocks in `alerting.tftest.hcl`.
2. Write `locals.tf`.
3. Run `bash monitoring/scripts/check-monitoring.sh`.

#### Check

- `bash monitoring/scripts/check-monitoring.sh` passes.
- `locals.tf` holds every threshold of [Thresholds](#thresholds), and no rule file will need a literal one: yes/no.

### Step 20 — Monitoring: contact points, policies and template

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d009.s20 route and lay out the alert notifications`
- **R:** R19, R23, R24, R34, R35, R38
- **Model:** sonnet · medium
- **Review:** code and security

#### Scope

Where each alert goes and what its notification shows.

- `monitoring/contact_points.tf` (new): email, IRM, and the watchdog's webhook with its URL from the sensitive variable.
- `monitoring/notification_policies.tf` (new): grouping by `alert_id` and `system` and the repeat intervals of [Notification grouping](#notification-grouping); `urgency = "page"` to IRM (R34), `urgency = "ticket"` to the alert list with no notification (R35); ALR12 to the watchdog every 5 min, and no other policy reaching it (R19).
- `monitoring/message_template.tf` (new) and `monitoring/templates/notification.tmpl` (new): the layout of [Notifications](#notifications), the alert's ID and checked IDs (R23) and the links to the catalog section, the alert's row and the events in Explore (R24), read only from labels and annotations (R38).
- `monitoring/tests/alerting.tftest.hcl` (modified): run blocks for the routing and ALR12's policy.
- Tests: the unit rows of R19, R34 and R35, and the Inspection row of R38.

#### Reads

- [D11](#d11-pages-for-what-waiting-makes-worse-tickets-for-the-rest), [D13](#d13-a-watchdog-outside-grafana-watches-its-alerting) and [D15](#d15-monitoring-security-threats), in this design: urgency, watchdog and what a notification may carry.
- [Notifications](#notifications), [Notification grouping](#notification-grouping) and [Watchdog](#watchdog), in this design: the layout, grouping and the watchdog's route.

#### Do

1. Write the run blocks in `alerting.tftest.hcl`.
2. Write `contact_points.tf`, `notification_policies.tf`, `message_template.tf` and `templates/notification.tmpl`.
3. Run `bash monitoring/scripts/check-monitoring.sh`.

#### Check

- `bash monitoring/scripts/check-monitoring.sh` passes.
- The template reads no field other than the alert's labels and annotations: yes/no.

### Step 21 — Monitoring: alerts on events

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d009.s21 alert on the events that need action`
- **R:** R7, R8, R9, R16, R17, R18, R22, R23, R41
- **Model:** opus · medium
- **Review:** code

#### Scope

The rules that fire on an event, the pattern the later rule steps follow.

- `monitoring/alert_rules.tf` (new): the rules' folder; ALR1 and ALR2 on failed runtime rules by severity, with `rule` taken from the event as a label (R7, R8); ALR3 on the page's failed deployment (R9); ALR9 (R16), ALR10 (R17), ALR11 (R18) and ALR14 (R22) from the selectors of `locals.tf`; each with `alert_id`, `urgency` and the checked catalog IDs the template reads (R23), and grouped by `system` with no list of systems (R41).
- `monitoring/tests/alerting.tftest.hcl` (modified): a run block per rule for its query, labels and urgency.
- Tests: the unit rows of R7–R9, R16–R18, R22, R23 and R41 for these rules.

#### Reads

- [D3](#d3-alerts-on-symptoms-that-need-action) and [D4](#d4-alerts-carry-their-own-id-and-the-catalog-ids-they-check), in this design: the alerts and their labels.
- [D9](#d9-a-missed-minutes-cause-goes-to-whoever-can-act-on-it), in this design: the causes ALR11 accepts.
- [Field mapping](#field-mapping) and [Grafana configuration](#grafana-configuration), in this design: the fields the queries select on.
- `.claude/rules/code/terraform.md`: how rules are written and tested.

#### Do

1. Write the run blocks in `alerting.tftest.hcl`.
2. Write the rules in `alert_rules.tf`.
3. Run `bash monitoring/scripts/check-monitoring.sh`.

#### Check

- `bash monitoring/scripts/check-monitoring.sh` passes.
- No query names a system: yes/no.

### Step 22 — Monitoring: threshold alerts and ALR12

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d009.s22 alert on thresholds and keep the watchdog's alert firing`
- **R:** R11, R14, R15, R19, R21, R39, R42
- **Model:** sonnet · medium
- **Review:** code

#### Scope

The rules that fire on a count or a measure over a window, and the rule the watchdog listens to.

- `monitoring/alert_rules.tf` (modified): ALR5, minutes in a row with no clean capture per system and feed, as a page, held only while capture's events reach Grafana (R11, R42); ALR7 on `duration_s` and `peak_memory_mb` (R14); ALR8 per component (R15); ALR13 on the Free tier's use (R21); ALR15 on each feed's minutes given to capture over 7 days (R39); ALR12, whose condition always holds (R19). Thresholds from `locals.tf`.
- `monitoring/tests/alerting.tftest.hcl` (modified): a run block per rule.
- Tests: the unit rows of R11, R14, R15, R19, R21, R39 and ALR5's part of R42.

#### Reads

- [Thresholds](#thresholds), [Capture silence](#capture-silence) and [Watchdog](#watchdog), in this design: each threshold, the condition of R42 and ALR12.
- [D10](#d10-a-target-on-captures-own-missed-minutes-only), in this design: how ALR15 counts.
- `monitoring/alert_rules.tf`, from Step 21: the pattern to follow.

#### Do

1. Write the run blocks in `alerting.tftest.hcl`.
2. Add the rules to `alert_rules.tf`.
3. Run `bash monitoring/scripts/check-monitoring.sh`.

#### Check

- `bash monitoring/scripts/check-monitoring.sh` passes.

### Step 23 — Monitoring: error budget module

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d009.s23 alert on each system's error budget burn`
- **R:** R12, R13, R42
- **Model:** sonnet · medium
- **Review:** code

#### Scope

ALR6's three burn-rate levels, one rule group per system.

- `monitoring/modules/error_budget_alert/main.tf` and `variables.tf` (new): as [Error budget alert module](#error-budget-alert-module) sets.
- `monitoring/alert_rules.tf` (modified): the module called once per system, with its DQM7 target from the variables.
- `monitoring/tests/alerting.tftest.hcl` (modified): three rules per system with their burn rates, windows and thresholds, both windows required, the 1 h and 6 h levels as pages and the 3 d level as a ticket (R12, R13); each held only while capture's events reach Grafana (R42); a target outside (0, 1) rejected.
- Tests: the unit rows of R12 and R13, and ALR6's part of R42.

#### Reads

- [Error budget alerts](#error-budget-alerts) and [Error budget alert module](#error-budget-alert-module), in this design: the levels and the module's contract.
- [D7](#d7-capture-completeness-target-per-system), in this design: the targets.

#### Do

1. Write the run blocks in `alerting.tftest.hcl`.
2. Write the module and call it from `alert_rules.tf`.
3. Run `bash monitoring/scripts/check-monitoring.sh`.

#### Check

- `bash monitoring/scripts/check-monitoring.sh` passes.

### Step 24 — Monitoring: synthetic check

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `feat: d009.s24 check the published files' age from outside`
- **R:** R10, R16, R22
- **Model:** sonnet · medium
- **Review:** code and security

#### Scope

ALR4's check from three probes, and the last alert, which completes the set the registry may cite.

- `monitoring/synthetic_check.tf` (new): a scripted k6 check every 5 min from three probes, with the published files and ALR4's threshold from `locals.tf`.
- `monitoring/checks/published_file_age.js` (new): reads each file the page serves, and fails when its data's age since `data_instant` exceeds the threshold or it cannot be read or parsed.
- `monitoring/alert_rules.tf` (modified): ALR4, firing when at least two of the three probes fail, as a page.
- `monitoring/tests/alerting.tftest.hcl` (modified): the check's frequency, probes and threshold, and ALR4's condition (R10); every alert ID in the registry is one Terraform declares (R16, R22).
- Tests: the unit row of R10, and the remaining part of R16 and R22.

#### Reads

- [D8](#d8-page-data-age-keeps-its-target) and [D14](#d14-the-synthetic-check-confirms-a-failure-from-two-of-three-probes), in this design: the target and the two of three probes.
- [Synthetic check](#synthetic-check), in this design: what the script measures and why not `Last-Modified`.
- `pipeline/src/bikesharing/core/published_file.py`: where `data_instant` sits in a published file.

#### Do

1. Write the run blocks in `alerting.tftest.hcl`.
2. Write `published_file_age.js` and `synthetic_check.tf`.
3. Add ALR4 to `alert_rules.tf`.
4. Run `bash monitoring/scripts/check-monitoring.sh`.

#### Check

- `bash monitoring/scripts/check-monitoring.sh` passes.
- The script fetches only the page's public files and sends no credential: yes/no.

### Step 25 — CI job monitoring and filters

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `ci: d009.s25 add the monitoring job and the registry to the filters`
- **R:** —
- **Model:** sonnet · low
- **Review:** code

#### Scope

The `monitoring` component in CI, and every job that reads a shared file runs when it changes.

- `.github/workflows/ci.yml` (modified): the job `monitoring`, following `.claude/rules/code/ci.md`, running `bash monitoring/scripts/check-monitoring.sh`; its filter holds `monitoring/**`, the event registry, its schema and `pipeline/src/bikesharing/core/run_settings.json`, which Terraform reads; the filters of `capture` and `pipeline` add the registry and its schema.
- `docs/testing-strategy.md` (modified): the monitoring component's section, and the registry tests of capture and the pipeline.

#### Reads

- `.claude/rules/code/ci.md`: the recipe of a component job and its filter.
- `.github/workflows/ci.yml`: the existing jobs and filters.
- `docs/testing-strategy.md`, a component's section: the layout of the new one.
- [Test plan](#26-test-plan), in this design: what `terraform test` verifies and what it does not.

#### Do

1. Add the job and the filters to `ci.yml`.
2. Update `docs/testing-strategy.md`.

#### Check

- The job follows each item of the recipe in `ci.md`, Terraform's version read from `.terraform-version`: yes/no.
- Each file Terraform reads with `file(...)` is in the job's filter: yes/no.
- The lint hook reports no error on `testing-strategy.md`.

### Step 26 — Architecture

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `docs: d009.s26 add monitoring to the architecture`
- **R:** —
- **Model:** sonnet · low
- **Review:** no

#### Scope

- `docs/architecture.md` (modified): monitoring as a building block, Grafana Cloud configured as code from `monitoring/`; its deployment, applied by the owner as [ADR-0051](../decisions/0051-monitoring-configuration-as-code.md) sets; the watchdog beside the heartbeats in Healthchecks.io; the event registry as a shared contract.

#### Reads

- [ADR-0051](../decisions/0051-monitoring-configuration-as-code.md): where the configuration lives and how it is applied.
- [D13](#d13-a-watchdog-outside-grafana-watches-its-alerting) and [Observability catalog](#observability-catalog), in this design: the watchdog and the registry.
- `docs/architecture.md`, building blocks and deployment view: where each item goes.
- `.claude/rules/docs/architecture.md`: how the document is written.

#### Do

1. Update `docs/architecture.md`.

#### Check

- The lint hook reports no error.
- Every statement added cites its ADR or decision: yes/no.

### Step 27 — PR and merge

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** —
- **R:** —
- **Model:** haiku · low
- **Review:** no

#### Scope

The build reaches `main`; the task stays open until the checks of Step 32.

#### Reads

- CLAUDE.md › Branches, PRs and CI: the PR's title, description and merge.

#### Do

1. Push `t060.2-monitoring` and open the PR `T060.2: Monitoring capture and pipeline`, with 2–3 lines of description and `Refs #64`.
2. Wait for every required check to pass, `monitoring` included.
3. Rebase merge, delete the local branch with `-D`, and recreate `t060.2-monitoring` from an up-to-date `main`.

#### Check

- The PR is merged with every check green: yes/no.

### Step 28 — Deploy capture

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** —
- **R:** R43
- **Model:** haiku · low
- **Review:** no

#### Scope

Capture sends its events to Grafana, and its heartbeat check follows the new cadence.

#### Reads

- [d004 › Deployment](d004-bronze-data-capture.md#deployment): how capture is deployed and its smoke test.
- [Capture's OTLP sender](#captures-otlp-sender), in this design: `OTLP_TOKEN` is base64 of `<instance ID>:<token>`.

#### Do

1. Run `npx wrangler secret put OTLP_TOKEN` in `capture/`, pasting base64 of `<instance ID>:<token>` with the `logs:write` token of [Prerequisites](#31-prerequisites).
2. Deploy capture and run its smoke test, as d004 › Deployment sets.
3. Once Healthchecks.io shows a signal at a minute that is a multiple of 5, set capture's check to a period of 10 min and a grace of 10 min. Not before: the Worker deployed until then signals once an hour.

#### Check

- Grafana's Explore shows capture's events with `warn` and `system`: yes/no.
- Capture's check in Healthchecks.io has a 10 min period and 10 min of grace, and is up (R43, Inspection): yes/no.

### Step 29 — Deploy the pipeline

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** —
- **R:** —
- **Model:** haiku · low
- **Review:** no

#### Scope

The scheduled pipeline sends its events to Grafana; a one-off run sends nothing.

#### Reads

- [Step 14](#step-14--pipeline-monitoring-modal-secret), in this design: the Secret's name and keys.

#### Do

1. Create the Modal Secret `bikesharing-pipeline-monitoring` with `OTLP_ENDPOINT`, the stack's OTLP logs URL, and `OTLP_TOKEN`, the value of Step 28.
2. Run `bash pipeline/scripts/deploy.sh`.

#### Check

- After the next scheduled run, Grafana's Explore shows the pipeline's events: yes/no.

### Step 30 — Watchdog and `terraform apply`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** —
- **R:** R20
- **Model:** sonnet · medium
- **Review:** no

#### Scope

Grafana's alerts, contact points, synthetic check and the watchdog are live.

#### Reads

- [Watchdog](#watchdog), in this design: the check's period and grace.
- [ADR-0051](../decisions/0051-monitoring-configuration-as-code.md): how the configuration is applied and where its state lives.

#### Do

1. Create the watchdog's check in Healthchecks.io, with a period of 5 min, a grace of 10 min and the owner's email.
2. Set its signal URL and the Grafana credentials in `.env`, as `.env.example` names them.
3. With `.env` loaded, run `terraform -chdir=monitoring init`, then `plan`, and `apply` once the plan shows only the resources of this design.

#### Check

- The watchdog's check has a 5 min period, 10 min of grace and the owner's email, and is up (R20, Inspection): yes/no.
- Grafana shows the rules ALR1–ALR15, and the synthetic check runs from three probes: yes/no.

### Step 31 — Demonstrations

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** —
- **R:** R10, R23, R24, R36, R40
- **Model:** sonnet · medium
- **Review:** no

#### Scope

The Demonstration rows of the [Test plan](#26-test-plan), and the notifications of [Done when](#14-done-when).

#### Reads

- [Test plan](#26-test-plan), the Demonstration rows, and [Done when](#14-done-when), in this design.
- `docs/observability.md`: the provider's minutes query.

#### Do

1. Send a test page and a test ticket from Grafana.
2. Run the synthetic check with ALR4's threshold set to 0 min for one probe, then restore it.
3. Open a test notification's links.
4. Run the provider's minutes query in Explore, in the browser and the mobile app.

#### Check

- The test page rings on the phone until acknowledged, and the test ticket appears in the app's list with no notification: yes/no.
- The k6 script passes on the live file and fails the probe with a threshold of 0 min (R10): yes/no.
- The notification shows the alert's ID and checked IDs, and its links open the catalog section, the alert's row and the events in Explore (R23, R24): yes/no.
- Explore shows events of capture and the pipeline and the synthetic check's results, in the browser and the app (R36), and the query shows each feed's minutes given to the provider over 7 days (R40): yes/no.

### Step 32 — Production checks and close

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** `docs: d009.s32 record the production checks and close`
- **R:** —
- **Model:** sonnet · low
- **Review:** no

#### Scope

The checks of [Done when](#14-done-when) on production data, and the records that close the task, written by the session that guides the owner.

- `docs/observability.md` (modified): the version and date capture changed to `warn` and `system`, resolving its `TODO(T060.2):` marker.
- `docs/designs/d009-monitoring.md` (modified): Close, with the Grafana account's facts and Free tier features of [Prerequisites](#31-prerequisites) and the checks below.

#### Reads

- [Done when](#14-done-when) and [Prerequisites](#31-prerequisites), in this design: what is recorded.

#### Do

1. Check that events of capture and of the pipeline reach Grafana, the watchdog's check is green, and the synthetic check reads the page from its three probes.
2. Record the outcomes, the account's facts and capture's deployed version and date.
3. Open the PR `T060.2: Monitoring capture and pipeline` with `Closes #64`, and merge it as in Step 27.

#### Check

- Every item of Done when is recorded in Close: yes/no.
- `grep -rn "TODO(T060.2)" .` finds nothing: yes/no.

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
