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
