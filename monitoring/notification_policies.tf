# The pages notify only from 08:00 to 23:00, Madrid time, every day; outside it Grafana holds
# the notification and sends it when the interval opens, if the alert still fires
# (d009 R44, Alertmanager's active time intervals).
resource "grafana_mute_timing" "pages_active" {
  name = "pages-daytime"

  intervals {
    location = "Europe/Madrid"

    times {
      start = "08:00"
      end   = "23:00"
    }
  }
}

# The tree has two policies and tickets have none: a ticket falls to the root, whose default
# is IRM, where its route leads to a chain with no steps. An alert groups by its ID and
# system into one notification, repeated every 4 h while it fires, Grafana's default
# (d009, Notification grouping).
resource "grafana_notification_policy" "root" {
  contact_point   = grafana_contact_point.irm.name
  group_by        = ["alert_id", "system"]
  repeat_interval = "4h"

  # ALR12 is first and does not continue, so no other policy routes it to IRM although it
  # carries urgency page (d009 R19, Watchdog).
  policy {
    contact_point   = grafana_contact_point.watchdog.name
    group_by        = ["alert_id"]
    repeat_interval = local.alr12_repeat_interval
    continue        = false

    matcher {
      label = "alert_id"
      match = "="
      value = "ALR12"
    }
  }

  policy {
    contact_point = grafana_contact_point.irm.name
    active_timings = [
      grafana_mute_timing.pages_active.name,
    ]

    matcher {
      label = "urgency"
      match = "="
      value = "page"
    }
  }
}
