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

# Verifies d009 R14
run "alr7_thresholds_are_80_percent_of_the_timeout_and_the_container_memory" {
  command = plan

  assert {
    condition     = local.alr7_duration_s == jsondecode(file("../pipeline/src/bikesharing/core/run_settings.json")).timeout_s * 0.8
    error_message = "ALR7's duration threshold must be 80% of the timeout."
  }

  # Modal measures memory in MiB and the event's field is in decimal MB.
  assert {
    condition     = local.alr7_memory_mb == ceil(jsondecode(file("../pipeline/src/bikesharing/core/run_settings.json")).container_memory_mib * 1048576 / 1000000 * 0.8)
    error_message = "ALR7's memory threshold must be 80% of the container's memory, in decimal MB."
  }
}

# Verifies d009 R15
run "alr8_thresholds_are_two_cadences_for_the_pipeline_and_five_minutes_for_capture" {
  command = plan

  assert {
    condition     = local.alr8_pipeline_silent_s == jsondecode(file("../pipeline/src/bikesharing/core/run_settings.json")).cadence_min * 2 * 60
    error_message = "ALR8's pipeline threshold must be 2 cadences."
  }

  assert {
    condition     = local.alr8_capture_silent_s == 300
    error_message = "ALR8's capture threshold must be 5 minutes."
  }
}

# Verifies d009 R10
run "alr4_threshold_is_the_cadence_plus_the_time_budget" {
  command = plan

  assert {
    condition     = local.alr4_max_age_s == jsondecode(file("../pipeline/src/bikesharing/core/run_settings.json")).cadence_min * 60 + jsondecode(file("../pipeline/src/bikesharing/core/run_settings.json")).time_budget_s
    error_message = "ALR4's threshold must be the cadence plus the time budget."
  }
}

# Verifies d009 R11, R19, R21, R39
run "fixed_thresholds_hold_the_values_of_the_design" {
  command = plan

  assert {
    condition = alltrue([
      local.synthetic_check_frequency_s == 300,
      local.alr5_minutes_in_a_row == 10,
      local.alr12_repeat_interval == "5m",
      local.alr13_logs_gb == 40,
      local.alr13_synthetic_executions == 80000,
      local.alr15_minutes_given_to_capture == 7,
    ])
    error_message = "A fixed threshold differs from the design's Thresholds table."
  }
}

# Verifies d009 R16
run "each_alert_selects_the_events_that_list_it" {
  command = plan

  assert {
    condition = alltrue([
      for id, names in local.alert_events :
      toset(names) == toset([for e in jsondecode(file("../contracts/log-events.registry.json")).events : e.event if contains(e.alerts, id)])
    ])
    error_message = "An alert's events must be exactly the registry's events that list its ID."
  }

  assert {
    condition     = local.alert_events["ALR1"] == tolist(["batch_failed", "file_invalid"]) && local.alert_event_regex["ALR5"] == "feed_captured|feed_failed"
    error_message = "ALR1's events or ALR5's regular expression differ from the registry's."
  }
}

# Verifies d009 R16
run "alr9_selects_the_actionable_events_that_no_alert_reads" {
  command = plan

  assert {
    condition = toset(local.alr9_events) == toset([
      for e in jsondecode(file("../contracts/log-events.registry.json")).events : e.event
      if e.needs_action && length(e.alerts) == 0
    ])
    error_message = "ALR9 must select the events with needs_action and no alert."
  }

  assert {
    condition     = contains(local.alr9_events, "stage_drained") && !contains(local.alr9_events, "batch_failed")
    error_message = "ALR9 must hold an actionable event with no alert and none that an alert covers."
  }
}

# Verifies d009 R22
run "alr14_knows_every_registered_event" {
  command = plan

  assert {
    condition = toset(local.registered_events) == toset([
      for e in jsondecode(file("../contracts/log-events.registry.json")).events : e.event
    ])
    error_message = "ALR14 must know exactly the registry's events."
  }

  assert {
    condition     = length(local.registered_events) == length(distinct(local.registered_events)) && split("|", local.registered_events_regex) == local.registered_events
    error_message = "The registered events must be listed once, and the regular expression must join them."
  }
}
