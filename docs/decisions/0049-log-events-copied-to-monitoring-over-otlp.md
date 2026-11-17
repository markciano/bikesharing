---
status: Proposed
date: 2026-11-18
---

# Log events copied to the monitoring tool by each emitter over OTLP

## Context and problem statement

Every component keeps its logs in object storage ([ADR-0036](0036-log-convention-across-components.md)), and a monitoring tool now shows them as dashboards and alerts ([ADR-0048](0048-grafana-cloud-as-monitoring-tool.md)). The events have to reach that tool without weakening what object storage already guarantees.

- Capture's logs are permanent evidence under a bucket lock ([ADR-0023](0023-storage-security-baseline.md)).
- Quality questions span components and are answered with one SQL query over the logs of all of them (ADR-0036).
- A failed pipeline run must be traceable days later, with the run measures that can reopen the execution platform ([ADR-0027](0027-modal-as-execution-platform.md)).
- The monitoring tool's free retention is shorter than the pipeline's 30 days, and a free tier can change without notice.
- Capture and the pipeline run on different platforms and fail independently; capture's runtime cannot run a collector or agent.
- One person operates the solution.

## Considered Options

Each option is compared on what it keeps of object storage's guarantees, how independent the components stay, and how much a change of tool costs.

### 1. Each emitter sends a copy over OTLP

Object storage stays the record. Each component sends its run's events to the tool itself, over HTTP with OTLP, the OpenTelemetry protocol, in its JSON encoding, when it writes them to object storage.

- Pros:
  - every guarantee of object storage is kept, and the tool needs only a short retention;
  - each component's events arrive on their own, so a stopped pipeline does not hide capture;
  - a standard protocol, so a change of tool changes an endpoint and a key, not the senders;
  - JSON lets a runtime with no protobuf library send with a plain HTTP request.
- Cons:
  - one more secret in each emitter;
  - one more request per run, which can fail;
  - the tool's documentation recommends JSON over OTLP for low traffic only.

### 2. Each emitter sends a copy with the tool's own push API

As option 1, with the tool's native ingest API instead of OTLP.

- Pros:
  - the most direct API, documented for JSON with no caveat.
- Cons:
  - specific to one tool: a change of tool rewrites the sending code of every component.

### 3. The pipeline forwards every component's logs

Each run of the pipeline reads the new log objects of every component from object storage and sends them to the tool.

- Pros:
  - capture is unchanged and holds no new secret.
- Cons:
  - capture's events arrive up to one pipeline cadence late;
  - a stopped pipeline also hides capture, coupling two components that fail independently.

### 4. The tool reads object storage in place

Nothing is copied; the tool queries the log objects where they are.

- Pros:
  - one copy of every event.
- Cons:
  - a log tool indexes, alerts and drills down on what it ingests; no free managed tool documents querying object storage in place, so a query engine would have to run somewhere.

## Decision Outcome

**Chosen option:** 1. Each emitter sends a copy over OTLP.

It keeps every guarantee object storage gives today, the bucket lock, the SQL query across components and the run history, so the tool's short retention and free tier carry no risk for the record. Each component reports on its own, as they fail on their own, and the standard protocol keeps the tool replaceable. A failed send does not change a run's outcome, since object storage holds the record.

Why not the others:

- The tool's own push API: it ties the code of every component to one tool, with no gain at the project's volume.
- The pipeline forwards: it makes capture's alerts depend on the pipeline running.
- The tool reads in place: it needs a query engine to run and maintain.

**Scope:** How log events reach the monitoring tool, for every component that follows ADR-0036. It does not change where logs are stored or for how long (ADR-0036); it does not cover how the common fields map to OTLP attributes and the tool's labels, set in T060.2; or the quality indicators the tool measures from outside the components.

### Consequences

#### Positive

- **The record does not depend on the tool:** losing the tool, its account or its free tier loses no event.
- **Independent reports:** capture's events and alerts do not wait for the pipeline.
- **A replaceable tool:** another tool that takes OTLP needs a new endpoint and key, not new code.

#### Negative

- **One more secret per emitter:** a leaked write token lets someone send false events to the tool; the controls are in [s018 › D8](../spikes/s018-monitoring-tool.md#d8-monitoring-tool-security-threats).
- **Two writes per run:** each run writes its events twice, and the tool's copy can miss a run whose send failed; object storage still has it.
- **JSON on a low-traffic path:** if the tool rejects or throttles JSON, the pipeline moves to protobuf with the OpenTelemetry SDK, and capture to the tool's own push API, which takes JSON.

## More information

- Extends [ADR-0036](0036-log-convention-across-components.md): its convention, place and retention are unchanged.
- Decided at framing in [s018 › D1](../spikes/s018-monitoring-tool.md#d1-r2-as-the-record-the-tool-with-a-copy), [D3](../spikes/s018-monitoring-tool.md#d3-each-emitter-sends-its-own-copy) and [D4](../spikes/s018-monitoring-tool.md#d4-otlp-over-http-with-json-encoding).
- Grafana Cloud documents JSON over OTLP for low-traffic testing: <https://grafana.com/docs/grafana-cloud/observe-and-act/send-data/otlp/otlp-format-considerations/>.
