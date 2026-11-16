---
paths:
  - "docs/data-model/**"
---

# Data model worksheet rules

A worksheet is the detailed design of one silver or gold table, after Kimball's detailed dimensional design worksheet: the table's dictionary and its source-to-target mapping at once. One file per table, named after it, linked from `docs/data-model.md`; the source fields it maps are described in the field dictionary of their source card.

- **Sections**, in this order and with these names in every worksheet; a cell or item that does not apply holds `—`:
  - `# <table>`: the table's physical name.
  - `## Table`: these list items, in this order:
    - **Layer:** silver or gold.
    - **Type:** dimension, or fact: transaction, periodic snapshot or accumulating snapshot.
    - **Description:** what the table represents, in one or two sentences.
    - **Grain:** what one row is (e.g. one row per station and capture).
    - **Keys:** primary key, natural key, and foreign keys, each linked to the worksheet of its dimension.
    - **History:** in a dimension, how it keeps changes to its attributes (slowly changing dimension); the type per attribute goes in Columns.
    - **Business process and questions:** its row in `docs/data-model.md` › Business processes and the questions of d002 it answers, as links.
    - **Sources:** the feeds it reads, linked to their section in the source cards.
    - **Table rules:** the IDs of the rules on the table as a whole, each linked where it lives: its transformation specs in `docs/data-model.md` › Data contract, and its runtime rules, such as its grain and invariants, in `docs/data-quality.md`.
    - **Size:** estimated rows per day and growth per year.
    - **Load:** frequency, full or incremental, and the incremental key.
    - **Partitioning:** the partition column or columns.
  - `## Columns`: one row per column, with these columns; Type, Nullable and Accepted values are the column's schema, checked in every run, and carry no ID:
    - **Column:** physical name.
    - **Description:** its meaning in one sentence.
    - **Type:** logical type (integer, string, boolean, date, timestamp in UTC…).
    - **Nullable:** yes or no.
    - **Accepted values:** the closed list of values the column takes, each in backticks; `—` when its type alone bounds it.
    - **Example:** one real value.
    - **SCD:** in a dimension, the slowly changing dimension type of the attribute.
    - **Additivity:** in a fact's measure, additive, semi-additive or non-additive.
  - `## Mapping`: one row per column, with these columns:
    - **Column:** as in Columns.
    - **AMBici:** feed and field path, linked to the feed's field dictionary.
    - **Bicing:** as AMBici; when real time and the archive differ, both, each named.
    - **Rule:** the column's transformation spec in EARS, led by its ID in bold and citing the decision it applies; a spec that covers several columns is written in the first one's row, and the others hold its ID.
- **Rule IDs:** a rule's ID tells its class: `TR` for a transformation spec, kept when it moves from `docs/data-model.md` › Data contract to its table's worksheet; `RDM` for a documentation item; `DQR` and `DQM` for a runtime rule and a quality indicator, in `docs/data-quality.md`. A new item takes the next free ID of its class, and an ID is never reused.
