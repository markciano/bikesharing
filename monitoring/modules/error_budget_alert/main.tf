# ALR6, the error budget burn of one system, as the SRE Workbook's multiwindow,
# multi-burn-rate alert: a level fires when its long and its short window both burn
# the budget faster than its rate (d009, Error budget alerts). The version of the
# provider is set by the root configuration.

terraform {
  required_providers {
    grafana = {
      source = "grafana/grafana"
    }
  }
}

locals {
  levels = {
    page_1h   = { urgency = "page", burn_rate = 14.4, long = "1h", short = "5m" }
    page_6h   = { urgency = "page", burn_rate = 6, long = "6h", short = "30m" }
    ticket_3d = { urgency = "ticket", burn_rate = 1, long = "3d", short = "6h" }
  }

  # The events ALR6 reads come from the registry, never written by hand. A pass writes
  # one of them for each dynamic feed, so the largest count among a system's feeds is
  # its passes that reached Grafana; a clean capture is an event of info level.
  registry     = jsondecode(file("${path.module}/../../../contracts/log-events.registry.json"))
  events_regex = join("|", sort(distinct([for e in local.registry.events : e.event if contains(e.alerts, "ALR6")])))
  passes       = "{service_name=\"capture\"} | event=~\"${local.events_regex}\" | system=\"${var.system}\""
  clean        = "{service_name=\"capture\", detected_level=\"info\"} | event=~\"${local.events_regex}\" | system=\"${var.system}\""

  budget = 1 - var.target

  # The error rate over a window: one minus the minutes with a clean capture over the
  # passes that reached Grafana.
  error_rate = {
    for k, v in local.levels : k => {
      long  = "1 - max by (system) (sum by (system, feed) (count_over_time(${local.clean} [${v.long}]))) / max by (system) (sum by (system, feed) (count_over_time(${local.passes} [${v.long}])))"
      short = "1 - max by (system) (sum by (system, feed) (count_over_time(${local.clean} [${v.short}]))) / max by (system) (sum by (system, feed) (count_over_time(${local.passes} [${v.short}])))"
    }
  }

  guard = "sum(count_over_time({service_name=\"capture\"} [${var.capture_silent_s}s]))"
}

resource "grafana_rule_group" "this" {
  name             = "ALR6 ${var.system}"
  folder_uid       = var.folder_uid
  interval_seconds = 60

  dynamic "rule" {
    for_each = local.levels

    content {
      name      = "ALR6 ${var.system} ${rule.key}"
      condition = "E"
      for       = "0s"
      # No series means the condition does not hold, not a missing measure.
      no_data_state  = "OK"
      exec_err_state = "Error"

      labels = {
        alert_id  = "ALR6"
        urgency   = rule.value.urgency
        system    = var.system
        component = "capture"
      }

      # The template skips an annotation that is absent.
      annotations = {
        summary         = "${var.system} spends its error budget ${rule.value.burn_rate} times faster than it allows"
        value           = "{{ printf \"%.4f\" $values.A.Value }} error rate in ${rule.value.long}"
        threshold       = "over ${rule.value.burn_rate * local.budget} in ${rule.value.long} and ${rule.value.short}"
        checks          = "DQM7"
        catalog_section = "quality-indicators"
        events_query    = local.passes
      }

      data {
        ref_id         = "A"
        datasource_uid = var.loki_datasource_uid

        relative_time_range {
          from = 300
          to   = 0
        }

        model = jsonencode({
          refId     = "A"
          queryType = "instant"
          instant   = true
          expr      = local.error_rate[rule.key].long
        })
      }

      data {
        ref_id         = "B"
        datasource_uid = var.loki_datasource_uid

        relative_time_range {
          from = 300
          to   = 0
        }

        model = jsonencode({
          refId     = "B"
          queryType = "instant"
          instant   = true
          expr      = local.error_rate[rule.key].short
        })
      }

      data {
        ref_id         = "C"
        datasource_uid = var.loki_datasource_uid

        relative_time_range {
          from = 300
          to   = 0
        }

        model = jsonencode({
          refId     = "C"
          queryType = "instant"
          instant   = true
          expr      = local.guard
        })
      }

      # Both windows over the threshold and the guard with data. The guard is a single
      # series with no labels, which Grafana joins with every series of the rates.
      data {
        ref_id         = "D"
        datasource_uid = "__expr__"

        relative_time_range {
          from = 0
          to   = 0
        }

        model = jsonencode({
          refId      = "D"
          type       = "math"
          expression = "($A > ${rule.value.burn_rate * local.budget}) && ($B > ${rule.value.burn_rate * local.budget}) && $C"
        })
      }

      data {
        ref_id         = "E"
        datasource_uid = "__expr__"

        relative_time_range {
          from = 0
          to   = 0
        }

        model = jsonencode({
          refId      = "E"
          type       = "threshold"
          expression = "D"
          conditions = [{ evaluator = { type = "gt", params = [0] } }]
        })
      }
    }
  }
}
