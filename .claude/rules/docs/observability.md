---
paths:
  - "contracts/log-events.registry.json"
  - "docs/observability.md"
---

# Observability catalog rules

The observability catalog is two files: `contracts/log-events.registry.json`, the registry and single source of every component's log events, and `docs/observability.md`, which holds the rest (common fields, heartbeat checks, alerts, error budgets, notification layout) and links to the registry for the events. The entry's shape is fixed by `contracts/log-events.schema.json`, and the registry tests check it with the rules below that a schema cannot express; this file holds only the conventions for writing.

- **Registry entries:**
  - A component adds its events in the design that designs its logs; a new component also adds itself to the schema's `component` enum.
  - Entries are ordered by `component`, then `event`, so that a diff shows one change per line.
  - **event:** what happened, as a noun and a past participle in snake_case (e.g. `feed_captured`, `log_upload_failed`); one pair of `component` and `event` per entry.
  - **fields:** only the event's own fields; the common fields of ADR-0036 and `run_id` are never listed.
  - **needs_action:** set by the criterion in `docs/observability.md` › Actionable events; an event is never left out to avoid classifying it.
  - **alerts:** the IDs of the alerts that read the event by name; an alert that reads by class, such as ALR9 or ALR14, is never listed. An event that needs action and lists no alert is what ALR9 reads.
  - **description:** what the event records, in one sentence; what the owner does about it belongs in the alert that reads it.
- **Changes:** logs are append-only, so renaming an event or a field, or changing a level, records in `docs/observability.md` the component's version and the date of the change, and the names before it, so that queries over older logs accept both.
- **Alerts:** one row per alert in `docs/observability.md`, with its ID, summary, the catalog IDs it checks, and its urgency (`page` or `ticket`); the events it reads are those that list it in the registry, never repeated in the row. The summary names the kind of failure, never the text of the rule it checks.
- **IDs:** an alert's ID is `ALR` followed by the next free number; an ID is never reused, and a retired alert keeps its row, marked retired.
