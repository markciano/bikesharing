---
status: Accepted
date: 2026-11-06
---

# Cloud resource naming

## Context and problem statement

The project creates resources in Cloudflare (R2 buckets, Workers, API tokens) and will create more in Modal ([ADR-0027](0027-modal-as-execution-platform.md)). Their names show in consoles shared with anything else in the same accounts, in bindings and in tokens' scopes. Some cannot be changed later: an R2 bucket cannot be renamed, and moving its data under a bucket lock is not possible ([ADR-0023](0023-storage-security-baseline.md)).

The first resources were named during spikes, one by one: the bucket `bikesharing-capture-spike` and the Worker `capture-v4` follow no common pattern. Without a rule, each design names its own resources, and a name that turns out wrong in a bucket can only be fixed by copying its data before the lock is enabled.

## Considered Options

### 1. One pattern for every cloud resource

Every resource is named `bikesharing-<name>`; buckets are named after their content, compute after its component, tokens after their component and purpose.

- Pros:
  - One prefix finds every project resource in any console.
  - A bucket's name does not depend on which component uses it, so it survives changes of components.
- Cons:
  - Names are longer than the provider's defaults.

### 2. A pattern for buckets only

Buckets are named `bikesharing-<content>`; other resources are named by each design.

- Pros:
  - Covers the only resources that cannot be renamed.
- Cons:
  - Workers, apps and tokens can still drift apart, and a token's name may not tell what it reaches.

## Decision Outcome

**Chosen option:** 1. One pattern for every cloud resource

Fixing the pattern now, with few resources, costs nothing; later it means renaming what can be renamed and copying what cannot. Naming buckets by content keeps them stable when the components that write or read them change.

Why not the others:

- A pattern for buckets only: tokens are where a clear name matters most, when deciding what a leaked one reaches.
- No convention: it is how the spike's names came about.

Rules:

- Every cloud resource the project creates MUST be named `bikesharing-<name>`, in lowercase letters, digits and hyphens, at most 63 characters. 63 is R2's limit for bucket names, the strictest the project uses.
- A bucket MUST be named after its content, not after the layer or the component that uses it: `bikesharing-bronze`, `bikesharing-lakehouse`. A layer prefix inside a bucket (e.g. `silver/`, `gold/`) is used only when the bucket holds more than one layer.
- The first prefix inside a bucket SHOULD name the kind of content (e.g. `raw/`, `logs/`, `state/`). The bucket lock applies per prefix, so content with different lock rules needs its own prefix ([ADR-0023](0023-storage-security-baseline.md)).
- A compute resource (a Worker, a Modal app) MUST be named `bikesharing-<component>`, where `<component>` is the `component` field of its logs ([ADR-0036](0036-log-convention-across-components.md)): `bikesharing-capture` for `capture`.
- An API token MUST be named `bikesharing-<component>-<purpose>` (e.g. `bikesharing-capture-deploy`). Its name then tells what it reaches when it is reviewed or revoked.
- A temporary resource, such as a probe's or a spike's, MUST carry the task that creates it, `bikesharing-<tnnn>-<purpose>` (e.g. `bikesharing-t039-write-once`), and is deleted when that task closes.
- Names carry no environment segment: the project has one environment, production.

**Scope:** Resources the project creates in Cloudflare, Modal and any later provider: buckets, Workers, apps, API tokens. It does not cover what lives inside a resource beyond a bucket's first prefix (keys follow [ADR-0012](0012-collectors-decoupled-by-output-contract.md)), the names of bindings, secrets or environment variables, nor the repository's files (`CLAUDE.md`).

### Consequences

#### Positive

- **One pattern:** any project resource is found and recognised by its name in every console.
- **Stable buckets:** a bucket's name does not change when its components do.
- **Clear tokens:** a token's name tells which component holds it and what for.

#### Negative

- **Longer names:** every name carries the `bikesharing-` prefix, longer than the providers' defaults.
- **A second environment changes this ADR:** names would then need an environment segment.

## More information

- The convention was set in [d004 › D1](../designs/d004-bronze-data-capture.md#d1-bronze-bucket-and-key-convention).
- `bikesharing-capture-spike` and `capture-v4` predate this ADR; T039 deletes them rather than renaming them.
