# The alert rules and their folder (docs/observability.md, Alerts). Each rule carries
# `alert_id`, `urgency` and the annotations the message template reads; its query
# groups by `system` and names none, so a new system needs no change (d009 D3, D4, R41).

resource "grafana_folder" "alerts" {
  title = "Bike sharing alerts"
}

# Rules that fire on an event: one event selected in the window fires the rule at once.
# Event lists come from the registry through locals.tf, never written by hand.

locals {
  # Evaluated every minute over the last 5 min, so an event that reaches Loki a few
  # minutes late still falls in a window.
  event_rules_interval_s = 60
  event_rules_window_s   = 300

  # The error types of capture's failures that d009 D9's table gives a cause: an HTTP
  # error status, a timeout reaching the provider and a failed write to R2. Any other
  # is a cause the table does not list, which ALR11 reports.
  classified_error_types = ["http", "timeout", "write"]

  # Labels every event rule groups by: the system, and the component and version that
  # wrote the event, shown by the template. An alert adds the fields that tell its
  # instances apart.
  event_rule_group_by = ["system", "service_name", "service_version"]

  event_rules = {
    ALR1 = {
      summary         = "A runtime rule of severity error failed"
      selector        = "{service_name=\"pipeline\", detected_level=\"error\"} | event=~\"${local.alert_event_regex["ALR1"]}\""
      group_by        = ["rule"]
      checks          = "{{ $labels.rule }}"
      catalog_section = "runtime-rules"
    }
    ALR2 = {
      summary         = "A runtime rule of severity warn failed"
      selector        = "{service_name=\"pipeline\", detected_level=\"warn\"} | event=~\"${local.alert_event_regex["ALR2"]}\""
      group_by        = ["rule"]
      checks          = "{{ $labels.rule }}"
      catalog_section = "runtime-rules"
    }
    ALR3 = {
      summary         = "The page's deployment failed"
      selector        = "{service_name=\"pipeline\"} | event=~\"${local.alert_event_regex["ALR3"]}\""
      group_by        = []
      checks          = ""
      catalog_section = ""
    }
    ALR9 = {
      summary         = "An actionable event that no other alert reads reached Grafana"
      selector        = "{service_name=~\".+\"} | event=~\"${local.alr9_event_regex}\""
      group_by        = ["event"]
      checks          = ""
      catalog_section = ""
    }
    # Capture's sender writes an array field as its JSON text, so an empty list is "[]".
    ALR10 = {
      summary         = "A provider's index lists a feed capture does not know"
      selector        = "{service_name=\"capture\"} | event=~\"${local.alert_event_regex["ALR10"]}\" | unknown_feeds!=\"\" | unknown_feeds!=\"[]\""
      group_by        = []
      checks          = ""
      catalog_section = ""
    }
    # A failure with no error_type also fires: an unknown cause goes to capture and is
    # reported, the fail-safe default of d009 D9.
    ALR11 = {
      summary         = "A pass logged a cause of a missed minute that DQM11 does not classify"
      selector        = "{service_name=\"capture\"} | event=~\"${local.alert_event_regex["ALR11"]}\" | error_type!~\"${join("|", local.classified_error_types)}\""
      group_by        = ["feed", "error_type"]
      checks          = "DQM11"
      catalog_section = "quality-indicators"
    }
    # A line with no event field also fires: it breaks ADR-0036's log convention, so it
    # is reported as an event to classify.
    ALR14 = {
      summary         = "An event the registry does not hold reached Grafana"
      selector        = "{service_name=~\".+\"} | event!~\"${local.registered_events_regex}\""
      group_by        = ["event"]
      checks          = ""
      catalog_section = ""
    }
  }
}

resource "grafana_rule_group" "events" {
  name             = "events"
  folder_uid       = grafana_folder.alerts.uid
  interval_seconds = local.event_rules_interval_s

  dynamic "rule" {
    for_each = local.event_rules

    content {
      name      = rule.key
      condition = "B"
      for       = "0s"
      # No event in the window is the normal state, not missing data.
      no_data_state  = "OK"
      exec_err_state = "Error"

      labels = {
        alert_id  = rule.key
        urgency   = "ticket"
        component = "{{ $labels.service_name }}"
        version   = "{{ $labels.service_version }}"
      }

      # The template skips an annotation that is absent, so empty ones are left out.
      annotations = {
        for k, v in {
          summary         = rule.value.summary
          checks          = rule.value.checks
          catalog_section = rule.value.catalog_section
          events_query    = rule.value.selector
        } : k => v if v != ""
      }

      data {
        ref_id         = "A"
        datasource_uid = var.loki_datasource_uid

        relative_time_range {
          from = local.event_rules_window_s
          to   = 0
        }

        model = jsonencode({
          refId     = "A"
          queryType = "instant"
          expr      = "sum by (${join(", ", concat(local.event_rule_group_by, rule.value.group_by))}) (count_over_time(${rule.value.selector} [${local.event_rules_window_s / 60}m]))"
        })
      }

      data {
        ref_id         = "B"
        datasource_uid = "__expr__"

        relative_time_range {
          from = 0
          to   = 0
        }

        model = jsonencode({
          refId      = "B"
          type       = "threshold"
          expression = "A"
          conditions = [{ evaluator = { type = "gt", params = [0] } }]
        })
      }
    }
  }
}
