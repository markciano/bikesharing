# Where notifications go: IRM, for every alert but ALR12, and the watchdog's webhook, for
# ALR12 alone (d009 D13, Notification routing).
resource "grafana_contact_point" "irm" {
  name = "irm"

  oncall {
    url     = grafana_oncall_integration.alerting.link
    message = "{{ template \"project.message\" . }}"
  }
}

# The URL is the watchdog's secret: it comes from the sensitive variable and is kept only
# here (d009 R37, TH1).
resource "grafana_contact_point" "watchdog" {
  name = "watchdog"

  webhook {
    url = var.watchdog_url
  }
}
