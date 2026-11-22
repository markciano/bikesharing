---
status: Accepted
date: 2026-11-22
---

# Monitoring configuration as code

## Context and problem statement

The monitoring tool, Grafana Cloud ([ADR-0048](0048-grafana-cloud-as-monitoring-tool.md)), holds the project's alert rules, the routes that make each alert a page or a ticket, synthetic checks and a watchdog that signals an outside heartbeat service. Alerts are defined in working documents and catalogs, and several thresholds derive from settings of other components, such as the pipeline's cadence, so a change of that setting must reach every threshold that depends on it. Set up by hand in Grafana's console, this configuration drifts from the documents that define it with no notice, cannot be checked in CI, and is rebuilt by hand if the account is suspended or lost. Grafana Cloud exposes all of it through an API.

## Considered Options

### 1. Terraform with Grafana's official provider

The configuration is declared in HCL files in the repository, and `terraform apply` creates or changes it through Grafana's API.

- Pros:
  - Each change is reviewed on a diff and checked in CI.
  - A lost or suspended account is recreated with one apply.
  - A threshold derived from the cadence is one variable.
- Cons:
  - A new tool and language, with its own version, lockfile, CI job and rules.
  - Terraform keeps a state file, which holds secrets and must be kept.

### 2. Console, with an export committed

The configuration is made in Grafana's console, and Grafana's export of it is committed as a record.

- Pros:
  - No new tool.
- Cons:
  - The export and the console drift apart with no notice.
  - Nothing to check in CI; a lost account is rebuilt by hand.

## Decision Outcome

**Chosen option:** 1. Terraform with Grafana's official provider

Rationale: Infrastructure as Code makes the configuration reviewable, testable and reproducible, which are what the console lacks: a drift between alerts and their documents goes unnoticed, and a lost account would take every alert with it.
Why not the others: the console with an export leaves the repository as a record that nothing keeps true.

The owner applies the configuration from the owner's machine, as an operational action. Terraform's state is kept locally, ignored by Git, next to `.env`. This adapts the practice of remote state, which serves several operators applying changes and locking against each other: with one operator, local state adds nothing to keep and leaves the secrets in one place. A lost state with a live account is recovered with `terraform import`.

**Scope:** every Grafana Cloud resource the project configures: alert rules, contact points, notification policies, synthetic checks, the watchdog and dashboards. It does not cover the Grafana Cloud account, its stack or its tokens, which the owner creates in the console, nor the checks of the heartbeat service ([ADR-0031](0031-heartbeat-alerts-for-the-pipeline.md)), nor the configuration of Cloudflare or Modal.

### Consequences

#### Positive

- **Reviewed and checked:** each change to Grafana goes through a pull request, and CI checks what needs no credentials.
- **Reproducible:** a new account takes the whole configuration with one apply.

#### Negative

- **One more component:** Terraform brings its own version, lockfile, CI job and rules file.
- **A local secret store:** the state holds secrets such as the watchdog's signal URL, and a token that can change Grafana's configuration is kept in `.env`; both live only on the owner's machine.
- **Console read-only:** a change made in the console to a resource Terraform manages is overwritten by the next apply.
