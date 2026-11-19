---
status: Accepted
date: 2026-11-19
supersedes: 0015-contract-tests-by-contract-kind
---

# Contract tests by contract kind: test vectors, and a native schema for data shape

## Context and problem statement

Components are decoupled by contracts, and each side may be written in a different language; a contract change must fail the tests of both sides. Contracts come in two kinds:

- **Format and behaviour contracts** (keys, naming, encoding), whose rules relate values in ways a schema cannot express, such as a date folder consistent with a timestamp.
- **Data-shape contracts**, which fix the fields, types and nullability of data that another component reads.

[ADR-0015](archive/0015-contract-tests-by-contract-kind.md) chose shared test vectors for the first kind, proven in s008, and an ODCS schema for the second, justified on paper only, leaving its validation to the first design that defines one. That design is d008: its first data-shape contract is a JSON document that the pipeline produces in Python and a browser page consumes in JavaScript, with a nested list of stations. Tables do not cross a component boundary: dbt's model contracts check them inside the pipeline at build time, and gold stays private.

## Considered Options

### 1. ODCS schema

The contract is an Open Data Contract Standard file, validated on each side with a tool that reads ODCS.

- Pros:
  - One standard for every data-shape contract, tables included, with room for quality rules and ownership.
- Cons:
  - It describes tables and datasets; a nested JSON document fits it awkwardly.
  - Each side needs an ODCS tool, and a JavaScript consumer still converts it to a schema it can validate.

### 2. The boundary's native schema, with shared test vectors

The contract is a schema in the language the boundary's data is written in, JSON Schema for a JSON document, shared in `contracts/` with a vectors file of valid and invalid cases, each invalid case breaking one rule with its `reason`.

- Pros:
  - Both sides validate the schema with a standard library of their own language, with no conversion.
  - The schema declares types, nullability and closed objects, which vectors show only by example; the vectors check the schema itself, since an invalid case that passes shows a gap, and show that both sides apply it alike.
- Cons:
  - Two files per contract, kept in step.
  - A table read by another component would need its own native form.

## Decision Outcome

**Chosen option:** 2, the boundary's native schema, with shared test vectors.

Rationale: the first data-shape contract is a nested JSON document read in two languages; JSON Schema is the form both validate natively, and the vectors keep the cross-language check that s008 proved for format contracts.
Why not the others: ODCS models tables, so for a JSON document it adds a tool on each side without describing the document better than JSON Schema.

**Scope:** contracts between components, in `contracts/`, tested as [testing.md](../../.claude/rules/code/testing.md) › Contracts between components sets.

- Format and behaviour contracts: shared test vectors, as ADR-0015 set.
- Data-shape contracts of a JSON document: a JSON Schema (draft 2020-12) and its vectors.
- Not in scope: schemas inside one component, such as dbt's model contracts and Delta schemas, which its design sets; the form of a table read by another component, decided when one exists; the content of data contracts (semantics, freshness, quality, ownership), which stays in the pipeline design.

### Consequences

#### Positive

- **No contract tooling:** each side validates with its language's JSON Schema library.
- **Schema checked by its cases:** a schema that is too loose fails its own vectors.
- **ADR-0015's open point closed:** ODCS was weighed on the first data-shape contract and not adopted.

#### Negative

- **Two files per data-shape contract:** a field added to the schema needs its cases in the same commit.
- **No single form for tables:** the first table that crosses a component boundary reopens the choice.
- **Quality rules outside the contract:** they live in the pipeline's data-quality catalog, not in the file the consumer reads.

## More information

- Evidence for vectors and the scored matrix D: [s008](../spikes/s008-testing-conventions.md) (F35, F36).
- First data-shape contract: [d008 › #28, #29](../designs/d008-pipeline-platform-and-walking-skeleton.md#22-decision-summary).
