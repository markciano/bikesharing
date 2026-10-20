# Spike: Testing conventions

- **Task:** T020
- **ADRs:** ADR-0009 (test fixtures), ADR-0011 (Worker and R2 capture), ADR-0012 (collectors decoupled by output contract), ADR-0013 (CI)
- **Code:** `spikes/testing-conventions/`

## Status

- State: Running 🔄
- Phase: [x] Questions · [x] Method · [x] Steps · [x] Steps review
- Started: 2026-10-19 · Finished: —
- Current step: 16

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
- Feedback time: the pre-merge checks of a PR finish in ≤ 10 min in total, measured as the wall-clock duration of the `pull_request` workflow run as GitHub shows it, all jobs included (XP ten-minute build); above it, the spike proposes moving slow tests to another CI layer — guide
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
| P1 Python | Minimal Python module with `unit` and `integration` tests: synthetic fixture (Shared behaviour 5), `conftest.py`, injected time, coverage report | Validates in practice the `.claude/rules/python.md` rules that need it; the rest are justified on paper (Q1) |
| P2 Spark | One PySpark transformation tested on a shared local SparkSession | The right test level for Spark and its real cost in CI: Java and session start-up (Q2) |
| P3 Worker | Minimal Worker split as functional core, imperative shell, tested with `vitest` in `workerd` (step 1 tool): pure functions as unit tests, the `scheduled` handler writing to an in-memory R2 binding as integration test | Whether the Worker can be tested in `workerd` without a Cloudflare account, locally and in CI (Q3) |
| P4 Contract | Shared golden test vectors for the collector contract of ADR-0012 (key, UTC timestamp, gzip payload unchanged); a producer test in JS on the Worker and a consumer test in Python on a bronze-side key parser | Whether one language-neutral contract breaks both sides when it changes (Q4) |
| P5 CI layers | P1–P4 running in the pre-commit, PR and `main` layers, with measured durations | Which test level goes in each layer, and whether ADR-0013 changes (Q5) |
| Desk analysis | Review of CLAUDE.md, the rules and the `/implement` skill; no code | Where each convention lives (Q6) |

Tool choices with real alternatives are scored on paper with a weighted decision matrix; the PoC uses the winner and alternatives are not built. Every other tool used in a PoC gets a "no real alternative" line with its source.

- `pytest` vs `unittest` (P1)
- Spark helpers: `pyspark.testing.assertDataFrameEqual` (PySpark ≥ 3.5) vs `chispa` (P2)
- Worker test tool: `@cloudflare/vitest-plugin` vs Miniflare API vs wrangler `createTestHarness()` (P3)
- Contract format: shared golden test vectors vs schema (JSON Schema / ODCS), scored separately for format/behaviour contracts (keys, naming, encoding) and data-shape contracts (silver, gold); only the vectors are built (P4)

### Shared behaviour

1. **One command per PoC,** documented in the README; dependencies pinned as set in the Decision log. Python: Claude writes only the direct dependencies with `==`; the owner's run step installs them, runs `pip freeze > requirements.txt`, adds the header line `# Python <version>; versions resolved by pip on <date>` and commits it with the step. Any later change to the direct dependencies or to the Python version repeats the freeze.
2. **Mutation check:** check and apply the patch (`git apply --check`, then `git apply`); run the test locally and keep the failing output; commit and push the change, marked as temporary, and record the red CI run URL; commit the revert and see CI green again. Only `pull_request` runs (the PR gate) are counted; `push` runs are not. Each mutation is a finding: what was changed, which test failed, the run URL. The P4 mutation is a change that the valid data of both sides stops meeting (e.g. a changed key format), never one that relaxes the contract, which would let invalid cases pass and fail only one side; it runs the tests of both sides.
3. **No network in tests** (hermetic tests), in Python and JS alike; in the Worker, calls to the source API are mocked with the outbound mock of the step 1 Worker test tool (`@msw/cloudflare` for `@cloudflare/vitest-plugin`). Hypothesis for Q1: checks against live sources belong outside the PR gate (e.g. a scheduled job); Q5 names their layer only.
4. **Measurements:** local duration with `time <command>`; CI duration per job as reported by GitHub, plus the wall-clock duration of the whole `pull_request` workflow run for criterion 3; all recorded in Findings.
5. **Fixtures** are hand-written synthetic data: GBFS JSON for P1 in `python/tests/fixtures/`; the P4 vectors and one GBFS payload in `contract/`; Spark builds its DataFrame inside the test. Payloads that must be gzip are compressed in memory by the test, so no binary file is committed. No source data is committed (ADR-0009).
6. **Commit messages** start the description with the step: `type(T020): sN description`.

### Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-10-19 | Exit criterion "fault injection" renamed to "tests detect faults (manual mutation testing)"; content unchanged | "Fault injection" names resilience testing of running distributed systems, which is not what the criterion checks |
| 2026-10-19 | One probe per question (P1–P5 plus desk analysis), no competing variants | Each probe answers a different question; the conventions cover every component, not a choice among them |
| 2026-10-19 | Tool alternatives are scored on paper; only the winner is built | Keeps the timebox; the PoC verifies the chosen tool, the matrix records why |
| 2026-10-19 | PoCs run in CI through temporary changes to `ci.yml` on the T020 branch: one job per PoC scoped to `spikes/testing-conventions/`; the PR is opened as draft; the changes are reverted at Conclusion, before merge. Amended 2026-10-20: the temporary `push` trigger for this branch (added in step 2) is removed in step 5 | Measures the real CI layers (criterion 2, Q5) while nothing temporary reaches `main` (ephemeral CI config on a feature branch); `act` does not reproduce the GitHub runner faithfully. Amendment: the double run (`push` + `pull_request`) was observed in step 3 and is documented GitHub behaviour; keeping the trigger only duplicates the remaining runs. Q5 is answered from the step 3 observation plus the standard |
| 2026-10-19 | The local layer (Q5) is the test command `/implement` runs before proposing each commit; its duration is measured. A Git `pre-commit` hook is assessed on paper only, and Claude Code hooks (`.claude/settings.json`) are assessed on paper in Q6 as the automatic form of that instruction | YAGNI: `/implement` already runs the tests before every commit the owner makes, so a Git hook would repeat them and add config, per-machine install and tear-down |
| 2026-10-19 | Dependencies follow the earlier spikes: Python `venv` + `requirements.txt` pinned with `==`; JS `npm` + `package-lock.json`; Python, Node and Java versions pinned in each CI job (`actions/setup-python`, `setup-node`, `setup-java`) | Criterion 2 with tools the owner already used; the dependency tooling of production code is not a testing convention |
| 2026-10-19 | Gate in P2: Python 3.14 + PySpark 4.2.0 + Java 17 run the Spark test locally and in CI; if not, P2 drops to an earlier Python version | Python 3.14 is supported since Spark 4.1.0 (SPARK-51169, 4.1.0 release notes); 4.2.0 is the latest stable (2026-07-14) and runs on Java 17/21/25, 17 being the lowest LTS. Not confirmed by docs: behaviour on the GitHub Actions runner and `pyspark.testing.assertDataFrameEqual` in an installed 4.2.0 |
| 2026-10-19 | Temporary commits (CI jobs, deliberate mutations and their reverts) stay on the T020 branch and reach `main` history through rebase merge; each one says in its message that it is temporary | The owner accepts them in history at this stage of the project; one branch and one PR is simpler than a throwaway branch. The final content of `main` stays clean |
| 2026-10-19 | Spike fixtures are hand-written synthetic JSON, not trimmed source samples | No ADR-0009 exception or new ADR is needed; the shape is enough to validate a convention (YAGNI); the trimming script belongs to the production design |
| 2026-10-19 | Java 17 is provisional, for this spike only; the production Java version is decided in T021, against the runtime of the deployment target (T022) | The testing conventions do not depend on the Java version; Spark 4.2 supports 17/21/25 and 17 is the most tested by the Spark ecosystem; choosing now would decide without the deployment runtime |
| 2026-10-19 | Tool matrices run first (step 1), before any PoC | The PoCs use the chosen tools; scoring after building would bias the matrix |
| 2026-10-19 | Placing conventions in the Claude files is split into placement map, owner approval and writing (steps 13–15) | In T018 conventions were written into CLAUDE.md first and redistributed later; deciding the place before writing follows progressive disclosure and spec-driven development |
| 2026-10-19 | Method change (Steps review): P4 tests the collector contract of ADR-0012 (key, UTC timestamp, gzip payload unchanged) with shared golden test vectors in `contract/collector-contract.json`. The earlier P4 assumed a station-shape contract validated with JSON Schema, which ADR-0012 does not define | Q4 must be answered on the real contract; conformance test vectors are the standard way to test one format across implementations in different languages, and they check what a schema cannot (date folder consistent with the timestamp, bytes unchanged) |
| 2026-10-19 | The Q4 convention states when each form applies: shared test vectors for format/behaviour contracts (keys, naming, encoding); a schema (JSON Schema / ODCS) for data-shape contracts (silver, gold). Only the vectors are built; the schema case is justified on paper in step 11 and goes to Not verified with its risk and the mitigation "validated in the first design that defines a data-shape contract" | Q4 serves later contracts too; building a data-shape contract now would have no real case to test (YAGNI) |
| 2026-10-19 | The Worker follows functional core, imperative shell: pure exported functions (e.g. `objectKey`) are unit-tested against the vectors (P4 producer); the `scheduled` handler is tested in `workerd` with the source fetch mocked, asserting the object written to the in-memory R2 binding (ADR-0011). The integration test answers Q3 and is what the step 6 Gate checks | A pure-function test alone does not need `workerd`, so it cannot answer Q3; the split keeps the logic testable without the runtime |
| 2026-10-19 | Old step 7 split: contract vectors become step 4, before the Worker; the producer test goes with the Worker (steps 5–6) and the consumer test with Python (steps 7–8) | The contract exists before either side; each PoC stays one code step plus one run step; `ajv` and `jsonschema` are no longer needed, so the late lockfile change disappears |
| 2026-10-19 | Amends "Dependencies follow the earlier spikes": Python dependencies are frozen with `pip freeze` in the owner's run steps (Shared behaviour 1), as in `spikes/realtime-capture-analysis/requirements.txt` | Criterion 2 requires every version pinned, transitive ones included; `==` on direct dependencies alone does not pin them |
| 2026-10-19 | Every tool used in a PoC gets a matrix or a "no real alternative" line with its source in step 1, the Worker test tool (Q3) included | Criterion 4: no tool choice is left to a code step |
| 2026-10-19 | Criterion 3 "in total" is the wall-clock duration of the `pull_request` workflow run as GitHub shows it, `docs` job included | Jobs run in parallel; the wall-clock time is what the developer waits for |
| 2026-10-19 | Replaces the consequence of "Gate in P2": on a failure, Claude diagnoses the cause first. Python incompatibility → the latest Python version PySpark 4.2.0 supports; Java → Java 21; runner or other → a finding, and P2 is re-decided with the owner | Dropping the Python version only fixes one of the possible causes; the Gate must say what happens for each |
| 2026-10-19 | Conditional change to "Java 17 is provisional": when the Java branch of "Replaces the consequence of 'Gate in P2'" applies, P2 moves to Java 21 (Temurin 21.0.10, installed locally), locally and in `setup-java`, and the change is recorded here | Java 21 is supported by Spark 4.2 and needs no install; production still decides in T021 |
| 2026-10-19 | Mutation runs count only `pull_request` runs: four red, four green | The PR run is the gate; each push also triggers a `push` run, which would double the count |
| 2026-10-19 | P1 unit tests are written test-first in their own commit (`s7 add failing unit tests`) before the code; a red phase by import error is accepted as the valid first red of TDD, and recorded as such in the Q1 evidence | The Git history is the evidence for the TDD rule in Q1 |
| 2026-10-19 | Amends "Spike fixtures are hand-written synthetic JSON": payloads that must be gzip are built in memory inside the tests from the JSON fixtures | The contract payload is gzip bytes (ADR-0012); compressing in the test keeps binary files out of the repo |
| 2026-10-19 | Deviation in step 1: the Worker test tool matrix compares `@cloudflare/vitest-plugin`, the Miniflare API and wrangler `createTestHarness()`, with the criteria and weights already approved; the outbound fetch mock is the one of the chosen tool (`@msw/cloudflare` for the plugin) | `@cloudflare/vitest-pool-workers` is deprecated on npm and renamed `@cloudflare/vitest-plugin`; `unstable_startWorker` is deprecated in favour of `createTestHarness()` (Cloudflare changelog, 2026-07-21); a convention for production cannot rest on deprecated tools |
| 2026-10-20 | Outcome of the step 6 diagnosis (F5–F7): the step 5 integration test intercepts the source fetch with Miniflare `outboundService` in the vitest config and keeps the bytes-unchanged assertion; MSW is no longer used to serve the gzip body. The Gate of step 6 is not failed: Q3 holds (the `scheduled` handler runs in `workerd` and writes R2 without an account) | MSW intercepts `fetch` in JavaScript and decodes by `Content-Encoding` before the Worker sees the response (F6); `outboundService` keeps the bytes (F7). Limit: since `outboundService` does not decode in default mode either, the test cannot detect a regression of `encodeResponseBody: 'manual'`; that platform behaviour is covered by the measured V4 capture (ADR-0011) and, for the future, by a post-deploy smoke test (layer 4, on paper only) |
| 2026-10-20 | Amends Shared behaviour 3: in the Worker, calls to the source API are simulated with Miniflare's `outboundService` (in `vitest.config.js`), not with the outbound mock of the step 1 tool (`@msw/cloudflare`), which is removed with `msw` from the PoC. The integration test compares the bytes stored in R2 with the in-memory gzip fixture, passed to it as a binding, and asserts that they start with the gzip magic bytes `1f 8b` | MSW decodes the body before the Worker sees it (F6), so it cannot serve a gzip body for a bytes-unchanged test; an oracle that does not travel through the mocked path (the fixture bytes, not a fetch back) keeps the test able to fail if any layer transforms the body |
| 2026-10-20 | Amends step 12: the owner verifies a synthesis (testing model) instead of each finding | About 30 findings are not reviewable one by one; a summary with traceability lets the owner verify what he will actually use |
| 2026-10-20 | Clarifies the expected output of the main question: the testing model answers, per component (python, spark, worker, contract, docs), (1) when a test is written, (2) which type, (3) format, (4) where it lives, (5) where and when it runs; and once for the project (6) the CI flow with the rule for moving tests from the PR run to the `main` run. Every statement cites its findings. `docs` is a component on paper (no PoC) | The main question asks which conventions each component adopts; a model with these six answers is what the component designs will apply |
| 2026-10-20 | Amends step 13: the placement map also covers the destination of the testing model, the docs local lint (pinned version, command, `.claude/settings.json` permission; completed in step 15, since docs is the only component with real code today) and a CI job recipe for future component designs, assessing a rule with `paths: .github/workflows/**` against a line in the `/design` skill or template. The CI jobs of python, spark and worker are still created in their own designs | The model needs an owner-facing home; docs can be linted locally today; the spike's temporary jobs are the evidence for a recipe that each component design would otherwise re-derive |
| 2026-10-21 | Step 15 deviation from the placement map: M6 and M7 go to `.claude/rules/cloudflare-worker.md` (`paths:` `collector/**/*.js`, `collector/**/package.json`), not to `collector.md`; the testing-strategy section is "Cloudflare Worker (JS)" | The content is Cloudflare-specific (`workerd`, R2, Miniflare), and a collector in another language must not load it |
| 2026-10-21 | Step 15 deviation from the placement map: the CI job recipe in `.claude/rules/ci.md` (M17) sets `timeout-minutes: 10` on every job | A hung test would otherwise hold the PR for the 6-hour default; it matches the 10-minute budget of the `pull_request` run and affects no other decision |
| 2026-10-21 | Step 15 deviation from the placement map: the docs local lint (M16) is a script `scripts/lint-docs.sh` run by the owner, with `markdownlint-cli2` 0.23.2 (the version of `markdownlint-cli2-action@v24`), instead of a `PostToolUse` hook; written in one commit with its mentions in `.claude/rules/docs.md` and `CLAUDE.md` | A hook would lint on every edit of a file in `docs/`, too often for the benefit; the docs rules already steer the writing, so a lint now and then is enough, and CI is the gate. No `settings.json` permission is needed because the owner runs it |

### File layout

P1 and P2 are separate folders with their own `requirements.txt`, so the Python job installs neither PySpark nor Java and the cost of Spark in CI is measured on its own (criterion 3). The contract folder is shared by both languages.

```text
spikes/testing-conventions/
├── README.md              Question, setup, one command per PoC; How we got here (at Conclusion)
├── .gitignore             venvs, node_modules/, .wrangler/, outputs/
├── contract/              P4 · shared by JS and Python
│   ├── collector-contract.json   golden test vectors: valid (source, feed, captured_at) → key; invalid keys
│   └── fixtures/                 one synthetic GBFS payload (JSON; gzipped in memory by the tests)
├── python/                P1 (+ P4 consumer test)
│   ├── requirements.txt      frozen with pip freeze (direct: pytest, pytest-cov)
│   ├── pyproject.toml        pytest config only
│   ├── poc/                  status parsing and staleness; bronze-side key parser
│   └── tests/                conftest.py, unit/, integration/, fixtures/
├── spark/                 P2
│   ├── requirements.txt      frozen with pip freeze (direct: pyspark 4.2.0, pytest)
│   ├── pyproject.toml        pytest config only
│   ├── poc/                  one transformation
│   └── tests/                conftest.py with a shared local SparkSession
├── worker/                P3 (+ P4 producer test)
│   ├── package.json · package-lock.json
│   ├── wrangler.jsonc · vitest.config.js
│   ├── src/                  contract.js (pure functions) · index.js (scheduled handler)
│   └── test/                 unit/ (pure functions) · integration/ (workerd, fetch mocked, in-memory R2)
├── mutations/             one .patch per PoC, applied and reverted by the owner
└── outputs/               ignored by Git: failing outputs of the mutation runs
```

Outside this folder, only `.github/workflows/ci.yml` changes, temporarily (Decision log). Tool matrices are recorded in 4. Findings, not in files; timings too (Shared behaviour 4).

## 3. Steps

| # | Title |
|---|---|
| 1 | Tool matrices |
| 2 | Spark PoC and temporary CI job |
| 3 | Run Spark locally and in CI; open draft PR |
| 4 | Collector contract vectors |
| 5 | Worker PoC (P3 + P4 producer) and temporary CI job |
| 6 | Run the Worker locally and in CI |
| 7 | Python PoC (P1 + P4 consumer) and temporary CI job |
| 8 | Run the Python PoC locally and in CI |
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

- **Status:** ✅ done
- **Who:** Claude
- **Scope:** the weighted decision matrices listed in 2. Method › Approach, in 4. Findings. The contract-format matrix is scored separately for format/behaviour contracts and data-shape contracts, so it records which form applies to each (Decision log). Every other tool used in a PoC (e.g. `vitest`, `wrangler`, `pytest-cov`) gets a "no real alternative" line with its source. Criteria and weights are written first and approved by the owner on the diff; only then are options scored, each score with a one-line reason and a source. Touches only this doc.
- **Reads:** 1. Questions; 2. Method › Approach, Decision log; ADR-0012; official docs of each tool
- **Check:** the weights were approved before any score was written; each matrix names a winner (the contract format, one per contract kind); every tool used in a PoC has a matrix or a "no real alternative" line
- **Commit:** `docs(T020): s1 add tool matrices to spike s008`

### Step 2 — Spark PoC and temporary CI job

- **Status:** ✅ done
- **Who:** Claude
- **Scope:**
  - `spark/requirements.txt` with the direct dependencies only (`pyspark==4.2.0`, `pytest`, the step 1 Spark helper if it is a package; all `==`); the owner freezes it in step 3 (Shared behaviour 1). `spark/pyproject.toml` (pytest config only).
  - `spark/poc/` with one transformation: a DataFrame of station status in, the same rows plus an occupancy ratio (`num_bikes_available / capacity`) out.
  - `spark/tests/conftest.py` with a session-scoped local SparkSession (`local[1]`, UI disabled), and `spark/tests/test_<module>.py` with one test using the step 1 helper. The session scope deviates from the function-scope rule in `.claude/rules/python.md` on purpose; the step records why as evidence for Q1 and Q2.
  - `README.md` (question, link to this doc, Spark command) and `.gitignore` (Shared behaviour, File layout).
  - `.github/workflows/ci.yml`: add `t020-testing-conventions` to the `push` branches and a job `poc-spark` (`actions/setup-python` with the Python version in the Decision log, `actions/setup-java` Temurin with the Java version in the Decision log, `pip install -r requirements.txt`, `pytest`, working directory `spikes/testing-conventions/spark`).
  - Must not touch: the `docs` job, anything outside `spikes/testing-conventions/` and `ci.yml`.
