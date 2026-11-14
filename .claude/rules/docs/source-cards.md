---
paths:
  - "docs/sources/**"
---

# Source card rules

A source card holds the facts about one data source. Source and Access follow W3C DCAT (dataset and distribution); quality facts follow the DAMA data quality dimensions; the field dictionary follows ISO/IEC 11179 (data element metadata) and DAMA-DMBOK data profiling.

- **Sections**, in this order and with these names in every card:
  - `## Source`: publisher, operator, coverage, standard, licence and attribution.
  - `## Access`: one `###` per distribution (e.g. real time, history): endpoint, format, auth, languages, declared refresh.
  - `## General facts`: facts about the source as a whole, not about one feed (latency, index, timestamps, response size, how the system runs). It opens with this line: "Facts that hold for the whole source, not for one feed: how it publishes its data and how the system runs."
  - `## Feeds`: it opens with this line: "One section per feed: what it holds, how often it changes and its quality issues; a feed the data model reads adds its field dictionary." Then one `###` per feed, named after it (e.g. `` ### `station_status` ``), with these list items, in this order, each omitted when empty:
    - **Content:** what one item represents, and counts (stations, bikes).
    - **Change:** measured change rate and size per day.
    - **Quality:** each issue led by its dimension (accuracy, completeness, consistency, timeliness, validity, uniqueness).
    - Below the list, in a feed the data model reads, `#### Field dictionary` (see Field dictionary).
  - `## Open questions`.
- **Provider cards:** a card of a service provider, which publishes no feeds, has `## Facts` in place of `## General facts` and `## Feeds`. It opens with one line saying what it holds, then one `###` per topic when there are several.
- **Field dictionary:** one table per feed, one row per field of a feed the data model reads, under `#### Field dictionary`, after one line that names the feed, the source, the GBFS version and the profile's dates (e.g. "Every field of `station_status` as AMBici publishes it: its meaning, its definition in GBFS 2.3 and the values profiled from 2026-10-14 to 2026-10-26."). Its columns follow; a cell that does not apply holds `—`:
  - **Field:** its path in the response (e.g. `data.stations[].vehicle_types_available[].count`). The header fields (`last_updated`, `ttl`, `version`) have a row in every feed's table.
  - **Description:** its meaning in this source, as observed, in one sentence and in the project's words, linked to its definition in the GBFS version the source publishes, as a reference link defined at the end of the card. How the model interprets it belongs to the worksheet that maps it, not here.
  - **Type:** its JSON type as published (integer, number, string, boolean, array, object); a format such as POSIX time goes in Unit or format.
  - **Required:** as GBFS sets it (required, optional, conditionally required).
  - **Unit or format:** e.g. metres, seconds, POSIX time, ISO 8601.
  - **Domain:** the values GBFS allows, only for a closed set.
  - **Observed:** share of nulls, distinct values, minimum and maximum, or the set of values seen. A count of distinct values that the profile estimates is marked `≈`.
  - **Example:** one real value.
  - **Notes:** a deviation from GBFS, led by `Differs from GBFS:`, or a quality issue, in one sentence, linking to its field note or its Quality item when it has one.
  - Below the table, in this order:
    - **Field notes:** a fact about a field that does not fit in one sentence, one list item each, led by the field's name, with its evidence and date.
    - **Evidence:** the profile the table comes from, with its link and dates. A row whose fact comes from other evidence cites it in its Notes.
- **Entry:** a fact enters a card only if it affects something the project uses or a documented fallback.
- **One fact, one item:** each fact outside the field dictionary is one list item with its evidence (a link) and the date it was confirmed.
- **Current state:** a fact corrected by later evidence is rewritten in place, with no trace of the earlier version.
- **One source per card:** a fact that compares sources (e.g. a field mapping) belongs to the data model, not to a card; the card holds only its own source's side.
