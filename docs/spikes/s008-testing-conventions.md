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
6. **Commit messages** start the description with the step: `type(T020): sN description`.

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
| 2026-10-19 | Java 17 is provisional, for this spike only; the production Java version is decided in T021, against the runtime of the deployment target (T022) | The testing conventions do not depend on the Java version; Spark 4.2 supports 17/21/25 and 17 is the most tested by the Spark ecosystem; choosing now would decide without the deployment runtime |
| 2026-10-19 | Tool matrices run first (step 1), before any PoC | The PoCs use the chosen tools; scoring after building would bias the matrix |
| 2026-10-19 | Placing conventions in the Claude files is split into placement map, owner approval and writing (steps 13–15) | In T018 conventions were written into CLAUDE.md first and redistributed later; deciding the place before writing follows progressive disclosure and spec-driven development |

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
├── mutations/             one .patch per PoC, applied and reverted by the owner
└── outputs/               ignored by Git: local timings and failing outputs
```

Outside this folder, only `.github/workflows/ci.yml` changes, temporarily (Decision log). Tool matrices are recorded in 4. Findings, not in files.

## 3. Steps

| # | Title |
|---|---|
| 1 | Tool matrices |
| 2 | Spark PoC and temporary CI job |
| 3 | Run Spark locally and in CI; open draft PR |
| 4 | Worker PoC and temporary CI job |
| 5 | Run the Worker locally and in CI |
| 6 | P1 Python PoC and temporary CI job |
| 7 | P4 contract PoC |
| 8 | Run P1 and P4 locally and in CI |
| 9 | Mutation patches |
| 10 | Apply and revert mutations |
| 11 | Analysis Q1–Q5 |
| 12 | Verify the analysis |
| 13 | Placement map (Q6) |
| 14 | Approve the placement map |
| 15 | Write the conventions into the Claude files |
| 16 | Conclusion |

All paths below are relative to `spikes/testing-conventions/` unless they start with `.github/`, `.claude/` or `docs/`.

### Step 1 — Tool matrices

- **Status:** 💤 todo
- **Who:** Claude
- **Scope:** three weighted decision matrices in 4. Findings: `pytest` vs `unittest`; `pyspark.testing.assertDataFrameEqual` vs `chispa`; hand-written JSON Schema vs schema generated from models (`pydantic`, `zod`). Criteria and weights are written first and approved by the owner on the diff; only then are options scored, each score with a one-line reason and a source. Touches only this doc.
- **Reads:** 1. Questions, 2. Method › Approach, official docs of each tool
- **Check:** the weights were approved before any score was written; each matrix names a winner
- **Commit:** `docs(T020): s1 add tool matrices to spike s008`

### Step 2 — Spark PoC and temporary CI job

- **Status:** 💤 todo
- **Who:** Claude
- **Scope:**
  - `spark/requirements.txt` (`pyspark==4.2.0`, `pytest`, the step 1 Spark helper if it is a package; all `==`), `spark/pyproject.toml` (pytest config only).
  - `spark/poc/` with one transformation: a DataFrame of station status in, the same rows plus an occupancy ratio (`num_bikes_available / capacity`) out.
  - `spark/tests/conftest.py` with a session-scoped local SparkSession (`local[1]`, UI disabled), and `spark/tests/test_<module>.py` with one test using the step 1 helper. The session scope deviates from the function-scope rule in `.claude/rules/python.md` on purpose; the step records why as evidence for Q1 and Q2.
  - `README.md` (question, link to this doc, Spark command) and `.gitignore` (Shared behaviour, File layout).
  - `.github/workflows/ci.yml`: add `t020-testing-conventions` to the `push` branches and a job `poc-spark` (`actions/setup-python` 3.14, `actions/setup-java` Temurin 17, `pip install -r requirements.txt`, `pytest`, working directory `spikes/testing-conventions/spark`).
  - Must not touch: the `docs` job, anything outside `spikes/testing-conventions/` and `ci.yml`.
- **Reads:** 2. Method › Shared behaviour, File layout, Decision log; step 1 matrix; `.github/workflows/ci.yml`
- **Check:** `pytest --collect-only` lists one test (run by the owner in step 3)
- **Commit:** `chore(T020): s2 add Spark PoC and temporary CI job`

### Step 3 — Run Spark locally and in CI; open draft PR

- **Status:** 💤 todo
- **Who:** Owner
- **Scope:**

  ```bash
  cd spikes/testing-conventions/spark
  export JAVA_HOME=$(/usr/libexec/java_home -v 17) && java -version
  python3.14 -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  time pytest
  cd ../../.. && git push -u origin t020-testing-conventions
  gh pr create --draft --base main --title "T020: Testing conventions and place in claude files" --body "Spike s008. Temporary CI jobs; reverted before merge."
  ```

  `java -version` must show 17; if not, install Temurin 17 (`brew install --cask temurin@17`) and repeat.

  Report: `java -version` output; local test result and `time`; PR URL; result, duration and run URL of `poc-spark` on the `push` and on the `pull_request` run.
- **Gate:** the test passes locally and in CI with Python 3.14 + PySpark 4.2.0 + Java 17 → if not, Claude drops `poc-spark` to the latest Python version PySpark 4.2.0 supports, records it in the Decision log, and this step is repeated.
- **Check:** `poc-spark` green on the PR

### Step 4 — Worker PoC and temporary CI job

- **Status:** 💤 todo
- **Who:** Claude
- **Scope:**
  - `worker/package.json` with exact versions (no `^`) of `wrangler`, `vitest` and `@cloudflare/vitest-pool-workers`, and `engines.node`; `worker/wrangler.jsonc`; `worker/vitest.config.js` using the Workers pool.
  - `worker/src/index.js`: a minimal scheduled Worker that fetches one GBFS feed and returns its stations in the contract shape.
  - `worker/test/`: one test that runs the Worker in `workerd` with the source fetch mocked (Shared behaviour 3).
  - `README.md`: Worker command. `.github/workflows/ci.yml`: job `poc-worker` (`actions/setup-node` with the `engines` version, `npm ci`, `npx vitest run`, working directory `spikes/testing-conventions/worker`).
  - Must not touch: other jobs, anything outside `spikes/testing-conventions/` and `ci.yml`.
- **Reads:** 2. Method › Shared behaviour, File layout; ADR-0011; `.github/workflows/ci.yml`
- **Check:** `package.json` has no ranges; the test makes no real network call
- **Commit:** `chore(T020): s4 add Worker PoC and temporary CI job` (after step 5 creates `package-lock.json`)

### Step 5 — Run the Worker locally and in CI

- **Status:** 💤 todo
- **Who:** Owner
- **Scope:**

  ```bash
  cd spikes/testing-conventions/worker
  node --version
  npm install
  time npx vitest run
  ```

  Then commit step 4 including `package-lock.json`, and `git push`. No Cloudflare login is needed. Report: Node version; local result and `time`; result, duration and run URL of `poc-worker`.
- **Gate:** the test passes in `workerd` locally and in CI without a Cloudflare account → if not, Q3 is re-decided with the owner before step 7, which depends on the Worker.
- **Check:** `poc-worker` green on the PR

### Step 6 — P1 Python PoC and temporary CI job

- **Status:** 💤 todo
- **Who:** Claude
- **Scope:**
  - `python/requirements.txt` (`pytest`, `pytest-cov`, `jsonschema`; all `==`), `python/pyproject.toml` (pytest config only, coverage reported without threshold).
  - `python/poc/`: a minimal module that parses one station-status JSON into records and flags stale stations against a `now` received as a parameter (UTC).
  - `python/tests/conftest.py` (function-scoped fixtures), `tests/unit/` (parsing and staleness, written test-first), `tests/integration/` (file fixture → records), following every rule in `.claude/rules/python.md` › Testing so that Q1 can test them.
  - `README.md`: Python command. `.github/workflows/ci.yml`: job `poc-python` (`setup-python` 3.14, `pip install -r requirements.txt`, `pytest --cov`).
  - Must not touch: other jobs, anything outside `spikes/testing-conventions/` and `ci.yml`.
- **Reads:** `.claude/rules/python.md`; 2. Method › Shared behaviour, File layout
- **Check:** each python.md testing rule is either applied in the PoC or listed in the README as "paper only"
- **Commit:** `chore(T020): s6 add Python PoC and temporary CI job`

### Step 7 — P4 contract PoC

- **Status:** 💤 todo
- **Who:** Claude
- **Scope:**
  - `contract/station.schema.json` in the step 1 format, consistent with ADR-0012; `contract/fixtures/` with valid and invalid synthetic cases (Shared behaviour 5).
  - Producer test in `worker/test/`: the Worker output validates against the schema. Consumer test in `python/tests/integration/`: the fixtures the Python side reads validate against the same schema, and the invalid ones are rejected.
  - Add any validator package to `worker/package.json` and `python/requirements.txt` with exact versions.
  - Must not touch: `spark/`, `ci.yml` (the existing jobs already run both tests).
- **Reads:** ADR-0012; step 1 matrix; 2. Method › Shared behaviour
- **Check:** both tests load the same schema file by relative path
- **Commit:** `chore(T020): s7 add contract PoC`

### Step 8 — Run P1 and P4 locally and in CI

- **Status:** 💤 todo
- **Who:** Owner
- **Scope:**

  ```bash
  cd spikes/testing-conventions/python
  python3.14 -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  time pytest --cov
  deactivate && cd ../worker && npm install && time npx vitest run
  ```

  Then commit steps 6 and 7 as proposed, and `git push`. Report: local results, coverage summary and times; result, duration and run URL of `poc-python` and `poc-worker`.
- **Check:** `poc-python`, `poc-worker` and `poc-spark` green on the PR

### Step 9 — Mutation patches

- **Status:** 💤 todo
- **Who:** Claude
- **Scope:** `mutations/p1-python.patch`, `p2-spark.patch`, `p3-worker.patch`, `p4-contract.patch`: each changes one line of the code under test (P4: one field of the schema or of the Worker output) and says in a header comment which test must fail. Adds `mutations/` usage to the README. Touches nothing else.
- **Reads:** the PoC code from steps 2–7
- **Check:** `git apply --check mutations/<patch>` succeeds for each (run by the owner in step 10)
- **Commit:** `chore(T020): s9 add mutation patches`

### Step 10 — Apply and revert mutations

- **Status:** 💤 todo
- **Who:** Owner
- **Scope:** for each patch, from the repo root (Shared behaviour 2):

  ```bash
  git apply spikes/testing-conventions/mutations/<patch>
  <PoC command from the README> 2>&1 | tee spikes/testing-conventions/outputs/<patch>.txt
  git commit -am "test(T020): s10 deliberate mutation <patch>, reverted next" && git push
  # wait for the red CI run, note its URL
  git revert --no-commit HEAD && git commit -m "test(T020): s10 revert mutation <patch>" && git push
  ```

  Report per patch: the test that failed locally, the red run URL, the green run URL after the revert.
- **Gate:** a mutation does not make its test fail → that convention is not adopted as is; Claude records it as a finding and step 11 re-decides it.
- **Check:** four red runs and four green runs recorded

### Step 11 — Analysis Q1–Q5

- **Status:** 💤 todo
- **Who:** Claude
- **Scope:** findings in 4. Findings:
  - Q1: each rule of `.claude/rules/python.md` › Testing with verdict (holds, corrected, dropped), reason, standard, and its evidence (PoC or paper).
  - Q2–Q4: answers from steps 2–10.
  - Q5: test level per CI layer (local via `/implement`, push to a feature branch, PR pre-merge, post-merge on `main`), the layer for checks against live sources, and the proposed change to ADR-0013 (including "require branches to be up to date"), with the measured durations against criterion 3.
  - Exit criteria results so far, and Production inputs.
  - Touches only this doc.
- **Reads:** 1. Questions, 2. Method, reports from steps 3, 5, 8 and 10, `.claude/rules/python.md`, ADR-0013
- **Check:** every Q1–Q5 has at least one finding; every finding cites its evidence
- **Commit:** `docs(T020): s11 add analysis to spike s008`

### Step 12 — Verify the analysis

- **Status:** 💤 todo
- **Who:** Owner
- **Scope:** read the step 11 findings; for each, check it against the reported runs and outputs, and say whether its reason is understood. Report the findings to correct or explain.
- **Check:** owner's OK on every finding

### Step 13 — Placement map (Q6)

- **Status:** 💤 todo
- **Who:** Claude
- **Scope:** a placement map in 4. Findings: a table with one row per convention from step 11 (convention · destination · reason). Destinations: `CLAUDE.md` (always loaded: short invariants), `.claude/rules/*.md` with `paths:` (loaded when matching files are touched), a skill such as `/implement` (procedures, loaded when invoked), hooks or `settings.json` (enforced by the harness), an ADR (cross-cutting why). The criterion is progressive disclosure: each convention goes to the narrowest place where it is needed, and nothing is duplicated. It includes the ADR-0009 citation fix (TODO in Approach) and the assessment of Claude Code hooks for the local layer (Decision log). Before drafting, Claude reads the official Claude Code docs on memory, rules, skills and hooks and cites them. No Claude file is edited in this step.
- **Reads:** step 11 findings; `CLAUDE.md`; listing of `.claude/rules/` and `.claude/skills/`, then only the files the map touches; official Claude Code docs
- **Check:** every convention from step 11 has exactly one destination
- **Commit:** `docs(T020): s13 add placement map to spike s008`

### Step 14 — Approve the placement map

- **Status:** 💤 todo
- **Who:** Owner
- **Scope:** review the map row by row; report the rows to move and why.
- **Check:** owner's OK on the whole map

### Step 15 — Write the conventions into the Claude files

- **Status:** 💤 todo
- **Who:** Claude
- **Scope:** edits exactly as the approved map, nothing more: one commit per destination, each explained to the owner before writing. ADR changes (e.g. ADR-0013) are not written here; they go to Follow-ups in step 16.
- **Reads:** the approved map; the files it names
- **Check:** `git diff --stat` touches only the files in the map
- **Commit:** `docs(T020): s15 <destination>: testing conventions`, one per destination

### Step 16 — Conclusion

- **Status:** 💤 todo
- **Who:** Owner + Claude
- **Scope:** 5. Conclusion and the destination of every Production input in this doc; How we got here in the README; tear-down: Claude restores `.github/workflows/ci.yml` to its content on `main` (`git show main:.github/workflows/ci.yml`), the owner commits and pushes it and deletes local venvs and `node_modules/`.
- **Reads:** 1. Questions, 2. Method › Decision log, 4. Findings
- **Check:** every Q answered; every exit criterion has a result; every P has a destination; `git diff main -- .github/workflows/ci.yml` is empty
- **Commit:** `docs(T020): s16 conclude spike s008`, then `ci(T020): s16 remove temporary spike jobs`

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
