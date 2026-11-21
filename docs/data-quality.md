# Data quality

The quality catalog of silver and gold: the runtime rules, checked on real data in every run, and the quality indicators, measured over time ([d007 › D4](designs/d007-pipeline-design.md#d4-data-quality-in-four-classes)). How each table and value is built, and what the model's documents hold, live in [data-model.md › Data contract](data-model.md#data-contract). Each item cites the decision it applies, and the test or alert that checks it cites the item's ID. IDs are flat, with a prefix per class, and never reused: `DQR` for a runtime rule and `DQM` for a quality indicator, a quality measure in ISO/IEC 25024. Dimensions follow DAMA-DMBOK: accuracy, completeness, consistency, timeliness, validity and uniqueness.

## Schema

Every run checks each column of silver and gold against its schema, the type, nullability and accepted values of its row in its table's worksheet. A schema carries no ID and is not repeated here ([d007 › #1](designs/d007-pipeline-design.md#22-decision-summary)).

A row that fails its schema is quarantined: it is written to the quarantine table with the check it failed and the bronze object it comes from, the failure is logged in the run's events, and the rest of its batch publishes. When a new code version is deployed, each bronze object with rows in quarantine is processed again, adding only the rows silver and gold do not hold yet ([d007 › #1](designs/d007-pipeline-design.md#22-decision-summary)). DQR13 counts the quarantined rows as accounted for. TODO(T060.5): until the quarantine table is built, a row that fails its schema halts its batch, which stays pending ([d008 › D9](designs/d008-pipeline-platform-and-walking-skeleton.md#d9-a-failed-batch-halts-the-pipeline-until-t0605)).

## Severity

A runtime rule's severity follows who causes its failure ([d007 › D4](designs/d007-pipeline-design.md#d4-data-quality-in-four-classes)):

- **error:** a rule on the pipeline's own logic. Following Write-Audit-Publish, a batch that fails commits nothing to silver and gold and is set aside until a new code version; a file that fails is not deployed, and the run ends with no failure signal. The page keeps the last file that passed, and the failure is logged in the run's events ([d007 › #9](designs/d007-pipeline-design.md#22-decision-summary)). TODO(T060.5): until batches can be set aside, a batch that fails stays pending and fails the run ([d008 › D9](designs/d008-pipeline-platform-and-walking-skeleton.md#d9-a-failed-batch-halts-the-pipeline-until-t0605)).
- **warn:** a rule on a provider's data. The failure is logged and the batch is committed.

## Runtime rules

### Facts

| ID | Rule | Dimension | Severity |
|---|---|---|---|
| DQR1 | The station stock shall hold one row per station and capture ([d005 › D4](designs/d005-data-model.md#d4-business-processes-and-the-grain-of-the-stock)). | Uniqueness | error |
| DQR2 | The station stock shall never update or delete a row once written ([d005 › D4](designs/d005-data-model.md#d4-business-processes-and-the-grain-of-the-stock)). | Consistency | error |
| DQR3 | The stock by vehicle type shall hold one row per station, capture and vehicle type ([d005 › D4](designs/d005-data-model.md#d4-business-processes-and-the-grain-of-the-stock)). | Uniqueness | error |
| DQR4 | The stock movements shall hold one row per station and pair of consecutive counts with departures or arrivals ([d005 › D4](designs/d005-data-model.md#d4-business-processes-and-the-grain-of-the-stock)). | Uniqueness | error |
| DQR5 | Each row of the stock movements shall hold departures or arrivals above 0, never both ([d005 › D22](designs/d005-data-model.md#d22-departures-and-arrivals)). | Validity | error |
| DQR6 | For each station and day, the stock movements' arrivals minus departures shall equal the sum, over the pairs of consecutive real-time counts whose later count falls on that day, of each rise in the vehicles at the station with `is_returning` true in both counts and each drop, as a negative, with `is_renting` true in both ([d005 › D22](designs/d005-data-model.md#d22-departures-and-arrivals), [D23](designs/d005-data-model.md#d23-movements-across-gaps-in-capture), [D24](designs/d005-data-model.md#d24-movements-at-an-out-of-service-station)). | Consistency | error |
| DQR10 | Every fact row shall reference an existing row of each dimension its process has in the bus matrix ([d005 › D5](designs/d005-data-model.md#d5-conformed-dimensions)). | Consistency | error |

### Dimensions

| ID | Rule | Dimension | Severity |
|---|---|---|---|
| DQR7 | The system dimension shall hold one row per system: AMBici and Bicing ([d005 › D5](designs/d005-data-model.md#d5-conformed-dimensions)). | Uniqueness | error |
| DQR8 | The date dimension shall hold one row per day ([d005 › D5](designs/d005-data-model.md#d5-conformed-dimensions)). | Completeness | error |
| DQR9 | The time-of-day dimension shall hold one row per minute of the day ([d005 › D5](designs/d005-data-model.md#d5-conformed-dimensions)). | Completeness | error |

### Runs and published files

| ID | Rule | Dimension | Severity |
|---|---|---|---|
| DQR11 | If a bronze feed adds or drops a field of those the model reads ([data-model.md › RDM2, RDM6](data-model.md#model-as-a-whole)), then the run shall log a schema drift ([d007 › D4](designs/d007-pipeline-design.md#d4-data-quality-in-four-classes)). | Validity | warn |
| DQR12 | If a capture of a system lists fewer than 90% of the median number of stations of that system's captures in the 24 h before its capture instant, then the run shall log a volume drop; with fewer than 60 such captures, the rule is not evaluated and the run logs it as such ([d007 › D4](designs/d007-pipeline-design.md#d4-data-quality-in-four-classes), [d008 › D4](designs/d008-pipeline-platform-and-walking-skeleton.md#d4-volume-drop-against-a-rolling-median)). | Completeness | warn |
| DQR13 | The rows a run adds to silver and gold shall match the items it reads from bronze, by count, or by total in a gold table that aggregates ([d007 › D4](designs/d007-pipeline-design.md#d4-data-quality-in-four-classes)). | Completeness | error |
| DQR14 | Each file the pipeline publishes shall match its JSON Schema before it is deployed ([d007 › D2](designs/d007-pipeline-design.md#d2-visualization-after-all-slices), [D4](designs/d007-pipeline-design.md#d4-data-quality-in-four-classes)). | Validity | error |

## Quality indicators

Each indicator is kept because it prompts an action, on capture, on a provider or on the model's reference data, or because it measures a provider's quality ([d002 › Q2](designs/d002-requirements.md#guiding-questions)); Why says which. A target's initial value comes from what the source cards measured on real captures. DQM4, DQM5, DQM8 and DQM9 form each provider's scorecard. Built in says where each indicator is built: a gold table when it measures silver and gold, the observability of the pipeline and capture when it measures something outside the model ([d007 › D4](designs/d007-pipeline-design.md#d4-data-quality-in-four-classes)). Rows are ordered by Built in, observability last. Each target is reviewed against weeks of production indicators by the child that closes it ([d007 › #11](designs/d007-pipeline-design.md#22-decision-summary)). TODO(T060.3): review DQM4's target.

| ID | Indicator | Dimension | Target | Built in | Why |
|---|---|---|---|---|---|
| DQM7 | The model shall measure each system's completeness as the share of UTC minutes with at least one real-time capture in the station stock, counted on each capture's instant, with a minute of two captures counted once ([d005 › D26](designs/d005-data-model.md#d26-timeliness-and-completeness-of-the-feeds), [D33](designs/d005-data-model.md#d33-local-calendar-keys)). | Completeness | At least 99.5% of the minutes of each calendar month ([d004 › D6](designs/d004-bronze-data-capture.md#d6-capture-completeness-target)) | Capture completeness | A missed month leads the owner to review its cause in capture |
| DQM4 | The model shall measure the share of real-time station items whose per-type counts in the stock by vehicle type do not add up to the station's `num_vehicles_available` in the station stock, over the items whose `num_vehicles_available` is not null ([d005 › D16](designs/d005-data-model.md#d16-vehicles-at-an-out-of-service-station), [D21](designs/d005-data-model.md#d21-per-type-counts-that-do-not-add-up-to-the-stations)). | Consistency | At most 3% of station items per month (Bicing 2.7%, [bicing › `station_status`](sources/bicing.md#station_status)) | Provider scorecard | Measures a provider's quality |
| DQM5 | The model shall take a Bicing count of the station stock as frozen when its `last_reported` is older than its capture time by more than the threshold that the design of the slice building the measure fixes ([d005 › D19](designs/d005-data-model.md#d19-last-reported-time-in-the-stock), [D25](designs/d005-data-model.md#d25-lack-of-service-and-frozen-counts), [D27](designs/d005-data-model.md#d27-gold-per-question)). | Timeliness | At most 15 stations frozen in one capture (15 installed stations unreported for more than 24 h, [bicing › `station_status`](sources/bicing.md#station_status)) | Provider scorecard | Measures a provider's quality; a published file marks a frozen count to the visitor |
| DQM8 | The model shall measure each capture's lateness as its capture time minus its response's `last_updated` ([d005 › D26](designs/d005-data-model.md#d26-timeliness-and-completeness-of-the-feeds)). | Timeliness | AMBici: at most 64 s per capture ([ambici › General facts](sources/ambici.md#general-facts)); Bicing: —, its `last_updated` is the request time ([bicing › General facts](sources/bicing.md#general-facts)) | Provider scorecard | Measures a provider's quality |
| DQM9 | The model shall measure the share of station items whose vehicles and docks exceed the station's `capacity`, leaving out AMBici's +P stations ([data-model.md › TR44](data-model.md#dimensions)), whose bikes in +P spaces exceed it by design ([d007 › D4](designs/d007-pipeline-design.md#d4-data-quality-in-four-classes)). | Consistency | At most 3% of station items per month in AMBici (3%, +P stations included, [ambici › `station_status`](sources/ambici.md#station_status)) and 4% in Bicing (3.8%, [bicing › `station_status`](sources/bicing.md#station_status)) | Provider scorecard | Measures a provider's quality |
| DQM1 | When a station whose post code comes from ICGC first appears or its coordinates change, if the 5 nearest addresses ICGC returns do not share one post code, then the review table shall hold a row for that station version ([d005 › D5](designs/d005-data-model.md#d5-conformed-dimensions), [D6](designs/d005-data-model.md#d6-ambicis-post-code)). | Accuracy | TODO(T060.6): from the review table's first rows | Review table | The owner confirms or corrects the station's post code |
| DQM2 | If a station's municipality, taken from AMBici's region or as Barcelona for Bicing, differs from the one that contains its coordinates, then the review table shall hold a row for that station version ([d005 › D5](designs/d005-data-model.md#d5-conformed-dimensions), [D9](designs/d005-data-model.md#d9-station-municipality)). | Consistency | TODO(T060.6): from the review table's first rows | Review table | The owner confirms or corrects the station's municipality |
| DQM3 | If a Bicing station's district or neighbourhood codes from `cross_street` differ from those of [data-model.md › TR38](data-model.md#dimensions), then the review table shall hold a row for that station version ([d005 › D5](designs/d005-data-model.md#d5-conformed-dimensions), [D10](designs/d005-data-model.md#d10-barcelona-district-and-neighbourhood)). | Consistency | TODO(T060.6): from the review table's first rows | Review table | The owner confirms or corrects the station's district and neighbourhood |
| DQM10 | The model shall measure the time since the capture of the data in each file the page serves ([d007 › D4](designs/d007-pipeline-design.md#d4-data-quality-in-four-classes)). | Timeliness | At most one cadence plus one run ([d002 › R3](designs/d002-requirements.md#requirements)) | Observability (T060.2) | The owner checks the pipeline and the deployment when the page serves old data |
| DQM11 | The solution shall measure the minutes with no capture of each feed, split by cause: capture's own failure or a gap in the provider's feed ([d002 › R14](designs/d002-requirements.md#requirements), [d007 › D4](designs/d007-pipeline-design.md#d4-data-quality-in-four-classes)). | Completeness | Set by T060.2 | Observability (T060.2) | The owner acts on capture for its own gaps, and on nothing for a provider's |
