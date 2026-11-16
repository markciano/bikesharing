---
status: Accepted
date: 2026-11-16
---

# Lineage at four levels, with run and code version in every row

## Context and problem statement

When a value on the page or in a table looks wrong, someone must trace it back to the tables, the source fields, the run and the code that produced it, and to the bronze object it comes from.

Each of those questions has a different lifetime. The model's tables and source fields are documented and versioned in Git. A run's events live in its logs, kept for a limited time ([ADR-0036](0036-log-convention-across-components.md)), as is the table history of the storage format. Bronze is kept indefinitely ([ADR-0021](0021-retention-per-layer.md)), and silver and gold rows outlive any log. A question about an old row can no longer be answered from the logs.

## Considered Options

### 1. Four levels, each with the least it needs

Lineage is answered by table, column, run and row, after the levels OpenLineage and Kimball's audit dimension name. Each level uses what already answers it, and adds only what is missing: every silver and gold row carries the ID of the run that wrote it and that run's code version.

- Pros:
  - Every level is answered for as long as the row exists.
  - Two columns per row, with no store of its own to build or keep.
- Cons:
  - A run's detail (what it read and wrote) is lost with its logs; only its ID and code version remain.
  - A silver row's bronze object is derived, not stored.

### 2. A table of runs and full keys in every row

As option 1, plus a table recording every run with its configuration version, and the bronze object's key in every silver row.

- Pros:
  - A run's detail and a row's bronze object are read directly, with no time limit.
- Cons:
  - One more table to write in every run and keep, and a long key in every silver row.

### 3. The run's ID alone in every row

Each row carries only the ID of the run that wrote it; the rest is read from the run's logs.

- Pros:
  - One column per row.
- Cons:
  - Once the logs expire, the code version behind a row is lost.

## Decision Outcome

**Chosen option:** 1. Four levels, each with the least it needs

| Level | Question | Answered by |
|---|---|---|
| Table | Which tables feed which | The model's documentation |
| Column | Which source field a column comes from | The source field dictionary |
| Run | What a run read and wrote, and its outcome | The run's log events |
| Row | Which run and code version wrote a row, and which bronze object it comes from | Run ID and code version in every silver and gold row; the bronze object follows from the row's system, feed and capture instant |

Rationale: rows outlive the logs, so the row carries what must stay answerable with it, the run and the code; everything else is already answered by the documentation, the logs or bronze's indefinite retention, so nothing more is stored.

Why not the others:

- Option 2 stores what the project has no question for once a run's logs expire.
- Option 3 loses the code behind a row after the log retention.

**Scope:** every silver and gold table the pipeline writes. It does not cover bronze, whose objects are named by their capture ([ADR-0020](0020-bronze-as-captured-objects.md)).

### Consequences

#### Positive

- **Lasting answer:** any row names the run and the code that wrote it for as long as it exists.
- **Little to build:** no lineage store or service.
- **Non-repudiation:** every row names the run and the code version that wrote it.

#### Negative

- **Short run detail:** what a run read and wrote is answerable only within the log retention.
- **Derived bronze link:** a row's bronze object depends on bronze keeping its naming by system, feed and capture instant.

## More information

- [d007 › D5](../designs/d007-pipeline-design.md#d5-lineage-at-four-levels); the model's tables and source field dictionary: [d005](../designs/d005-data-model.md).
