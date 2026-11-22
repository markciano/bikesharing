---
paths:
  - "monitoring/**/*.tf"
  - "monitoring/**/*.tftest.hcl"
---

# Terraform code and testing rules

## Code comments

General comment rules are in `general.md`.

- Every variable and output has a `description`; a variable also has a `type`, and a `validation` block when only some values are valid.
- Comments use `#`, never `//` or `/* */`.

## Style

- `terraform fmt` sets the layout and `terraform validate` checks the configuration; `monitoring/scripts/check-monitoring.sh` runs both with `terraform test`, as CI does.
- Names follow HashiCorp's style: snake_case for resources, variables and locals; a resource's name does not repeat its type.

## Structure

The configuration declares Grafana Cloud's alerting, synthetic check and watchdog, and the owner applies it from the owner's machine, with its state kept there and ignored by Git ([ADR-0051](../../../docs/decisions/0051-monitoring-configuration-as-code.md)).

- Files follow HashiCorp's standard module structure: `versions.tf`, `providers.tf`, `variables.tf`, `locals.tf`, then one file per kind of resource; a module lives in `modules/<name>/` with its own `main.tf` and `variables.tf`.
- Every threshold is a named local in `locals.tf`, never a literal figure in a rule. One that depends on other data is derived from it, `pipeline/src/bikesharing/core/run_settings.json` or the event registry `contracts/log-events.registry.json`, read with `jsondecode(file(...))`; a fixed one states its reason in a comment.
- Every alert's event list, ALR9's and ALR14's included, is built from the event registry, never written by hand: an alert selects the events whose `alerts` list its ID.
- Every alert rule carries the labels `alert_id` and `urgency` (`page` or `ticket`), `system` where it applies, and the annotations the message template reads; the template reads only labels and annotations.
- A secret, such as a token or the watchdog's signal URL, is a `sensitive` variable with no default, set from `.env` as `TF_VAR_<name>`; never in code or in a `.tfvars` file.
- `terraform plan` and `apply` against Grafana Cloud are operational actions, run by the owner only.

## Testing

General principles are in `testing.md`; reasons and detail in the [testing strategy](../../../docs/testing-strategy.md) (Monitoring section).

- Tool: `terraform test`, with `mock_provider "grafana"` and `command = plan`, so no test reaches Grafana Cloud or needs a credential.
- `bash monitoring/scripts/check-monitoring.sh` runs every check, from the project root.
- Tests assert the planned attributes: each rule's query, threshold, labels and annotations, and each policy's routing. Whether Grafana evaluates and notifies them is shown end to end, never in a test.
- Files in `monitoring/tests/`, named `<subject>.tftest.hcl`; each `run` block is named for the behaviour it checks.
