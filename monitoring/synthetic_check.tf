# ALR4's synthetic check: a scripted k6 check that reads each file the page serves from
# three probes and measures the age of its data (d009, Synthetic check). The failures it
# reports reach ALR4 through the Prometheus data source.

# The probes' IDs exist only in Grafana, so each name of the variable is looked up.
data "grafana_synthetic_monitoring_probes" "main" {}

resource "grafana_synthetic_monitoring_check" "published_file_age" {
  for_each = toset(var.published_files)

  job       = "${local.synthetic_check_job_prefix}${each.key}"
  target    = "${var.page_base_url}/${each.key}"
  enabled   = true
  frequency = local.synthetic_check_frequency_s * 1000
  timeout   = local.synthetic_check_timeout_ms
  probes    = [for name in var.probes : data.grafana_synthetic_monitoring_probes.main.probes[name]]

  settings {
    scripted {
      # The script has no access to Terraform's variables, so its configuration is
      # written before it as a constant.
      script = "const CONFIG = ${jsonencode({
        url       = "${var.page_base_url}/${each.key}"
        max_age_s = local.alr4_max_age_s
      })};\n${file("${path.module}/checks/published_file_age.js")}"
    }
  }
}
