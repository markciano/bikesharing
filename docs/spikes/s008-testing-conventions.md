# Spike: Testing conventions

- **Task:** T020
- **ADRs:** ADR-0009 (test fixtures), ADR-0012 (collectors decoupled by output contract), ADR-0013 (CI)
- **Code:** `spikes/testing-conventions/`

## Status

- State: Draft 📝
- Phase: [x] Questions · [x] Method · [ ] Steps · [ ] Steps review
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
- Tests detect faults (manual mutation testing): in each PoC (Python, Spark, Worker, contract), at least one deliberate change to the code under test makes its test fail, locally and in CI — hard cut
- Reproducible from scratch: each PoC passes with one command documented in its README, locally and in a CI job that starts from a clean environment, with every dependency version pinned in the repo — hard cut
- Feedback time: the pre-merge checks of a PR finish in ≤ 10 min in total (XP ten-minute build); above it, the spike proposes moving slow tests to another CI layer — guide
- Traceability: every convention adopted or corrected (including each rule in `.claude/rules/python.md`, Q1) records its reason and the standard it comes from; every tool with real alternatives is chosen with a weighted decision matrix whose criteria and weights are fixed before scoring — hard cut

### Out of scope

- Language of the local live process and of the historical ingestion: decided in the `collector` design.
- Testing of `apps/` and `infra/`, not yet defined.
- Building checks against live sources (e.g. a scheduled job): Q5 only names their CI layer.
- The real CI jobs and test configuration of each component: created by its design.
- Data quality checks on the data itself, and the content of data contracts (semantics, freshness, quality, ownership): part of the pipeline design.

## 2. Method — how we find out

### Approach

- TODO: parked from Questions: ADR-0009 cites "CLAUDE.md › Testing", which now lives in `.claude/rules/python.md`; fix it when the Claude files are updated (Q6).

There are no competing variants: one probe per question, each telling something the others do not.

| Probe | What it is | What it tells |
|---|---|---|
| P1 Python | Minimal Python module with `unit` and `integration` tests: trimmed fixture (ADR-0009), `conftest.py`, injected time, coverage report | Validates in practice the `.claude/rules/python.md` rules that need it; the rest are justified on paper (Q1) |
| P2 Spark | One PySpark transformation tested on a shared local SparkSession | The right test level for Spark and its real cost in CI: Java and session start-up (Q2) |
| P3 Worker | Minimal Worker tested with `vitest` and `@cloudflare/vitest-pool-workers` | Whether the Worker can be tested in `workerd` without a Cloudflare account, locally and in CI (Q3) |
| P4 Contract | One shared JSON Schema; a producer test in JS on the Worker output and a consumer test in Python | Whether one contract breaks both sides when it changes, whatever the language (Q4) |
| P5 CI layers | P1–P4 running in the pre-commit, PR and `main` layers, with measured durations | Which test level goes in each layer, and whether ADR-0013 changes (Q5) |
| Desk analysis | Review of CLAUDE.md, the rules and the `/implement` skill; no code | Where each convention lives (Q6) |

Tool choices with real alternatives are scored on paper with a weighted decision matrix; the PoC uses the winner and alternatives are not built:

- `pytest` vs `unittest` (P1)
- Spark helpers: `pyspark.testing.assertDataFrameEqual` (PySpark ≥ 3.5) vs `chispa` (P2)
- Contract format: hand-written JSON Schema vs schema generated from models (`pydantic`, `zod`) (P4)

### Shared behaviour

1. **One command per PoC,** documented in the README; dependencies pinned as set in the Decision log.
2. **Mutation check:** change one line of the code under test; run the test locally and keep the failing output; commit and push the change, marked as temporary, and record the red CI run URL; commit the revert and see CI green again. Each mutation is a finding: what was changed, which test failed, the run URL.
3. **No network in tests** (hermetic tests), in Python and JS alike; in the Worker, calls to the source API are mocked with the `vitest-pool-workers` fetch mock. Hypothesis for Q1: checks against live sources belong outside the PR gate (e.g. a scheduled job); Q5 names their layer only.
4. **Measurements:** local duration with `time <command>`; CI duration per job as reported by GitHub; both recorded in Findings.
5. **Fixtures** are hand-written synthetic JSON with the GBFS shape defined by the P4 schema; no source data is committed (ADR-0009).

### Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-10-19 | Exit criterion "fault injection" renamed to "tests detect faults (manual mutation testing)"; content unchanged | "Fault injection" names resilience testing of running distributed systems, which is not what the criterion checks |
| 2026-10-19 | One probe per question (P1–P5 plus desk analysis), no competing variants | Each probe answers a different question; the conventions cover every component, not a choice among them |
| 2026-10-19 | Tool alternatives are scored on paper; only the winner is built | Keeps the timebox; the PoC verifies the chosen tool, the matrix records why |
| 2026-10-19 | PoCs run in CI through temporary changes to `ci.yml` on the T020 branch: one job per PoC scoped to `spikes/testing-conventions/`, plus a `push` trigger for this branch; the PR is opened as draft; the changes are reverted at Conclusion, before merge | Measures the real CI layers (criterion 2, Q5) while nothing temporary reaches `main` (ephemeral CI config on a feature branch); `act` does not reproduce the GitHub runner faithfully |
| 2026-10-19 | The local layer (Q5) is the test command `/implement` runs before proposing each commit; its duration is measured. A Git `pre-commit` hook is assessed on paper only, and Claude Code hooks (`.claude/settings.json`) are assessed on paper in Q6 as the automatic form of that instruction | YAGNI: `/implement` already runs the tests before every commit the owner makes, so a Git hook would repeat them and add config, per-machine install and tear-down |
| 2026-10-19 | Dependencies follow the earlier spikes: Python `venv` + `requirements.txt` pinned with `==`; JS `npm` + `package-lock.json`; Python, Node and Java versions pinned in each CI job (`actions/setup-python`, `setup-node`, `setup-java`) | Criterion 2 with tools the owner already used; the dependency tooling of production code is not a testing convention |
| 2026-10-19 | Gate in P2: Python 3.14 + PySpark 4.2.0 + Java 17 run the Spark test locally and in CI; if not, P2 drops to an earlier Python version | Python 3.14 is supported since Spark 4.1.0 (SPARK-51169, 4.1.0 release notes); 4.2.0 is the latest stable (2026-07-14) and runs on Java 17/21/25, 17 being the lowest LTS. Not confirmed by docs: behaviour on the GitHub Actions runner and `pyspark.testing.assertDataFrameEqual` in an installed 4.2.0 |
| 2026-10-19 | Temporary commits (CI jobs, deliberate mutations and their reverts) stay on the T020 branch and reach `main` history through rebase merge; each one says in its message that it is temporary | The owner accepts them in history at this stage of the project; one branch and one PR is simpler than a throwaway branch. The final content of `main` stays clean |
| 2026-10-19 | Spike fixtures are hand-written synthetic JSON, not trimmed source samples | No ADR-0009 exception or new ADR is needed; the shape is enough to validate a convention (YAGNI); the trimming script belongs to the production design |

### File layout

P1 and P2 are separate folders with their own `requirements.txt`, so the Python job installs neither PySpark nor Java and the cost of Spark in CI is measured on its own (criterion 3). The contract folder is shared by both languages.

```text
spikes/testing-conventions/
├── README.md              Question, setup, one command per PoC; How we got here (at Conclusion)
├── .gitignore             venvs, node_modules/, .wrangler/, outputs/
├── contract/              P4 · shared by JS and Python
│   ├── station.schema.json   JSON Schema of the contract
│   └── fixtures/             synthetic GBFS JSON: valid and invalid cases
├── python/                P1 (+ P4 consumer test)
│   ├── requirements.txt      pinned (pytest, pytest-cov, jsonschema)
│   ├── pyproject.toml        pytest config only
│   ├── poc/                  minimal module under test
│   └── tests/                conftest.py, unit/, integration/
├── spark/                 P2
│   ├── requirements.txt      pinned (pyspark 4.2.0, pytest)
│   ├── pyproject.toml        pytest config only
│   ├── poc/                  one transformation
│   └── tests/                conftest.py with a shared local SparkSession
├── worker/                P3 (+ P4 producer test)
│   ├── package.json · package-lock.json
│   ├── wrangler.jsonc · vitest.config.js
│   ├── src/index.js          minimal Worker
│   └── test/                 vitest tests in workerd, fetch mocked
└── outputs/               ignored by Git: local timings and failing outputs
```

Outside this folder, only `.github/workflows/ci.yml` changes, temporarily (Decision log). Tool matrices are recorded in 4. Findings, not in files.

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
