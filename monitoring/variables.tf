# Secrets and values that depend on the account have no default and come from .env as
# TF_VAR_<name>; never in code or in a .tfvars file (d009 R37).

variable "grafana_url" {
  description = "The stack's URL, for the provider's alerting and IRM resources."
  type        = string
}

variable "grafana_auth" {
  description = "Token of the stack service account for alerting and IRM; needs plugins.app:access."
  type        = string
  sensitive   = true
}

variable "grafana_sm_url" {
  description = "The stack's Synthetic Monitoring API URL, for ALR4's check."
  type        = string
}

variable "grafana_sm_access_token" {
  description = "Synthetic Monitoring access token, for ALR4's check."
  type        = string
  sensitive   = true
}

variable "watchdog_url" {
  description = "Signal URL of the watchdog's check in Healthchecks.io; kept only in Grafana's notification setting."
  type        = string
  sensitive   = true
}

variable "loki_datasource_uid" {
  description = "UID of the stack's Loki data source, where the events of capture and the pipeline land."
  type        = string
}

variable "prometheus_datasource_uid" {
  description = "UID of the stack's Prometheus data source, where the synthetic check's results land."
  type        = string
}

variable "usage_datasource_uid" {
  description = "UID of the stack's usage data source, which ALR13 reads."
  type        = string
}

# TODO(T041): replace the workers.dev address with a custom domain, if one is bought.
variable "page_base_url" {
  description = "Base URL of the page as web/'s deployment serves it, without a trailing slash."
  type        = string
  default     = "https://bikesharing-web.zarek-90.workers.dev"

  validation {
    condition     = startswith(var.page_base_url, "https://") && !endswith(var.page_base_url, "/")
    error_message = "The page's base URL must start with https:// and have no trailing slash."
  }
}

variable "published_files" {
  description = "Files the page serves, under its base URL, whose data age ALR4's check reads; a child that publishes another file adds it."
  type        = list(string)
  default     = ["latest-station-count.json"]
}

variable "probes" {
  description = "Names of the synthetic check's three probe locations, all in Europe, near the owner and the stack."
  type        = list(string)
  default     = ["Frankfurt", "Paris", "London"]

  validation {
    condition     = length(var.probes) == 3
    error_message = "The synthetic check runs from exactly three probes."
  }
}

variable "github_base_url" {
  description = "The repository's base URL on GitHub, where the notifications link the catalogs."
  type        = string
  default     = "https://github.com/markciano/bikesharing"
}

variable "dqm7_targets" {
  description = "Each system's DQM7 target as a fraction of the minutes of a calendar month; its error budget is 1 - target (d009 D7)."
  type        = map(number)
  default = {
    ambici = 0.995
    bicing = 0.97
  }
}
