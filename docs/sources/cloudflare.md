# Source card — Cloudflare

Facts about the Cloudflare services this project uses: R2 as the object store for every medallion layer (s010 D2), and Workers Static Assets for the visualization ([s013 › D4](../spikes/s013-visualization-tool.md#d4-data-published-by-redeploying-on-workers-static-assets)). Living document: update it when something new is confirmed.

## Source

| | |
|---|---|
| Provider | Cloudflare |
| Services | R2, S3-compatible object storage; Workers, including Static Assets |
| Pricing pages | <https://developers.cloudflare.com/r2/pricing/>, <https://developers.cloudflare.com/workers/platform/pricing/> |
| Licence | Commercial service; Cloudflare's terms of service |

## Access

| | |
|---|---|
| R2 endpoint | S3-compatible API, `https://<account_id>.r2.cloudflarestorage.com` |
| R2 format | Objects of any format |
| R2 auth | R2 API token (access key ID and secret) |
| Workers deployment | `wrangler deploy`, with a Cloudflare API token |
| Update frequency | Pages updated by Cloudflare; R2 pricing last updated 2026-10-30 |

## Facts

Facts confirmed on 2026-11-03 come from a tool that summarizes pages, so their wording is not verbatim. "Not stated" means the pages read do not say it, which is not the same as Cloudflare denying it.

### Account and tokens

| Fact | Evidence | Confirmed |
|---|---|---|
| Any customer can create additional Free accounts, from the dashboard or the API. A limit of 5 accounts and a 7-day tenure come from a community post, not official | [Changelog](https://developers.cloudflare.com/changelog/post/2026-09-15-free-account-creation/); [community post](https://community.cloudflare.com/t/cloudflare-fundamentals-create-free-accounts-from-the-dashboard/945749) | 2026-11-03 |
| Worker roles can be scoped to individual Workers: a token uses the scope "Specified Workers". Editor can update and deploy a Worker but not delete it | [Changelog](https://developers.cloudflare.com/changelog/post/2026-09-15-granular-worker-permissions/) | 2026-11-03 |
| Deploying an existing Worker needs Editor scoped to it; creating a Worker needs Admin at the Workers product scope; changing routes needs Workers Routes Write on each zone | [Workers authorization](https://developers.cloudflare.com/workers/authorization/) | 2026-11-03 |
| Not stated: that a token scoped to one Worker can upload static assets | [Workers authorization](https://developers.cloudflare.com/workers/authorization/); [direct upload](https://developers.cloudflare.com/workers/static-assets/direct-upload/) | 2026-11-03 |
| The global API limit is 1,200 requests per 5 minutes per user; going over blocks all calls for 5 minutes | [API limits](https://developers.cloudflare.com/fundamentals/api/reference/limits/) | 2026-11-03 |

### R2: pricing and operations

| Fact | Evidence | Confirmed |
|---|---|---|
| Standard free tier per month: 10 GB-month storage, 1M Class A, 10M Class B operations, free egress | Pricing page | 2026-11-03 |
| The free tier is taken as per account: the pricing page does not say, but per bucket would make it unbounded (100,000 buckets included per account); per account is also the pessimistic case for the cost model | Inferred from the pricing page | 2026-10-31 |
| Standard prices above the free tier: $0.015/GB-month, $4.50 per million Class A, $0.36 per million Class B; no retrieval fee | Pricing page | 2026-11-03 |
| Infrequent Access: $0.010/GB-month, $9.00 per million Class A, $0.90 per million Class B, $0.01/GB retrieved, 30-day minimum, no free tier | Pricing table supplied by the owner | 2026-10-26 |
| Class A: ListBuckets, PutBucket, ListObjects, PutObject, CopyObject, CreateMultipartUpload, UploadPart, UploadPartCopy, CompleteMultipartUpload, ListMultipartUploads, ListParts, LifecycleStorageTierTransition, PutBucketEncryption, PutBucketCors, PutBucketLifecycleConfiguration | Pricing page | 2026-10-26 |
| Class B: HeadBucket, HeadObject, GetObject, UsageSummary, GetBucketEncryption, GetBucketLocation, GetBucketCors, GetBucketLifecycleConfiguration | Pricing page | 2026-10-26 |
| Free operations: DeleteObject, DeleteBucket, AbortMultipartUpload | Pricing page | 2026-10-26 |
| Storage is billed as the average of the daily peak over a 30-day billing period | Pricing page | 2026-10-26 |

### R2: security and access

| Fact | Evidence | Confirmed |
|---|---|---|
| API token levels: Admin Read & Write, Admin Read only, Object Read & Write (read, write, list), Object Read only. Object tokens can be scoped to specific buckets; Admin tokens cover every bucket | [Tokens](https://developers.cloudflare.com/r2/api/tokens/) | 2026-10-26 |
| API tokens scope to whole buckets, not key prefixes; no write-only or no-delete level. Temporary credentials can be scoped to prefixes and S3 actions | [Tokens](https://developers.cloudflare.com/r2/api/tokens/); [Temporary credentials](https://developers.cloudflare.com/r2/api/s3/temporary-credentials/) | 2026-10-26 |
| A token scoped to one bucket gets 403 `AccessDenied` on list, read and write in another bucket | [s010/F19](../spikes/s010-storage-table-format.md#4-findings) | 2026-10-28 |
| Bucket locks block deletes and overwrites, per bucket or prefix, for an age, until a date, or indefinitely; they override lifecycle rules; removing a rule needs an Admin-level token | [Bucket locks](https://developers.cloudflare.com/r2/buckets/bucket-locks/) | 2026-10-26 |
| A bucket lock lets an Object Read & Write token create new objects, but blocks their overwrite and delete with 409 `ObjectLockedByBucketPolicy` | [s010/F19](../spikes/s010-storage-table-format.md#4-findings) | 2026-10-28 |
| The S3 Object Lock API and object versioning (`PutBucketVersioning`) are not implemented | [S3 API](https://developers.cloudflare.com/r2/api/s3/api/) | 2026-10-26 |
| Buckets are private by default; public only through a custom domain or the r2.dev URL, both enabled explicitly and removable | [Public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/) | 2026-10-26 |
| Objects and metadata are encrypted at rest by default (AES-256), with keys managed by Cloudflare | [Data security](https://developers.cloudflare.com/r2/reference/data-security/) | 2026-10-26 |
| Conditional PutObject with `If-None-Match: *` is enforced under a race: one PUT wins, the other gets 412 `PreconditionFailed`. delta-rs relies on it for safe commits with `aws_conditional_put: "etag"` and no external lock | [s010/F1](../spikes/s010-storage-table-format.md#4-findings), [s010/F19](../spikes/s010-storage-table-format.md#4-findings) | 2026-10-28 |

### R2: metrics

| Fact | Evidence | Confirmed |
|---|---|---|
| The GraphQL Analytics API (`r2OperationsAdaptiveGroups`) gives operations per bucket, operation and status, filtered by a `datetime` range; failed requests show as `userError` | [s010/#36](../spikes/s010-storage-table-format.md#decision-log), [s010/#37](../spikes/s010-storage-table-format.md#decision-log), [s010/#39](../spikes/s010-storage-table-format.md#decision-log) | 2026-10-28 |
| Operation metrics are sampled: the total matches an exact count within 0.02%, but per-object counts do not | [s010/F14](../spikes/s010-storage-table-format.md#4-findings) | 2026-10-28 |
| The dashboard's operation figures are not exact: its summary and charts differ, and neither its day boundary nor an operation breakdown is documented | [s010/#36](../spikes/s010-storage-table-format.md#decision-log) | 2026-10-28 |

### Workers Static Assets

| Fact | Evidence | Confirmed |
|---|---|---|
| Requests for static assets are free and unlimited, and storing them has no extra cost | [Billing and limitations](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/) | 2026-11-03 |
| Free plan: 20,000 files per version, 25 MiB per file | [Workers limits](https://developers.cloudflare.com/workers/platform/limits/) | 2026-11-03 |
| Not stated: any limit on the number of deployments or versions. Wrangler lists only the 100 most recent, which limits the view, not creation. Nothing found discourages redeploying to refresh data; the terms were not read | [Workers limits](https://developers.cloudflare.com/workers/platform/limits/); [versions and deployments](https://developers.cloudflare.com/workers/configuration/versions-and-deployments/) | 2026-11-03 |
| A deployment sends code and assets in one operation, and reaches 100% of traffic in a single step. Not stated: that no request gets a 5xx during it | [Static Assets](https://developers.cloudflare.com/workers/static-assets/); [versions and deployments](https://developers.cloudflare.com/workers/configuration/versions-and-deployments/) | 2026-11-03 |
| A deployment makes one upload-session POST, one or more upload POSTs and one script PUT. Wrangler's exact call count is not stated | [Direct upload](https://developers.cloudflare.com/workers/static-assets/direct-upload/) | 2026-11-03 |
| A missing asset gets a 404, or the nearest `404.html` with a 404 status under `404-page`. Not stated: whether old assets are kept for a time after a deployment | [Static Assets](https://developers.cloudflare.com/workers/static-assets/); [static site generation](https://developers.cloudflare.com/workers/static-assets/routing/static-site-generation/) | 2026-11-03 |
| The default header is `public, max-age=0, must-revalidate`, with an ETag that hashes the file, so browsers should revalidate on every use (inferred). Assets are cached with tiered caching. Not stated: how soon a same-named file refreshes after a deployment | [Headers](https://developers.cloudflare.com/workers/static-assets/headers/); [Static Assets](https://developers.cloudflare.com/workers/static-assets/) | 2026-11-03 |

### Workers with the Cache API (fallback of the visualization)

| Fact | Evidence | Confirmed |
|---|---|---|
| Free plan: 100,000 Worker requests a day, resetting at 00:00 UTC. Past it the route gets Error 1027, or bypasses the Worker if set to fail open | [Workers limits](https://developers.cloudflare.com/workers/platform/limits/) | 2026-11-03 |
| The Cache API allows 50 calls per request, shared with the subrequest quota, and objects up to 512 MB | [Workers limits](https://developers.cloudflare.com/workers/platform/limits/) | 2026-11-03 |
| A cache hit avoids R2 operations, as the billing page says. R2's own pricing page does not address caching | [How charges accrue](https://developers.cloudflare.com/billing/understand/how-charges-accrue/) | 2026-11-03 |
