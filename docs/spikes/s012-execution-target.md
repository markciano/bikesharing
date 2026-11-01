# Spike: Execution target

- **Task:** T037
- **ADRs:** [ADR-0010](../decisions/0010-ingestion-logic-separated-from-platform.md) (to be replaced), [ADR-0016](../decisions/0016-runtime-versions-pinned-per-component.md), [ADR-0023](../decisions/0023-storage-security-baseline.md), [ADR-0024](../decisions/0024-duckdb-as-processing-engine.md), [ADR-0025](../decisions/0025-sql-models-directed-by-python.md), [ADR-0026](../decisions/0026-budget-shares-per-component.md)
- **Code:** `spikes/execution-target/`

## Status

- State: Draft 📝
- Phase: [ ] Questions · [ ] Method · [ ] Steps · [ ] Steps review
- Started: — · Finished: —
- Current step: —

## 1. Questions — what we need to know

### 1.1 Context

Storage (T035), engine and pipeline language (T036) are decided; this spike decides where the pipeline runs (D1, the central decision), what schedules it (D2), its threats and new requirements (D3), how processing logic is separated from the platform (D4) and how the pipeline logs (D5). The refresh cadence is not chosen here: [s010 › P5](s010-storage-table-format.md#production-inputs) leaves it to T040, and R2's Class B operations limit it, not the machine. D2–D5 depend on D1.

### 1.2 Decided at framing

#### D1. Execution platform

`TODO(T037)`: decision, once scored.

Needs and hard cuts:

| # | Need | Source | Hard cut |
|---|---|---|---|
| N1 | Run Python and DuckDB with pinned code installed ahead of the run | [d002 › R20](../designs/d002-requirements.md#requirements), [ADR-0016](../decisions/0016-runtime-versions-pinned-per-component.md) | Not possible: out |
| N2 | Memory for a MERGE bounded to one day: about 0.8 GB on average, 3 GB at worst ([s011 › D1](s011-engine-pipeline-language.md#d1-processing-engine)) | [ADR-0024](../decisions/0024-duckdb-as-processing-engine.md) | Under 3 GB, plus disk to spill: out |
| N3 | Run every 5 minutes or less, and on demand, so the platform does not limit T040's cadence | [d002 › R3](../designs/d002-requirements.md#requirements), [s010 › P5](s010-storage-table-format.md#production-inputs) | Not possible: out |
| N4 | Cost within the pipeline's share | [d002 › R4](../designs/d002-requirements.md#requirements), [ADR-0026](../decisions/0026-budget-shares-per-component.md) | Above €4 per month: out |
| N5 | A known run limit, so T040 can size its catch-up batches to it | [d002 › R11](../designs/d002-requirements.md#requirements) | None: reported for each candidate, as an input for T040 |
| N6 | Component credentials outside logs and files | [d002 › R15, R22](../designs/d002-requirements.md#requirements) | No way to inject secrets: out |
| N7 | Failures with limited retries, a time limit and an alert | [d002 › R23](../designs/d002-requirements.md#requirements) | Scored |
| N8 | Pipeline logs: where they live, retention and access | [D5](#d5-pipeline-logs) | Scored |

Criteria:

| Criterion | Weight | What it measures |
|---|---|---|
| Operational load | 5 | Patches, outages and maintenance for one person |
| Schedule reliability | 4 | Whether runs start on time, with none skipped |
| Cost margin | 4 | How much of the €4 stays free |
| Portfolio value | 3 | How standard and demonstrable it is in a data engineering project |
| Observability and alerts | 3 | Covers N7 and N8 |
| Portability | 2 | How much changing platform costs |

#### D2. Scheduler

`TODO(T037)`: depends on D1.

#### D3. Pipeline security

`TODO(T037)`: depends on D1.

#### D4. Processing logic separated from the platform

`TODO(T037)`: replaces ADR-0010.

#### D5. Pipeline logs

`TODO(T037)`: depends on D1.

### 1.3 Questions

### 1.4 Exit criteria

### 1.5 Out of scope

- The pipeline's mode and refresh cadence, and how the ≤ 5-minute freshness of R3 is reconciled with them ([s010 › P5](s010-storage-table-format.md#production-inputs)) — T040
- Which events the pipeline logs — T040
- The size of catch-up batches, and where the one-off history load runs — T040
- The pipeline's end-to-end and post-deploy smoke tests, on paper in [testing-strategy](../testing-strategy.md) — T040
- Aligning capture's logs with the convention this spike sets for the pipeline: format and field names only; log objects from before the production start are deleted before the bucket lock is enabled ([ADR-0023](../decisions/0023-storage-security-baseline.md)), so only the new format remains — T039

### 1.6 Open questions

| Question | Notes |
|---|---|
| | |

## 2. Method — how we find out

### 2.1 Approach

| Variant | What it is | What it tells |
|---|---|---|
| | | |

### 2.3 Decision log

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|

### 2.4 File layout

```text
spikes/execution-target/
└── README.md        Question, setup and commands, what each script does, link to the report; How we got here (written at Conclusion)
```

## 3. Steps

### 3.1 Prerequisites

## 4. Findings

### 4.1 Production inputs

| P | Input | Origin | Destination |
|---|---|---|---|

## 5. Conclusion

### 5.1 Answers

### 5.2 Exit criteria

| Criterion | Kind | Result | Findings |
|---|---|---|---|

### 5.3 Verdict

### 5.4 Decisions to record

| D | Outcome | Why |
|---|---|---|

### 5.5 Not verified

### 5.6 Follow-ups

## 6. Sources
