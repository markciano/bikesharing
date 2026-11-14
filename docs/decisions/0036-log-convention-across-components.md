---
status: Accepted
date: 2026-11-06
supersedes: 0030
---

# One log convention for every component, with its origin in each event

## Context and problem statement

More than one component writes logs: capture runs on Cloudflare and the pipeline on Modal, each deployed on its own. [ADR-0030](archive/0030-pipeline-logs.md) set a convention for the pipeline's logs only, and left capture to align with it.

- Quality questions span components and are answered with one SQL query over the logs of all of them (T042), so events from different components must share a format and be told apart.
- A change of behaviour must be traced to the deployed code that caused it, and each component deploys independently of the others.
- The event names of different components can coincide, such as a run's start or a failed write.
- Capture's logs are permanent evidence in bronze under a bucket lock ([ADR-0023](0023-storage-security-baseline.md)); the pipeline must not write to bronze ([d002/R17](../designs/d002-requirements.md#requirements)).
- Nothing is built yet on the convention of ADR-0030.

## Considered Options

Each option is compared on whether one query can tell the origin of an event and its deployed code, and on what it adds to each component.

### 1. Common fields for the component and its version

Every event carries two more common fields: `component`, the part of the system that wrote it, and `version`, the identifier of its deployed code.

- Pros:
  - one field per meaning, filtered directly in SQL;
  - follows OpenTelemetry's `service.name` and `service.version`, the usual practice for telling services apart in shared logs.
- Cons:
  - two more fields in every event;
  - each component's deploy must make its version available at run time.

### 2. The origin as a prefix of the event name

Event names carry their component, such as `capture.feed_captured`.

- Pros:
  - no new field.
- Cons:
  - one field holds two meanings, split by a naming convention;
  - it still does not identify the deployed code.

### 3. Keep ADR-0030 as it is

Each component follows the four common fields of ADR-0030, and the origin is inferred from where the object is stored.

- Pros:
  - nothing to change.
- Cons:
  - the origin is lost once events from several components are read together;
  - no event identifies the deployed code.

## Decision Outcome

**Chosen option:** 1. Common fields for the component and its version.

It meets both forces of the Context, a shared query and a trace to the deployed code, with one field per meaning and an established practice. The cost is small while nothing is built on ADR-0030.

Why not the others:

- The origin as a prefix: it still leaves the deployed code unknown, which is half of the problem.
- Keep ADR-0030: a shared query cannot tell components apart, which is the problem itself.

**Scope:** The format, common fields and placement of the logs of every component. It does not cover which events each component writes and their own fields, set in each component's design; or how alerts reach the owner ([ADR-0031](0031-heartbeat-alerts-for-the-pipeline.md)).

### The convention

- **Format:** JSON Lines, one event per line.
- **Common fields:** every event carries `ts` (UTC, [ADR-0005](archive/0005-utc-for-all-stored-timestamps.md)), `level`, `component`, `version`, `run_id` and `event`, in that order, before its own fields.
- **One object per run:** each run writes its events as one object, with the UTC day in the key (`date=YYYY-MM-DD/<run_id>.jsonl`).
- **Place and retention, per component:**
  - Capture: under `logs/` in bronze, kept under the bucket lock with the data they describe.
  - Pipeline: in a prefix of its own outside bronze, deleted after 30 days by a lifecycle rule; events also go to stdout. Its final event carries `duration_s` and `peak_memory_mb`, the measures that can reopen [ADR-0027](0027-modal-as-execution-platform.md). Why the logs are stored in R2 rather than on the platform or in a log service is in [ADR-0030](archive/0030-pipeline-logs.md).
- **Access:** SQL with the engine from the owner's machine, with a read-only token.

### Consequences

#### Positive

- **One query across components:** the logs of all components can be read together and filtered by origin.
- **Traceable behaviour:** a change in results can be matched to the deploy that introduced it.
- **One place for the rule:** a new component follows this ADR and adds only its place and retention.

#### Negative

- **Larger events:** two fields more per event, about 70 bytes with a UUID as version, negligible against R2's free tier at the current volumes.
- **One more deploy duty:** a component whose platform gives no version identifier must provide one itself, such as the commit it was built from.
- **Different retention:** capture's logs last forever and the pipeline's 30 days, so a query that spans both can only go back 30 days for the pipeline.

## More information

- Decided at framing in [d004 › D9](../designs/d004-bronze-data-capture.md#d9-capture-logs).
- Capture's `version` is the Worker's version ID, from its version metadata binding ([d004 › Pass logs](../designs/d004-bronze-data-capture.md#pass-logs)); the pipeline's is set in T040.
