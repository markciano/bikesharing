---
status: Proposed
date: 2026-10-30
---

# Storage security baseline

## Context and problem statement

R2 holds every layer ([ADR-0019](0019-own-lakehouse-on-cloudflare-r2.md)), including the only copy of bronze, which cannot be rebuilt ([ADR-0021](0021-retention-per-layer.md)). Its credentials give access to both the data and the bill. Threats are listed with STRIDE:

| Threat | Impact |
|---|---|
| Leaked credentials | An attacker deletes or overwrites data, or drives up cost with requests (denial of wallet) |
| A pipeline bug writes to bronze | Bronze cannot be rebuilt, so the damage is permanent |
| A bucket is made public by mistake | Anyone can list and read all data, and every read costs |

- R2 API tokens scope to whole buckets, not key prefixes ([R2 source card](../sources/r2-storage.md)).
- R2 has no object versioning.
- R2 has no write-only token.
- Bronze holds prefixes that only receive new objects and cannot be rebuilt, and one working index that capture rewrites on every pass and can rebuild from them.
- Several components touch storage: capture, the owner's one-off history upload, the pipeline, the visualization, and spike probes.

## Considered Options

Each option is judged on what a leaked credential or a pipeline bug can reach, protection of bronze, and the number of buckets and tokens to manage.

### 1. Two buckets, one token per component, bronze locked

A bronze bucket and a lakehouse bucket for silver and gold; each component gets its own token with only the access it needs (least privilege, NIST SP 800-53 AC-6); bronze's append-only prefixes carry a bucket lock.

- Pros:
  - a leak or a bug reaches only one component's access;
  - the pipeline cannot write to bronze;
  - the lock blocks delete and overwrite of bronze.
- Cons:
  - more tokens to manage;
  - the lock also blocks a legitimate rewrite of a key.

### 2. One token for everything

A single token with read and write on every bucket.

- Pros:
  - simplest to set up and rotate.
- Cons:
  - a single leak or pipeline bug puts bronze at risk.

### 3. One bucket per layer

Bronze, silver and gold each in their own bucket, with tokens per component.

- Pros:
  - the visualization could read gold alone.
- Cons:
  - more buckets and tokens, with no current need for gold on its own.

## Decision Outcome

**Chosen option:** 1. Two buckets, one token per component, bronze locked

Since tokens scope to whole buckets, a read-only bronze needs its own bucket; silver and gold share one because they have the same access pattern. Per-component tokens bound the damage of a leak, and the lock is the only guard against losing bronze because R2 has no versioning.

Why not the others:

- One token for everything: it leaves bronze, the only data that cannot be rebuilt, one mistake away from loss.
- One bucket per layer: it adds buckets and tokens for an access split nothing needs yet; gold can move to its own bucket when it does.

Rules:

- Each component MUST have its own token with only the access it needs. A leaked credential then reaches only what that component can do ([d002/R15](../designs/d002-requirements.md#requirements)).
- Bronze MUST live in its own bucket, read-only for the pipeline. Tokens scope to whole buckets, so a pipeline bug cannot touch bronze ([d002/R17](../designs/d002-requirements.md#requirements)).
- Bronze prefixes that only receive new objects and cannot be rebuilt MUST carry an indefinite bucket lock against delete and overwrite (e.g. `raw/`, `logs/` and the history archives). They are the data whose loss is permanent ([d002/R16](../designs/d002-requirements.md#requirements)).
- Prefixes that can be rebuilt (e.g. capture's working index, `state/`) SHOULD stay unlocked. They are rewritten on every pass.
- Buckets MUST stay private, and any public access is a separate decision. A public bucket exposes all data and bills every read ([d002/R18](../designs/d002-requirements.md#requirements)).
- The Admin token, the only one that can remove a lock rule, MUST be held by the owner and used only for the retention review ([ADR-0021](0021-retention-per-layer.md)). It is the one credential that can undo bronze's protection.
- Secrets MUST live in `.env`, never in code. A secret in the repository is a leaked credential.

Access per component:

| Component | Bronze bucket | Lakehouse bucket |
|---|---|---|
| Capture | Read and write (R2 has no write-only token; capture reads its working index) | None |
| Owner (one-off history upload) | Read and write | None |
| Pipeline | Read | Read and write |
| Visualization | None | Read |
| Spike probes | None | None; a separate test bucket only |

**Scope:** Buckets, tokens and the bucket lock in R2. It does not cover the security of capture's runtime ([ADR-0011](0011-cloudflare-workers-r2-for-realtime-capture.md)) or how gold is served to the public.

### Consequences

#### Positive

- **Verified on R2:** a token scoped to a test bucket cannot list, read or write the production bucket, and the lock blocks overwrite and delete even by an Object Read & Write token, which R2's docs did not state ([s010/F19](../spikes/s010-storage-table-format.md#4-findings)).
- **Bounded damage:** a leak or a bug reaches one component's access only.

#### Negative

- **Capture can read bronze:** R2 has no write-only token.
- **The lock is the only guard:** R2 has no object versioning, so bronze depends on the lock and on the Admin token staying with the owner.
- **The lock blocks rewrites too:** a capture retry that rewrites a key would fail. TODO(T039): before the lock is enabled, confirm that capture writes each key under its locked prefixes once ([ADR-0012](0012-collectors-decoupled-by-output-contract.md) key layout).
- **Buckets cannot be renamed:** TODO(production design): capture's existing bucket keeps a spike name; a production name means copying the locked prefixes to a new bucket before the lock is enabled.
- **More tokens to manage:** one per component, each to create and rotate.
- **Private by default is not tested:** it rests on R2's documented default.

## More information

- Framing decision: [s010/D7](../spikes/s010-storage-table-format.md#d7-storage-security-baseline); outcome in [s010 Decisions to record](../spikes/s010-storage-table-format.md#decisions-to-record); security requirements in [s010 Security requirements](../spikes/s010-storage-table-format.md#security-requirements).
