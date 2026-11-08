---
status: Accepted
date: 2026-11-08
---

# Account-wide Workers Editor token for deploys

## Context and problem statement

Workers are deployed from the local machine with wrangler, which needs an API credential. Least privilege (NIST SP 800-53 AC-6, [ADR-0023](0023-storage-security-baseline.md)) calls for a credential that reaches only the Worker it deploys, with an expiry. Cloudflare announced per-Worker scoping for API tokens, but the account's token creation form offers the Workers roles only at account level: a token can reach every Worker of the account or none.

## Considered Options

### 1. Token scoped to one Worker

- Pros:
  - A leak reaches only that Worker.
- Cons:
  - Not offered by the dashboard.

### 2. Account-owned token, Workers Editor role on all Workers

- Pros:
  - Updates and deploys, but cannot create or delete Workers.
  - Expires, and leaves no account-wide session on the machine.
- Cons:
  - A leak reaches every Worker of the account, including future ones.

### 3. `wrangler login` for every deploy

- Pros:
  - No token to store.
- Cons:
  - Keeps the owner's account-wide OAuth session on the machine.

## Decision Outcome

**Chosen option:** 2, an account-owned token with the Workers Editor role on all Workers of the account and a one-year expiry, read by wrangler from `CLOUDFLARE_API_TOKEN`.

Rationale: it is the narrowest credential the dashboard offers. The Editor role alone was enough to deploy a Worker with an R2 binding, a cron trigger and `workers_dev: false`.
Why not the others: option 1 is not available; option 3 grants more than option 2.

**Scope:** deploy credentials for the project's Workers. Not the R2 access keys used by rclone, nor the first deploy of a new Worker, which Editor cannot create.

### Consequences

#### Positive

- **Expiry:** a leaked token stops working within a year at most.

#### Negative

- **Wider reach:** every Worker of the account is exposed to a leak, not only the one deployed.
- **Revisit:** when per-Worker scoping is available in the dashboard, this ADR is superseded by a token scoped to each Worker.
