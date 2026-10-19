"""Shared local SparkSession for the Spark PoC tests (spike s008, P2)."""

import pytest
from pyspark.sql import SparkSession


# Session scope on purpose, against the function-scope rule in
# .claude/rules/python.md: starting the JVM and the session costs seconds, so
# it is paid once per run. Tests stay isolated because each builds its own
# DataFrame and nothing is written to the session. Evidence for Q1 and Q2.
@pytest.fixture(scope="session")
def spark():
    session = (
        SparkSession.builder.master("local[1]")
        .appName("poc-spark")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield session
    session.stop()
