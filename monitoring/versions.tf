# The Terraform and provider versions of the monitoring configuration. The exact
# Terraform release is pinned in .terraform-version; this range only states which
# releases the configuration is compatible with (ADR-0016, ADR-0017).
terraform {
  required_version = ">= 1.17.1, < 2.0.0"

  required_providers {
    grafana = {
      source  = "grafana/grafana"
      version = "~> 4.54.0"
    }
  }
}
