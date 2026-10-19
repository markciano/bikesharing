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
