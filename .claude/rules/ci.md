---
paths:
  - ".github/workflows/**"
---

# CI workflow rules

Flow and reasons: [testing strategy](../../docs/testing-strategy.md) (CI flow section), ADR-0013 and ADR-0014. The jobs of each component are created in that component's design.

## Job per component

- One job per component in `.github/workflows/ci.yml`, with `defaults.run.working-directory` set to the component folder.
- Pin the runtime with `actions/setup-python`, `actions/setup-node` or `actions/setup-java`; never rely on the runner's default.
- Install dependencies from the lockfile (`npm ci`) or a frozen `requirements.txt` (`pip install -r`).
- Cache dependencies with the `cache:` input of `setup-python` (`pip`) and `setup-node` (`npm`). `setup-java` caches only Maven, Gradle or sbt, so a Spark job installs PySpark through the Python cache.
- One test command per job (`pytest`, `npx vitest run`).
- Set `timeout-minutes: 10` on every job, so a hung test cannot hold the PR for the default 6 hours.
- Keep the `pull_request` run light: at most 10 min wall-clock for the whole workflow. Heavier tests belong to the `push` run on `main`.

```yaml
  <component>:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    defaults:
      run:
        working-directory: <component folder>
    steps:
      - uses: actions/checkout@<version>
      - uses: actions/setup-<runtime>@<version>
        with:
          <runtime>-version: "<pinned version>"
          cache: <pip | npm>
      - run: <install from lockfile>
      - run: <one test command>
```

## Aggregator and required check

- When the second component job is added, add a final job `ci-passed` that `needs` every other job, and switch the ruleset's required check from `docs` to `ci-passed` (ADR-0013). The ruleset change is done by the owner. The TODO in `ci.yml` stays until then.
- If a job uses path filters, the shared contract file must be inside the filters of every job that reads it, so a contract change runs the tests of both sides.
