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
      selector        = "{service_name=\"pipeline\"} | detected_level=\"error\" | event=~\"${local.alert_event_regex["ALR1"]}\""
      group_by        = ["rule"]
      checks          = "{{ $labels.rule }}"
      catalog_section = "runtime-rules"
    }
    ALR2 = {
      summary         = "A runtime rule of severity warn failed"
      selector        = "{service_name=\"pipeline\"} | detected_level=\"warn\" | event=~\"${local.alert_event_regex["ALR2"]}\""
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

# Rules that fire on a count or a measure over a window. Each rule is one query (A), its
# threshold (B) and, for a rule held only while capture's events reach Grafana, a guard
# query (C) and the math that joins both (D) (d009, Thresholds and Capture silence).

locals {
  # The causes d009 D9 gives to the provider; every other failure of a feed is a minute
  # given to capture, so ALR15 counts it.
  provider_error_types = ["http", "timeout"]

  dynamic_feeds_filter = "feed=~\"${join("|", local.capture_dynamic_feeds)}\""

  # ALR5 looks at one minute more than its threshold, so a feed with no clean capture
  # for more minutes than the threshold fires, whatever the cause: a failure or a pass
  # with no event. The feeds it watches are the dynamic ones with an event of its alert
  # in the seen window; a clean capture is an event of info level, as the registry gives
  # them.
  alr5_window_min = local.alr5_minutes_in_a_row + 1
  alr5_events     = "{service_name=\"capture\"} | event=~\"${local.alert_event_regex["ALR5"]}\" | ${local.dynamic_feeds_filter}"
  alr5_clean      = "{service_name=\"capture\"} | detected_level=\"info\" | event=~\"${local.alert_event_regex["ALR5"]}\" | ${local.dynamic_feeds_filter}"

  # The window ALR8 gives capture: while its events reach Grafana within it, ALR5 holds
  # (d009, Capture silence), so a broken send never pages for data that R2 holds.
  capture_reaches_grafana = "sum(count_over_time({service_name=\"capture\"} [${local.alr8_capture_silent_s}s]))"

  # ALR7 reads the largest value of the runs finished in one cadence, so every run is
  # seen by at least one evaluation. A run that ends in error and wrote no measure is
  # left out (`__error__=""`) rather than failing the query.
  alr7_window = "${local.run_settings.cadence_min}m"
  alr7_events = "{service_name=\"pipeline\"} | event=~\"${local.alert_event_regex["ALR7"]}\""

  # ALR15's count, as ALR6 counts: the passes are the largest count of a system's feeds
  # of feed_captured and feed_failed events; a feed's passes with no event are the
  # passes minus its events, for the dynamic feeds only, since a static feed is fetched
  # less often.
  alr15_events     = "{service_name=\"capture\"} | event=~\"${local.alert_event_regex["ALR15"]}\""
  alr15_per_feed   = "sum by (system, feed) (count_over_time(${local.alr15_events} [${local.alr15_window}]))"
  alr15_passes     = "max by (system) (${local.alr15_per_feed})"
  alr15_dynamic    = "sum by (system, feed) (count_over_time(${local.alr15_events} | ${local.dynamic_feeds_filter} [${local.alr15_window}]))"
  alr15_no_event   = "(${local.alr15_passes} - on (system) group_right () (${local.alr15_dynamic}))"
  alr15_given_fail = "sum by (system, feed) (count_over_time({service_name=\"capture\"} | detected_level=\"error\" | event=~\"${local.alert_event_regex["ALR15"]}\" | error_type!~\"${join("|", local.provider_error_types)}\" [${local.alr15_window}]))"
  # A feed with no failure given to capture has no second series, so `or` keeps its
  # passes with no event.
  alr15_expr = "(${local.alr15_no_event} + on (system, feed) (${local.alr15_given_fail})) or ${local.alr15_no_event}"

  # Fields every rule defines, so the rules share one type.
  threshold_rules = {
    # A failing probe has `probe_success` 0 for its latest result, read over two
    # cadences of the check so that one late result is still seen; the rule fires when
    # more probes fail than one, so a single probe's network never pages (d009 D14).
    ALR4 = {
      alert_id        = "ALR4"
      urgency         = "page"
      summary         = "A file the page serves has data older than its target, or cannot be read"
      datasource_uid  = var.prometheus_datasource_uid
      expr            = "sum by (job, instance) (1 - last_over_time(probe_success{job=~\"${local.synthetic_check_job_prefix}.+\"}[${local.synthetic_check_frequency_s * 2 / 60}m]))"
      threshold       = local.alr4_probes_to_confirm - 1
      guard_expr      = ""
      value           = "{{ printf \"%.0f\" $values.A.Value }} of ${length(var.probes)} probes failing"
      threshold_text  = "at least ${local.alr4_probes_to_confirm} probes"
      events_query    = ""
      checks          = "DQM10"
      catalog_section = "quality-indicators"
      labels          = { component = "page" }
    }
    ALR5 = {
      alert_id        = "ALR5"
      urgency         = "page"
      summary         = "A feed has had no clean capture for too many minutes in a row"
      datasource_uid  = var.loki_datasource_uid
      expr            = "sum by (system, feed, service_name, service_version) (count_over_time(${local.alr5_events} [${local.alr5_feed_seen_window}])) unless on (system, feed) sum by (system, feed) (count_over_time(${local.alr5_clean} [${local.alr5_window_min}m]))"
      threshold       = 0
      guard_expr      = local.capture_reaches_grafana
      value           = "no clean capture in the last ${local.alr5_window_min} minutes"
      threshold_text  = "over ${local.alr5_minutes_in_a_row} minutes in a row"
      events_query    = local.alr5_events
      checks          = ""
      catalog_section = ""
      labels          = { component = "{{ $labels.service_name }}", version = "{{ $labels.service_version }}" }
    }
    "ALR7 duration" = {
      alert_id        = "ALR7"
      urgency         = "ticket"
      summary         = "A pipeline run lasted close to the timeout"
      datasource_uid  = var.loki_datasource_uid
      expr            = "max by (service_name, service_version) (max_over_time(${local.alr7_events} | unwrap duration_s | __error__=\"\" [${local.alr7_window}]))"
      threshold       = local.alr7_duration_s
      guard_expr      = ""
      value           = "{{ printf \"%.0f\" $values.A.Value }} s"
      threshold_text  = "over ${local.alr7_duration_s} s"
      events_query    = local.alr7_events
      checks          = ""
      catalog_section = ""
      labels          = { component = "{{ $labels.service_name }}", version = "{{ $labels.service_version }}" }
    }
    "ALR7 memory" = {
      alert_id        = "ALR7"
      urgency         = "ticket"
      summary         = "A pipeline run used close to the container's memory"
      datasource_uid  = var.loki_datasource_uid
      expr            = "max by (service_name, service_version) (max_over_time(${local.alr7_events} | unwrap peak_memory_mb | __error__=\"\" [${local.alr7_window}]))"
      threshold       = local.alr7_memory_mb
      guard_expr      = ""
      value           = "{{ printf \"%.0f\" $values.A.Value }} MB"
      threshold_text  = "over ${local.alr7_memory_mb} MB"
      events_query    = local.alr7_events
      checks          = ""
      catalog_section = ""
      labels          = { component = "{{ $labels.service_name }}", version = "{{ $labels.service_version }}" }
    }
    "ALR8 capture" = {
      alert_id        = "ALR8"
      urgency         = "ticket"
      summary         = "A component has sent no event to Grafana"
      datasource_uid  = var.loki_datasource_uid
      expr            = "absent_over_time({service_name=\"capture\"} [${local.alr8_capture_silent_s}s])"
      threshold       = 0
      guard_expr      = ""
      value           = ""
      threshold_text  = "no event in ${local.alr8_capture_silent_s / 60} min"
      events_query    = "{service_name=\"capture\"}"
      checks          = ""
      catalog_section = ""
      labels          = { component = "{{ $labels.service_name }}" }
    }
    "ALR8 pipeline" = {
      alert_id        = "ALR8"
      urgency         = "ticket"
      summary         = "A component has sent no event to Grafana"
      datasource_uid  = var.loki_datasource_uid
      expr            = "absent_over_time({service_name=\"pipeline\"} [${local.alr8_pipeline_silent_s}s])"
      threshold       = 0
      guard_expr      = ""
      value           = ""
      threshold_text  = "no event in ${local.alr8_pipeline_silent_s / 60} min"
      events_query    = "{service_name=\"pipeline\"}"
      checks          = ""
      catalog_section = ""
      labels          = { component = "{{ $labels.service_name }}" }
    }
    "ALR13 logs" = {
      alert_id        = "ALR13"
      urgency         = "ticket"
      summary         = "The month's logs are close to the Free tier's limit"
      datasource_uid  = var.usage_datasource_uid
      expr            = "max(grafanacloud_org_logs_usage)"
      threshold       = local.alr13_logs_gb
      guard_expr      = ""
      value           = "{{ printf \"%.1f\" $values.A.Value }} GB"
      threshold_text  = "over ${local.alr13_logs_gb} GB"
      events_query    = ""
      checks          = ""
      catalog_section = ""
      labels          = { component = "grafana" }
    }
    "ALR13 checks" = {
      alert_id        = "ALR13"
      urgency         = "ticket"
      summary         = "The month's synthetic check executions are close to the Free tier's limit"
      datasource_uid  = var.usage_datasource_uid
      expr            = "max(grafanacloud_org_sm_billable_check_executions)"
      threshold       = local.alr13_synthetic_executions
      guard_expr      = ""
      value           = "{{ printf \"%.0f\" $values.A.Value }} executions"
      threshold_text  = "over ${local.alr13_synthetic_executions} executions"
      events_query    = ""
      checks          = ""
      catalog_section = ""
      labels          = { component = "grafana" }
    }
    ALR15 = {
      alert_id        = "ALR15"
      urgency         = "ticket"
      summary         = "A feed's minutes given to capture over ${local.alr15_window} are above the target's share"
      datasource_uid  = var.loki_datasource_uid
      expr            = local.alr15_expr
      threshold       = local.alr15_minutes_given_to_capture
      guard_expr      = ""
      value           = "{{ printf \"%.0f\" $values.A.Value }} minutes in ${local.alr15_window}"
      threshold_text  = "over ${local.alr15_minutes_given_to_capture} minutes"
      events_query    = local.alr15_events
      checks          = "DQM11"
      catalog_section = "quality-indicators"
      labels          = { component = "capture" }
    }
  }
}

resource "grafana_rule_group" "thresholds" {
  name             = "thresholds"
  folder_uid       = grafana_folder.alerts.uid
  interval_seconds = local.event_rules_interval_s

  dynamic "rule" {
    for_each = local.threshold_rules

    content {
      name      = rule.key
      condition = rule.value.guard_expr == "" ? "B" : "D"
      for       = "0s"
      # No series means the condition does not hold, not a missing measure.
      no_data_state  = "OK"
      exec_err_state = "Error"

      labels = merge({ alert_id = rule.value.alert_id, urgency = rule.value.urgency }, rule.value.labels)

      # The template skips an annotation that is absent, so empty ones are left out.
      annotations = {
        for k, v in {
          summary         = rule.value.summary
          value           = rule.value.value
          threshold       = rule.value.threshold_text
          checks          = rule.value.checks
          catalog_section = rule.value.catalog_section
          events_query    = rule.value.events_query
        } : k => v if v != ""
      }

      data {
        ref_id         = "A"
        datasource_uid = rule.value.datasource_uid

        relative_time_range {
          from = local.event_rules_window_s
          to   = 0
        }

        # `instant` serves a Prometheus-type data source and `queryType` a Loki one.
        model = jsonencode({
          refId     = "A"
          queryType = "instant"
          instant   = true
          expr      = rule.value.expr
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
          conditions = [{ evaluator = { type = "gt", params = [rule.value.threshold] } }]
        })
      }

      dynamic "data" {
        for_each = rule.value.guard_expr == "" ? [] : [rule.value.guard_expr]

        content {
          ref_id         = "C"
          datasource_uid = var.loki_datasource_uid

          relative_time_range {
            from = local.event_rules_window_s
            to   = 0
          }

          model = jsonencode({
            refId     = "C"
            queryType = "instant"
            instant   = true
            expr      = data.value
          })
        }
      }

      # The guard is a single series with no labels, which Grafana joins with every
      # series of the threshold.
      dynamic "data" {
        for_each = rule.value.guard_expr == "" ? [] : [1]

        content {
          ref_id         = "D"
          datasource_uid = "__expr__"

          relative_time_range {
            from = 0
            to   = 0
          }

          model = jsonencode({
            refId      = "D"
            type       = "math"
            expression = "$B && $C"
          })
        }
      }
    }
  }
}

# ALR6, the error budget burn: one rule group per system, from its DQM7 target (d009 D7,
# Capture completeness target per system). A new system is one more entry of the
# variable.
module "error_budget_alert" {
  source   = "./modules/error_budget_alert"
  for_each = var.dqm7_targets

  system              = each.key
  target              = each.value
  folder_uid          = grafana_folder.alerts.uid
  loki_datasource_uid = var.loki_datasource_uid
  stock_feed          = local.alr6_stock_feed
  capture_silent_s    = local.alr8_capture_silent_s
}

# The watchdog's rule: its condition always holds, and no data fires it too, so the
# signal reaches the check as long as Grafana evaluates and notifies (d009 D13, A
# watchdog outside Grafana watches its alerting). Its own policy sends it, never IRM.
resource "grafana_rule_group" "watchdog" {
  name             = "watchdog"
  folder_uid       = grafana_folder.alerts.uid
  interval_seconds = local.event_rules_interval_s

  rule {
    name           = "ALR12"
    condition      = "B"
    for            = "0s"
    no_data_state  = "Alerting"
    exec_err_state = "Alerting"

    labels = {
      alert_id = "ALR12"
      urgency  = "page"
    }

    annotations = {
      summary = "The watchdog's signal: Grafana is evaluating and notifying"
    }

    data {
      ref_id         = "A"
      datasource_uid = "__expr__"

      relative_time_range {
        from = 0
        to   = 0
      }

      model = jsonencode({
        refId      = "A"
        type       = "math"
        expression = "1"
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
