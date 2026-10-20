# Testing conventions (spike s008, task T020)

Throwaway proofs of concept for the testing conventions of each component.
Question, method and results: [s008](../../docs/spikes/s008-testing-conventions.md).

## Contract

Golden test vectors for the collector contract of ADR-0012 (key, UTC timestamp, gzip payload unchanged), shared by JS and Python.

- `contract/collector-contract.json`: `valid` cases `{source, feed, captured_at, key}` and `invalid` keys, each breaking one rule, with its `reason`.
- `contract/fixtures/station_status.json`: a synthetic GBFS payload; the tests gzip it in memory.
- Read by the producer test in `worker/` and the consumer test in `python/` (loaded by relative path).

## P2 Spark

One PySpark transformation tested on a shared local SparkSession. Needs Python 3.14 and Java 17.

```bash
cd spikes/testing-conventions/spark
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## P3 Worker

A minimal Worker (functional core, imperative shell) tested in `workerd` with `@cloudflare/vitest-plugin`: `objectKey` against the contract vectors, and the `scheduled` handler writing to an in-memory R2 binding with the source fetch mocked. Needs Node 25.9.0; no Cloudflare account.

```bash
cd spikes/testing-conventions/worker
npm install
npm test
```

## P1 Python

A status parser with staleness (time received as a parameter), a bronze-side key parser and a gzip reader, tested with `pytest` at two levels (`tests/unit/`, `tests/integration/`). The integration tests are also the P4 consumer test: they read `contract/collector-contract.json` by relative path. Needs Python 3.14.

```bash
cd spikes/testing-conventions/python
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest --cov
```

Rules of `.claude/rules/python.md` › Testing that this PoC does not exercise ("paper only", judged in Q1):

- `tests/e2e/` level: there is no end-to-end flow in a PoC.
- "Every requirement and Done-when condition is covered": a PoC has no design to trace.
- Recorded fixtures (ADR-0009): the fixtures are hand-written synthetic data (Decision log).
- One `conftest.py` per level: one in `tests/` is enough here.
- Data quality checks stay out of the suite: the PoC has none.

## Mutations

One patch per PoC in `mutations/`, each changing the code under test so that its test must fail (manual mutation testing). Each patch names the expected failing test in its header comment. Apply from the repo root, run the PoC's test command, then revert:

```bash
git apply --check spikes/testing-conventions/mutations/p1-python.patch
git apply spikes/testing-conventions/mutations/p1-python.patch
# run the PoC tests and check that the named test fails
git apply -R spikes/testing-conventions/mutations/p1-python.patch
```

- `p1-python.patch`: staleness boundary in `python/poc/status.py`.
- `p2-spark.patch`: occupancy formula in `spark/poc/occupancy.py`.
- `p3-worker.patch`: key prefix in `worker/src/contract.js`.
- `p4-contract.patch`: date folder format in the valid vectors of `contract/collector-contract.json`; run the Python and Worker tests, both must fail.

Method and CI procedure: Shared behaviour 2 and step 10 of [s008](../../docs/spikes/s008-testing-conventions.md).
