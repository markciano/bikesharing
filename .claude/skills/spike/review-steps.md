# Review: spike Steps

A fresh session. Read the whole spike doc; read a file cited in Reads only when a finding needs it.

The question: can each step be executed, by Claude through `/implement` or by the owner by hand, with nothing left to decide, and will the run answer the Questions against the Exit criteria?

## Severity

- **Blocking:** the run cannot answer a Q or measure an exit criterion, or a step cannot be executed without deciding something.
- **Important:** the steps can run, but a likely failure would waste the run or its evidence: a missing gate, an analysis with no verification, a billable resource with no limit or tear-down.
- **Minor:** wording, order or consistency, with no effect on the run.

## Checklist

### Coverage

- Every Q and every exit criterion is answered or measured by at least one step; every "Observe only" item says where it is noted.
- Every item in File layout is produced by a step, and no step produces a file outside it.
- The last step is the Conclusion.

### Order and gates

- An assumption that would invalidate later steps is tested first, with a Gate that states what is dropped or re-decided.
- The code of each Claude step is run by a later Owner step before anything is built on it.

### Executability

- Claude steps: Scope names the files and what must not be touched; Reads cites only what is needed; names, formats and thresholds come from Method or Shared behaviour, not from the step.
- Owner steps: exact commands or actions, where they run, and what to report back.
- Every Check has a yes/no result.
- Only steps that change committed files have a Commit, following the Git conventions in CLAUDE.md.

### Evidence

- Each analysis is verified independently (known arithmetic, independent counts, fault injection) before its figures become Findings.
- The window and measures used by the steps match the Exit criteria.

### Safety and cost

- Secrets in `.env`; captured data ignored by Git (ADR-0009); stored timestamps in UTC (ADR-0005).
- Every billable resource has an alert or a cap, and a tear-down step or a recorded decision to keep it.
