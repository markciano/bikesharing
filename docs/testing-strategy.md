# Testing strategy

Single source of truth for how this project tests. Evidence: spike [s008](spikes/s008-testing-conventions.md) (F-numbers cite its Findings). The imperative form of each section lives in `.claude/rules/`, which links back here; when they differ, this document leads. The spike is an audit trail for the owner: implementation sessions do not read it.

## Testing model

Each component design applies the five answers below. "Paper" marks a statement with no proof of concept behind it.

1. When a test is written.
2. Which type.
3. Format.
4. Where it lives.
5. Where and when it runs.

### Components

#### Python (`src/bikesharing/`, non-Spark)

1. **When:** unit tests are written before the code (red, green, refactor), one or more for every requirement and "Done when" condition, at the lowest level that can verify it (F20, F22).
2. **Type:** unit for logic; integration when behaviour crosses a file or format boundary (file fixture → records) (F11, F25); contract, consumer side, when the code reads another component's output (F35); e2e on paper (F25).
3. **Format:** files `test_<module>.py`, functions `test_<behaviour>_<condition>` (F26); Arrange–Act–Assert, one concept per test, no shared state (F23); assertions on outputs, not internals (F21); shared fixtures in `conftest.py`, function-scoped (F27); current time passed as a parameter, fixed UTC in tests (F29); no network, recorded fixtures (ADR-0009) and edge cases by hand (F28); pytest, coverage reported without threshold, source set in `[tool.coverage.run] source` (F24).
4. **Where:** `tests/unit/` mirroring `src/`, `tests/integration/`, `tests/e2e/`, `tests/fixtures/`; one `conftest.py` in `tests/`, plus one per level when needed (F25, F27).
5. **Runs:** locally before each commit via `/implement`, under 1 s (F37); every level in the PR run (F39) and again in the `main` run (F40).

#### Spark (transformations in `src/bikesharing/`)

1. **When:** as Python; each transformation is written as a function DataFrame → DataFrame so it can be tested alone (F31).
2. **Type:** unit, on a local SparkSession (F31). Integration of a whole Spark job: not covered by the spike.
3. **Format:** as Python, plus: one session-scoped SparkSession (`local[1]`, UI disabled) in `conftest.py`, the documented exception to function scope (F27); input DataFrames built inside the test; comparison with `pyspark.testing.assertDataFrameEqual` (F2, F31).
4. **Where:** the Python tree (`tests/unit/`). Whether Spark tests get their own folder or CI job, to keep Java and PySpark out of the Python job, is decided in the pipeline design (F32).
5. **Runs:** locally before each commit, about 35 s (F37); in the PR run, where it is the slowest job at 39–56 s (F32, F39), and in the `main` run (F40). It is the first candidate to move under the rule in [Moving tests](#moving-tests).

#### JS (`collector/`)

TODO: when the collector design fixes the layout (`collector/{bicing,ambici}`, and sources in other languages such as `collector/<source>_python`), rename this section's paths and scope it to the JS collectors; a Python collector follows the Python section.

1. **When:** tests before code, as in Python. TDD was shown only in Python (F22); the Worker follows the same rule on paper.
2. **Type:** unit for the functional core (pure functions such as `objectKey`); integration for the `scheduled` handler in `workerd`, with an in-memory R2 binding and the source simulated by Miniflare `outboundService` (F33); contract, producer side, on the same vectors (F35); post-deploy smoke test for `encodeResponseBody: 'manual'`, on paper (F34).
3. **Format:** `@cloudflare/vitest-plugin` with `vitest` (F8); Arrange–Act–Assert, one concept per test, assertions on outputs (F21, F23); no network: `outboundService`, not MSW, when bytes must stay unchanged (F6–F8, F28); the oracle does not travel through the mocked path. Files `<module>.test.js`, matched by the default `include` pattern of [Vitest](https://vitest.dev/config/#include); test names are plain sentences stating behaviour and condition, the JS form of `test_<behaviour>_<condition>` (F26).
4. **Where:** `test/unit/` and `test/integration/` inside the component; Node pinned in `package.json` `engines` within the range the test tools support (F9).
5. **Runs:** locally before each commit, about 1.3 s (F37); PR run 13–15 s (F39); `main` run (F40); smoke test after deploy (F40, paper).

#### Contract (between components)

1. **When:** as soon as a contract between two components is defined, before either side is written.
2. **Type:** contract tests. Format/behaviour contracts (keys, naming, encoding): shared golden test vectors (F35). Data-shape contracts (silver, gold): ODCS schema, on paper (F36).
3. **Format:** one JSON file with `valid` cases (input → expected output) and `invalid` cases, each breaking exactly one rule with its `reason`; binary payloads are built in memory by the tests. A change to the contract makes the valid data stop meeting it; it never relaxes it.
4. **Where:** one shared file, read by relative path by the producer tests and the consumer tests (F35); inside the path filters of every component job that reads it.
5. **Runs:** inside the test runs of both sides, so a contract change fails both (F18, F35).

#### Docs (`docs/`)

1. **When:** no test is written; every Markdown change in `docs/` is linted (F49).
2. **Type:** static check (markdownlint), not a test level (F49).
3. **Format:** the rules in `.markdownlint-cli2.yaml` and the "write them right the first time" list in `.claude/rules/docs.md` (F49).
4. **Where:** config at the repo root; scope `docs/**/*.md`, which leaves out `CLAUDE.md`, `.claude/**` and the READMEs in `spikes/` (F49).
5. **Runs:** PR run and `main` run (F49). No local layer today.

## CI flow

1. Branch `tNNN-short-title` from an up-to-date `main` (ADR-0013); before each commit, `/implement` runs the tests of the touched component (F37).
2. First push opens a draft PR. No CI on `push` to feature branches: the PR's `pull_request` run fires on every push (F38).
3. The `pull_request` run is the gate: every automated level of every affected component, contract tests and `docs` lint, light, at most 10 min wall-clock (F39, F47). Proposed: "require branches to be up to date before merging" (F42).
4. Rebase merge (ADR-0013).
5. The `push` run on `main` repeats the workflow on the merged result; it may hold heavier tests, and later post-deploy smoke tests (F40).
6. A scheduled run holds checks against live sources, outside the gate and not required (F41, paper).

### Moving tests

When the `pull_request` run passes 10 min wall-clock, the slowest group of tests moves from the PR run to the `main` run, starting with the heaviest job (today Spark, F32). It stays in the local layer, and a red `main` run is fixed at once in a new PR. Today the run takes 42–52 s, so nothing moves (F39).
