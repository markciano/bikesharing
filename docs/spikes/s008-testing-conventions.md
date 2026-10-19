# Spike: Testing conventions

- **Task:** T020
- **ADRs:** ADR-0009 (test fixtures), ADR-0013 (CI)
- **Code:** `spikes/testing-conventions/`

## Status

- State: Draft 📝
- Phase: [x] Questions · [ ] Method · [ ] Steps · [ ] Steps review
- Started: — · Finished: —
- Current step: —

## 1. Questions — what we need to know

### Context

Earlier spikes settled how the data is captured, so the first production code (`collector/` in JS, `src/bikesharing/` in Python/Spark) can now be written. This spike fixes the testing conventions before that code exists, so each component design applies them without deciding anything about testing. It builds on ADR-0009 (fixtures), ADR-0013 (branching and CI) and the Testing section of `.claude/rules/python.md`, whose rules have no recorded reasons and are treated here as hypotheses. The owner has little testing experience: each convention must come with its reason and, where it adds understanding, a minimal throwaway proof of concept running locally and in CI.

### Questions

Main question: which testing conventions (levels, tools, CI layers) does each component adopt, for what reasons, and where are they recorded in the Claude files?

- **Q1.** Does each testing rule in `.claude/rules/python.md` hold, and why?
- **Q2.** How are Spark transformations tested (test level, session setup), and what do they cost in CI?
- **Q3.** Which tool and test levels test the Cloudflare Worker without a Cloudflare account, locally and in CI?
- **Q4.** How is a contract between two components defined and tested, independently of the language of each side? Case tested: the `collector` contract (Worker, local live process, historical ingestion).
- **Q5.** Which test level runs in each CI layer (local pre-commit, `push` to a feature branch, pre-merge on the `pull_request`, post-merge on `main`), and does ADR-0013 need to change (including CI on feature-branch pushes before a PR is opened, and "require branches to be up to date before merging")?
- **Q6.** Which Claude files (CLAUDE.md, rules, skills) and which ADRs record the conventions?
- **Observe only:** duration of each CI job and of the local test cycle.

### Exit criteria

- **Standard:** test pyramid (levels), weighted decision matrix (tools), proof of concept in CI (evidence)
- **Timebox:** 2 working days; the run ends when every exit criterion has a result or the time is spent, and whatever is not covered goes to Not verified with its risk
- Fault injection: in each PoC (Python, Spark, Worker, contract), at least one deliberately injected fault makes its test fail, locally and in CI — hard cut
- Reproducible from scratch: each PoC passes with one command documented in its README, locally and in a CI job that starts from a clean environment, with every dependency version pinned in the repo — hard cut
- Feedback time: the pre-merge checks of a PR finish in ≤ 10 min in total (XP ten-minute build); above it, the spike proposes moving slow tests to another CI layer — guide
- Traceability: every convention adopted or corrected (including each rule in `.claude/rules/python.md`, Q1) records its reason and the standard it comes from; every tool with real alternatives is chosen with a weighted decision matrix whose criteria and weights are fixed before scoring — hard cut

### Out of scope

- Language of the local live process and of the historical ingestion: decided in the `collector` design.
- Testing of `apps/` and `infra/`, not yet defined.
- The real CI jobs and test configuration of each component: created by its design.
- Data quality checks on the data itself, and the content of data contracts (semantics, freshness, quality, ownership): part of the pipeline design.

## 2. Method — how we find out

### Approach

- TODO: parked from Questions: how the PoC runs in CI (recommended: temporary jobs in the T020 PR, removed before merge, so nothing reaches `main`).
- TODO: parked from Questions: ADR-0009 cites "CLAUDE.md › Testing", which now lives in `.claude/rules/python.md`; fix it when the Claude files are updated (Q6).

| Variant | What it is | What it tells |
|---|---|---|
| | | |

### Shared behaviour

-

### Decision log

| Date | Decision | Reason |
|---|---|---|
| | | |

### File layout

```text
spikes/testing-conventions/
├── README.md        Setup, commands, what each script does; How we got here (written at Conclusion)
└── <file>           <purpose>
```

## 3. Steps

### Step N — Conclusion

- **Status:** 💤 todo
- **Who:** Owner + Claude
- **Scope:** 5. Conclusion and the destination of every Production input in this doc; How we got here in the README; tear-down of what does not outlive the spike.
- **Reads:** 1. Questions, 2. Method › Decision log, 4. Findings
- **Check:** every Q answered; every exit criterion has a result; every P has a destination
- **Commit:** `docs(T020): conclude spike s008`

## 4. Findings

### Production inputs

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | | Step N · FN | |

## 5. Conclusion

Observed window: —

### Answers

### Exit criteria

### Verdict

### Not verified

### Follow-ups

## Sources

-
