---
status: Proposed
date: 2026-11-16
---

# Data quality checks in four classes, with severity by who causes a failure

## Context and problem statement

The pipeline publishes data to a public page every few minutes, 24/7, with no one watching each run. Its input comes from two providers' feeds, which the project reads but cannot fix; its logic is the project's own code, which it can fix and deploy again.

The checks the model needs differ in nature: some state how a value is built, some what must always hold on real data, some a measure to follow over time, and some the structure of the model itself. Each needs a different moment and means of verification, from a test on fixtures to inspection.

Without a policy, each check is verified as its author sees fit, and a failure on real data either stops the page for a fault the project cannot fix, or lets the visitor see wrong data with no sign of it.

## Considered Options

### 1. Severity by who causes a failure

The pipeline's logic fails with severity error, following Write-Audit-Publish: each batch is written to staging, audited, and published only if its checks pass. A provider's data fails with severity warn: logged, and published. A row that fails its column's schema is quarantined, and the rest of its batch publishes.

- Pros:
  - Wrong output of the pipeline never reaches the page.
  - A provider's fault removes at most its own rows, never the page.
- Cons:
  - Each rule must state which side it checks.
  - A warn reaches the owner only through observability, with no stop to prompt action.

### 2. Every failure blocks the publish

Every check fails with severity error, whoever causes it.

- Pros:
  - No data that fails a check is ever published.
- Cons:
  - A provider's change stops the page until the project adapts, though the project cannot fix the source.

### 3. Every failure only warns

Every check is logged and the run publishes.

- Pros:
  - The page is never held back.
- Cons:
  - A fault in the pipeline's logic reaches the visitor as wrong data, with no sign of it.

## Decision Outcome

**Chosen option:** 1. Severity by who causes a failure

Every data quality check belongs to one of four classes, after the terms of DAMA-DMBOK and ISO/IEC 25024; the class sets how it is verified:

| Class | What it is | Verified by |
|---|---|---|
| Transformation spec | How a table or value is built | Unit or integration test in CI, on fixtures |
| Runtime rule | What must always hold on real data | Data test in every run, with its severity |
| Quality indicator | A measure tracked over time, against a target | A gold table, or observability for what lies outside the model |
| Documentation | The model's structure and the sources it reads | Inspection |

A column's type, nullability and accepted values are its schema, checked in every run; a runtime rule states only what no schema states. A quality indicator is kept only if it prompts an action or measures a provider's quality; its target starts from what was measured on real captures and is reviewed against production values, following the SRE practice of setting an objective from a measured baseline.

Rationale: the project can fix its own code but not its providers' data, so a failure blocks the publish only where a fix is in the project's hands. Write-Audit-Publish keeps a faulty batch off the page while the last good file stays published, so the visitor sees at most an older data age; the quarantine keeps a provider's new value out of the page without holding back the rest of its batch. The classes give each check the cheapest verification that proves it.

Why not the others:

- Option 2 stops the page for faults the project cannot fix.
- Option 3 publishes the pipeline's own faults with no sign of them.

**Scope:** every check on the pipeline's silver and gold tables and on the files it publishes, in every slice. It does not cover capture, which keeps bronze untouched ([ADR-0006](0006-raw-layer-keeps-source-responses-untouched.md)), nor how a failed batch is set aside and returns, which belongs to the pipeline's run mode.

### Consequences

#### Positive

- **Safe page:** the pipeline's faults never reach the visitor; a provider's fault removes only its rows.
- **One verification per check:** each check is proved once, where it is cheapest.
- **Provider scorecard:** the indicators that measure each provider answer how good its data is.

#### Negative

- **Classification work:** every new check needs a class and, if a runtime rule, a severity.
- **Late warnings:** a warn or a quarantined row reaches the owner only through observability.
- **Older data on failure:** while a batch is held back, the page serves older data.

## More information

- Quality catalog: [data-quality.md](../data-quality.md); transformation specs and documentation items: [data-model.md › Data contract](../data-model.md#data-contract).
- [d007 › D4](../designs/d007-pipeline-design.md#d4-data-quality-in-four-classes), [#1](../designs/d007-pipeline-design.md#22-decision-summary); a batch set aside and its return: [d007 › D7](../designs/d007-pipeline-design.md#d7-catch-up-in-bounded-batches).
