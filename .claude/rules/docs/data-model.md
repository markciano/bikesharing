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
    - **Table rules:** the IDs of its grain and invariant rules, linked to `docs/data-model.md` › Data contract, where they live.
    - **Size:** estimated rows per day and growth per year.
    - **Load:** frequency, full or incremental, and the incremental key.
    - **Partitioning:** the partition column or columns.
  - `## Columns`: one row per column, with these columns:
    - **Column:** physical name.
    - **Description:** its meaning in one sentence.
    - **Type:** logical type (integer, string, boolean, date, timestamp in UTC…).
    - **Nullable:** yes or no.
    - **Example:** one real value.
    - **SCD:** in a dimension, the slowly changing dimension type of the attribute.
    - **Additivity:** in a fact's measure, additive, semi-additive or non-additive.
    - **Column rules:** the IDs of its rules in Column rules.
  - `## Mapping`: one row per column, with these columns:
    - **Column:** as in Columns.
    - **AMBici:** feed and field path, linked to the feed's field dictionary.
    - **Bicing:** as AMBici; when real time and the archive differ, both, each named.
    - **Rule:** the transformation in one sentence, linking the decision it applies.
  - `## Column rules`: one list item per rule on type, nullability or accepted values, led by its ID in bold, in EARS, citing the decision it applies.
- **Rule IDs:** column rules keep the `RDM` ID they had in `docs/data-model.md` › Data contract; a new rule takes the next free ID there, and an ID is never reused.
