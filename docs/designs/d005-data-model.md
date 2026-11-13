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
- Next: OQ2.3. The data profile (Kimball's data realities) is reviewed, and its findings are in the source cards ([AMBici](../sources/ambici.md), [Bicing](../sources/bicing.md)). The open questions follow Kimball's four-step design: the dimensions' conformed values (D8–D13), the vocabulary of the measures (D14), the stock's measures from the feed (D15, D16, D19–D21), occupancy (D17) and AMBici's +P stations (D18) are decided; facts (OQ2.3–OQ2.6) and detailed design (OQ3) remain.
  - For failure cases: the behaviours observed over 2026-10-14 to 10-26 that each decision relies on; first known gap: Bicing's `num_docks_available` at a closed station. For [D16](#d16-vehicles-at-an-out-of-service-station): GBFS 2.x counts the bikes of a station with `is_renting` false as disabled ([NABSA/gbfs#195](https://github.com/NABSA/gbfs/pull/195)), while Bicing reports 0. For [D19](#d19-last-reported-time-in-the-stock): the counts of a Bicing station in service that has not reported for a long time, and from what age they stop being current. For [D20](#d20-zero-counts-in-the-stock-by-vehicle-type): a capture where no station of a system lists a type that has stock in others.
  - For the Plan: an ADR that supersedes [ADR-0008](../decisions/0008-common-model-on-gbfs-3-0.md) with D14, GBFS 3.0 as the vocabulary of the model.
  - Outputs: source facts go to the source cards, which decisions link when they need them; dimensions and facts go to `docs/data-model.md`; the detailed design's place is decided in OQ3.
  - Until OQ3 closes, a change to D3–D7 rewrites the decision as if taken now, with no trace of the earlier version.
  - For D3: the Bicing history archives as a source of the model.

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

Bicing's `post_code` comes with and without its leading zero (`08001`, `8001`) and is missing for 0.37% of its stations ([Bicing › `station_information`](../sources/bicing.md#station_information)). It is left-padded with zeros to the 5 digits of a Spanish post code, and a missing one is taken from ICGC by the same rule and doubt flag as AMBici's.

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
- Stations out of service: 8 in AMBici, for the whole period; 121 in Bicing, about 5 per pass.
- An out-of-service station still reports its bikes in AMBici, as 2.3 allows (`num_bikes_available` counts the bikes that would be available). In Bicing it reports 0 vehicles while its bikes stay at the station, which departs from 3.0 ([D16](#d16-vehicles-at-an-out-of-service-station)).

Check in [spikes/d005-data-model](../../spikes/d005-data-model/README.md).

What would change it: a source whose flags stop matching these definitions, found by running that check again; the model then maps that source's values to the GBFS meaning.

Rejected: merging `is_renting` and `is_returning` into one in-service flag. They never disagree in these sources, but GBFS keeps them apart and a station may accept returns while not renting.

#### D8. Vehicle propulsion

The bikes of both systems are either mechanical or electrically assisted; none is fully electric. The vehicle type's propulsion, the level that compares across systems ([D5](#d5-conformed-dimensions)), therefore takes two values, derived from the `propulsion_type` each source publishes in `vehicle_types`, a vocabulary GBFS 2.3 and 3.0 share:

| `propulsion_type` | Propulsion |
|---|---|
| `human` | Mechanical |
| `electric_assist` | Electric |

The rule reads only what each type publishes, so a new or renamed type, such as Bicing's `METRO`, which became `METRO_BASE` on 2026-10-22, is classified with no change to the model. The dimension keeps one row per published type, with its `vehicle_type_id`, name and `form_factor`, so stock is still counted per type; propulsion is the level above it, used to compare systems.

- AMBici: `196` is `human`; `204` and `420` are `electric_assist`.
- Bicing: of its 11 types, only `FIT`, `EFIT`, `BOOST` and `ICONIC` appear in `vehicle_types_available`; `ICONIC` and `FIT` are `human`, and `BOOST` and `EFIT` are `electric_assist`. Check in [spikes/d005-data-model](../../spikes/d005-data-model/README.md). The standing scooter (`CHLOE`) and the trailer (`TRAILER`) are published but not rented, and never have stock.

Rejected: a hand-kept table of propulsion per `vehicle_type_id`, since type IDs are local to each system and change, and every new type would wait for an edit to be classified.

#### D9. Station municipality

Every station gets one municipality, by one rule: the municipality its operator publishes, when it publishes one; otherwise the municipality that contains its coordinates. Both take their code and name from ICGC's municipal boundaries ("Divisions administratives", 1:5,000, CC BY 4.0), so the values come from one domain: `CODIMUNI`, the 6-digit IDESCAT code, and `NOMMUNI`.

- AMBici publishes a municipality as the region of each station, except "AMB", which holds the 10 stations in or at the edge of Barcelona ([AMBici › `system_regions`](../sources/ambici.md#system_regions)). Those 10 take the containing municipality: 8 Barcelona, 1 Sant Adrià de Besòs, 1 L'Hospitalet de Llobregat. A published region is matched to ICGC's name without its leading article.
- Bicing is Barcelona's service: every station is Barcelona.
- The containing municipality is computed for every station, by point-in-polygon on ICGC's boundaries, and kept with the published region. A station where they differ is flagged for review. Of the 768 stations whose municipality is given, 227 by AMBici's region and 541 as Bicing's, 2 differ, both 4 m from a boundary, within the error of the coordinates: AMBici's `135349994` falls in Sant Just Desvern, not Sant Feliu de Llobregat, and Bicing's `352` in L'Hospitalet de Llobregat. Check in [spikes/d005-data-model](../../spikes/d005-data-model/README.md).

What would change it: an operator publishing a region that is not a municipality, or a flagged station whose published value proves wrong; the containing municipality then applies to it.

Rejected: the containing municipality for every station, since at a boundary the operator knows which municipality a station belongs to and the coordinates do not; and keeping "AMB" as a value, since those stations could not be compared by municipality.

#### D10. Barcelona district and neighbourhood

Every station in Barcelona gets its district and neighbourhood, whichever system operates it, so a neighbourhood counts all its stations. They are the geography residents identify with, finer than the municipality and clearer than the post code, and their official codes link the model to the City Council's open data, such as population per neighbourhood. They answer [d002 › Q4](d002-requirements.md#guiding-questions), by district and neighbourhood within Barcelona.

Every station in Barcelona takes the neighbourhood that contains its coordinates, on the City Council's official boundaries ("Unitats administratives", 73 neighbourhoods in 10 districts, CC BY 4.0), and the district that neighbourhood belongs to in the official hierarchy. The City Council defines both the codes and the polygons, so the computed value is the authoritative one, and the hierarchy rules out a neighbourhood paired with the wrong district.

- Bicing publishes district and neighbourhood in `cross_street`, with the official codes, e.g. `01-CiutatVella/01-el Raval`. It is kept as published, split into codes, and a station where it differs from the computed value is flagged for review. On 541 stations it gives a neighbourhood outside its own district in 7, and a neighbouring one in 19, 0 to 82 m from the boundary, most on streets that form it ([Bicing › `station_information`](../sources/bicing.md#station_information)).
- AMBici publishes neither. Its 8 stations in Barcelona ([D9](#d9-station-municipality)) fall in 4 districts and 6 neighbourhoods.
- A station outside Barcelona takes "Not applicable" in both, not null, so every group in a query has a label.

Check in [spikes/d005-data-model](../../spikes/d005-data-model/README.md).

What would change it: the City Council redrawing its neighbourhoods; the model then takes the new boundaries, with the station dimension's history keeping the earlier ones.

Rejected: Bicing's published neighbourhood where it exists, since 23 of its 541 stations disagree with the official boundaries, 7 of them with an impossible pair; district and neighbourhood for Bicing only, since AMBici's stations in Barcelona would be missing from their neighbourhood; and leaving `cross_street` out of the model, since the neighbourhood is the level residents look for.

#### D11. Place names

Municipalities, districts and neighbourhoods keep one name each: their official form, as the authority that defines them publishes it, ICGC for municipalities ([D9](#d9-station-municipality)) and the City Council for districts and neighbourhoods ([D10](#d10-barcelona-district-and-neighbourhood)). The official form of a place name in Catalonia is the Catalan one (Llei 1/1998 de política lingüística, art. 18), the endonym the UN Group of Experts on Geographical Names (UNGEGN) recommends. A leading article is part of the name and stays lower case, e.g. "l'Hospitalet de Llobregat", "el Raval"; capitalising it at the start of a label is left to presentation.

Each place also keeps a sorting form, with the leading article moved to the end, e.g. "Hospitalet de Llobregat, l'": ICGC's `NOMMUNIIND` for municipalities, and the same rule applied to districts and neighbourhoods, whose source publishes none.

Rejected: translations into Spanish or English, since no source publishes them, Barcelona's neighbourhoods have no official Spanish names, and they would be kept by hand.

#### D12. Station names

A station's name is a datum of its operator, not a place name with an official form, so the model keeps it as published, only trimmed of leading and trailing spaces. Each system keeps its own style: Bicing's names are addresses in capitals, e.g. `C/ NÀPOLS, 82`, and AMBici's carry a prefix, e.g. `AMB - Diagonal I`.

Bicing localises `name` in 5 languages (`ca`, `es`, `en`, `fr`, `nl`), always with the same text, and 7 of its stations have names with stray spaces ([Bicing › `station_information`](../sources/bicing.md#station_information)). The model takes the `ca` entry, the language of [D11](#d11-place-names); AMBici publishes one plain string.

What would change it: Bicing's languages starting to differ; the `ca` entry is still the one kept.

Rejected: rewriting names into one common style, since it changes the operator's data with casing rules for Catalan that fail on edge cases, and the name would no longer match the one at the station and in the operator's app.

#### D13. Model labels

The values the model defines itself are in English, the project's language, and form a closed, documented domain: `Mechanical` and `Electric` for propulsion ([D8](#d8-vehicle-propulsion)), and `Not applicable` for district and neighbourhood outside Barcelona ([D10](#d10-barcelona-district-and-neighbourhood)). The public visualization shows them in Catalan, Spanish and English, translated with its interface texts; a closed domain lets it translate every value the model can produce. Place and station names are proper names and are never translated ([D11](#d11-place-names), [D12](#d12-station-names)).

Rejected: labels in Catalan, since the project defines everything in English and proper names in their own language do not make the data multilingual; translated label columns in gold, since a closed set of a few values is translated with the interface texts.

#### D14. Vocabulary of the measures

A measure that comes from a GBFS field takes its name and definition from GBFS 3.0 ([v3.0](https://raw.githubusercontent.com/MobilityData/gbfs/v3.0/gbfs.md)), the standard both sources publish, so that a measure with one name means the same in AMBici and Bicing (Kimball's conformed facts): e.g. `num_vehicles_available`, `num_docks_available`. A source takes the name only if its values meet the 3.0 definition; otherwise they are mapped to it, as with the status flags ([D7](#d7-station-status-flags)). AMBici's 2.3 fields map to 3.0 field by field ([s002 › 2](../spikes/s002-bicing-realtime-capture.md#2-common-model)); among the measures, only `num_bikes_available` is renamed, to `num_vehicles_available`.

A measure the model derives, such as occupancy, departures or arrivals, takes a name of its own in the same style, defined in [data-model.md](../data-model.md). The tables take the shape of the dimensional model, with native types: a timestamp in UTC, a name as plain text ([D12](#d12-station-names)).

What would change it: a GBFS version after 3.0 that renames or redefines a measure; whether the model follows it is then a new decision.

Rejected: business names of the model's own, such as `bikes_available` or `free_docks`, since every definition would be written and kept by the project with no external standard behind it.

#### D15. Disabled vehicles and docks

Bicing publishes `num_vehicles_disabled` and `num_docks_disabled`; AMBici publishes neither, since both are optional in GBFS 2.3. The model keeps Bicing's values as published and null for AMBici: a null is a value that is not known, while 0 would state that AMBici has none. Aggregates ignore nulls, so a total across both sources is not lowered by false zeros. AMBici's share of the fleet in use ([d002 › Q5](d002-requirements.md#guiding-questions)) is therefore an upper bound, since its disabled bikes cannot be subtracted.

What would change it: AMBici publishing either field; the model then takes its value.

Rejected: 0 for AMBici, since Q5 would compare a measured value with an invented one; leaving both measures out of the model, since Bicing's disabled vehicles, a mean of 2.9 per station against 7.5 available ([Bicing › `station_status`](../sources/bicing.md#station_status)), would then count as in use.

#### D16. Vehicles at an out-of-service station

GBFS 3.0 defines `num_vehicles_available` as the vehicles physically at the station, whether or not it is renting. AMBici's out-of-service stations meet it: they keep reporting their bikes, and the model keeps them as published. Bicing's do not: a station that goes out of service (`is_renting` and `is_returning` false) reports 0 vehicles while its bikes stay there ([Bicing › `station_status`](../sources/bicing.md#station_status)). The model therefore stores null as Bicing's `num_vehicles_available` while a station is out of service ([D14](#d14-vocabulary-of-the-measures)): the count is not known, and a 0 would count those bikes as in use in [d002 › Q5](d002-requirements.md#guiding-questions) and as departures in the stock movements.

Over 2026-10-14 to 10-26, only three combinations of the flags occurred: all true; installed but out of service; and, at one Bicing station, all false. AMBici's 8 out-of-service stations stayed so the whole period, so how AMBici reports a closing is not observed. Check in [spikes/d005-data-model](../../spikes/d005-data-model/README.md).

What would change it: Bicing reporting bikes while out of service, or AMBici reporting 0 at a closing, found by running that check again; the rule then follows each source's values.

Rejected: keeping Bicing's 0 and leaving each query to filter by `is_renting`, since every query would have to remember it and each closing would enter the stock movements as departures.

#### D17. Occupancy

A station's occupancy is the share of its usable docks taken by vehicles: `num_vehicles_available` over `num_vehicles_available` plus `num_docks_available`. It is what both feeds measure alike: it never exceeds 100%, leaves out Bicing's disabled vehicles and docks ([D15](#d15-disabled-vehicles-and-docks)), which no one can use, and its 0% and 100% are the empty and full runs of [d002 › Q3](d002-requirements.md#guiding-questions). Occupancy is a ratio, so the fact stores its two terms and it is computed at query time (Kimball's non-additive facts): a day's occupancy is the sum of vehicles over the sum of both terms, not the mean of the ratios. While a Bicing station is out of service, its vehicles are null ([D16](#d16-vehicles-at-an-out-of-service-station)), and so is its occupancy.

Full means no free dock. At AMBici's 57 stations with +P parking, a bike can still be left beside the docks when they are full, but no source gives a station's +P places ([AMBici › `nextbike-live.json`](../sources/ambici.md#nextbike-livejson)), so occupancy counts docks only. Check in [spikes/d005-data-model](../../spikes/d005-data-model/README.md).

What would change it: AMBici publishing each station's +P places; they then join the denominator.

Rejected: vehicles over `capacity`, since AMBici's bikes exceed it at 141 of 237 stations, 90 of them without +P ([AMBici › `station_status`](../sources/ambici.md#station_status)), and it would count Bicing's disabled docks as free; `capacity` plus +P places estimated from the FAQ's mean, about 20 per station, since it presents an assumption as a measure and leaves the stations without +P above 100%.

#### D18. AMBici's +P stations

The station dimension marks whether a station has +P parking, where a bike can be left beside the docks when they are full ([D17](#d17-occupancy)). Only nextbike's feed gives it, as `place_type` 27 or 33 ([AMBici › `nextbike-live.json`](../sources/ambici.md#nextbike-livejson)), and +P stations are added rarely, so that feed stays out of the pipeline. The list of +P stations is reference data: a CSV under version control that the pipeline loads as a table (a seed, in dbt's terms). It holds one row per +P station, sorted by `station_id`, with the station's name from `station_information` so a reader can check it. A station absent from the list has no +P, a new station of either source included, so the attribute is never null.

A script rebuilds the list on demand: it reads nextbike's feed once, matches it to AMBici's stations by station id, rewrites the CSV and prints the stations added and removed. The change enters by pull request, where Git's diff shows the same stations. The file holds no check date, so a run with no change leaves no diff.

What would change it: AMBici publishing +P in its GBFS feed; the model then takes it from there.

Rejected: capturing nextbike's feed in the pipeline, since it adds a non-GBFS feed with no stated licence for a list that rarely changes; editing the list by hand, since the script also finds the stations that stop being +P.

#### D19. Last reported time in the stock

Each row of the station stock keeps the station's `last_reported`, with its GBFS 3.0 name and definition ([D14](#d14-vocabulary-of-the-measures)): the last time the station reported its status to the operator's backend. The sources differ in what it carries:

- **Bicing:** a real time per station, whose age tells a frozen count from a current one. With `last_reported` 24 h old or more, a station's counts almost never change, even at stations in service ([Bicing › `station_status`](../sources/bicing.md#station_status)).
- **AMBici:** the feed time ([AMBici › `station_status`](../sources/ambici.md#station_status)), so it carries no information per station, and a frozen AMBici station cannot be told from one with no movement.

The stock's counts (`num_vehicles_available`, `num_vehicles_disabled`, `num_docks_available`, `num_docks_disabled`) are semi-additive, as set in [D4](#d4-business-processes-and-the-grain-of-the-stock): they are summed across stations, not over time. `last_reported` is non-additive.

What would change it: AMBici publishing a real time per station; the model takes it with no change.

Rejected: keeping only the capture time, since a frozen Bicing station would read as a station with no movement, and recovering it would mean reading bronze again.

#### D20. Zero counts in the stock by vehicle type

The stock by vehicle type is a dense periodic snapshot: in each capture, every station has a row for every vehicle type that any station of its system lists in `vehicle_types_available`, with `num_vehicles_available` 0 when it has none of that type. The measure is the `count` of each entry, under its GBFS 3.0 name ([D14](#d14-vocabulary-of-the-measures)). An average over time or an empty run per type then reads the table with no filling.

- **Bicing** lists its 4 types with stock at every station, with count 0 when there are none ([Bicing › `station_status`](../sources/bicing.md#station_status)).
- **AMBici** omits the types with count 0, and its list is empty at a station with no bikes ([AMBici › `station_status`](../sources/ambici.md#station_status)); the missing types get a row with 0. Only `196` and `204` ever appear ([profile › station_status_vehicle_types](../../spikes/d005-data-model/profile/ambici/station_status_vehicle_types.csv)).

A type that no station lists, such as AMBici's `420` or Bicing's `CHLOE` and `TRAILER` ([D8](#d8-vehicle-propulsion)), has no rows.

Rejected: a row only for counts above 0, since every average over time or empty run would have to fill the missing rows from the station stock, and a missed fill inflates the result.

#### D21. Per-type counts that do not add up to the station's

The station stock keeps the station's `num_vehicles_available` and the stock by vehicle type keeps each type's count, both as the source publishes them, even when the types do not add up to the station's count, as in 2.7% of Bicing's station items ([Bicing › `station_status`](../sources/bicing.md#station_status)). The data model states that the two may differ, and the share of station items where they do is a data quality indicator (DAMA's consistency).

Rejected: making them add up, by taking the station's count from the types or adjusting a type, since the model would publish a count no source gives and hide the source's inconsistency.

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
- A language selector in the public visualization (Catalan, Spanish, English) for its interface texts and the model's labels ([D13](#d13-model-labels)) — T041

### 1.6 Open questions

<!-- Optional. The decisions still to take about the what, in dependency order. Each one closes as a decision in Decided at framing and leaves the table, so it is empty at Spec approval. Questions about the how are Plan decisions. -->

| OQ | Question | Depends on | Notes |
|---|---|---|---|
| OQ2.3 | The facts of the stock by vehicle type, beyond [D20](#d20-zero-counts-in-the-stock-by-vehicle-type) and [D21](#d21-per-type-counts-that-do-not-add-up-to-the-stations): per-type counts at a Bicing station out of service ([D16](#d16-vehicles-at-an-out-of-service-station)) | D19, D8, D20 | The Bicing archive splits stock only into mechanical and electric |
| OQ2.4 | The facts of the stock movements: departures, arrivals, and how they relate to gaps in capture | D19 | During a suspension of rentals, such as Bicing's of 3 and 4 October, departures drop for lack of service, not of demand. How the null count of a Bicing station out of service ([D16](#d16-vehicles-at-an-out-of-service-station)) enters the movements, before and after it |
| OQ2.5 | The facts of the capture passes: lateness and completeness | D4 | — |
| OQ2.6 | Which d002 question gold answers, and with which table | OQ2.2–OQ2.5 | Handed to T040 by [d002 › Out of scope](d002-requirements.md). How gold and the visualization show a measure known for one source only, such as disabled vehicles ([D15](#d15-disabled-vehicles-and-docks)) |
| OQ3 | How each silver or gold column is traced back to the raw fields and the calculation it comes from, and a dictionary of the source fields with their official GBFS definition and how each source behaves (Kimball's detailed design) | OQ2.6 | Standards to weigh: the data dictionary with data profiling, and Kimball's detailed design worksheet per table, the base of the source-to-target mapping (column-level lineage). The source cards in `docs/sources/` already hold facts observed per source, with their evidence and date. Row-level lineage, to bronze and to the run, is decided in [d007](d007-pipeline-design.md). A count discrepancy per stock item, `capacity` minus available and disabled vehicles and docks, as a data quality indicator ([Bicing › `station_status`](../sources/bicing.md#station_status)); an idea, not decided |

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