- **Reads:** 2. Method › Shared behaviour, File layout, Decision log; step 1 matrix; `.github/workflows/ci.yml`
- **Check:** `pytest --collect-only` lists one test (run by the owner in step 3)
- **Commit:** `chore(T020): s2 add Spark PoC and temporary CI job` (after step 3 freezes `spark/requirements.txt`)

### Step 3 — Run Spark locally and in CI; open draft PR

- **Status:** ✅ done
- **Who:** Owner
- **Scope:**

  Python 3.14 and Java 17 are the versions in the Decision log; if the Gate changed them, use the ones it recorded.

  ```bash
  cd spikes/testing-conventions/spark
  export JAVA_HOME=$(/usr/libexec/java_home -v 17) && java -version
  python3.14 -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  pip freeze > requirements.txt
  pytest --collect-only -q
  time pytest
  deactivate && cd ../../..
  ```

  `java -version` must show 17; if not, install Temurin 17 (`brew install --cask temurin@17`) and repeat. After the freeze, add the header line of Shared behaviour 1 at the top of `spark/requirements.txt`.

  Commit step 1 (if not done yet) and step 2, including the frozen `requirements.txt`. Then:

  ```bash
  git push -u origin t020-testing-conventions
  gh pr create --draft --base main --title "T020: Testing conventions and place in claude files" --body "Spike s008. Temporary CI jobs; reverted before merge."
  ```

  Report: `java -version` output; `--collect-only` output; local test result and `time`; PR URL; result, duration and run URL of `poc-spark` on the `push` and on the `pull_request` run.
- **Gate:** the test passes locally and in CI with Python 3.14 + PySpark 4.2.0 + Java 17 → if not, Claude diagnoses the cause from the failing output first:
  - Python incompatibility → drop `poc-spark` to the latest Python version PySpark 4.2.0 supports;
  - Java → retry with Java 21 (`-v 21` locally, `setup-java` 21), as in the Decision log;
  - runner or other → record a finding and re-decide P2 with the owner.

  Each change is recorded in the Decision log, and this step is repeated, freeze included.
- **Check:** `poc-spark` green on the PR

### Step 4 — Collector contract vectors

- **Status:** ✅ done
- **Who:** Claude
- **Scope:**
  - `contract/collector-contract.json` in the step 1 format for format/behaviour contracts, following ADR-0012:
    - `valid`: cases `{source, feed, captured_at}` with `captured_at` in UTC, ISO 8601 with `Z` (ADR-0005), each with its expected `key` (`raw/<source>/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz`); one case is within an hour of midnight UTC, where local time and UTC fall on different dates;
    - `invalid`: keys that each break exactly one rule (extension, timestamp without `Z`, date folder not matching the timestamp, missing segment), each with a one-line `reason`.
  - `contract/fixtures/`: one synthetic GBFS `station_status` payload as JSON (Shared behaviour 5).
  - `README.md`: a Contract section (what the vectors are, which tests read them).
  - Must not touch: anything outside `contract/` and `README.md`.
- **Reads:** ADR-0012; ADR-0005; step 1 contract-format matrix; 2. Method › Shared behaviour
- **Check:** in every valid case the date folder is the date of `captured_at` in UTC; every invalid case breaks exactly one rule
- **Commit:** `chore(T020): s4 add collector contract vectors`

### Step 5 — Worker PoC (P3 + P4 producer) and temporary CI job

- **Status:** ✅ done
- **Who:** Claude
- **Scope:**
  - `worker/package.json` with exact versions (no `^`) of `wrangler`, `vitest` and the step 1 Worker test tool, and an exact `engines.node`; `worker/wrangler.jsonc` with one cron trigger and an R2 binding `RAW_BUCKET`; `worker/vitest.config.js` using the step 1 Worker test tool.
  - Functional core, imperative shell (Decision log):
    - `worker/src/contract.js`: pure exported `objectKey(source, feed, capturedAt)`;
    - `worker/src/index.js`: a `scheduled` handler that takes one capture time per pass (UTC), fetches one GBFS feed as set in ADR-0011 (`Accept-Encoding: gzip`, `encodeResponseBody: 'manual'`) and stores the body unchanged in `RAW_BUCKET` under `objectKey(...)`.
  - `worker/test/unit/`: `objectKey` returns the expected key for every valid vector in `../contract/collector-contract.json` (P4 producer test).
  - `worker/test/integration/`: in `workerd`, trigger `scheduled` with the source fetch mocked (Shared behaviour 3), serving the contract fixture gzipped in memory with `Content-Encoding: gzip`; assert one object in the in-memory R2 binding, at the expected key, with bytes identical to those served. This test answers Q3. Whether the mock reproduces the runtime's handling of `encodeResponseBody: 'manual'` is observed only and noted in Findings (risk in ADR-0011).
  - `README.md`: Worker command. `.github/workflows/ci.yml`: job `poc-worker` (`actions/setup-node` with `node-version-file: package.json`, `npm ci`, `npx vitest run`, working directory `spikes/testing-conventions/worker`); and remove `t020-testing-conventions` from the `push` branches with its TODO comment, so `push` stays `[main]` (Decision log, amended 2026-10-20).
  - Must not touch: other jobs, `contract/`, anything outside `spikes/testing-conventions/` and `ci.yml`.
- **Reads:** 2. Method › Shared behaviour, File layout, Decision log; ADR-0011; ADR-0012; `contract/collector-contract.json`; step 1 Worker test tool matrix; `.github/workflows/ci.yml`
- **Check:** `package.json` has no ranges; no test makes a real network call; the unit test loads the vectors by relative path
- **Commit:** `chore(T020): s5 add Worker PoC and temporary CI job` (after step 6 creates `package-lock.json`)

### Step 6 — Run the Worker locally and in CI

- **Status:** ✅ done
- **Who:** Owner
- **Scope:**

  ```bash
  cd spikes/testing-conventions/worker
  node --version
  npm install
  time npx vitest run
  cd ../../..
  ```

  Then commit steps 4 and 5, step 5 including `package-lock.json`, and `git push`. No Cloudflare login is needed. Report: Node version; local result of both tests and `time`; result, duration and run URL of `poc-worker` on the `pull_request` run.
- **Gate:** the integration test passes in `workerd` locally and in CI without a Cloudflare account → if not, Q3 is re-decided with the owner before step 9, whose p3 and p4 patches depend on the Worker.
- **Check:** `poc-worker` green on the PR

### Step 7 — Python PoC (P1 + P4 consumer) and temporary CI job

- **Status:** ✅ done
- **Who:** Claude
- **Scope:**
  - `python/requirements.txt` with the direct dependencies only (`pytest`, `pytest-cov`; all `==`); the owner freezes it in step 8 (Shared behaviour 1). `python/pyproject.toml` (pytest config only, coverage reported without threshold).
  - `python/poc/`:
    - a module that parses one station-status JSON into records and flags stale stations against a `now` received as a parameter (UTC);
    - a bronze-side key parser: `parse_key(key)` returns `(source, feed, captured_at)` in UTC and rejects keys that break ADR-0012; a reader that decompresses a gzip payload.
  - `python/tests/conftest.py` (function-scoped fixtures); `tests/fixtures/` (synthetic GBFS JSON, Shared behaviour 5); `tests/unit/` (parsing, staleness, key parser); `tests/integration/` (file fixture → records; P4 consumer test: every valid vector in `../contract/collector-contract.json` parses to its `(source, feed, captured_at)`, every invalid one is rejected, and the contract fixture gzipped in memory is read back unchanged). Every rule in `.claude/rules/python.md` › Testing is followed, so that Q1 can test them.
  - Test-first, in two commits (Decision log): Claude writes `tests/unit/` and `conftest.py`, the owner commits them; then Claude writes the rest.
  - `README.md`: Python command. `.github/workflows/ci.yml`: job `poc-python` (`actions/setup-python` with the Python version in the Decision log, `pip install -r requirements.txt`, `pytest --cov`, working directory `spikes/testing-conventions/python`).
  - Must not touch: other jobs, `contract/`, `worker/`, `spark/`, anything outside `spikes/testing-conventions/` and `ci.yml`.
- **Reads:** `.claude/rules/python.md`; 2. Method › Shared behaviour, File layout, Decision log; ADR-0012; `contract/collector-contract.json`
- **Check:** each `python.md` testing rule is either applied in the PoC or listed in the README as "paper only"; the consumer test loads the vectors by relative path; the first commit contains only `tests/unit/` and `conftest.py`
- **Commit:** `test(T020): s7 add failing unit tests`, then `chore(T020): s7 add Python PoC code and temporary CI job` (after step 8 freezes `python/requirements.txt`)

### Step 8 — Run the Python PoC locally and in CI

- **Status:** ✅ done
- **Who:** Owner
- **Scope:**

  ```bash
  cd spikes/testing-conventions/python
  python3.14 -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  pip freeze > requirements.txt
  time pytest --cov
  deactivate && cd ../../..
  ```

  After the freeze, add the header line of Shared behaviour 1 at the top of `python/requirements.txt`. Then make the second step 7 commit, including the frozen `requirements.txt`, and `git push`. Report: local result, coverage summary and `time`; result, duration and run URL of `poc-python`; the wall-clock duration of the whole `pull_request` workflow run as GitHub shows it (criterion 3).
- **Check:** `poc-python`, `poc-worker` and `poc-spark` green on the PR

### Step 9 — Mutation patches

- **Status:** ✅ done
- **Who:** Claude
- **Scope:** `mutations/p1-python.patch`, `p2-spark.patch`, `p3-worker.patch`, `p4-contract.patch`.
  - P1–P3: each changes one line of the code under test.
  - P4: changes one rule of the key format in every valid vector of `contract/collector-contract.json` (e.g. the date folder as `YYYY/MM/DD`), so the valid data of both sides stops meeting it; never a change that relaxes the contract (Shared behaviour 2).
  - Each patch says in a header comment, before its first `diff` line, which test must fail; for P4, the producer unit test in `worker/` and the consumer test in `python/`, and why a relaxing change would not do.
  - Adds `mutations/` usage to the README. Touches nothing else.
- **Reads:** the PoC code and contract from steps 2–8; 2. Method › Shared behaviour
- **Check:** `git apply --check mutations/<patch>` succeeds for each (run by the owner in step 10)
- **Commit:** `chore(T020): s9 add mutation patches`

### Step 10 — Apply and revert mutations

