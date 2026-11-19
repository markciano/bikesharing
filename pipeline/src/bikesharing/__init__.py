"""Pipeline of the Barcelona bike sharing project.

Reads the captured bronze feeds, builds the silver and gold tables and
publishes the file the public page reads. The package splits into a functional
core of pure decisions and an imperative shell that does the I/O (ADR-0046,
Functional core and imperative shell for the pipeline).
"""
