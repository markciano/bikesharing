# Testing conventions (spike s008, task T020)

Throwaway proofs of concept for the testing conventions of each component.
Question, method and results: [s008](../../docs/spikes/s008-testing-conventions.md).

## P2 Spark

One PySpark transformation tested on a shared local SparkSession. Needs Python 3.14 and Java 17.

```bash
cd spikes/testing-conventions/spark
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```
