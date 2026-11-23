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

# The event rules are looked up by their alert_id label; one() fails the run if a rule
# is missing or declared twice.

# Verifies d009 R7, R8
run "alr1_and_alr2_select_the_failed_rules_by_level_take_the_rule_from_the_event_and_are_tickets" {
  command = plan

  assert {
    condition = (
      jsondecode(one([for r in grafana_rule_group.events.rule : r if r.labels.alert_id == "ALR1"]).data[0].model).expr ==
      "sum by (system, service_name, service_version, rule) (count_over_time({service_name=\"pipeline\", detected_level=\"error\"} | event=~\"batch_failed|file_invalid\" [5m]))"
    )
    error_message = "ALR1 must count the pipeline's error-level events of its rules, by system and rule."
  }

  assert {
    condition = (
      jsondecode(one([for r in grafana_rule_group.events.rule : r if r.labels.alert_id == "ALR2"]).data[0].model).expr ==
      "sum by (system, service_name, service_version, rule) (count_over_time({service_name=\"pipeline\", detected_level=\"warn\"} | event=~\"rule_checked|schema_drift_field\" [5m]))"
    )
    error_message = "ALR2 must count the pipeline's warn-level events of its rules, by system and rule."
  }

  assert {
    condition = alltrue([
      for r in grafana_rule_group.events.rule :
      r.labels.urgency == "ticket" && r.annotations.checks == "{{ $labels.rule }}" && r.annotations.catalog_section == "runtime-rules"
      if contains(["ALR1", "ALR2"], r.labels.alert_id)
    ])
    error_message = "ALR1 and ALR2 must be tickets that check the rule taken from the event, in the runtime rules' section."
  }
}

# Verifies d009 R9
run "alr3_selects_the_failed_page_deployment_as_a_ticket" {
  command = plan

  assert {
    condition = (
      jsondecode(one([for r in grafana_rule_group.events.rule : r if r.labels.alert_id == "ALR3"]).data[0].model).expr ==
      "sum by (system, service_name, service_version) (count_over_time({service_name=\"pipeline\"} | event=~\"page_deploy_failed\" [5m]))"
    )
    error_message = "ALR3 must count the pipeline's failed page deployments."
  }

  assert {
    condition     = one([for r in grafana_rule_group.events.rule : r if r.labels.alert_id == "ALR3"]).labels.urgency == "ticket"
    error_message = "ALR3 must be a ticket."
  }
}

# Verifies d009 R16
run "alr9_counts_the_actionable_events_no_alert_reads_as_a_ticket" {
  command = plan

  assert {
    condition = (
      jsondecode(one([for r in grafana_rule_group.events.rule : r if r.labels.alert_id == "ALR9"]).data[0].model).expr ==
      "sum by (system, service_name, service_version, event) (count_over_time({service_name=~\".+\"} | event=~\"${local.alr9_event_regex}\" [5m]))"
    )
    error_message = "ALR9 must count, in every component, the events of its registry selector."
  }

  assert {
    condition     = one([for r in grafana_rule_group.events.rule : r if r.labels.alert_id == "ALR9"]).labels.urgency == "ticket"
    error_message = "ALR9 must be a ticket."
  }
}

# Verifies d009 R17
run "alr10_counts_index_refreshes_with_unknown_feeds_as_a_ticket" {
  command = plan

  # Capture's sender writes an array field as its JSON text, so no unknown feed is "[]".
  assert {
    condition = (
      jsondecode(one([for r in grafana_rule_group.events.rule : r if r.labels.alert_id == "ALR10"]).data[0].model).expr ==
      "sum by (system, service_name, service_version) (count_over_time({service_name=\"capture\"} | event=~\"index_refreshed\" | unknown_feeds!=\"\" | unknown_feeds!=\"[]\" [5m]))"
    )
    error_message = "ALR10 must count capture's index refreshes whose unknown_feeds is not empty."
  }

  assert {
    condition     = one([for r in grafana_rule_group.events.rule : r if r.labels.alert_id == "ALR10"]).labels.urgency == "ticket"
    error_message = "ALR10 must be a ticket."
  }
}

