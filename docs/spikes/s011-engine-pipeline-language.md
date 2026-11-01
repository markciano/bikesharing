# Spike: Processing engine and pipeline language

- **Task:** T036
- **ADRs:** [ADR-0008](../decisions/0008-common-model-on-gbfs-3-0.md), [ADR-0018](../decisions/0018-medallion-architecture.md), [ADR-0019](../decisions/0019-own-lakehouse-on-cloudflare-r2.md), [ADR-0020](../decisions/0020-bronze-as-captured-objects.md), [ADR-0022](../decisions/0022-delta-lake-for-silver-and-gold.md), [ADR-0023](../decisions/0023-storage-security-baseline.md)
- **Code:** `spikes/engine-pipeline-language/`

## Status

- State: Draft 📝
- Phase: [ ] Questions · [ ] Method · [ ] Steps · [ ] Steps review
- Started: — · Finished: —
- Current step: —

## 1. Questions — what we need to know

### 1.1 Context

T036 decides the single-node processing engine, then the pipeline language, which depends on the engine, and models the component's threats to add requirements to [d002](../designs/d002-requirements.md#requirements). It builds on [s010](s010-storage-table-format.md), which set Delta Lake on Cloudflare R2 and showed that `deltalake` writes and MERGEs there and that Polars and DuckDB read the table. All three decisions are expected to be settled by documents and arithmetic; a run is added only if the winning engine rests on an unknown that they cannot settle.

### 1.2 Decided at framing

#### D`<N>`. `<Title of decision N>`

### 1.3 Questions

Main question: `<one sentence>`

- **Q1.** `<question>`
- **Observe only:** `<item>`

### 1.4 Exit criteria

- **Standard:** `<standard or pattern applied>`
- **Timebox:** `<window, and what ends it>`
- `<criterion>` — `<threshold>` — hard cut | guide

### 1.5 Out of scope

- `<item>`

### 1.6 Open questions

| Question | Notes |
|---|---|
| | |

## 2. Method — how we find out

### 2.1 Approach

| Variant | What it is | What it tells |
|---|---|---|
| | | |

#### 2.1.1 Shared behaviour

-

#### `<A>`. `<Title of variant, option or probe A>`

### 2.3 Decision log

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| `<N>` |  |  |  |  |

### 2.4 File layout

```text
spikes/engine-pipeline-language/
├── README.md        Setup, commands, what each script does; How we got here (written at Conclusion)
└── <file>           <purpose>
```

## 3. Steps

### 3.1 Prerequisites

### Step 1 — `<title>`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** following the Git conventions in CLAUDE.md.
- **R:** R1, R3 (or —)
- **Model:** `<model · effort>` (or —)
- **Gate:** `<condition>` → `<consequence>`

#### Scope

#### Reads

#### Do

#### Check

### Step N — Conclusion

## 4. Findings

### F1. `<one-line statement>`

Step N · YYYY-MM-DD · `<source of evidence>`

- `<evidence>`
- Consequence: `<for variants, steps or questions>`

### 4.1 Production inputs

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | | Step N · FN | |

## 5. Conclusion

Observed window: `<from–to, UTC; what it does not cover>`

### 5.1 Answers

- **Q1. Title** `<answer>` (FN)

### 5.2 Exit criteria

| Criterion | Kind | Result | Findings |
|---|---|---|---|

### 5.3 Verdict

### 5.4 Decisions to record

| D | Outcome | Why |
|---|---|---|

### 5.5 Not verified

- `<item>` — `<risk>` — `<mitigation>`

### 5.6 Follow-ups

- `<ADR or task>`

## 6. Sources

-
