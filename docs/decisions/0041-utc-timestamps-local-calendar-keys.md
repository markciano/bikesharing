---
status: Accepted
date: 2026-11-14
supersedes: 0005
---

# Timestamps are stored in UTC, calendar keys in local time

## Context and problem statement

Local time in Barcelona (`Europe/Madrid`) skips one hour in spring and repeats one in autumn, so a local timestamp can be missing or ambiguous.

The questions group facts by day and by hour as people in Barcelona live them. A UTC day is not a local day: it starts at 01:00 or 02:00 local time, depending on the season. ADR-0005 stores everything in UTC and converts only when presenting, so every view that groups by local day or hour converts and re-aggregates the data itself.

## Considered Options

### 1. UTC instants with local calendar keys

Every stored timestamp, file name and partition is in UTC. A fact row also references the date and time-of-day dimensions by the local date and minute of its instant.

- Pros:
  - The stored instant is never missing or ambiguous.
  - Facts group by local day and hour with no conversion at query time.
- Cons:
  - The model converts each instant to local time when it builds the keys.
  - On the autumn change, one local minute maps to two instants, so a count of UTC minutes reads the instant, not the key.

### 2. UTC everywhere, local time only when presenting

As ADR-0005 reads.

- Pros:
  - One time zone in storage, with no conversion in the model.
- Cons:
  - Every view converts and re-aggregates; one that forgets shows shifted days.

### 3. Local time everywhere

Timestamps, file names and partitions in `Europe/Madrid`.

- Pros:
  - Values read as people live them.
- Cons:
  - One hour a year is missing and one is ambiguous.

## Decision Outcome

**Chosen option:** 1. UTC instants with local calendar keys

Rationale: the UTC instant keeps time unambiguous, and the local keys give the questions their local days and hours once, in the model, instead of in every view. This follows Kimball's local calendar keys beside a UTC timestamp.

Why not the others:

- Option 2 repeats the conversion in every view, at hourly grain.
- Option 3 stores ambiguous instants.

**Scope:** every stored timestamp, file name and partition, in every component and layer. Local calendar keys apply to the fact tables of the model only.

### Consequences

#### Positive

- **Unambiguous storage:** no instant is missing or repeated.
- **Local grouping in the model:** views read local days and hours as stored.

#### Negative

- **Two times per fact:** a measure picks the instant or the key by what it counts.
- **Time zone rules:** the model depends on the `Europe/Madrid` rules of its time zone database.

## More information

- [d005 › D33](../designs/d005-data-model.md#d33-local-calendar-keys)