# Verifies d009 R18
run "alr11_counts_the_missed_minute_causes_outside_d9s_table_as_a_ticket" {
  command = plan

  assert {
    condition = (
      jsondecode(one([for r in grafana_rule_group.events.rule : r if r.labels.alert_id == "ALR11"]).data[0].model).expr ==
      "sum by (system, service_name, service_version, feed, error_type) (count_over_time({service_name=\"capture\"} | event=~\"feed_failed|index_rejected\" | error_type!~\"http|timeout|write\" [5m]))"
    )
    error_message = "ALR11 must count capture's failures whose error_type is none of D9's causes."
  }

  assert {
    condition = (
      one([for r in grafana_rule_group.events.rule : r if r.labels.alert_id == "ALR11"]).labels.urgency == "ticket" &&
      one([for r in grafana_rule_group.events.rule : r if r.labels.alert_id == "ALR11"]).annotations.checks == "DQM11" &&
      one([for r in grafana_rule_group.events.rule : r if r.labels.alert_id == "ALR11"]).annotations.catalog_section == "quality-indicators"
    )
    error_message = "ALR11 must be a ticket that checks DQM11, in the quality indicators' section."
  }
}

# Verifies d009 R22
run "alr14_counts_the_events_the_registry_does_not_hold_as_a_ticket" {
  command = plan

  assert {
    condition = (
      jsondecode(one([for r in grafana_rule_group.events.rule : r if r.labels.alert_id == "ALR14"]).data[0].model).expr ==
      "sum by (system, service_name, service_version, event) (count_over_time({service_name=~\".+\"} | event!~\"${local.registered_events_regex}\" [5m]))"
    )
    error_message = "ALR14 must count, in every component, the events outside the registry."
  }

  assert {
    condition     = one([for r in grafana_rule_group.events.rule : r if r.labels.alert_id == "ALR14"]).labels.urgency == "ticket"
    error_message = "ALR14 must be a ticket."
  }
}

# Verifies d009 R23
run "every_event_rule_carries_its_id_component_and_the_annotations_the_template_reads" {
  command = plan

  assert {
    condition     = toset([for r in grafana_rule_group.events.rule : r.labels.alert_id]) == toset(["ALR1", "ALR2", "ALR3", "ALR9", "ALR10", "ALR11", "ALR14"])
    error_message = "The event rules must be ALR1, ALR2, ALR3, ALR9, ALR10, ALR11 and ALR14."
  }

  assert {
    condition = alltrue([
      for r in grafana_rule_group.events.rule :
      r.name == r.labels.alert_id &&
      r.labels.component == "{{ $labels.service_name }}" &&
      r.labels.version == "{{ $labels.service_version }}" &&
      length(r.annotations.summary) > 0 &&
      strcontains(jsondecode(r.data[0].model).expr, r.annotations.events_query)
    ])
    error_message = "Every event rule must carry its ID, component and version labels, a summary and the query of its events."
  }
}

# Verifies d009 R41
run "every_event_rule_groups_by_system_and_names_none" {
  command = plan

  assert {
    condition = alltrue([
      for r in grafana_rule_group.events.rule :
      startswith(jsondecode(r.data[0].model).expr, "sum by (system, ") &&
      length(regexall("(?i)ambici|bicing", r.data[0].model)) == 0
    ])
    error_message = "Every event rule must group by system and name no system."
  }
}

# One event is enough: each rule fires at once when its count is above 0, and no event
# is a normal state, not missing data.
run "every_event_rule_fires_on_one_event" {
  command = plan

  assert {
    condition = alltrue([
      for r in grafana_rule_group.events.rule :
      r.condition == "B" &&
      r.for == "0s" &&
      r.no_data_state == "OK" &&
      jsondecode(r.data[1].model).type == "threshold" &&
      jsondecode(r.data[1].model).expression == "A" &&
      jsondecode(r.data[1].model).conditions[0].evaluator.type == "gt" &&
      jsondecode(r.data[1].model).conditions[0].evaluator.params[0] == 0
    ])
    error_message = "Every event rule must fire at once on a count above 0, with no data as OK."
  }
}
