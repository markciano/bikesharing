---
paths:
  - "docs/sources/**"
---

# Source card rules

A source card holds the facts about one data source. Source and Access follow W3C DCAT (dataset and distribution); quality facts follow the DAMA data quality dimensions; the field dictionary follows ISO/IEC 11179 (data element metadata) and DAMA-DMBOK data profiling.

- **Sections**, in this order and with these names in every card:
  - `## Source`: publisher, operator, coverage, standard, licence and attribution.
  - `## Access`: one `###` per distribution (e.g. real time, history): endpoint, format, auth, languages, declared refresh.
  - `## Facts`:
    - `### Service`: facts about the source as a whole, not about one feed (latency, index, timestamps, response size).
    - One `###` per feed, named after it (e.g. `` ### `station_status` ``), with these list items, in this order, each omitted when empty:
      - **Content:** what one item represents, and counts (stations, bikes).
      - **Change:** measured change rate and size per day.
      - **Quality:** each issue led by its dimension (accuracy, completeness, consistency, timeliness, validity, uniqueness).
    - Below the list, in a feed the data model reads, its field dictionary (see Field dictionary).
  - `## Open questions`.
- **Field dictionary:** one table per feed, one row per field of a feed the data model reads, with these columns; a cell that does not apply holds `—`:
  - **Field:** its path in the response (e.g. `data.stations[].vehicle_types_available[].count`).
  - **Description:** its meaning in this source, as observed, in one sentence and in the project's words, linked to its definition in the GBFS version the source publishes. How the model interprets it belongs to the worksheet that maps it, not here.
  - **Type:** as published (integer, string, boolean, timestamp…).
  - **Required:** as GBFS sets it (required, optional, conditionally required).
  - **Unit or format:** e.g. metres, seconds, POSIX time, ISO 8601.
  - **Domain:** the values GBFS allows, only for a closed set.
  - **Observed:** share of nulls, distinct values, minimum and maximum, or the set of values seen.
  - **Example:** one real value.
  - **Notes:** a deviation from GBFS, led by `Differs from GBFS:`, or a quality issue, in one sentence, linking to its field note or its Quality item when it has one.
  - Below the table, in this order:
    - **Field notes:** a fact about a field that does not fit in one sentence, one list item each, led by the field's name, with its evidence and date.
    - **Evidence:** the profile the table comes from, with its link and dates. A row whose fact comes from other evidence cites it in its Notes.
- **Entry:** a fact enters a card only if it affects something the project uses or a documented fallback.
- **One fact, one item:** each fact outside the field dictionary is one list item with its evidence (a link) and the date it was confirmed.
- **Current state:** a fact corrected by later evidence is rewritten in place, with no trace of the earlier version.
- **One source per card:** a fact that compares sources (e.g. a field mapping) belongs to the data model, not to a card; the card holds only its own source's side.
