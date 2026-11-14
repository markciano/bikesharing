---
status: Accepted
date: 2026-11-14
supersedes: 0008
---

# The model takes its vocabulary from GBFS 3.0, not its layout

## Context and problem statement

AMBici and Bicing publish GBFS in different versions, with different names and values for the same facts. The model in silver and gold compares both systems, so a measure with one name must mean the same in each.

GBFS 3.0 defines the station measures, and also a feed layout and formats made for publishing: timestamps as RFC 3339 strings, names as lists of localised strings. ADR-0008 made the common model follow GBFS 3.0 without stating which of these parts apply to analytical tables.

## Considered Options

### 1. GBFS 3.0 for the vocabulary, dimensional tables

A measure that comes from a GBFS field takes its name and definition from GBFS 3.0. A measure the model derives takes a name of its own in the same style. Tables take the shape of the dimensional model, with native types.

- Pros:
  - Each source measure has one external definition, shared by both systems.
  - Tables hold typed values, with nothing to parse at query time.
- Cons:
  - Two references: GBFS for source measures, the model's documentation for derived measures and table shape.

### 2. GBFS 3.0 for vocabulary, layout and formats

The model keeps GBFS 3.0 as published, as ADR-0008 reads.

- Pros:
  - One reference for names, layout and formats.
- Cons:
  - Timestamps and names stay as strings and localised lists, parsed by every query.

### 3. Business names of the model's own

The model names and defines every measure itself, e.g. `bikes_available`, `free_docks`.

- Pros:
  - Names read without knowing GBFS.
- Cons:
  - Every definition is written and kept by the project, with no external standard behind it.

## Decision Outcome

**Chosen option:** 1. GBFS 3.0 for the vocabulary, dimensional tables

Rationale: GBFS 3.0 is the standard both sources publish, so taking its names and definitions gives conformed measures across the two systems. Its layout and formats serve feed publishing, not analysis.

Why not the others:

- Option 2 carries publishing formats into tables that are only queried.
- Option 3 replaces an external standard with definitions the project must maintain.

A source whose values do not meet a 3.0 definition is mapped to it; one that publishes an earlier version maps its fields to 3.0 field by field.

**Scope:** measures and their columns in silver and gold. It does not apply to bronze, which keeps source responses untouched ([ADR-0006](0006-raw-layer-keeps-source-responses-untouched.md)).

### Consequences

#### Positive

- **Conformed measures:** a measure name means the same in AMBici and Bicing.
- **Version changes stay local:** a source moving to 3.0 changes only its mapping.

#### Negative

- **Derived measures:** their definitions are kept by the project.
- **Later GBFS versions:** one that renames or redefines a measure needs a new decision.

## More information

- [d005 › D14](../designs/d005-data-model.md#d14-vocabulary-of-the-measures)