- **Status:** ✅ done
- **Who:** Owner
- **Scope:** all commands from the repo root (Shared behaviour 2). Once:

  ```bash
  mkdir -p spikes/testing-conventions/outputs
  ```

  For each patch, check and apply it:

  ```bash
  git apply --check spikes/testing-conventions/mutations/<patch>
  git apply spikes/testing-conventions/mutations/<patch>
  ```

  Run the block of its PoC; for `p4-contract.patch`, run both the Python and the Worker blocks. Use the Java version in the Decision log.

  ```bash
  # P1 Python (and P4)
  (cd spikes/testing-conventions/python && source .venv/bin/activate && pytest) 2>&1 | tee spikes/testing-conventions/outputs/<patch>-python.txt
  # P2 Spark
  (cd spikes/testing-conventions/spark && export JAVA_HOME=$(/usr/libexec/java_home -v 17) && source .venv/bin/activate && pytest) 2>&1 | tee spikes/testing-conventions/outputs/<patch>-spark.txt
  # P3 Worker (and P4)
  (cd spikes/testing-conventions/worker && npx vitest run) 2>&1 | tee spikes/testing-conventions/outputs/<patch>-worker.txt
  ```

  Then commit, push and revert:

  ```bash
  git commit -am "test(T020): s10 deliberate mutation <patch>, reverted next" && git push
  # wait for the red pull_request run, note its URL
  git revert --no-commit HEAD && git commit -m "test(T020): s10 revert mutation <patch>" && git push
  # wait for the green pull_request run, note its URL
  ```

  Report per patch: the test that failed locally (for P4, on each side), the red `pull_request` run URL, the green `pull_request` run URL after the revert. `push` runs are not counted.
- **Gate:** a mutation does not make its test fail (for P4, on both sides) → that convention is not adopted as is; Claude records it as a finding and step 11 re-decides it.
- **Check:** four red and four green `pull_request` runs recorded; the P4 mutation failed on both sides

### Step 11 — Analysis Q1–Q5

- **Status:** ✅ done
- **Who:** Claude
- **Scope:** findings in 4. Findings:
  - Q1: each rule of `.claude/rules/python.md` › Testing with verdict (holds, corrected, dropped), reason, standard, and its evidence (PoC or paper). The TDD evidence is the two step 7 commits; the red phase by import error is recorded as the valid first red of TDD (Decision log).
  - Q2–Q4: answers from steps 2–10. Q4 states when each contract form applies: shared test vectors for format/behaviour contracts (built), a schema (JSON Schema / ODCS) for data-shape contracts (justified on paper; to Not verified with its risk and the mitigation "validated in the first design that defines a data-shape contract").
  - Q5: test level per CI layer (local via `/implement`, push to a feature branch (answered from the step 3 double-run observation plus the standard, not measured again), PR pre-merge, post-merge on `main`), the layer for checks against live sources, and the proposed change to ADR-0013 (including "require branches to be up to date"), with the measured durations and the wall-clock `pull_request` run against criterion 3.
  - Observe only: job and local durations; whether the Worker fetch mock reproduces `encodeResponseBody: 'manual'` (step 5).
  - Exit criteria results so far, and Production inputs.
  - Touches only this doc.
- **Reads:** 1. Questions, 2. Method, reports from steps 3, 6, 8 and 10, `.claude/rules/python.md`, ADR-0013
- **Check:** every Q1–Q5 has at least one finding; every finding cites its evidence
- **Commit:** `docs(T020): s11 add analysis to spike s008`

### Step 12 — Verify the analysis

- **Status:** ✅ done
- **Who:** Owner + Claude
- **Scope:** synthesis first (Decision log).
  - Claude: drafts 4. Findings › Testing model from the findings, answering (1)–(6) as set in the Decision log, each statement citing its findings. Touches only this doc.
  - Owner: verifies the model, and goes down to a finding only where something is unclear or unsupported. Reports the statements to correct or explain.
- **Reads:** 4. Findings; 2. Method › Decision log
- **Check:** owner's OK on the testing model
- **Commit:** `docs(T020): s12 add testing model to spike s008`

### Step 13 — Placement map (Q6)

