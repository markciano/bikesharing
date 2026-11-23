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
  irm_owner_username        = "owner"
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

# Verifies d009 R34, R35
run "every_alert_reaches_irm_by_default" {
  command = plan

  assert {
    condition     = grafana_notification_policy.root.contact_point == grafana_contact_point.irm.name
    error_message = "The root policy's default contact point must be IRM."
  }

  assert {
    condition     = toset(grafana_notification_policy.root.group_by) == toset(["alert_id", "system"]) && grafana_notification_policy.root.repeat_interval == "4h"
    error_message = "The root policy must group by alert ID and system and repeat every 4 h."
  }

  assert {
    condition     = grafana_oncall_integration.alerting.type == "grafana_alerting"
    error_message = "The IRM integration must be of type grafana_alerting."
  }
}

# Verifies d009 R34
run "a_page_chain_notifies_the_owner_as_important_waits_five_minutes_and_repeats" {
  command = plan

  assert {
    condition     = grafana_oncall_escalation.page_notify.type == "notify_persons" && grafana_oncall_escalation.page_notify.important == true && grafana_oncall_escalation.page_notify.position == 0
    error_message = "A page's first step must notify the owner as important."
  }

  assert {
    condition     = grafana_oncall_escalation.page_wait.type == "wait" && grafana_oncall_escalation.page_wait.duration == 300 && grafana_oncall_escalation.page_wait.position == 1
    error_message = "A page's second step must wait 5 min."
  }

  assert {
    condition     = grafana_oncall_escalation.page_repeat.type == "repeat_escalation" && grafana_oncall_escalation.page_repeat.position == 2
    error_message = "A page's third step must repeat the chain from the beginning."
  }

  assert {
    condition     = grafana_oncall_route.page.routing_type == "jinja2" && strcontains(grafana_oncall_route.page.routing_regex, "commonLabels.urgency") && strcontains(grafana_oncall_route.page.routing_regex, "page")
    error_message = "The pages' route must match the alert's urgency label."
  }
}

# Verifies d009 R35
run "a_ticket_chain_has_no_steps" {
  command = plan

  # An id exists only after apply; a known one lets the plan compare which chain a step hangs from.
  override_resource {
    target          = grafana_oncall_escalation_chain.page
    values          = { id = "page-chain" }
    override_during = plan
  }

  override_resource {
    target          = grafana_oncall_escalation_chain.ticket
    values          = { id = "ticket-chain" }
    override_during = plan
  }

  # The chain exists and is the integration's default route; every step declared in
  # irm.tf hangs from the pages' chain, so the ticket's has none.
  assert {
    condition     = grafana_oncall_escalation_chain.ticket.name == "ticket" && grafana_oncall_escalation_chain.page.name == "page"
    error_message = "Both escalation chains must exist."
  }

  assert {
    condition = alltrue([
      for s in [
        grafana_oncall_escalation.page_notify,
        grafana_oncall_escalation.page_wait,
        grafana_oncall_escalation.page_repeat,
      ] : s.escalation_chain_id == "page-chain"
    ])
    error_message = "Every escalation step must belong to the pages' chain."
  }
}

# Verifies d009 R44
run "the_pages_policy_is_active_from_08_to_23_madrid_time_and_no_other_has_an_interval" {
  command = plan

  assert {
    condition = (
      grafana_mute_timing.pages_active.intervals[0].times[0].start == "08:00" &&
      grafana_mute_timing.pages_active.intervals[0].times[0].end == "23:00" &&
      grafana_mute_timing.pages_active.intervals[0].location == "Europe/Madrid"
    )
    error_message = "The pages' interval must be 08:00 to 23:00, Europe/Madrid."
  }

  assert {
    condition = (
      toset(grafana_notification_policy.root.policy[1].active_timings) == toset([grafana_mute_timing.pages_active.name]) &&
      length(coalesce(grafana_notification_policy.root.policy[0].active_timings, [])) == 0
    )
    error_message = "Only the pages' policy has an active time interval."
  }
}

# Verifies d009 R19
run "alr12_goes_to_the_watchdog_every_five_minutes_first_and_nothing_else_reaches_it" {
  command = plan

  assert {
    condition = (
      grafana_notification_policy.root.policy[0].contact_point == grafana_contact_point.watchdog.name &&
      grafana_notification_policy.root.policy[0].repeat_interval == local.alr12_repeat_interval &&
      grafana_notification_policy.root.policy[0].continue == false &&
      one(grafana_notification_policy.root.policy[0].matcher).value == "ALR12"
    )
    error_message = "ALR12's policy must be the first, match its ID, repeat every 5 min and not continue."
  }

  assert {
    condition = (
      one(grafana_notification_policy.root.policy[1].matcher).value == "page" &&
      grafana_notification_policy.root.policy[1].contact_point == grafana_contact_point.irm.name &&
      length(grafana_notification_policy.root.policy) == 2
    )
    error_message = "The pages' policy must go to IRM and no other policy may exist."
  }

  assert {
    condition     = one(grafana_contact_point.watchdog.webhook).url == var.watchdog_url
    error_message = "The watchdog's contact point must use the sensitive URL variable."
  }
}

# Verifies d009 R23, R24
run "the_template_shows_the_ids_and_links_the_catalogs_and_the_events" {
  command = plan

  assert {
    condition = alltrue([
      strcontains(grafana_message_template.notification.template, ".Labels.alert_id"),
      strcontains(grafana_message_template.notification.template, ".Annotations.checks"),
      strcontains(grafana_message_template.notification.template, "docs/data-quality.md"),
      strcontains(grafana_message_template.notification.template, "docs/observability.md"),
      strcontains(grafana_message_template.notification.template, "/explore?left="),
      strcontains(grafana_message_template.notification.template, var.github_base_url),
    ])
    error_message = "The template must show the alert ID and checked IDs, and link the catalogs and Explore."
  }
}

# Verifies d009 R38
run "the_template_reads_no_event_body_or_value" {
  command = plan

  assert {
    condition     = length(regexall("\\.(Values|ValueString|Body|SilenceURL|GeneratorURL)", grafana_message_template.notification.template)) == 0
    error_message = "The template may read only an alert's labels and annotations, and its own state and times."
  }
}
