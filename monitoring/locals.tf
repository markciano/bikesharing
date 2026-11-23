# Every threshold and event list the alert rules use. A threshold that depends on the
# pipeline's settings is derived from run_settings.json, so a change of cadence, time
# budget or container size changes it with no rewrite; a fixed one states its reason.
# Event lists come from the event registry, never written by hand (d009 D5, Observability
# catalog; d009, Thresholds).

locals {
  registry     = jsondecode(file("${path.module}/../contracts/log-events.registry.json"))
  run_settings = jsondecode(file("${path.module}/../pipeline/src/bikesharing/core/run_settings.json"))

  # Thresholds derived from the pipeline's settings.

  # ALR4 fires at the target the page promises its visitor: a run's cadence plus its
  # time budget (d009 D8, Page data age keeps its target).
  alr4_max_age_s = local.run_settings.cadence_min * 60 + local.run_settings.time_budget_s

  # ALR7 warns at 80% of each limit that ends a run, the practice for capacity limits.
  alr7_duration_s = local.run_settings.timeout_s * 0.8
  # Modal sizes the container in MiB and the event's peak_memory_mb is decimal MB.
  alr7_memory_mb = ceil(local.run_settings.container_memory_mib * 1048576 / 1000000 * 0.8)

  # ALR8 lets one lost send go, since the copy is best-effort (d009 D2, The copy to
  # Grafana never affects a run): the pipeline is silent after 2 cadences.
  alr8_pipeline_silent_s = local.run_settings.cadence_min * 2 * 60

  # Fixed thresholds.

  # Capture runs one pass a minute (d004, Bronze data capture), so 5 minutes with no
  # event is five passes missing: a broken send, not a single failure (R42).
  alr8_capture_silent_s = 300

  # The check runs more often than the pipeline's cadence, so a stale file is seen
  # within one run's interval.
  synthetic_check_frequency_s = 300

  # Longer than a request to a static file needs, so a slow answer is read and judged
  # by the age of its data and not cut off; the check's frequency stays well above it.
  synthetic_check_timeout_ms = 30000

  # ALR4 fires when at least two of the three probes fail a file, since the age of a
  # file is the same from every location and a single failing probe points to its own
  # network (d009 D14, The synthetic check confirms a failure from two of three probes).
  alr4_probes_to_confirm = 2

  # Prefix of every check's job, which ALR4 selects in Prometheus.
  synthetic_check_job_prefix = "published_file_age_"

  # Twice the longest run of minutes with no clean capture measured, 5; stays quiet in
  # normal operation (d009, Thresholds).
  alr5_minutes_in_a_row = 10

  # ALR5 watches a feed seen in the last 24 h, so a feed that exists but sends no event
  # is still watched through a day of silence; a longer silence is ALR8's and the
  # heartbeat's.
  alr5_feed_seen_window = "24h"

  # The feeds capture fetches in every pass (d004 D3, Feed cadence): station_status
  # of each source and free_bike_status of AMBici. A static feed is fetched once a day,
  # so the alerts that count a feed's minutes leave it out. It duplicates capture's
  # source table, so a new dynamic feed is added here too.
  capture_dynamic_feeds = ["free_bike_status", "station_status"]

  # The feed that holds the station stock, whose clean captures are the minutes DQM7
  # counts and so the ones ALR6 measures (d009 D7, Capture completeness target per
  # system). It duplicates capture's source table, as the list above does.
  alr6_stock_feed = "station_status"

  # The watchdog policy's repeat_interval: the signal must reach Healthchecks.io well
  # inside its period of 5 min and grace of 10 min.
  alr12_repeat_interval = "5m"

  # ALR13 warns at 80% of each Free tier limit (50 GB of logs, 100k synthetic check
  # executions a month), as ALR7 does for a capacity limit.
  alr13_logs_gb              = 40
  alr13_synthetic_executions = 80000

  # The 7-day share of DQM11's target of 30 minutes a month given to capture per feed
  # (d009 D10, A target on capture's own missed minutes only).
  alr15_minutes_given_to_capture = 7

  # Grafana keeps 14 days of events and cannot add up a calendar month, so ALR15 follows
  # a rolling window of the 7 days the threshold above is shared for.
  alr15_window = "7d"

  # Event selectors, built from the registry.

  # The same event name may be registered by two components, so every list is distinct.
  alert_ids = sort(distinct(flatten([for e in local.registry.events : e.alerts])))

  # Each alert's events: those whose `alerts` list holds its ID.
  alert_events = {
    for id in local.alert_ids :
    id => sort(distinct([for e in local.registry.events : e.event if contains(e.alerts, id)]))
  }

  # The same lists as a LogQL regular expression for `event=~"..."`.
  alert_event_regex = { for id, names in local.alert_events : id => join("|", names) }

  # ALR9: events the owner must act on that no alert reads by name.
  alr9_events = sort(distinct([
    for e in local.registry.events : e.event if e.needs_action && length(e.alerts) == 0
  ]))
  alr9_event_regex = join("|", local.alr9_events)

  # ALR14: every event the registry holds, so `event!~"..."` finds one it does not.
  registered_events       = sort(distinct([for e in local.registry.events : e.event]))
  registered_events_regex = join("|", local.registered_events)
}
