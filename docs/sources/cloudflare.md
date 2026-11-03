# Source card — Cloudflare R2 (object storage)

Facts about the object store used for every medallion layer (s010 D2). Living document: update it when something new is confirmed.

## Source

| | |
|---|---|
| Provider | Cloudflare |
| Service | R2, S3-compatible object storage |
| Pricing page | <https://developers.cloudflare.com/r2/pricing/> |
| Licence | Commercial service; Cloudflare's terms of service |

## Access

| | |
|---|---|
| Endpoint | S3-compatible API, `https://<account_id>.r2.cloudflarestorage.com` |
| Format | Objects of any format |
| Auth | R2 API token (access key ID and secret) |
| Update frequency | Pricing page updated by Cloudflare; last update 2026-10-01 |

## Facts

| Fact | Evidence | Confirmed |
|---|---|---|
| Standard free tier per month: 10 GB-month storage, 1M Class A, 10M Class B operations, free egress | Pricing page | 2026-10-26 |
| The free tier is taken as per account: the pricing page does not say, but per bucket would make it unbounded (100,000 buckets included per account); per account is also the pessimistic case for the cost model | Inferred from the pricing page | 2026-10-31 |
| Standard prices above the free tier: $0.015/GB-month, $4.50 per million Class A, $0.36 per million Class B; no retrieval fee | Pricing page | 2026-10-26 |
| Infrequent Access: $0.010/GB-month, $9.00 per million Class A, $0.90 per million Class B, $0.01/GB retrieved, 30-day minimum, no free tier | Pricing table supplied by the owner | 2026-10-26 |
| Class A: ListBuckets, PutBucket, ListObjects, PutObject, CopyObject, CreateMultipartUpload, UploadPart, UploadPartCopy, CompleteMultipartUpload, ListMultipartUploads, ListParts, LifecycleStorageTierTransition, PutBucketEncryption, PutBucketCors, PutBucketLifecycleConfiguration | Pricing page | 2026-10-26 |
| Class B: HeadBucket, HeadObject, GetObject, UsageSummary, GetBucketEncryption, GetBucketLocation, GetBucketCors, GetBucketLifecycleConfiguration | Pricing page | 2026-10-26 |
| Free operations: DeleteObject, DeleteBucket, AbortMultipartUpload | Pricing page | 2026-10-26 |
| Storage is billed as the average of the daily peak over a 30-day billing period | Pricing page | 2026-10-26 |
| API token levels: Admin Read & Write, Admin Read only, Object Read & Write (read, write, list), Object Read only. Object tokens can be scoped to specific buckets; Admin tokens cover every bucket | [Tokens](https://developers.cloudflare.com/r2/api/tokens/) | 2026-10-26 |
| API tokens scope to whole buckets, not key prefixes; no write-only or no-delete level. Temporary credentials can be scoped to prefixes and S3 actions | [Tokens](https://developers.cloudflare.com/r2/api/tokens/); [Temporary credentials](https://developers.cloudflare.com/r2/api/s3/temporary-credentials/) | 2026-10-26 |
| Bucket locks block deletes and overwrites, per bucket or prefix, for an age, until a date, or indefinitely; they override lifecycle rules; removing a rule needs an Admin-level token | [Bucket locks](https://developers.cloudflare.com/r2/buckets/bucket-locks/) | 2026-10-26 |
| The S3 Object Lock API and object versioning (`PutBucketVersioning`) are not implemented | [S3 API](https://developers.cloudflare.com/r2/api/s3/api/) | 2026-10-26 |
| Buckets are private by default; public only through a custom domain or the r2.dev URL, both enabled explicitly and removable | [Public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/) | 2026-10-26 |
| Objects and metadata are encrypted at rest by default (AES-256), with keys managed by Cloudflare | [Data security](https://developers.cloudflare.com/r2/reference/data-security/) | 2026-10-26 |
| Conditional PutObject with `If-None-Match: *` is enforced under a race: one PUT wins, the other gets 412 `PreconditionFailed`. delta-rs relies on it for safe commits with `aws_conditional_put: "etag"` and no external lock | [s010/F1](../spikes/s010-storage-table-format.md#4-findings), [s010/F19](../spikes/s010-storage-table-format.md#4-findings) | 2026-10-28 |
| A bucket lock lets an Object Read & Write token create new objects, but blocks their overwrite and delete with 409 `ObjectLockedByBucketPolicy` | [s010/F19](../spikes/s010-storage-table-format.md#4-findings) | 2026-10-28 |
| A token scoped to one bucket gets 403 `AccessDenied` on list, read and write in another bucket | [s010/F19](../spikes/s010-storage-table-format.md#4-findings) | 2026-10-28 |
| The GraphQL Analytics API (`r2OperationsAdaptiveGroups`) gives operations per bucket, operation and status, filtered by a `datetime` range; failed requests show as `userError` | [s010/#36](../spikes/s010-storage-table-format.md#decision-log), [s010/#37](../spikes/s010-storage-table-format.md#decision-log), [s010/#39](../spikes/s010-storage-table-format.md#decision-log) | 2026-10-28 |
| Operation metrics are sampled: the total matches an exact count within 0.02%, but per-object counts do not | [s010/F14](../spikes/s010-storage-table-format.md#4-findings) | 2026-10-28 |
| The dashboard's operation figures are not exact: its summary and charts differ, and neither its day boundary nor an operation breakdown is documented | [s010/#36](../spikes/s010-storage-table-format.md#decision-log) | 2026-10-28 |

TODO(T040): confirm with R2's per-operation metrics (GraphQL Analytics) the class of conditional PutObject, ListObjectsV2 and DeleteObjects, which the pricing page does not name; s010 confirmed only class totals ([s010 › F14](../spikes/s010-storage-table-format.md#4-findings)).
