# Observability

The observability catalog of capture and the pipeline: the log events each component writes, the alerts that read them and the heartbeat checks that watch each component from outside Grafana ([d009 › D5](designs/d009-monitoring.md#d5-one-observability-catalog-built-here)). It exists so that the owner can tell, from one place, what each event means, which alert reads it and what to do when that alert fires.

The catalog has two parts. [`contracts/log-events.registry.json`](../contracts/log-events.registry.json) is the registry and the single source of the events; [`contracts/log-events.schema.json`](../contracts/log-events.schema.json) fixes the shape of its entries. This document holds the rest: the common fields, the heartbeat checks, the alerts, how the error budget alerts work and the layout of a notification. It links to the registry for the events and never lists them, and an alert's row never lists the events it reads.

## How to read the catalog

- **An event** is one entry of the registry: its `component`, its `levels` (one, or several for an event whose level follows its outcome), its own `fields` (the common fields are not repeated), `needs_action`, the `alerts` that read it by name and a one-sentence `description`.
- **An alert** is one row of [Alerts](#alerts): its ID (`ALR` and a number, never reused), the kind of failure it signals, the catalog IDs it checks (`DQR` runtime rules and `DQM` quality indicators of [data-quality.md](data-quality.md)) and its urgency, `page` or `ticket`.
- **An alert reads an event** when the event lists the alert's ID in the registry. Two alerts read by class instead and are never listed: ALR9 reads the events that need an action and list no alert, and ALR14 reads every event the registry does not hold.

### Worked example

The pipeline checks the runtime rule DQR12 on a capture of Bicing and finds that it lists fewer stations than 95% of the 7-day median. The run follows this path:

1. The run writes the event `rule_checked` with `rule` `DQR12`, `rule_severity` `warn` and `status` `fail`, at level `warn`. It goes to R2 and, as a copy, to Grafana.
2. The registry entry of `rule_checked` (component `pipeline`) lists `ALR2` in `alerts`, so ALR2 reads it. ALR2 is a ticket: a rule of severity warn blocks nothing.
3. Grafana raises ALR2 with the rule's ID, `DQR12`, taken from the event, groups it by alert and system, and sends it to IRM as a ticket.
4. The ticket enters the list of alerts of the Grafana mobile app with no notification, until the owner closes it. It reads:

```text
[FIRING] [ALR2] A runtime rule of severity warn failed · DQR12
  pipeline · system: bicing · version: 3f2a9c1
  since 11:00 CET
  → rule in the catalog   → this alert   → events in Grafana
```

The first link opens `DQR12` in [data-quality.md](data-quality.md#runtime-rules), the second this alert's row in [Alerts](#alerts), the third the events that raised it in Grafana.

## Common fields

Every event of every component carries these fields first, in this order ([ADR-0036](decisions/0036-log-convention-across-components.md)). The events add their own fields, listed in the registry.

| Field | Content |
|---|---|
| `ts` | The event's time, in UTC |
| `level` | `info`, `warn` or `error` |
| `component` | The part of the system that wrote it: `capture` or `pipeline` |
| `version` | The identifier of the component's deployed code |
| `run_id` | The pass or run that wrote it |
| `event` | The event's name, a noun and a past participle in snake_case |

## Actionable events

An event needs an action from the owner when one occurrence of it calls for that action and no other signal reports it. The registry marks it `needs_action`, and an actionable event that lists no alert is what ALR9 reads.

An event is not actionable when waiting changes nothing or another signal already reports it:

- a retry that succeeds, such as `fetch_retried`, needs no action, and one that fails is a `feed_failed`;
- `heartbeat_failed` is reported by the missing signal of the heartbeat service;
- `log_upload_failed` leaves its events in Grafana, and a lasting R2 failure fails the batches too.

A design that adds or changes an event classifies it when it designs its logs, and the registry's test keeps an unclassified event from passing CI.

## Level and field names

Every component writes `warn` for a failure that does not affect the data and `system` for the bike sharing system, as the pipeline does ([d009 › Warning level and Field mapping](designs/d009-monitoring.md#warning-level)). Capture's code and bronze keys keep `source`.

Logs are append-only, so capture's logs in R2 written before the change keep `warning` and `source`. Capture writes `warn` and `system` from its Worker version `2f68178a-be4f-4bfc-99d7-a29ce8f9d544`, deployed on 2026-11-23. A query over both periods accepts `warn` or `warning` and `system` or `source`.

The pipeline's `rule_checked` writes the rule's configured severity as `rule_severity`, since Loki reads an attribute named `severity` as the log level ([d009 › DI10](designs/d009-monitoring.md#43-decisions-taken-during-implementation)). The pipeline writes `rule_severity` from version `8b20ef7ca29e0cebdacf07fcb59b0fa598c01874`, deployed on 2026-11-23. Its logs written before that keep `severity`, and a query over both periods accepts `rule_severity` or `severity`.

## Heartbeat checks

Each check is a dead man's switch of Healthchecks.io ([ADR-0031](decisions/0031-heartbeat-alerts-for-the-pipeline.md)): the component, or Grafana, signals it, and the service emails the owner at any hour when no signal arrives within the period plus the grace. Their period and grace are set in Healthchecks.io's console, outside Terraform; a change of the pipeline's cadence also changes its check there.

| Check | Signalled by | Period | Grace | Reports |
|---|---|---|---|---|
| Capture | Capture's pass whose scheduled minute is a multiple of 5, when it stored all three dynamic feeds | 10 min | 10 min | A capture that stores nothing, in about 20 min (R43) |
| Pipeline | The run: `/start` when it starts, then success or `/fail` as its last action | 15 min | 15 min | A run that never starts, ends in failure or is killed |
| Watchdog | ALR12, which always fires and signals every 5 min | 5 min | 10 min | A Grafana that no longer evaluates rules or sends notifications (R20) |

## Alerts

One row per alert. The urgency follows [d009 › D11](designs/d009-monitoring.md#d11-pages-for-what-waiting-makes-worse-tickets-for-the-rest): a page when waiting makes the harm worse, a ticket when the action can wait for days. A page notifies the owner on the phone from 08:00 to 23:00, Madrid time, and a ticket sends no notification. An alert that covers a class of items takes the failing item's ID from the event.

| ID | Summary | Checks | Urgency |
|---|---|---|---|
| ALR1 | A runtime rule of severity error failed | `DQR`, the failing rule | ticket |
| ALR2 | A runtime rule of severity warn failed | `DQR`, the failing rule | ticket |
| ALR3 | The page's deployment failed | — | ticket |
| ALR4 | A published file is older than its target | DQM10 | page |
| ALR5 | A feed has had no clean capture for too many minutes in a row | DQM11 | page |
| ALR6 | Capture burns a system's monthly error budget at a rate that would exhaust it | DQM7 | page at a fast burn, ticket at a slow one |
| ALR7 | A run nears its time or memory limit | — | ticket |
| ALR8 | A component sends no events to Grafana | — | ticket |
| ALR9 | An actionable event that no other alert reads reached Grafana | — | ticket |
| ALR10 | A provider's index lists a feed capture does not know | — | ticket |
| ALR11 | A pass logged a cause of a missed minute that DQM11 does not classify | DQM11 | ticket |
| ALR12 | Grafana stopped signalling the heartbeat service (watchdog) | — | page, by email from the heartbeat service |
| ALR13 | Grafana's use nears a limit of its Free tier | — | ticket |
| ALR14 | An event the registry does not hold reached Grafana | — | ticket |
| ALR15 | A feed's minutes given to capture over the last 7 days exceed the 7-day share of DQM11's target | DQM11 | ticket |

ALR6 and ALR15 are paused: their rules stay defined but Grafana does not evaluate them, since their queries read days of capture's logs every minute. TODO(T078): review their cost and resume them.

ALR12 never goes through Grafana's notifications or IRM, since every other alert is silent when Grafana is. The limits and costs of Cloudflare and Modal are watched by each provider's own usage and budget notifications.

## Error budget alerts

ALR6 follows the multiwindow, multi-burn-rate alert of the SRE Workbook, written as LogQL alert rules over capture's events. For each system and window:

- **Error rate:** one minus the minutes with a `feed_captured` over the minutes DQM7 counts in the window in which capture's events reach Grafana. Grafana counts those passes as the largest count, among capture's dynamic feeds, of `feed_captured` and `feed_failed` events in the window: every pass writes one of the two for each dynamic feed and sends all its events in one request.
- **Minutes with no pass in Grafana:** a pass the cron never ran, a pass that wrote no event or a gap in Grafana's ingest counts in no window, since Grafana cannot tell them apart. Capture's heartbeat reports a capture that stores nothing, and DQM7's monthly value over R2 counts every minute.
- **Burn rate:** the error rate over the system's budget, one minus its DQM7 target.
- **Firing:** a level fires when both its windows exceed its burn rate: the long window shows the burn is serious and the short one that it is still going on. Every window fits Grafana's 14 days.

| Level | Burn rate | Long window | Short window | Budget spent in the long window |
|---|---|---|---|---|
| Page | 14.4 | 1 h | 5 min | 2% |
| Page | 6 | 6 h | 30 min | 5% |
| Ticket | 1 | 3 d | 6 h | 10% |

ALR5 and ALR6 are evaluated only while capture's events reach Grafana. A capture silent altogether raises ALR8 instead, so a broken send never pages the owner for data that R2 holds. ALR15 counts a feed's minutes given to capture the same way, over 7 days. The budget left in the month is queried with SQL over R2 ([ADR-0036](decisions/0036-log-convention-across-components.md)).

## Notification layout

Every notification uses one message template, managed by Terraform, that reads only the alert's labels and annotations, never an event's body, so it carries no credentials and no visitor data:

```text
[FIRING] [ALR5] A feed has had no clean capture for too many minutes in a row
  capture · system: bicing · feed: station_status · version: 7f3c2a9
  14 minutes in a row · threshold: over 10 · since 11:12 CET
  → rule in the catalog   → this alert   → events in Grafana
```

- **First line:** the state, the alert's ID and summary, and the catalog IDs it checks, when it checks any.
- **Second line:** where it happens: the component, system, feed and version, those the alert carries.
- **Third line:** the value that raised the alert and its threshold, when it has one, and since when, in Madrid's local time with its zone (`CET` or `CEST`); stored times stay in UTC.
- **Links:** the section of [data-quality.md](data-quality.md) that holds the checked item (Runtime rules for a `DQR`, Quality indicators for a `DQM`), the alert's row in [Alerts](#alerts), and Grafana's Explore on the events that raised it, filtered by their labels and time.

The rule's text is not copied into the notification: the summary names the kind of failure and the item is one link away.

## Minutes given to the provider

DQM11 gives a minute with no capture of a feed to the provider when the pass logs an HTTP error status or a timeout from the provider, and to capture otherwise. Grafana shows the provider's minutes of each feed over the last 7 days, with no target, in Explore on the Loki data source, over the minutes in which capture's events reach Grafana:

```text
sum by (system, feed) (
  count_over_time({service_name="capture"} | event="feed_failed" | error_type=~"http|timeout" [7d])
)
```

A system's index has no feed, so its minutes come from `index_rejected`:

```text
sum by (system) (
  count_over_time({service_name="capture"} | event="index_rejected" | error_type=~"http|timeout" [7d])
)
```

Grafana keeps 14 days of events, so the month's value is queried with SQL over R2.