- **Status:** ✅ done
- **Who:** Claude
- **Scope:** a placement map in 4. Findings: a table with one row per convention from step 11 (convention · destination · reason). Destinations: `CLAUDE.md` (always loaded: short invariants), `.claude/rules/*.md` with `paths:` (loaded when matching files are touched), a skill such as `/implement` (procedures, loaded when invoked), hooks or `settings.json` (enforced by the harness), an ADR (cross-cutting why). The criterion is progressive disclosure: each convention goes to the narrowest place where it is needed, and nothing is duplicated. It includes the ADR-0009 citation fix (TODO in Approach) and the assessment of Claude Code hooks for the local layer (Decision log). Before drafting, Claude reads the official Claude Code docs on memory, rules, skills and hooks and cites them. No Claude file is edited in this step. The map also covers (Decision log):
  - the destination of the testing model, an owner-facing document;
  - the docs local lint: pinned version, command and the `.claude/settings.json` permission, completed in step 15;
  - a CI job recipe for future component designs: job skeleton and rules (runtime pinned via `setup-*`, `working-directory` per component, one test command, dependencies from the lockfile or frozen `requirements.txt`, and the pending `ci-passed` aggregator with the switch of the ruleset's required check, from the TODO in `ci.yml`), with the spike's temporary jobs as evidence. Two placements are assessed: a rule with `paths: .github/workflows/**`, and a line in the `/design` skill or template so a design that adds a component plans its CI job in its File layout. The CI jobs of python, spark and worker are still created in their own designs (Out of scope).
- **Reads:** step 11 findings; `CLAUDE.md`; listing of `.claude/rules/` and `.claude/skills/`, then only the files the map touches; official Claude Code docs
- **Check:** every convention from step 11 has exactly one destination
- **Commit:** `docs(T020): s13 add placement map to spike s008`

### Step 14 — Approve the placement map

- **Status:** ✅ done
- **Who:** Owner
- **Scope:** review the map row by row; report the rows to move and why.
- **Check:** owner's OK on the whole map

### Step 15 — Write the conventions into the Claude files

- **Status:** ✅ done
- **Who:** Claude
- **Scope:** edits exactly as the approved map, nothing more: one commit per destination, each explained to the owner before writing. ADR changes (e.g. ADR-0013) are not written here; they go to Follow-ups in step 16.
- **Reads:** the approved map; the files it names
- **Check:** `git diff --stat` touches only the files in the map
- **Commit:** `docs(T020): s15 <destination>: testing conventions`, one per destination

### Step 16 — Conclusion

- **Status:** 💤 todo
- **Who:** Owner + Claude
- **Scope:**
  - Claude: 5. Conclusion (Not verified includes the schema case of Q4) and the destination of every Production input in this doc; How we got here in the README; T020 to ✅ in `docs/tasks.md`, in the conclusion commit.
  - Tear-down: Claude restores `.github/workflows/ci.yml` to its content on `main` (`git show main:.github/workflows/ci.yml`); the owner commits both commits, pushes, and deletes the local environments:

    ```bash
    rm -rf spikes/testing-conventions/{python,spark}/.venv spikes/testing-conventions/worker/node_modules
    gh pr ready
    ```

  - Then Claude gives the close sequence from CLAUDE.md (checks green, rebase merge, clean up with `-D`), and the owner runs it.
- **Reads:** 1. Questions, 2. Method › Decision log, 4. Findings
- **Check:** every Q answered; every exit criterion has a result; every P has a destination; `git diff main -- .github/workflows/ci.yml` is empty
- **Commit:** `docs(T020): s16 conclude spike s008`, then `ci(T020): s16 remove temporary spike jobs`

## 4. Findings

### Tool matrices

Weighted decision matrices (step 1). Criteria, weights and scale were approved by the owner before any score was written.

#### Scale and rules

| Score | Meaning |
|---|---|
| 5 | Covered natively and documented, no extra work |
| 4 | Covered with minor configuration or an official plugin |
| 3 | Covered with own code or a maintained third-party plugin |
| 2 | Partly covered |
| 1 | Covered with serious limitations |
| 0 | Not covered |

- Total = Σ (weight × score) / 5; maximum 100. The highest total wins.
- Each score has a one-line reason and a source (official docs, release notes, changelog). Without a source, the score is 3 and marked *unverified*.
- Weights and scale are not changed once scoring starts.
- Tie or difference ≤ 5 points: the option with the better score on the highest-weight criterion wins, recorded as a close call.
- Knock-out: an option scoring 0 on the highest-weight criterion is discarded whatever its total.

#### A. Python test runner: `pytest` vs `unittest` (P1)

| Criterion | Weight | `pytest` | `unittest` | Source |
|---|---|---|---|---|
| Fixture and isolation model (fixtures, `conftest`, `parametrize`) | 25 | 5 — fixtures, `conftest.py` and `parametrize` are native | 3 — `setUp`/`setUpClass` and `subTest`; sharing and parametrizing need own code | [pytest fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html), [parametrize](https://docs.pytest.org/en/stable/how-to/parametrize.html), [unittest](https://docs.python.org/3/library/unittest.html) |
| Industry adoption, documentation and learning curve for a beginner | 25 | 5 — PySpark docs call it "one of the most popular Python testing frameworks" | 4 — stdlib with solid docs; xUnit class boilerplate is heavier for a beginner | [Testing PySpark](https://spark.apache.org/docs/latest/api/python/getting_started/testing_pyspark.html) |
| Readability of tests and failure messages | 20 | 5 — plain `assert` with assertion rewriting and detailed diffs | 3 — `self.assertEqual` style; plainer failure output | [pytest assert](https://docs.pytest.org/en/stable/how-to/assert.html) |
| Plugins the PoCs need (coverage, Spark) | 20 | 4 — `pytest-cov` plugin; PySpark docs show a pytest fixture | 3 — `coverage run -m unittest`; PySpark docs show `setUpClass` | [pytest-cov](https://pytest-cov.readthedocs.io/en/latest/), [coverage.py](https://coverage.readthedocs.io/) |
| Dependency cost (stdlib or external) | 10 | 3 — one external dev dependency | 5 — stdlib | [pytest on PyPI](https://pypi.org/project/pytest/) |
| **Total** | 100 | **92** | 69 | |

Winner: `pytest`. Latest stable: `pytest` 9.1.1 and `pytest-cov` 7.1.0, both declaring Python 3.14 (PyPI classifiers, 2026-10-19).

#### B. Spark helper: `pyspark.testing.assertDataFrameEqual` vs `chispa` (P2)

| Criterion | Weight | `assertDataFrameEqual` | `chispa` | Source |
|---|---|---|---|---|
| Official support and maintenance with PySpark 4.2 | 30 | 5 — part of PySpark, ships with 4.2 | 3 — v0.12.0 (2026-03-24); CI covers PySpark 3.5–4.1, not 4.2; Python classifiers up to 3.12 | [chispa on PyPI](https://pypi.org/project/chispa/), [chispa repo](https://github.com/MrPowers/chispa) |
| Comparison options (row order, approximate float, schema); the occupancy ratio is a float | 25 | 5 — `checkRowOrder` (default `False`), `rtol`/`atol`, `ignoreNullable` | 5 — `ignore_row_order`, approximate float equality, `ignore_nullable`, `ignore_column_order` | [pyspark/testing/utils.py](https://github.com/apache/spark/blob/master/python/pyspark/testing/utils.py), [chispa repo](https://github.com/MrPowers/chispa) |
| Clarity of the diff on failure | 20 | 3 — `difflib` row diff, `showOnlyDiff`, `maxErrors` | 5 — coloured cell-level diff | same as above |
| Dependency cost | 15 | 5 — no extra dependency | 4 — one package plus `prettytable` | [chispa on PyPI](https://pypi.org/project/chispa/) |
| Adoption and documentation | 10 | 5 — official PySpark docs | 4 — own docs site, ~780 GitHub stars | [chispa repo](https://github.com/MrPowers/chispa) |
| **Total** | 100 | **92** | 83 | |

Winner: `assertDataFrameEqual`. Parameter details come from the Spark `master` source, not the 4.2.0 API page: confirmed in the installed 4.2.0 at step 3 (Decision log, "Gate in P2"). Both DataFrames are collected to the driver, which is fine for test-sized data.

#### C. Worker test tool: `@cloudflare/vitest-plugin` vs Miniflare API vs wrangler `createTestHarness()` (P3)

| Criterion | Weight | `@cloudflare/vitest-plugin` | Miniflare API | `createTestHarness()` | Source |
|---|---|---|---|---|---|
| Runs in real `workerd` with bindings (in-memory R2, `scheduled` trigger) without an account | 30 | 5 — tests run inside `workerd` with bindings from the config; `createScheduledController` triggers `scheduled` | 4 — runs `workerd` and dispatches scheduled events; needs own glue | 3 — *unverified*: `worker.scheduled()` documented; R2 and no-account not stated | [test APIs](https://developers.cloudflare.com/workers/testing/vitest-integration/test-apis/), [wrangler API](https://developers.cloudflare.com/workers/wrangler/api/), [test harness](https://developers.cloudflare.com/workers/testing/test-harness/) |
| Official recommendation and API stability | 25 | 5 — recommended for unit tests; stable 1.x after the rename | 3 — Miniflare 5 still in beta; direct use no longer recommended | 3 — *unverified*: recommended for integration tests, no GA label found | [Vitest integration](https://developers.cloudflare.com/workers/testing/vitest-integration/), [changelog 2026-07-21](https://developers.cloudflare.com/changelog/post/2026-07-21-integration-test-harness/) |
| `fetch` mocking for hermetic tests | 20 | 4 — `@msw/cloudflare`, the documented mechanism | 3 — *unverified* | 3 — *unverified*: outbound `fetch` proxied through Node, so MSW applies | [migration guide](https://developers.cloudflare.com/workers/testing/vitest-integration/migration-guides/migrate-to-vitest-plugin/), [prepare test state](https://developers.cloudflare.com/workers/testing/test-harness/prepare-test-state/) |
| Unit and integration tests with one runner | 15 | 5 — pure functions and handler both run under Vitest in `workerd` | 3 — tests in Node, own harness | 3 — any Node runner; pure functions run in Node, not `workerd` | [Workers testing](https://developers.cloudflare.com/workers/testing/) |
| Setup and CI cost | 10 | 4 — one plugin plus a config file; Node ≥ 22 | 3 — *unverified* | 3 — *unverified*: no CI page | [npm](https://www.npmjs.com/package/@cloudflare/vitest-plugin) |
| **Total** | 100 | **94** | 66 | 60 | |

Winner: `@cloudflare/vitest-plugin` (1.4.5; peer `vitest` ^4.1.0 or ^5.0.0; Node ≥ 22 via `wrangler` 4.151.2). Cloudflare positions the plugin for functions and modules inside the runtime and `createTestHarness()` for whole-Worker integration across Workers and external services ([Workers testing](https://developers.cloudflare.com/workers/testing/)); the PoC needs one Worker and its R2 binding, which the plugin covers. Observe only (step 5): whether `@msw/cloudflare` passes a gzip body unchanged with `encodeResponseBody: 'manual'`.

#### No real alternative

| Tool | Why | Source |
|---|---|---|
| `pytest-cov` | The pytest integration of coverage.py, the same engine; `coverage run -m pytest` only drops the plugin options | [pytest-cov](https://pytest-cov.readthedocs.io/en/latest/) |
| `pytest` (Spark PoC) | Follows from matrix A; the PySpark testing guide has a pytest section with a shared SparkSession fixture | [Testing PySpark](https://spark.apache.org/docs/latest/api/python/getting_started/testing_pyspark.html) |
| `vitest` | Peer dependency of `@cloudflare/vitest-plugin`; no other runner is supported | [npm](https://www.npmjs.com/package/@cloudflare/vitest-plugin) |
| `wrangler` | Dependency of the plugin; reads `wrangler.jsonc` and provides the local runtime (Miniflare, `workerd`) | [npm](https://www.npmjs.com/package/wrangler) |
| `@msw/cloudflare` | The outbound mock documented for the plugin | [migration guide](https://developers.cloudflare.com/workers/testing/vitest-integration/migration-guides/migrate-to-vitest-plugin/) |

#### D. Contract format: shared golden test vectors vs schema (JSON Schema / ODCS) (P4)

Same criteria and weights, scored separately for format/behaviour contracts (keys, naming, encoding) and data-shape contracts (silver, gold).

Format/behaviour contracts (the collector contract of ADR-0012):

| Criterion | Weight | Test vectors | Schema | Source |
|---|---|---|---|---|
| Expresses the rules of that contract kind (cross-field consistency, unchanged bytes, types and nullability) | 35 | 5 — input → expected cases express the date folder = UTC date of the timestamp, and byte equality | 1 — JSON Schema cannot compare two properties; only a regex on the key shape; nothing on bytes | [cross-field validation](https://jsonforms.discourse.group/t/validation-by-comparing-2-fields/1696) |
| Language neutrality: the same artefact serves JS and Python without code generation | 20 | 5 — one JSON file read by the tests of each language | 4 — the schema is neutral, but the cross-field rule needs code per language | [JSON Schema Test Suite](https://github.com/json-schema-org/JSON-Schema-Test-Suite) |
| A breaking change fails the tests of both sides | 20 | 5 — both suites read the same file, so a changed case fails both | 3 — validates sample outputs only; implementations can drift | [JSON Schema Test Suite](https://github.com/json-schema-org/JSON-Schema-Test-Suite) |
| Adopted standard and tooling | 15 | 3 — widely used pattern (conformance suites), no formal standard | 3 — JSON Schema is a standard, but not for this contract kind | [JSON Schema Test Suite](https://github.com/json-schema-org/JSON-Schema-Test-Suite) |
| Maintenance cost | 10 | 3 — *unverified* | 3 — *unverified* | — |
| **Total** | 100 | **90** | 50 | |

Data-shape contracts (silver, gold):

| Criterion | Weight | Test vectors | Schema (ODCS) | Source |
|---|---|---|---|---|
| Expresses the rules of that contract kind (cross-field consistency, unchanged bytes, types and nullability) | 35 | 2 — types and nullability only by example | 5 — ODCS declares columns, types, required, uniqueness and quality rules | [ODCS v3.1.0](https://bitol.io/?p=302), [ODCS docs](https://docs.datacontract.com/open-data-contract-standard) |
| Language neutrality: the same artefact serves JS and Python without code generation | 20 | 5 — plain JSON | 4 — YAML/JSON, though ODCS tooling is mostly Python/Java | [ODCS v3.1.0](https://bitol.io/?p=302) |
| A breaking change fails the tests of both sides | 20 | 2 — cases never see the real table's columns | 3 — *unverified*: the contract can be checked against real tables in CI | — |
| Adopted standard and tooling | 15 | 2 — no data-contract ecosystem | 5 — Bitol, a Linux Foundation project; tool support (e.g. DataHub) | [ODCS docs](https://docs.datacontract.com/open-data-contract-standard) |
| Maintenance cost | 10 | 3 — *unverified* | 3 — *unverified* | — |
| **Total** | 100 | 54 | **84** | |

Winners: shared test vectors for format/behaviour contracts; a schema (ODCS) for data-shape contracts, justified on paper only (Decision log).

### Findings log

| F | Finding | Step · Source |
|---|---|---|
| F1 | The Gate of P2 passes: the Spark test runs with Python 3.14.4 + PySpark 4.2.0 + Java Temurin 17.0.20.1 locally (macOS) and in CI (`poc-spark`, Python 3.14, Temurin 17, `ubuntu-latest`), on the `push` run and on the `pull_request` run. No change to the Decision log | Step 3 · owner report; [push run](https://github.com/markciano/bikesharing/actions/runs/39332952154/job/118335360931?pr=6), [pull_request run](https://github.com/markciano/bikesharing/actions/runs/39332955352/job/118335372260?pr=6), [PR #6](https://github.com/markciano/bikesharing/pull/6) |
| F2 | `pyspark.testing.assertDataFrameEqual` exists and compares two DataFrames in the installed PySpark 4.2.0 (default options only; `checkRowOrder`, `rtol` and `atol` were not exercised). This confirms the part of matrix B that was unconfirmed | Step 3 · owner report (1 test passed) |
| F3 | Duration of the Spark job with one test: locally 34.66 s as reported by `pytest` (34.859 s with `time`), first and only run, JVM and SparkSession start-up included and not measured apart; in CI `poc-spark` 50 s on `push` and 56 s on `pull_request`, whole job (checkout, setup, install, test) | Step 3 · owner report |
| F4 | `pip freeze` of the Spark PoC resolves 7 packages: `pyspark` 4.2.0 and `pytest` 9.1.1 plus `iniconfig`, `packaging`, `pluggy`, `py4j` and `Pygments` | Step 3 · `spark/requirements.txt` |
| F5 | The step 5 integration test fails locally on its last assertion: the bytes stored in R2 start with `123, 34, 108` (decoded JSON) and the bytes served by the MSW mock with `31, 139, 8` (gzip). The key and the single object in R2 were correct; the unit test passes 5/5 (vitest 5.0.5, Node 25.9.0, `time` 1.725 s) | Step 6 · local run 2026-10-20 |
| F6 | Diagnosis 1, MSW: a gzip body served with `Content-Encoding: gzip` reaches the Worker decoded (533 bytes, starts `123, 34, 108`) with `encodeResponseBody: 'manual'` and without it; the same body served without `Content-Encoding` reaches it unchanged (192 bytes, `31, 139, 8`). MSW decodes by the header and ignores `manual` | Step 6 · local run 2026-10-20, temporary `diag/*.diag.js` (not committed) |
| F7 | Diagnosis 2, Miniflare `outboundService` (accepted by the `miniflare` option of `cloudflareTest`): the gzip body (220 bytes, `31, 139, 8`) reaches the Worker unchanged in all three variants: with `Content-Encoding` and `manual`, with `Content-Encoding` and without `manual`, and without `Content-Encoding`. It keeps the bytes but does not decode in default mode either, so it cannot tell whether `manual` is honoured | Step 6 · local run 2026-10-20, temporary `diag/*.diag.js` (not committed) |
| F8 | Corrects the Worker test tool matrix C (step 1), which names `@msw/cloudflare` as the documented mechanism for the outbound mock: for a test that asserts unchanged gzip bytes, MSW is replaced by the `outboundService` interception, with F6 and F7 as evidence. The matrix scores are not rewritten | Step 6 · F6, F7 |
| F9 | Local result of the Worker PoC after the change (F8), Node v25.9.0: unit test 5 passed, integration test 1 passed in `workerd` without a Cloudflare account; vitest 523 ms, `time` 1.260 s total. `npm install` warns EBADENGINE: `vitest@5.0.5` requires Node `^22.12.0 \|\| ^24.0.0 \|\| >=26.0.0`, and 25.9.0 is outside that range | Step 6 · local run 2026-10-20 |
| F10 | `poc-worker` passes in CI on the `pull_request` run of commit `44a8f0d` (event `pull_request`, shown on the run page): job 13 s, `poc-spark` job 49 s, whole workflow 52 s as reported by the owner; run <https://github.com/markciano/bikesharing/actions/runs/39342670910>. The Gate of step 6 passes: the integration test runs in `workerd` without a Cloudflare account locally (F9) and in CI | Step 6 · owner report 2026-10-20 |
| F11 | Local result of the Python PoC with Python 3.14.4, pytest 9.1.1 and pytest-cov 7.1.0: 26 passed (11 integration, 15 unit), `time` 0.559 s total, pytest 0.05 s. The consumer test passed for the 5 valid and 4 invalid contract vectors read by relative path | Step 8 · owner report 2026-10-20 |
| F12 | `pip freeze` of the Python PoC resolves 7 packages: `pytest` 9.1.1 and `pytest-cov` 7.1.0 plus `coverage`, `iniconfig`, `packaging`, `pluggy` and `Pygments`. The freeze was committed apart from the PoC code (`1c155f3`, `69c6498`) | Step 8 · `python/requirements.txt`, `git log` |
| F13 | `pytest --cov` on the command line overrides `--cov=poc` from `addopts`, so the coverage table includes the test files (TOTAL 120 statements, 100%) instead of only `poc/` (25 statements, 0 missed). The 100% is the same on `poc/`, but the total is not that of the logic | Step 8 · owner report 2026-10-20 |
| F14 | `poc-python` passes in CI on the `pull_request` run: job 12 s, `poc-worker` 15 s, `poc-spark` 39 s; whole workflow 42 s as GitHub shows it, the three jobs green; run <https://github.com/markciano/bikesharing/actions/runs/39393325460/job/118529857966?pr=6>. Against criterion 3, 42 s is far below 10 min | Step 8 · owner report 2026-10-20 |
| F15 | Mutation P1 (`p1-python.patch`: `>` to `>=` in `find_stale`): locally only `test_find_stale_keeps_station_exactly_at_max_age` failed, as the patch header predicts. Red `pull_request` run <https://github.com/markciano/bikesharing/actions/runs/39397024368>; green after the revert <https://github.com/markciano/bikesharing/actions/runs/39397370983> | Step 10 · owner report 2026-10-20 |
| F16 | Mutation P2 (`p2-spark.patch`: `/` to `*` in `add_occupancy`): locally `test_add_occupancy_divides_bikes_by_capacity` failed. Red `pull_request` run <https://github.com/markciano/bikesharing/actions/runs/39398939405>; green after the revert <https://github.com/markciano/bikesharing/actions/runs/39399211902> | Step 10 · owner report 2026-10-20 |
| F17 | Mutation P3 (`p3-worker.patch`: key prefix `raw/` to `bronze/` in `objectKey`): locally 6 of 6 Worker tests failed: the 5 `objectKey` tests of `test/unit/contract.test.js` (one per valid vector) and `stores the served gzip bytes unchanged at the contract key` in `test/integration/scheduled.test.js`, run in `workerd`. Red `pull_request` run <https://github.com/markciano/bikesharing/actions/runs/39399487844>; green after the revert <https://github.com/markciano/bikesharing/actions/runs/39399989457> | Step 10 · owner report 2026-10-20 |
| F18 | Mutation P4 (`p4-contract.patch`: date folder `YYYY/MM/DD` in the 5 valid vectors) failed on both sides. Consumer: the owner reported `test_parse_key_accepts_every_valid_contract_vector[midday capture]` for Python (only that case was reported, not the full list). Producer: the 5 `objectKey` tests of `test/unit/contract.test.js` failed, and also the integration test `stores the served gzip bytes unchanged at the contract key`, which reads `vectors.valid[0].key`. Red `pull_request` run <https://github.com/markciano/bikesharing/actions/runs/39400503320>; green after the revert <https://github.com/markciano/bikesharing/actions/runs/39400596333> | Step 10 · owner report 2026-10-20 |

### Analysis (step 11)

Findings drawn from steps 2–10 and from paper. Numbering continues from the Findings log.

#### Q1 — rules of `.claude/rules/python.md` › Testing

| F | Rule | Verdict | Reason · standard | Evidence |
|---|---|---|---|---|
| F19 | Follow the test pyramid | Holds | Many fast unit tests, fewer slower integration tests: feedback cost grows with the level · test pyramid ([Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)) | PoC: P1 15 unit, 11 integration in 0.559 s (F11); Spark shows the cost of a heavier level (F3) |
| F20 | Every requirement and "Done when" covered at the lowest level that can verify it | Holds | Traceability from spec to test; lower levels are cheaper and point at the fault · test pyramid ("push tests down") | Paper: the spike has no design with "Done when" |
| F21 | Tests verify observable behaviour, not implementation | Holds | Tests that assert outputs survive refactoring and still catch faults · Practical Test Pyramid; Beck, *TDD by Example* | PoC: every mutation was caught by tests asserting outputs only (F15–F18) |
| F22 | Unit tests first (TDD: red, green, refactor) | Holds | The failing test proves it can fail before the code exists · Beck, *TDD by Example* | PoC: `fd6a830` adds only tests and `conftest.py`, `1c155f3` the code; the red by import error is the valid first red (Decision log) |
| F23 | Arrange–Act–Assert; one concept per test; no shared state or order dependency | Holds | A failing test names one cause; independent tests run in any order · AAA (Bill Wake), Meszaros, *xUnit Test Patterns* | PoC: P1 and P2 mutations each failed only the tests of the changed concept (F15, F16) |
| F24 | pytest; `pytest` runs all, `pytest tests/<level>` one level; coverage reported, never enforced | Corrected | Tool and threshold hold (matrix A; coverage is a tool to find untested code, not a target: [TestCoverage](https://martinfowler.com/bliki/TestCoverage.html)). Correction: the coverage source is set in `[tool.coverage.run] source` ([coverage.py config](https://coverage.readthedocs.io/en/latest/config.html)), not only in `addopts`, because a bare `--cov` on the command line overrides it | PoC: F11; F13 |
| F25 | Levels are folders: `tests/unit/` (mirrors `src/`), `tests/integration/`, `tests/e2e/` | Holds | Folder per level lets each level run alone (F24) and in its CI layer · [pytest good practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html) | PoC: P1 `unit/` and `integration/`; `e2e/` paper only |
| F26 | Naming: `test_<module>.py`; `test_<behaviour>_<condition>` | Holds | A failing test name reads as the broken specification · pytest discovery conventions (pytest good practices) | PoC: F15 failure name `test_find_stale_keeps_station_exactly_at_max_age` |
| F27 | Shared fixtures in `conftest.py`, function-scoped by default | Corrected | Function scope keeps tests independent (F23). Correction: an expensive, immutable resource such as a SparkSession is session-scoped, with the reason in the fixture · [pytest fixture scopes](https://docs.pytest.org/en/stable/how-to/fixtures.html), [Testing PySpark](https://spark.apache.org/docs/latest/api/python/getting_started/testing_pyspark.html) | PoC: step 2 session fixture; one Spark test costs 34.66 s with start-up (F3) |
| F28 | No test touches the network; recorded fixtures (ADR-0009); edge cases by hand | Holds | Hermetic tests are deterministic and run without credentials · *Software Engineering at Google*, ch. 14 (hermetic tests). The same holds for JS: the Worker simulates the source with Miniflare `outboundService` (Decision log 2026-10-20) | PoC: P1, P3 and P4 run offline in CI (F10, F14); the spike used synthetic fixtures by Decision log, recorded fixtures are paper only |
| F29 | Code that uses the current time receives it as a parameter; tests pass a fixed UTC time | Holds | A fixed clock makes boundary cases testable and repeatable · dependency injection, functional core, imperative shell | PoC: `find_stale` takes `now`; the boundary mutation was caught only thanks to a fixed time (F15) |
| F30 | Data quality checks on the data belong to the pipeline design | Holds | Tests check code against fixed inputs before merge; data quality checks check real data at run time | Paper |

#### Q2 — Spark

| F | Finding | Evidence |
|---|---|---|
| F31 | Spark transformations are written as functions DataFrame → DataFrame and tested at unit level on a session-scoped local SparkSession (`local[1]`, UI disabled), compared with `assertDataFrameEqual`. They run with Python 3.14, PySpark 4.2.0 and Java 17 locally and in CI | F1, F2, F16, F27 |
| F32 | Cost: one trivial test takes 34.66 s locally with start-up included, and the `poc-spark` job takes 39–56 s in CI, the slowest job. The marginal cost per extra test was not measured (only one test) | F3, F10, F14 |

#### Q3 — Worker

| F | Finding | Evidence |
|---|---|---|
| F33 | The Worker is tested with `@cloudflare/vitest-plugin`, without a Cloudflare account: pure functions (functional core) as unit tests, the `scheduled` handler as an integration test in `workerd` with an in-memory R2 binding and the source simulated by Miniflare `outboundService`. Local 1.26 s; CI job 13–15 s | F8, F9, F10, F14, F17 |
| F34 | Limit: no local mock tells whether `encodeResponseBody: 'manual'` is honoured; MSW decodes by header, `outboundService` decodes in no mode. That behaviour stays covered by the V4 capture (ADR-0011) and, in future, by a post-deploy smoke test | F6, F7 |

#### Q4 — Contracts between components

| F | Finding | Evidence |
|---|---|---|
| F35 | Format/behaviour contracts (keys, naming, encoding) are shared golden test vectors in one JSON file, read by relative path by the producer tests (JS) and the consumer tests (Python). A change that the valid data stops meeting fails both sides | Matrix D; F11, F18 |
| F36 | Data-shape contracts (silver, gold) use a schema (ODCS). Justified on paper only: to Not verified, risk "the schema form is not proven in this project", mitigation "validated in the first design that defines a data-shape contract" | Matrix D; Decision log |

#### Q5 — CI layers

| F | Finding | Evidence |
|---|---|---|
| F37 | Local layer: `/implement` runs the unit and integration tests of the touched component before proposing each commit. Measured: Python 0.559 s, Worker 1.26 s, Spark 34.86 s. A Git `pre-commit` hook is not adopted (Decision log, YAGNI); Claude Code hooks are assessed in Q6 | F3, F9, F11 |
| F38 | Push to a feature branch: no CI run. Once a PR is open, each push triggers its `pull_request` run (`synchronize`); a `push` trigger on the branch doubles every run, as observed in step 3. Before a PR exists the local layer applies; a draft PR opened early gives CI from the first push · [events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) | F1; Decision log (amended 2026-10-20) |
| F39 | PR pre-merge (the gate): every automated level of every affected component, plus `docs`. Measured wall-clock of the `pull_request` workflow: 42–52 s, far below the 10 min of criterion 3; no test needs to move to another layer · [Continuous Integration](https://martinfowler.com/articles/continuousIntegration.html) (ten-minute build) | F10, F14 |
| F40 | Post-merge on `main`: the same workflow on `push` to `main`, which checks the merged result. Post-deploy smoke tests (e.g. F34) belong to this layer once deployment exists; paper only | `ci.yml`; F34 |
| F41 | Checks against live sources run in a separate `schedule` workflow, outside the PR gate and not required by the ruleset, because a source outage must not block a merge. Paper only | Shared behaviour 3 |
| F42 | Proposed change to ADR-0013: record the four layers (F37–F41) and enable "require branches to be up to date before merging": the PR checks then run on exactly what `main` will contain. Cost: one re-run of under 1 min after a rebase, and with one owner `main` rarely moves under an open PR · [about protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) | F10, F14; ADR-0013 |
| F49 | The `docs` component has no PoC. Its CI job runs `DavidAnson/markdownlint-cli2-action@v24` on `docs/**/*.md`, on every `pull_request` and on `push` to `main`, with `.markdownlint-cli2.yaml` at the repo root (the standard location for tool config). The glob leaves out `CLAUDE.md`, `.claude/**` and the READMEs in `spikes/`. There is no local layer today: Claude cannot run the lint, since `markdownlint-cli2` is not installed and npx cancels the download without permission | `ci.yml`; `.markdownlint-cli2.yaml`; step 11 local attempt 2026-10-20 |

#### Observe only

| F | Finding | Evidence |
|---|---|---|
| F43 | Durations. Local: Python 0.559 s, Worker 1.26 s, Spark 34.86 s. CI jobs: `poc-python` 12 s, `poc-worker` 13–15 s, `poc-spark` 39–56 s. Whole `pull_request` workflow: 42–52 s | F3, F9, F10, F11, F14 |
| F44 | The Worker fetch mock does not reproduce `encodeResponseBody: 'manual'` (answered by F34) | F6, F7 |

#### Exit criteria so far

| F | Criterion | Result | Evidence |
|---|---|---|---|
| F45 | Tests detect faults | Met: four red and four green `pull_request` runs; P4 failed on both sides | F15–F18 |
| F46 | Reproducible from scratch | Met in CI from a clean runner with pinned versions (frozen `requirements.txt`, `package-lock.json`, exact `package.json`). Caveat: the local Node 25.9.0 is outside the `vitest` range (P1) | F1, F4, F9, F10, F12, F14 |
| F47 | Feedback time | Met: 42–52 s against 10 min | F10, F14 |
| F48 | Traceability | Met so far: matrices A–D, with matrix C corrected by F8; each Q1 rule has a reason and a standard (F19–F30). Pending the owner's verification in step 12 | Matrices A–D; F19–F30 |

### Testing model

Synthesis of the findings (step 12): what each component design applies. Its final destination is decided in step 13. "Paper" marks a statement with no PoC behind it.

#### Python (`src/bikesharing/`, non-Spark)

1. **When:** unit tests are written before the code (red, green, refactor), one or more for every requirement and "Done when" condition, at the lowest level that can verify it (F20, F22).
2. **Type:** unit for logic; integration when behaviour crosses a file or format boundary (file fixture → records) (F11, F25); contract, consumer side, when the code reads another component's output (F35); e2e on paper (F25).
3. **Format:** files `test_<module>.py`, functions `test_<behaviour>_<condition>` (F26); Arrange–Act–Assert, one concept per test, no shared state (F23); assertions on outputs, not internals (F21); shared fixtures in `conftest.py`, function-scoped (F27); current time passed as a parameter, fixed UTC in tests (F29); no network, recorded fixtures (ADR-0009) and edge cases by hand (F28); pytest, coverage reported without threshold, source set in `[tool.coverage.run] source` (F24, P2).
4. **Where:** `tests/unit/` mirroring `src/`, `tests/integration/`, `tests/e2e/`, `tests/fixtures/`; one `conftest.py` in `tests/`, plus one per level when needed (F25, F27).
5. **Runs:** locally before each commit via `/implement`, under 1 s (F37); every level in the PR run (F39) and again in the `main` run (F40).

#### Spark (transformations in `src/bikesharing/`)

1. **When:** as Python; each transformation is written as a function DataFrame → DataFrame so it can be tested alone (F31).
2. **Type:** unit, on a local SparkSession (F31). Integration of a whole Spark job: not covered by the spike.
3. **Format:** as Python, plus: one session-scoped SparkSession (`local[1]`, UI disabled) in `conftest.py`, the documented exception to function scope (F27); input DataFrames built inside the test; comparison with `pyspark.testing.assertDataFrameEqual` (F2, F31).
4. **Where:** the Python tree (`tests/unit/`). Whether Spark tests get their own folder or CI job, to keep Java and PySpark out of the Python job, is decided in the pipeline design (F32).
5. **Runs:** locally before each commit, about 35 s (F37); in the PR run, where it is the slowest job at 39–56 s (F32, F39), and in the `main` run (F40). It is the first candidate to move under the rule in (6).

#### Worker (`collector/`, JS)

1. **When:** tests before code, as in Python. TDD was shown only in Python (F22); the Worker follows the same rule on paper.
2. **Type:** unit for the functional core (pure functions such as `objectKey`); integration for the `scheduled` handler in `workerd`, with an in-memory R2 binding and the source simulated by Miniflare `outboundService` (F33); contract, producer side, on the same vectors (F35); post-deploy smoke test for `encodeResponseBody: 'manual'`, on paper (F34, P4).
3. **Format:** `@cloudflare/vitest-plugin` with `vitest` (matrix C, F8); Arrange–Act–Assert, one concept per test, assertions on outputs (F21, F23); no network: `outboundService`, not MSW, when bytes must stay unchanged (F6–F8, F28); the oracle does not travel through the mocked path (Decision log 2026-10-20). Naming follows the common JS standard: files `<module>.test.js`, matched by the default `include` pattern of Vitest ([Vitest config](https://vitest.dev/config/#include)); test names are plain sentences stating behaviour and condition, the JS form of `test_<behaviour>_<condition>` (F26), as the PoC did.
4. **Where:** `test/unit/` and `test/integration/` inside the component; Node pinned in `package.json` `engines` within the range the test tools support (F9, P1).
5. **Runs:** locally before each commit, about 1.3 s (F37); PR run 13–15 s (F39); `main` run (F40); smoke test after deploy (F40, paper).

#### Contract (between components)

1. **When:** as soon as a contract between two components is defined, before either side is written (Decision log, step split).
2. **Type:** contract tests. Format/behaviour contracts (keys, naming, encoding): shared golden test vectors (F35). Data-shape contracts (silver, gold): ODCS schema, on paper (F36).
3. **Format:** one JSON file with `valid` cases (input → expected output) and `invalid` cases, each breaking exactly one rule with its `reason`; binary payloads are built in memory by the tests (Shared behaviour 5). A change to the contract makes the valid data stop meeting it; it never relaxes it (Shared behaviour 2).
4. **Where:** one shared file, read by relative path by the producer tests and the consumer tests (F35); inside the path filters of every component job that reads it (P3).
5. **Runs:** inside the test runs of both sides, so a contract change fails both (F18, F35).

#### Docs (`docs/`)

1. **When:** no test is written; every Markdown change in `docs/` is linted (F49).
2. **Type:** static check (markdownlint), not a test level (F49).
3. **Format:** the rules in `.markdownlint-cli2.yaml` and the "write them right the first time" list in `.claude/rules/docs.md` (F49).
4. **Where:** config at the repo root; scope `docs/**/*.md`, which leaves out `CLAUDE.md`, `.claude/**` and the READMEs in `spikes/` (F49).
5. **Runs:** PR run and `main` run (F49). No local layer today (F49); its local lint is placed in step 13 and completed in step 15 (Decision log).

#### CI flow (project)

1. Branch `tNNN-short-title` from an up-to-date `main` (ADR-0013); before each commit, `/implement` runs the tests of the touched component (F37).
2. First push opens a draft PR. No CI on `push` to feature branches: the PR's `pull_request` run fires on every push (F38).
3. The `pull_request` run is the gate: every automated level of every affected component, contract tests and `docs` lint, light, ≤ 10 min wall-clock (F39, F47). Proposed: "require branches to be up to date before merging" (F42).
4. Rebase merge (ADR-0013).
5. The `push` run on `main` repeats the workflow on the merged result; it may hold heavier tests, and later post-deploy smoke tests (F40).
6. A scheduled run holds checks against live sources, outside the gate and not required (F41, paper).

Rule for moving tests (criterion 3, paper): when the `pull_request` run passes 10 min wall-clock, the slowest group of tests moves from the PR run to the `main` run, starting with the heaviest job (today Spark, F32). It stays in the local layer, and a red `main` run is fixed at once in a new PR. Today the run takes 42–52 s, so nothing moves (F39).

### Placement map (step 13)

One row per convention from step 11 (F19–F42, F49), plus the items the Decision log adds (testing model, docs local lint, CI recipe, ADR-0009 citation, hooks). F43–F48 are measurements and exit-criteria results, not conventions: they have no destination here and feed 5. Conclusion. Production inputs get their destination at Conclusion. 👉 marks a judgement call for the owner in step 14. ADR changes are follow-ups of step 16, not edits of step 15.

#### Destinations

Criterion: progressive disclosure. Each convention goes to the narrowest place that is loaded when it is needed, and has one copy.

| Destination | When Claude loads it | Source |
|---|---|---|
| `CLAUDE.md` | Always, at launch; files it `@import`s also load at launch | [Memory](https://code.claude.com/docs/en/memory.md) |
| `.claude/rules/<name>.md` with `paths:` | On matching path: when Read, Write or Edit touches a matching file; a rule without `paths:` loads always | [Memory](https://code.claude.com/docs/en/memory.md) |
| Skill (`SKILL.md`, its template and supporting files) | On skill invocation; only the description is always in context; supporting files when needed | [Skills](https://code.claude.com/docs/en/skills.md) |
| Hook in `.claude/settings.json` | Enforced by the harness: runs at its event whatever the model decides | [Hooks guide](https://code.claude.com/docs/en/hooks-guide.md) |
| Permission in `.claude/settings.json` | Enforced by the harness: deny, then ask, then allow | [Permissions](https://code.claude.com/docs/en/permissions.md) |
| ADR or another doc in `docs/` | Never automatically; read on demand when a rule or skill links it | — |

New files proposed (names for the owner's approval): `docs/testing-strategy.md`; `.claude/rules/testing.md` with `paths:` `src/**`, `tests/**`, `collector/**`; `.claude/rules/collector.md` with `paths:` `collector/**`; `.claude/rules/ci.md` with `paths:` `.github/workflows/**`.

#### Map

| # | Convention | Destination | Loaded | Reason |
|---|---|---|---|---|
| M1 | Testing model as a whole: answers (1)–(5) per component and the CI flow, with reasons and findings | `docs/testing-strategy.md` (new) 👉 | On demand, linked from the rules | Owner-facing single source of truth; the rules hold the condensed imperative form and each line links its section (spec-driven: the doc leads, the rules derive). Not `@import`ed, since imports load at launch in every session. Rejected: rules only (no reasons for the owner); spike only (frozen at Conclusion). Risk: doc and rules drift; mitigation: the same-commit rule of `CLAUDE.md` and the section links. Format (owner, step 14): text, one `####` heading per component with items (1)–(5), so a rule links to one section and only that section is read |
| M2 | Language-neutral principles: pyramid (F19), "Done when" at the lowest level (F20), observable behaviour (F21), TDD (F22), AAA and independence (F23), hermetic tests (F28), injected time (F29), data quality outside the suite (F30) | `.claude/rules/testing.md` (new) 👉 | On matching path | They hold for Python and JS alike; one copy for both instead of one per language rule. They move out of `python.md` |
| M3 | pytest specifics: runner and coverage with `[tool.coverage.run] source` (F24), level folders (F25), naming (F26), fixture scope with the session-scoped exception (F27) | `.claude/rules/python.md` › Testing (modified) | On matching path `src/**`, `tests/**` | Tool-specific to Python; F24 and F27 are the corrections of Q1 |
| M4 | Spark: transformations as DataFrame → DataFrame, unit-tested on a session-scoped local SparkSession with `assertDataFrameEqual` (F31) | `.claude/rules/python.md` › Testing › Spark (modified) | On matching path | Spark code lives in `src/bikesharing/`, already in scope |
| M5 | Own folder or CI job for Spark tests (F32) | None: decided in the pipeline design (testing model, Spark (4)) | — | An open choice of that design, not a convention |
| M6 | Worker: `@cloudflare/vitest-plugin`; unit tests on the functional core, integration of the `scheduled` handler in `workerd` with in-memory R2 and Miniflare `outboundService`; `<module>.test.js` and sentence names; `test/unit/`, `test/integration/`; Node pinned in `engines` (F33) | `.claude/rules/collector.md` (new) | On matching path `collector/**` | JS-specific; the `python.md` scope does not reach `collector/` |
| M7 | Limit: no local mock verifies `encodeResponseBody: 'manual'` (F34) | `.claude/rules/collector.md` (new) | On matching path | Prevents a mock-based test for what no mock can check; the smoke test itself is P4 |
| M8 | How to write and use contract vectors: `valid` and `invalid` cases with `reason`, read by relative path by both sides, a change never relaxes the contract (F35, part) | `.claude/rules/testing.md` (new) | On matching path | Producer and consumer both apply it. TODO: add the shared contract folder to `paths:` when a design defines it |
| M9 | Choice of contract form: vectors for format/behaviour contracts, ODCS schema for data-shape contracts (F35, part; F36) | New ADR (follow-up, step 16) | On demand | A cross-cutting decision for every pair of components (`.claude/rules/docs.md`: an ADR records why) |
| M10 | Local layer: before proposing each commit, run the unit and integration tests of the touched component (F37) | `/implement` `SKILL.md` (modified) | On skill invocation | A procedure of the build session; the skill body loads only when used |
| M11 | Claude Code hooks for the local test layer (Decision log) | Not adopted | — | A `PreToolUse` hook only intercepts commands Claude runs, and the owner makes every commit; `PostToolUse` or `Stop` would run Spark (~35 s, F37) on every edit or turn. M10 is enough (YAGNI) |
| M12 | Draft PR at the first push; no CI on `push` to feature branches (F38) | `CLAUDE.md` › Branches, PRs and CI (one line) | Always | Applies to every session that ends in commits, next to the GitHub Flow lines already there; its reason goes with M13 |
| M13 | CI layers (F39–F41) and the rule for moving tests from the PR run to the `main` run | ADR-0013 amendment (follow-up, step 16) | On demand | ADR-0013 already sets the CI; layers are a cross-cutting why |
| M14 | "Require branches to be up to date before merging" (F42) | ADR-0013 amendment (same follow-up); ruleset change by the owner | Enforced by the GitHub ruleset | Operational action, done by the owner (`CLAUDE.md`) |
| M15 | Docs lint in CI: `markdownlint-cli2` on `docs/**/*.md`, config at the root (F49) | Unchanged: `ci.yml` job `docs`, `.markdownlint-cli2.yaml`, list in `.claude/rules/docs.md` | Enforced by CI; on matching path `docs/**` | Already in place |
| M16 | Docs local lint, missing today (Decision log, amends step 13) | Hook `PostToolUse` on Edit and Write of `docs/**/*.md` in `.claude/settings.json`, running `markdownlint-cli2` on the edited file at the version that `markdownlint-cli2-action@v24` uses 👉 | Enforced by the harness | Hooks make an action always happen instead of relying on the model; per-file lint is fast, unlike tests (M11); same scope as the CI job. Version, command and any permission are completed in step 15. Rejected: a line in `docs.md` plus an allow rule `Bash(npx markdownlint-cli2@<version> *)`, which relies on Claude choosing to run it |
| M17 | CI job recipe: job skeleton, runtime pinned via `setup-*`, `working-directory` per component, one test command, dependencies from the lockfile or frozen `requirements.txt`, the `ci-passed` aggregator and the switch of the ruleset's required check (TODO in `ci.yml`, which stays). Evidence: the spike's `poc-*` jobs | `.claude/rules/ci.md` (new) 👉 | On matching path `.github/workflows/**` | Loads exactly when a step edits a workflow; a design session touches no workflow, so the recipe does not load there |
| M18 | A design that adds a component plans its CI job in its File layout | `/design` `template.md` › File layout comment (one line) | On skill invocation | The trigger in the design, without carrying the recipe (M17) into every design session |
| M19 | Spike code: no test suite, targeted checks only | Unchanged: `.claude/rules/spikes.md` | On matching path `spikes/**` | `testing.md` does not include `spikes/**` |
| M20 | ADR-0009 cites "CLAUDE.md › Testing" (TODO in Approach) | ADR-0009, citation to `docs/testing-strategy.md` (follow-up, step 16, own commit) | — | The owner-facing doc is the stable home; rule files may move |

Consequential edits in step 15, not conventions: `CLAUDE.md` › Project structure lists `docs/testing-strategy.md`; `.claude/rules/docs.md` names the testing strategy as a doc type. Related and parked: T023 (scope of `.claude/rules/docs.md`), which does not change this map.

### Production inputs

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | Pin the Node version of a Worker to a release inside the range its test tools support (here `vitest` 5.0.5: 22.12, 24 or ≥ 26), not to the version installed on the owner's machine | Step 6 · F9 | |
| P2 | Set the coverage source in `[tool.coverage.run] source`, so the CI command cannot widen the report to the test files | Step 11 · F13, F24 | |
| P3 | The shared contract file must be inside the path filters of every component job that reads it, so a contract change runs the tests of both sides | Step 11 · F35, ADR-0013 | |
| P4 | A post-deploy smoke test that checks the Worker stores gzip bytes unchanged (`encodeResponseBody: 'manual'`) | Step 11 · F34 | |

## 5. Conclusion

Observed window: —

### Answers

### Exit criteria

### Verdict

### Not verified

### Follow-ups

## Sources

- [Claude Code: Memory (CLAUDE.md, imports, rules)](https://code.claude.com/docs/en/memory.md), read 2026-10-20
- [Claude Code: Skills](https://code.claude.com/docs/en/skills.md), read 2026-10-20
- [Claude Code: Hooks guide](https://code.claude.com/docs/en/hooks-guide.md) and [Hooks reference](https://code.claude.com/docs/en/hooks), read 2026-10-20
- [Claude Code: Permissions](https://code.claude.com/docs/en/permissions.md), read 2026-10-20
