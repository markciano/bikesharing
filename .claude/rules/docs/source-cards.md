---
paths:
  - "docs/sources/**"
---

# Source card rules

A source card holds the facts about one data source. Source and Access follow W3C DCAT (dataset and distribution); quality facts follow the DAMA data quality dimensions.

- **Sections**, in this order and with these names in every card:
  - `## Source`: publisher, operator, coverage, standard, licence and attribution.
  - `## Access`: one `###` per distribution (e.g. real time, history): endpoint, format, auth, languages, declared refresh.
  - `## Facts`:
    - `### Service`: facts about the source as a whole, not about one feed (latency, index, timestamps, response size).
    - One `###` per feed, named after it (e.g. `` ### `station_status` ``), with these list items, in this order, each omitted when empty:
      - **Content:** what one item represents, and counts (stations, bikes).
      - **Fields:** per field, its meaning and the values observed.
      - **Change:** measured change rate and size per day.
      - **Quality:** each issue led by its dimension (accuracy, completeness, consistency, timeliness, validity, uniqueness).
  - `## Open questions`.
- **Entry:** a fact enters a card only if it affects something the project uses or a documented fallback.
- **One fact, one item:** each fact is one list item with its evidence (a link) and the date it was confirmed.
- **Current state:** a fact corrected by later evidence is rewritten in place, with no trace of the earlier version.
- **One source per card:** a fact that compares sources (e.g. a field mapping) belongs to the data model, not to a card; the card holds only its own source's side.
