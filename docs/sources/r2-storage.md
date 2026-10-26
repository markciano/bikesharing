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

TODO: confirm in s010 probe C (bucket metrics) the class of conditional PutObject, ListObjectsV2 and DeleteObjects, which the pricing page does not name.
TODO: confirm whether the free tier is per account or per bucket; the pricing page does not say.
TODO: confirm in s010 probe C whether a bucket lock blocks a delete made with an Object Read & Write token; the bucket locks page does not say.
