# Tests of the alerting configuration against a mocked provider: nothing reaches
# Grafana Cloud and no credential is needed (d009, Test plan). The values below are
# placeholders, never real secrets.
mock_provider "grafana" {}

variables {
  grafana_url               = "https://stack.example.invalid"
  grafana_auth              = "placeholder"
  grafana_sm_url            = "https://sm.example.invalid"
  grafana_sm_access_token   = "placeholder"
  watchdog_url              = "placeholder"
  loki_datasource_uid       = "loki-uid"
  prometheus_datasource_uid = "prometheus-uid"
  usage_datasource_uid      = "usage-uid"
  page_base_url             = "https://page.example.invalid"
}

# Verifies d009 R37
run "watchdog_url_is_sensitive" {
  command = plan

  assert {
    condition     = issensitive(var.watchdog_url)
    error_message = "The watchdog's signal URL must be a sensitive variable."
  }
}
