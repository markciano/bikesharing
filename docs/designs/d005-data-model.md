<!--
Design doc template. A design doc is the working document of one task: Spec (what and why), Plan (how), Steps (implementation), Close (what was delivered).
It is detailed enough that Code can implement it without making design decisions.
Sections marked Optional are kept only when they apply.
-->

# Design: Data model

- **Task:** T040
- **ADRs:** [ADR-0006](../decisions/0006-raw-layer-keeps-source-responses-untouched.md), [ADR-0008](../decisions/0008-common-model-on-gbfs-3-0.md), [ADR-0026](../decisions/0026-budget-shares-per-component.md)
- **New ADRs from this doc:** none

## Status

<!-- State: Draft 📝 · Ready for implementation 🎬 · In progress 🔄 · Complete ✅.
Phase: the blocks and reviews completed.
Current step: the step being implemented, or —. -->

- State: Draft 📝
- Phase: [ ] Spec · [ ] Plan · [ ] Plan review · [ ] Steps · [ ] Steps review
- Current step: —
- Next: review the data profile ([spikes/d005-data-model › profile](../../spikes/d005-data-model/README.md#profile)), Kimball's data realities, before the open questions, which follow Kimball's four-step design: dimensions (OQ1), facts (OQ2), detailed design (OQ3).
  - Outputs: profile findings go to the source cards (`docs/sources/ambici.md`, `bicing.md`), which decisions link when they need them; dimensions and facts go to `docs/data-model.md`; the detailed design's place is decided in OQ3.
  - Before adding findings, decide how the source cards are organized so that they hold no redundant facts.
  - Until OQ3 closes, a change to D3–D7 rewrites the decision as if taken now, with no trace of the earlier version.
  - Whether `spikes/d005-data-model/vehicle-types/vehicle_types_check.py` stays is pending; it is the only evidence that `METRO` became `METRO_BASE` (OQ1).

## 1. Spec — what and why

<!-- What the result does seen from outside, not how it is built. The test: if whoever uses the result would notice a change, it belongs here; if not, it belongs to the Plan. External systems and their data (feeds, fields) may be named. -->

### 1.1 Context

<!-- 2–4 sentences for a reader with no prior context: the problem or need and why it matters now; who or what uses the result; where things stand today, including any design or spike this builds on. No solution here: it starts in Decided at framing. For a correction: current vs expected behaviour and how to reproduce it. -->

The questions of [d002](d002-requirements.md) compare AMBici and Bicing, two systems that publish different GBFS versions, each with its own names and values for the same facts. Capture writes both systems' raw feeds to the bronze layer on R2 ([d004](d004-bronze-data-capture.md)), but no model defines yet what silver and gold hold, so the pipeline that builds them ([d007](d007-pipeline-design.md)) and the public visualization (T041) have nothing to build on.

### 1.2 Decided at framing

<!-- Optional. One heading per decision about what the result does. In this order, so the reader finds what matters first:
1. The decision and why, in one short paragraph.
2. What would change it, and what would not, each with the action to take. Only when a later event could reopen it.
3. The options rejected.
4. The artefact that fixes it, in whatever form the decision needs (e.g. a mapping table, a page map, a weighted matrix). An artefact that does not fit here or must outlive the design goes in its own file: the Plan decides where it lives and its format, File layout lists it, and this decision links to it.

A security decision lists its threats in this table, with IDs `TH1`, `TH2`… per document:

| # | Threat (STRIDE) | Impact | Control | Requirement |
|---|---|---|---|---|
| `TH1` | | | | |
-->

#### D1. One model over one bus matrix

The whole model is designed once, here, following Kimball's bus architecture, so that every business process shares the same dimensions and both sources compare on the same terms. This design fixes the feeds that enter, the bus matrix (business processes, the grain of each fact, the conformed dimensions), how the two sources' terms and values are made comparable, and which questions gold answers. The pipeline builds the model one business process at a time ([d007 › D1](d007-pipeline-design.md#d1-build-by-vertical-slice)), and each slice's design fixes its columns and gold tables within this model.

#### D2. Capture's fixtures as the feed sample

The sample for inspecting each feed is capture's fixtures, `capture/test/fixtures/<source>/<feed>.json`: pretty-printed, uncompressed JSON with the whole index and the first 3 entries of every other feed, and their provenance in `manifest.json` ([d004 › Fixtures](d004-bronze-data-capture.md#fixtures)). They show the full structure of each feed, enough to judge what it contributes to the model. Bronze objects are gzip (`.json.gz`), which is why an editor shows them as binary; DuckDB reads them directly.

What would change it: a feed whose value cannot be judged from 3 entries; that feed's latest bronze object is then downloaded and decompressed for inspection, outside Git.

Rejected: a new sample from R2 in a folder ignored by Git, since it shows the same structure and adds local R2 credentials and a script to maintain.

#### D3. Feeds that enter the model

A feed enters silver only if it answers a question of [d002 › Guiding questions](d002-requirements.md#guiding-questions). The rest stay in bronze untouched ([ADR-0006](../decisions/0006-raw-layer-keeps-source-responses-untouched.md)) and the model does not read them. Prices and opening hours answer no question, and no feed ties a trip to a pricing plan, since trips are estimated from stock changes; if a measure ever needs them, they enter as parameters.

What would change it: a new question that needs a discarded feed; the feed then enters, and its history is already in bronze.

| Feed | AMBici | Bicing | Use in the model |
|---|---|---|---|
| `station_status` | Enters | Enters | The stock snapshot, base fact of Q1 and Q3–Q7 |
| `station_information` | Enters | Enters | Station dimension; Q8, and Bicing's `post_code` for Q4 |
| `vehicle_types` | Enters | Enters | Bikes by type in Q1, through `vehicle_type_id` in `vehicle_types_available` |
| `system_regions` | Enters | Discarded: empty | AMBici's regions are municipalities, linked by `region_id` in `station_information`: the municipality of Q4 |
| `free_bike_status` | Discarded: adds nothing to `station_status` | Not published | Over 17,870 passes (2026-10-14 to 10-26), every bike has a `station_id`, none is disabled, a mean of 0.6 are reserved, and 99.1% of the station counts match `num_bikes_available`, with the rest off by about one bike. Its battery fields (`current_fuel_percent`, `current_range_meters`) answer no question yet. Check in [spikes/d005-data-model](../../spikes/d005-data-model/README.md) |
| `geofencing_zones` | Discarded: empty | Discarded: empty | — |
| `system_pricing_plans` | Discarded | Discarded | No question uses prices |
| `system_hours` | Discarded | Not published | No question uses opening hours |
| `system_information` | Discarded | Discarded | One row per system with nothing to measure; the system dimension's few static attributes are fixed in [D5](#d5-conformed-dimensions) |
| `gbfs.json`, `gbfs_versions` | Discarded | Discarded | Discovery index, used only by capture |

#### D4. Business processes and the grain of the stock

The model follows Kimball's inventory case, as framed in [d002 › Guiding questions](d002-requirements.md#guiding-questions): each capture is a stock count per station, and trips are stock movements derived from consecutive counts. Four business processes answer Q1–Q7; Q8 is answered by the history of the station dimension, not by a fact. The model, with how each question maps to a process, lives in [data-model.md](../data-model.md).

- **Station stock:** one row per station and capture, a periodic snapshot. Semi-additive: it is not summed over time.
- **Stock by vehicle type:** one row per station, capture and vehicle type, from the real-time feeds only, since the Bicing archive has no per-type counts.
- **Stock movements:** one row per station and pair of consecutive captures with a change, derived from the stock. Additive: departures and arrivals are summed over time.
- **Capture passes:** one row per source, feed and capture pass, from capture's logs.

Every capture is kept as a row, even when the station has not changed: rows are only appended, a gap in capture is visible as missing rows, and the Bicing archive's 5-minute snapshots fit the same grain. Rows that repeat values compress well in columnar storage, and small files are compacted by the pipeline.

What would change it: silver's storage cost approaching its share of the budget ([ADR-0026](../decisions/0026-budget-shares-per-component.md)); rows older than a set age are then reduced to intervals or a coarser resolution.

Rejected: one row per station state with `valid_from` and `valid_to` (a timespan tracking fact). It stores far fewer rows, but every change rewrites the open row with a MERGE, with more R2 operations and more conflicts, and a gap in capture reads as an unchanged state.

#### D5. Conformed dimensions

Each dimension answers what describes a fact row: when, where, whose and what. The bus matrix and the reasons for each dimension live in [data-model.md › Dimensions](../data-model.md#dimensions).

- **Date** and **time of day**, apart, since questions group by day and by hour or time band; the exact UTC instant stays in the fact.
- **System**, its own dimension, since capture passes have no station and every question compares AMBici with Bicing.
- **Station**, with its history (SCD type 2), since Q8 asks for it and past occupancy needs the capacity of its time; post code and municipality flattened into it.
- **Vehicle type**, with its propulsion as the level that compares across systems and with the Bicing archive, whose only split is mechanical and electric.
- **Feed**, for capture passes.

The status flags `is_installed`, `is_renting` and `is_returning` stay in the stock fact, not in a dimension.

Rejected: system as an attribute of the station, since capture passes could not be compared by system; municipality as a dimension of its own linked to the station (a snowflake), since it adds a join for a small hierarchy.

#### D6. AMBici's post code

Bicing publishes each station's `post_code`; AMBici does not. AMBici's post code comes from ICGC's reverse geocoder (`eines.icgc.cat/geocodificador/invers`), as the post code of the address nearest to the station. The owner checks by hand only the stations with a doubt flag, set when the 5 nearest addresses ICGC returns do not share one post code, each time a station first appears or its coordinates change. No open post-code polygons exist ([BOE-A-2023-11522](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-11522)), so every public source returns the code of the nearest address, and a station on a street that divides two codes may get the other side's. On 84 Bicing stations, 2 per published code, ICGC gave Bicing's code for 95.2%; in the 4 misses the owner confirmed Bicing right. The doubt flag marked 7 of the 84 and caught 2 of the 4 misses, so about 2.5% of AMBici's stations, some 5 or 6 of 237, may keep a wrong code unnoticed. ICGC's data may be reused freely under Law 37/2007, citing ICGC and the date of the data, and it asks for no API key. Check in [spikes/d005-data-model](../../spikes/d005-data-model/README.md).

What would change it: AMBici publishing `post_code`; its own value then replaces ICGC's.

Rejected: the nearest GeoNames post-code point, right for 71.4% of 539 Bicing stations; CartoCiudad (IGN), whose post codes are subject to the agreement with Correos (BOE 2023); checking all 237 stations by hand, too much manual work for about 11 wrong codes.

#### D7. Station status flags

`is_installed`, `is_renting` and `is_returning` mean in both sources what GBFS defines: whether a station is on the street and in service, not whether it has bikes or free docks, which `num_*_available` give. The model keeps the three as published. AMBici publishes GBFS 2.3 and Bicing 3.0, and both versions define the flags alike ([v2.3](https://raw.githubusercontent.com/MobilityData/gbfs/v2.3/gbfs.md), [v3.0](https://raw.githubusercontent.com/MobilityData/gbfs/v3.0/gbfs.md), `station_status.json`):

- `is_installed`: "Is the station currently on the street?"
- `is_renting`: "Even if the station is empty, if it would otherwise allow rentals, this value MUST be `true`." It MUST be `false` while the station is temporarily out of service.
- `is_returning`: "Even if the station is full, if it would otherwise allow vehicle returns, this value MUST be `true`." It MUST be `false` while the station is temporarily out of service.

Both sources follow these definitions. Over about 17,870 passes per source (2026-10-14 to 10-26):

- `is_renting` and `is_returning` never disagree, in any row of either source.
- Empty stations keep `is_renting = true` in 96.5% of AMBici's rows and 93.2% of Bicing's; full stations keep `is_returning = true` in 95.9% and 85.3%.
- `is_installed` is always `true` in AMBici; in Bicing it is `false` for 1 station, in every pass.
- Stations out of service: 8 in AMBici, apparently for the whole period; 121 in Bicing, about 5 per pass.
- An out-of-service station still reports its bikes in AMBici, as 2.3 allows (`num_bikes_available` counts the bikes that would be available). In Bicing it always reports 0 vehicles, while 3.0 counts those physically at the station: either Bicing empties its closed stations or it departs from 3.0, and the data cannot tell which.

Check in [spikes/d005-data-model](../../spikes/d005-data-model/README.md).

What would change it: a source whose flags stop matching these definitions, found by running that check again; the model then maps that source's values to the GBFS meaning.

Rejected: merging `is_renting` and `is_returning` into one in-service flag. They never disagree in these sources, but GBFS keeps them apart and a station may accept returns while not renting.

### 1.3 Requirements

<!-- Optional. The acceptance criteria, cited by number in the Test plan and the steps. They translate Decided at framing and cite the decision they come from; nothing is decided here.
One behaviour per requirement, verifiable, with a measurable threshold where one applies. Written in EARS:
- Ubiquitous: The <system> shall <response>.
- Event: When <trigger>, the <system> shall <response>.
- State: While <state>, the <system> shall <response>.
- Unwanted: If <condition>, then the <system> shall <response>.
- Optional: Where <feature is included>, the <system> shall <response>.
Only requirements specific to this task; project-wide rules (CLAUDE.md, ADRs) are not repeated. -->

- **R1** `<EARS statement>` (D`<N>`)

### 1.4 Done when

<!-- Optional. Only what closes this task and Requirements cannot express: operational actions, checks on real data, understanding. The general closing rule is checked in `.claude/skills/implement/review.md`. -->

- `<extra condition>`

### 1.5 Out of scope

<!-- Optional. What someone could expect and will not be done, each item pointing to the task that covers it. -->

- Capturing less often, or no longer capturing, the feeds that do not enter the model ([D3](#d3-feeds-that-enter-the-model)), except `free_bike_status`, kept for future questions on AMBici's battery levels — task assigned at the end of this design

### 1.6 Open questions

<!-- Optional. The decisions still to take about the what, in dependency order. Each one closes as a decision in Decided at framing and leaves the table, so it is empty at Spec approval. Questions about the how are Plan decisions. -->

| OQ | Question | Depends on | Notes |
|---|---|---|---|
| OQ1 | How the dimension values of AMBici and Bicing are conformed (Kimball step 3: same names and domain values) | D5 | [ADR-0008](../decisions/0008-common-model-on-gbfs-3-0.md) reviewed critically: GBFS 3.0 as vocabulary rather than shape. Vehicle types: AMBici publishes 3 (`196` human; `204` and `420` electric assist); Bicing publishes 11, bicycles with human or electric-assist propulsion plus a standing scooter (`CHLOE`) and a trailer (`TRAILER`), and on 2026-10-22 `METRO` became `METRO_BASE` ([spikes/d005-data-model](../../spikes/d005-data-model/README.md)). Regions: AMBici's 237 stations sit in 16 regions, 15 of them municipalities; "AMB" groups 10 stations, most of them in Barcelona or on a boundary; municipal boundaries are open (ICGC, CC BY 4.0). To decide: how each source's vehicle types map to the propulsion level of D5, and the municipality of the stations in "AMB" |
| OQ2 | The facts of each business process (Kimball step 4): their measures, one definition and name for both sources, their additivity, and which d002 question each answers in gold | D4, OQ1 | Which questions gold answers is handed to T040 by [d002 › Out of scope](d002-requirements.md). Expected: the facts match in both sources (same service, near-identical schema). To check: GBFS 3.0 renamed `num_bikes_available` to `num_vehicles_available` ([GBFS PR #354](https://github.com/MobilityData/gbfs/pull/354)); an out-of-service station reports its bikes in AMBici and 0 in Bicing ([D7](#d7-station-status-flags)); the Bicing archive splits stock only into mechanical and electric |
| OQ3 | How each silver or gold column is traced back to the raw fields and the calculation it comes from, and a dictionary of the source fields with their official GBFS definition and how each source behaves (Kimball's detailed design) | OQ1, OQ2 | Standards to weigh: the data dictionary with data profiling, and Kimball's detailed design worksheet per table, the base of the source-to-target mapping (column-level lineage). The source cards in `docs/sources/` already hold facts observed per source, with their evidence and date. Row-level lineage, to bronze and to the run, is decided in [d007](d007-pipeline-design.md) |

## 2. Plan — how

<!-- 2-3 sentences -->

### 2.1 Approach

<!-- Detailed plan organized by #### blocks.
Block `3. Steps` is written using this plan.
If some block contains `options considered`, include them with pros and cons.
-->

### 2.2 Decision summary

<!-- It logs decisions about the plan, including changes. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Applies to: anchor link(s) to the section where the decision is applied, named in one or two words.
- Decided at: the Status phase where it was decided (Plan, Steps), or `<phase> review` when decided while reviewing that phase.
- R: Requirement affected.
-->

| # | Applies to | Decision | Reason | R | Decided at |
|---|---|---|---|---|---|
| | | | | | |

### 2.3 Architecture

<!-- Optional. One diagram and 2–3 sentences. -->

### 2.4 File layout

<!-- Every file and folder the task creates or modifies, documents included, as a tree: (new) or (modified), and its purpose or change in one line. A task that adds a component also lists its CI job in `.github/workflows/ci.yml` (recipe in `.claude/rules/code/ci.md`), and its version files, manifest and lockfile (`.claude/rules/code/dependencies.md`). -->

```text
<path>/
└── <file>      (new)        <purpose>
```

### 2.5 Components

<!-- Optional. One subsection per component. The contract is exact, in the component's own language, never pseudocode. -->

#### `<ComponentName>`

- **Responsibility:** `<one sentence>`
- **Location:** `path/to/file`
- **Contract:**

```python
```

### 2.6 Test plan

<!-- Optional. Every requirement has at least one verification method (IADT: Inspection, Analysis, Demonstration, Test). Test is the default, at the lowest level that can verify the requirement. Another method only when no test can: Inspection for configuration or documents, Analysis for production data or measurements, Demonstration for behaviour observed end to end, such as a third-party service. -->

| R | Method | What is verified | Level |
|---|---|---|---|
| R1 | Test / Inspection / Analysis / Demonstration | | unit / integration / e2e; — for other methods |

### 2.7 Breaking changes

<!-- Optional. Shared models or interfaces this design changes, and how their dependants are handled. -->

| File | Why it breaks | Strategy |
|---|---|---|
| | | |

### 2.8 What does not change

<!-- Optional. Code or documents that must not be modified. Out of scope limits the what; this section limits the how. -->

-

## 3. Steps

<!-- Each step is one reviewable result and one commit, touching at most 2–3 files.
- Status: where the step is: 💤 todo · 🎬 ready · 🔄 in progress · ⛔ blocked · ✅ done
- Who: Owner (manual actions: dashboards, accounts, deploys, runs, checks) or Claude (code and documents).
- R: the requirements the step implements or tests, or —.
- Commit: the proposed message, following the Git conventions in CLAUDE.md.
- Model: the model and effort the step's session runs with (e.g. sonnet · medium), or — when Who is Owner. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

### Step 1 — `<Title>`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** following the Git conventions in CLAUDE.md, including `<dNNN.sN - >` at the begining of the message, for the design and the step number.
- **R:** R1, R3 (or —)
- **Model:** `<model · effort>` (or —)

#### Scope

<!-- The result of the step. List the components, the files created or changed (code, tests, docs), and the tests from the Test plan that cover it. A reviewer should know what the diff will contain from this section alone. -->

#### Reads

<!-- List of reads containing what to read (be specific with paragraph or line), what contains the read, and why it is interesting here.  -->

#### Do

<!-- Numbered actions in execution order, one verb each (write, implement, update, run). Every file named here must appear in Scope; add nothing Scope does not list. -->

#### Check

<!-- command/s or verification with a yes/no result. -->

## 4. Close

<!-- The record of what the task delivered, for whoever opens this design later. -->

### 4.1 Implemented

<!-- Component — what was delivered; tests passing. -->

### 4.2 Known gaps at close

<!-- What the task leaves undone or imperfect, each with the task that covers it: requirements not fully met, File layout items not delivered, TODOs citing this task. "None" is valid. -->

- `<gap>` — TNNN

### 4.3 Decisions taken during implementation

<!-- Decisions made after the Plan was approved, including deviations from Scope approved by the owner. Oldest first; "None" is valid.
- #: `DI1`, `DI2`… (decision during implementation).
- Applies to: anchor link(s) to the design section the decision changes, or the path of a file outside the design.
- Decision and Reason: one line each; the content goes where it applies.
- Decided at: the step where it was decided (`Step N`).
-->

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| | | | | |
