# Tests of the IRM integration against a mocked provider: nothing reaches Grafana Cloud
# and no credential is needed (d009, Test plan). The values below are placeholders, never
# real secrets.
mock_provider "grafana" {
  # The probes' IDs exist only in Grafana; the check looks them up by name.
  mock_data "grafana_synthetic_monitoring_probes" {
    defaults = {
      probes = {
        Frankfurt = 11
        Paris     = 12
        London    = 13
      }
    }
  }
}

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
  irm_owner_username        = "owner"
}

# Verifies d009 R23, R24 (DI7)
run "irm_shows_the_notification_layout_in_the_web_and_mobile_app" {
  command = plan

  assert {
    condition     = grafana_oncall_integration.alerting.templates[0].web[0].message == "{{ payload.message }}"
    error_message = "IRM's web message must be the payload's message, the layout of project.message."
  }

  assert {
    condition     = grafana_oncall_integration.alerting.templates[0].mobile_app[0].message == "{{ payload.message }}"
    error_message = "IRM's mobile app message must be the payload's message, the layout of project.message."
  }
}
