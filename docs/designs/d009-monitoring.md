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
- Phase: [x] Spec · [ ] Plan · [ ] Plan review · [ ] Steps · [ ] Steps review
- Current: Plan › Test plan; Components written. Check there capture's heartbeat limit: `heartbeat.js` says 10 s, Thresholds says capture's send uses 5 s "as capture's heartbeat". Then What does not change, which holds: `pipeline/modal_one_off.py` gets no monitoring Secret (d008 › Observability).

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

DQM11 takes a target on the minutes D9 gives to capture: at most 30 minutes per feed and calendar month. The minutes given to the provider are measured and shown with no target, since the owner takes no action on them and DQM7 already bounds their effect on completeness (D7). Over the first 14.6 days of production pass logs (2026-11-07 10:19 to 2026-11-22 01:39 UTC), each dynamic feed lost 6 or 7 minutes to capture, each a single minute and at most one a day: four passes the cron never ran, the same minutes for every feed, and passes logged with no event for any feed; about 10 minutes a month. The provider took 13 and 15 minutes from AMBici's two feeds and 486 from Bicing's, 481 of them a 403, 32 a day at the median; no run of missed minutes lasted over 5 minutes ([`spikes/d009-baselines/capture-gaps/`](../../spikes/d009-baselines/capture-gaps/)). The target sits at about three times that baseline, which comes from two weeks only, following the SRE practice of D7: a target on what the owner can fix, set from measured performance and revised. ALR15 warns when a feed's minutes given to capture over the last 7 days exceed the target's share for 7 days, 7 minutes, against about 3 a week today: Grafana keeps 14 days of events and cannot add up a calendar month, so the alert follows a rolling window, and the month's value is queried with SQL over R2 ([ADR-0036](../decisions/0036-log-convention-across-components.md)), as [s018 › D6](../spikes/s018-monitoring-tool.md#d6-quality-indicators-reach-the-tool-by-push) sets. **#6**

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
- **R39** When a feed's minutes given to capture over the last 7 days exceed 7, the 7-day share of DQM11's target, Grafana shall raise ALR15 as a ticket. (D3, D10, D11, #6)
- **R40** Grafana shall show each feed's minutes given to the provider over the last 7 days, with no target. (D10, #6)
- **R41** Grafana's queries and alerts shall select events by the fields they carry, with no list of systems. (D1)
- **R42** While no event of capture has reached Grafana within ALR8's threshold, Grafana shall not raise ALR5 or ALR6. (D2, #10)
- **R43** If no heartbeat signal of capture arrives within 10 min plus 10 min of grace, then the heartbeat service shall email the owner; capture shall signal it from one pass in five, when that pass stored all three dynamic feeds. (#10)

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

The observability catalog of D5 is a registry of events with its schema, and a document. `contracts/log-events.registry.json` is the registry, the single source of each event of every component: its component, level, own fields and whether it needs an action from the owner. `contracts/log-events.schema.json`, a JSON Schema (draft 2020-12) that the registry names in `$schema`, fixes the shape of an entry, and the registry test validates the registry against it. The registry is reference data written in the repository and read by several components, not data one component sends another, so it has no test vectors ([ADR-0050](../decisions/0050-contract-tests-by-contract-kind-with-native-schemas.md) covers the latter). `docs/observability.md`, beside `docs/data-quality.md`, holds the rest: the common fields of ADR-0036, the heartbeat checks, the alerts with their IDs, the catalog IDs they check and their urgency, and how alerts on an error budget work; it links to the registry for the events. Terraform reads the registry to build the event lists of ALR9 and ALR14, and the tests of capture and the pipeline check that every event they write is registered. **#2**

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

ALR6 follows the SRE Workbook's multiwindow, multi-burn-rate alert, written as LogQL alert rules over capture's events. For each system and window, the error rate is one minus the minutes with a `feed_captured` over the minutes DQM7 counts in the window, so a minute with no pass counts as missed with no rule of its own; the burn rate is that error rate over the system's budget, one minus its DQM7 target (D7). A level fires when both its windows exceed its burn rate: the long one shows the burn is serious, the short one that it is still going on.

| Level | Burn rate | Long window | Short window | Budget spent in the long window |
|---|---|---|---|---|
| Page | 14.4 | 1 h | 5 min | 2% |
| Page | 6 | 6 h | 30 min | 5% |
| Ticket | 1 | 3 d | 6 h | 10% |

A Terraform module builds the three levels from each system's target, so a new system or target is one variable; every window fits Grafana's 14 days. The budget left in the month is queried with SQL over R2, as DQM11's month is (#6). **#7**

- **What would change it:** a longer retention, from a paid plan, or many more SLOs: Grafana's SLO app then gives its budget view, with the same queries kept as Loki recording rules; the alert, its ID and its requirements are unchanged.

#### Thresholds

Each threshold is a formula over the settings it depends on, never a figure measured on the walking skeleton, so a change of cadence, time budget or container size changes every threshold that depends on it with no rewrite; the measured figures only show that each alert stays quiet today.

| Threshold | Formula | Today | Measured today |
|---|---|---|---|
| ALR4, age of a published file | cadence + time budget, DQM10's target (D8) | 22 min | 19.6 min at most |
| Synthetic check frequency | fixed, while the cadence is longer than it | 5 min | — |
| ALR7, run duration (`duration_s`) | 80% of the time budget | 336 s | 43–70 s per steady-state run |
| ALR7, run memory (`peak_memory_mb`) | 80% of the container's memory | 3,436 MB (80% of 4,096 MiB) | 2,428 MB at most |
| ALR8, pipeline silent in Grafana | 2 × cadence | 30 min | — |
| Pipeline's send time limit (R5) | fixed, one attempt | 10 s | — |
| ALR5, minutes in a row with no clean capture of a feed | fixed: capture's cadence is one pass a minute ([d004](d004-bronze-data-capture.md)) | over 10 | 5 at most, any cause |
| ALR8, capture silent in Grafana | fixed | 5 min with no event | — |
| Capture's send time limit (R5) | fixed, one attempt, as capture's heartbeat | 10 s | — |
| ALR13, logs of the month | 80% of the Free tier's 50 GB | 40 GB | about 200 MB a month (D1) |
| ALR13, synthetic check executions of the month | 80% of the Free tier's 100k | 80k | 25,920 a month (D14) |
| ALR12, watchdog signal | the watchdog policy's `repeat_interval` | 5 min | — |
| Watchdog check in Healthchecks.io | period and grace | 5 min and 10 min | — |

ALR4 fires at the target itself, since the target is what the page promises its visitor. ALR7 follows the practice of warning at 80% of a capacity limit: runs that grow towards the time budget as later children add models raise it, which is the signal to review the cadence or the budget. ALR8 at two cadences lets one lost send go, since the copy is best-effort (D2); a run that never starts is reported by the heartbeat. The pipeline's send uses the per-attempt timeout of the heartbeat's pings ([d008 › Observability](d008-pipeline-platform-and-walking-skeleton.md#observability)). ALR5 at twice the longest run measured stays quiet in normal operation; on AMBici the fast burn of ALR6 fires first, so ALR5 serves Bicing, whose budget is larger, and the feeds DQM7 does not count. ALR8 at five passes with no event points to a broken send rather than a single failure, and is the window of R42. ALR13 warns at 80% of each Free tier limit, as ALR7 does, reading Grafana Cloud's usage data source; if the Free tier lacks it, which account set-up checks with the other Free tier features, Grafana Cloud's own usage notifications cover it, as for Cloudflare and Modal (D3). A Grafana that stops evaluating or notifying is reported by email in about 15 min, the grace covering one lost signal; the watchdog takes the third of Healthchecks.io's 20 free checks. **#8**

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

ALR12 is an alert rule whose condition always holds, with a notification policy of its own that sends it every 5 min, its `repeat_interval`, to a webhook contact point on the watchdog's check in Healthchecks.io, never through IRM (D13). The check's URL enters Terraform as a sensitive variable from `.env` (R37).

#### Volume drop

DQR12 follows D6 in the model `capture_volume`: the median takes the captures of the 7 days before each capture instant, and a capture is flagged below 95% of it, with the minimum of 60 captures unchanged. The history the shell reads from `processed_objects` widens from 24 h to 7 days before the batch's first capture, about 20,000 rows, and the model's dbt unit tests take the new window and threshold. **refines [d008 › D4](d008-pipeline-platform-and-walking-skeleton.md#d4-volume-drop-against-a-rolling-median)**

#### Notification grouping

Notifications follow Alertmanager's grouping, which Grafana Alerting implements: an alert fires one instance per set of labels and stays firing while its condition holds, the notification policy groups instances by alert ID and system into one notification, repeats it every 4 h while it fires, Grafana's default `repeat_interval`, and sends one notice when it resolves. A page's repeats join its alert group in IRM, which notifies until the owner acknowledges it, so a failure that lasts hours pages once per alert and system.

The pipeline's cadence, time budget, timeout and container memory live in one data file, `pipeline/src/bikesharing/core/run_settings.json`: the core parses it into typed settings and the shell reads it once, as the functional core and imperative shell set ([ADR-0046](../decisions/0046-functional-core-imperative-shell-for-the-pipeline.md)), for the run and for Modal's app and image files, which take the schedule, the timeout and the container memory from it; Terraform reads it with `jsondecode(file(...))`, so the pipeline and its thresholds change together. The period and grace of the heartbeat's check stay in Healthchecks.io's console, outside Terraform (ADR-0051), and the catalog states that a change of cadence also changes them there. **#9**

#### Capture silence

Grafana cannot tell a capture that stores nothing from a capture whose send is broken: both reach it as no events. ALR5 and ALR6 are therefore evaluated only while capture's events reach Grafana, and a capture silent altogether raises ALR8 instead, so a broken send or an outage of Grafana's ingest never pages the owner for data that R2 holds. Whether data is being stored is checked from outside Grafana by capture's heartbeat, a dead man's switch that signals only when a pass stored all three dynamic feeds: capture signals it on every fifth pass, and Healthchecks.io emails the owner when no signal arrives within a period of 10 min plus 10 min of grace, so a capture that stores nothing is reported in about 20 min. A single failed signal, such as one of Bicing's scattered 403s, is covered by the next ones within the grace. **#10** **refines [d004 › D10](d004-bronze-data-capture.md#d10-capture-heartbeat)**

#### Sending the copy

Each component sends its events over OTLP/HTTP with JSON encoding, as [ADR-0049](../decisions/0049-log-events-copied-to-monitoring-over-otlp.md) sets, in one request per pass or run, after writing them to R2 (D2):

- **Capture:** after the pass's log is written to R2 and its heartbeat sent, the Worker sends the pass's events inside `ctx.waitUntil`, aborted at the send's time limit. The token is a Worker secret.
- **Pipeline:** after the run's log is uploaded to R2, the run sends its events, aborted at the send's time limit. The token is a Modal Secret of the scheduled function only ([d008 › Observability](d008-pipeline-platform-and-walking-skeleton.md#observability)).

A send that fails or reaches its limit is written to the platform's own logs, Workers Logs or stdout as `log_upload_failed` is, and changes nothing else: the R2 log is already written and the outcome and heartbeat signal are already set (R3–R5).

The copy is built from the same JSON lines written to R2, never serialized again, so each line reaches Grafana as the body of its record and the redaction each component applies before writing reaches the copy with no code of its own (R4, R6).

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
| 2 | [Observability catalog](#observability-catalog), [D5](#d5-one-observability-catalog-built-here) | The catalog's events in a machine-readable registry, `contracts/log-events.registry.json`, its single source, validated against its JSON Schema `contracts/log-events.schema.json`; `docs/observability.md` holds the rest and links to it (a registry as in OpenTelemetry's semantic conventions, validated by its schema as configuration files are) | Terraform and the components' tests read the same list; each fact lives in one place; a malformed entry fails CI | R16, R22, R25, R26 | Plan |
| 3 | [Observability catalog](#observability-catalog) | The criterion for classifying an event in `docs/observability.md`, enforced by the registry test, with a path rule for writing entries; no line in the design template (poka-yoke) | The test already blocks an unclassified event; the template would repeat it in every design | R16, R22, R25 | Plan |
| 4 | [Warning level](#warning-level) | `warn` for every component, OpenTelemetry's short severity name; capture changes from `warning`, and its logs in R2 are not rewritten (append-only logs) **refines [d004 › D9](d004-bronze-data-capture.md#d9-capture-logs)** | One name in queries from now on; the record stays as written | R27 | Plan |
| 5 | [Field mapping](#field-mapping) | `system` for the bike sharing system in every component's log events; capture changes from `source` in its logs only (one name per concept, as OpenTelemetry's semantic conventions, in ADR-0040's vocabulary) **refines [d004 › D9](d004-bronze-data-capture.md#d9-capture-logs)** | Queries by system cover every component with one field | R41 | Plan |
| 6 | [D10](#d10-a-target-on-captures-own-missed-minutes-only), [D3](#d3-alerts-on-symptoms-that-need-action) | ALR15 and the provider's minutes over a rolling 7 days in Grafana, from capture's events; DQM11's monthly value queried with SQL over R2 (alerts on rolling windows, SLO period measured from the durable store) | Grafana keeps 14 days; the pipeline needs no access to capture's logs | R39, R40 | Plan |
| 7 | [Error budget alerts](#error-budget-alerts) | ALR6 as LogQL alert rules built by a Terraform module, with the SRE Workbook's multiwindow, multi-burn-rate levels; not Grafana's SLO app | Fewer parts, every window within 14 days; moving to the SLO app later keeps the same queries | R12, R13 | Plan |
| 8 | [Thresholds](#thresholds) | The pipeline's thresholds as formulas over its cadence, time budget and container (ALR4 at DQM10's target, ALR7 at 80% of each limit, ALR8 at 2 cadences), a 5-minute synthetic check; capture's ALR5 over 10 minutes in a row and ALR8 at 5 min; each component's send limited to its heartbeat's timeout, 10 s; ALR13 at 80% of each Free tier limit; the watchdog signalling every 5 min to a check with 10 min of grace | Thresholds follow the pipeline as it grows and its cadence is tuned, with no rewrite; the others stay quiet at what production shows and warn with margin | R5, R10, R11, R14, R15, R19, R20, R21 | Plan |
| 9 | [Thresholds](#thresholds) | The pipeline's run settings in one JSON data file read by the pipeline and by Terraform (single source of truth, configuration as data) | A change of cadence is one edit; no copy to keep aligned | R10, R14, R15 | Plan |
| 10 | [Capture silence](#capture-silence) | ALR5 and ALR6 only while capture's events reach Grafana; a silent capture raises ALR8, and capture's heartbeat on every fifth pass, with 10 min of period and 10 min of grace, reports a capture that stores nothing (dead man's switch) **refines [d004 › D10](d004-bronze-data-capture.md#d10-capture-heartbeat)** | No page for a broken send; a dead capture reported in about 20 min instead of 2 h | R11, R12, R13, R15, R42, R43 | Plan |
| 11 | [Notifications](#notifications) | A message template of the project's own: alert ID, summary and checked IDs; where; the value against its threshold and since when, in Madrid's local time; then links to the item's catalog section, the alert's row and its events; no rule text copied (link, don't copy; actionable alerts show the value that fired) | Read on a phone, enough to tell a page from a wait; the item's text lives in its catalog only | R23, R24, R38 | Plan |
| 12 | [Observability catalog](#observability-catalog) | The provider's 7-day minutes as a LogQL query in `docs/observability.md`, run in Explore; no dashboard in this task (dashboards in T060.10) | Meets R40 with what Grafana ships, leaving every dashboard decision to the task that designs them | R40 | Plan |

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
│           └── observability.md                (new)       Conventions for writing a catalog entry (#3)
├── .github/workflows/
│   └── ci.yml                                  (modified)  Job monitoring; the registry and its schema in the filters of capture, pipeline and monitoring
├── contracts/
│   ├── log-events.registry.json                (new)       Every component's events: component, level, own fields, needs action (#2)
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
│   ├── package.json, package-lock.json         (modified)  JSON Schema validator as a dev dependency
│   ├── wrangler.jsonc                          (modified)  OTLP endpoint as a variable
│   ├── src/
│   │   ├── otlp.js                             (new)       Builds the OTLP/HTTP JSON request from the pass's lines and sends it within its limit
│   │   ├── log.js                              (modified)  warn and system (#4, #5); toLines serializes the events once, for the log and the copy
│   │   ├── heartbeat.js                        (modified)  Signal on every fifth pass that stored the three dynamic feeds (#10)
│   │   ├── pass.js                             (modified)  Sends the copy after the log and the heartbeat
│   │   └── worker.js                           (modified)  The send inside ctx.waitUntil; the token as a Worker secret
│   └── test/
│       ├── unit/otlp.test.js                   (new)       Request built from the lines; failed or late send changes nothing
│       ├── unit/log.test.js, unit/heartbeat.test.js (modified) warn and system; the fifth-pass signal
│       ├── integration/pass.test.js            (modified)  Order: log, heartbeat, copy
│       └── contract/log-events-registry.test.js (new)      Registry valid against its schema; every capture event registered
├── pipeline/
│   ├── modal_image.py                          (modified)  The monitoring token's Modal Secret; container memory and timeout from settings (#9)
│   ├── modal_app.py                            (modified)  That Secret on the scheduled function only; the schedule from the cadence in settings (#9)
│   ├── src/bikesharing/
│   │   ├── core/run_settings.json              (new)       Cadence, time budget, timeout and container memory (#9)
│   │   ├── core/settings.py                    (modified)  RunSettings and its pure parser; TIME_BUDGET moves into it
│   │   ├── core/events.py                      (modified)  otlp_send_failed, at warn, stdout only
│   │   ├── core/otlp_payload.py                (new)       Builds the OTLP/HTTP JSON request from the run's lines
│   │   ├── shell/event_log.py                  (modified)  lines(): the kept lines, for the copy
│   │   ├── shell/otlp_exporter.py              (new)       Sends it within its limit, one attempt; raises on failure
│   │   ├── shell/run_settings.py               (new)       Reads run_settings.json once into RUN_SETTINGS
│   │   └── shell/run.py                        (modified)  Sends the copy after the log upload and the ping, a failure to stdout; OTLP target in the scheduled config; 7-day volume history (DQR12)
│   ├── dbt/models/silver/
│   │   ├── capture_volume.sql                  (modified)  7-day median, 95% threshold (DQR12)
│   │   └── silver.yml                          (modified)  capture_volume's unit tests for the new window and threshold
│   └── tests/
│       ├── unit/core/test_otlp_payload.py      (new)       Request built from the lines
│       ├── unit/core/test_settings.py          (new)       Settings parsed from data; invalid data rejected
│       ├── integration/test_otlp_exporter.py   (new)       Failed or late send changes nothing
│       ├── integration/test_run.py             (modified)  Copy sent after the log upload
│       └── integration/test_log_events_registry_contract.py (new) Registry valid against its schema; every pipeline event registered
└── docs/
    ├── observability.md                        (new)       The catalog: common fields, heartbeat checks, alerts, error budgets, notification layout, the provider's minutes query (#2, #3, #11, #12)
    ├── data-quality.md                         (modified)  DQM7, DQM10, DQM11 and DQR12
    ├── architecture.md                         (modified)  Monitoring as a building block, and its deployment
    ├── testing-strategy.md                     (modified)  The monitoring component and the registry tests
    └── designs/
        ├── d004-bronze-data-capture.md         (modified)  D6, D9 with R20 and the level type, D10 with R19; links to the catalog
        └── d008-pipeline-platform-and-walking-skeleton.md (modified) D4; links to the catalog
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

- **Callers:** `EventLog.lines() -> tuple[str, ...]` returns the kept lines that `body()` joins. `scheduled_config` reads `OTLP_ENDPOINT` and `OTLP_TOKEN` into the run's configuration as an `OtlpTarget`; `one_off_config` sets none, so a one-off run sends nothing. `run` sends after the log upload and the heartbeat ping, and catches any exception as it does for the upload, emitting `otlp_send_failed(ts, *, error_type)` at `warn`, to stdout only; the outcome does not change (R3–R5).

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
      "required": ["event", "component", "level", "fields", "needs_action", "description"],
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
| R1 | Test | A pass's request, and a run's, holds one record per line written to R2, of every level, in order | integration |
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
| R12, R13 | Test | The module builds three rules per system with the burn rates and windows of [Error budget alerts](#error-budget-alerts), each threshold the burn rate times `1 - target`, both windows required, the 1 h and 6 h levels as pages and the 3 d level as a ticket; a target outside (0, 1) is rejected | unit |
| R14 | Test | ALR7's thresholds derive from `run_settings.json`: 80% of the time budget and of the container's memory | unit |
| R15 | Test | ALR8 fires per component after 2 cadences for the pipeline and 5 min for capture with no event, as a ticket | unit |
| R16, R22 | Test | ALR9 selects the registry's events with `needs_action` and no other alert, ALR14 every event the registry does not list, both built from the registry | unit |
| R17 | Test | ALR10 selects `index_refreshed` events with a non-empty `unknown_feeds` | unit |
| R18 | Test | ALR11 selects a pass's missed-minute cause outside D9's table | unit |
| R19 | Test | ALR12's condition always holds, its policy repeats every 5 min to the watchdog's webhook contact point, and no other policy reaches it | unit |
| R20 | Inspection | The watchdog's check in Healthchecks.io has a 5 min period, 10 min of grace and the owner's email | — |
| R21 | Test | ALR13 fires at 40 GB of logs and 80k check executions a month, as a ticket | unit |
| R23 | Test | Every rule carries `alert_id` and the checked catalog IDs that the template reads | unit |
| R23, R24 | Demonstration | A test notification shows the alert's ID and checked IDs, and its links open the catalog section, the alert's row and the events in Grafana's Explore | — |
| R25 | Test | The registry is valid against its schema, each `component` and `event` pair appears once, and every event capture and the pipeline write is registered | contract |
| R25, R26 | Inspection | `docs/observability.md` lists the common fields, the heartbeat checks, and every alert with its ID, checked IDs, urgency and the events it reads | — |
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
| R39 | Test | ALR15 sums each feed's minutes given to capture over 7 days and fires over 7, as a ticket | unit |
| R40 | Demonstration | The query in `docs/observability.md`, run in Explore, shows each feed's minutes given to the provider over the last 7 days, with no target | — |
| R41 | Test | Every rule's query groups by `system` and names no system, except ALR6's, which takes its system from the module's variable | unit |
| R42 | Test | Every ALR5 and ALR6 rule holds only while capture has events in Grafana within ALR8's threshold | unit |
| R43 | Test | Capture signals the heartbeat from one pass in five that stored the three dynamic feeds, and from no other pass | unit |
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
- Model: the model and effort the step's session runs with (e.g. sonnet · medium), or — when Who is Owner.
- Review: `code`, `security`, `code and security`, or `no`. A review goes on the step that completes a reviewable unit (a flow or action, usually built over several steps); the last code step has at least `code`. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

- TODO(T060.2): when choosing Terraform's versions, check whether `hashicorp/setup-terraform` reads a version file; if it does, `.claude/rules/code/ci.md` passes it `.terraform-version` directly, with no step reading it.

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
