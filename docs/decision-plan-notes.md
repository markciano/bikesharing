# Decision plan notes (provisional)

TODO: delete after the decision-plan session.

Input for the session that orders the project's decisions. Collected while running s009, which was discarded because it assumed a processing engine and storage format that were never decided. Nothing here is a decision.

## Standard decision order

Data platform decisions follow their dependencies, each taken at the last responsible moment:

1. Requirements and data characteristics: volume, frequency, consumers, portfolio goal.
2. Storage and table format: where data lives and in which format (Delta, Iceberg, plain Parquet).
3. Processing engine: Spark, or a single-node engine such as DuckDB or Polars.
4. Execution target: where the pipeline runs; depends on what the engine needs.
5. Visualization: depends on where the consumption layer lives and whether it must be public.

## Topics to decide

Raised by the owner; open, not decided:

- ADR-0003 and ADR-0004: whether they still hold.
- ADR-0010: confirm what it states (s009 summarised it as "code runs in Python"; the owner reads it as "raw data lands as is and is processed in the pipeline").
- T007, T025 and T033: whether they are removed or reframed.
- T022: renamed to cover the decision plan.

## Findings with official sources

Accessed 2026-10-23.

- **R2 S3 compatibility:** R2 supports ListObjectsV2, multipart upload and atomic conditional PutObject (`If-None-Match`); some S3 operations are not implemented (bucket versioning, policies, ACLs, tagging). Region is `auto`. <https://developers.cloudflare.com/r2/api/s3/api/>
- **R2 endpoint:** `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`. <https://developers.cloudflare.com/r2/examples/aws/aws-cli/>
- **R2 Data Catalog:** Cloudflare's native catalog for R2 uses Apache Iceberg; its Spark examples use Iceberg, and no official Cloudflare example uses Delta Lake. <https://developers.cloudflare.com/r2/data-catalog/config-examples/spark-python/>
- **Delta Lake on S3-compatible storage:** works by default when all writes to a table come from a single driver; multi-writer setups need DynamoDB (AWS only). No section on R2. <https://docs.delta.io/latest/delta-storage.html>
- **Spark requirements:** runs on any platform with a supported Java (17/21/25), x86_64 and ARM64; "can run well with anywhere from 8 GiB" of memory per machine; driver memory defaults to 1 GB. Delta 4.x supports Spark up to 4.1. <https://spark.apache.org/docs/latest/>, <https://spark.apache.org/docs/latest/hardware-provisioning.html>, <https://docs.delta.io/latest/releases.html>
- **Volume vs Spark:** Spark is built to spread work across machines for data that does not fit in one. The project's volume (estimated, not measured: millions of rows per year) fits in a laptop's memory, so Spark's fixed overhead would dominate. Single-node engines are the usual fit for this size; Spark's value here is portfolio.

## Open questions

- Measure the real data volume in R2 (files, size, rows per day) instead of estimating it.
- R2 free-tier storage and operations (reads, writes, listings) for the whole pipeline, and whether only part of the history can be kept in R2.
- Once engine and format are chosen: a minimal script that reads `json.gz` from R2 and writes and reads a table in the chosen format, before the pipeline design.
- Whether Iceberg (native to R2 Data Catalog) is an option next to Delta in the storage-format decision.
