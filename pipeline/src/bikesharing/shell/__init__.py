"""Imperative shell: the I/O and the orchestration of a run.

Reads from and writes to R2, runs DuckDB and dbt, publishes the file and sends
the heartbeat, calling the core for every decision.
"""
