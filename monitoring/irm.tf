# IRM: the integration Grafana Alerting sends to, the pages' route and the two
# escalation chains (d009, Notification routing; d009 R34, R35). Terraform manages them
# with the stack service account's token; the owner's personal notification rules and their
# override of Do Not Disturb are set in the app.

data "grafana_oncall_user" "owner" {
  username = var.irm_owner_username
}

resource "grafana_oncall_integration" "alerting" {
  name = "Grafana Alerting"
  type = "grafana_alerting"

  # IRM's own layout is built from the alert's labels and annotations and ignores the
  # message the contact point sends; these show that message, the layout of
  # project.message with the alert's ID, checks and links (d009 R23, R24, DI7).
  templates {
    web {
      message = "{{ payload.message }}"
    }
    mobile_app {
      message = "{{ payload.message }}"
    }
  }

  # The default route takes every alert group that no other route matches: the tickets.
  default_route {
    escalation_chain_id = grafana_oncall_escalation_chain.ticket.id
  }
}

# A ticket enters the list of alert groups with no notification: its chain has no steps.
resource "grafana_oncall_escalation_chain" "ticket" {
  name = "ticket"
}

resource "grafana_oncall_escalation_chain" "page" {
  name = "page"
}

# A page notifies the owner as important, waits 5 min and repeats from the beginning 5
# times: 6 notifications in about 25 min, then the alert group stays in the list until it
# is acknowledged.
resource "grafana_oncall_escalation" "page_notify" {
  escalation_chain_id = grafana_oncall_escalation_chain.page.id
  type                = "notify_persons"
  persons_to_notify   = [data.grafana_oncall_user.owner.id]
  important           = true
  position            = 0
}

resource "grafana_oncall_escalation" "page_wait" {
  escalation_chain_id = grafana_oncall_escalation_chain.page.id
  type                = "wait"
  duration            = 300
  position            = 1
}

resource "grafana_oncall_escalation" "page_repeat" {
  escalation_chain_id = grafana_oncall_escalation_chain.page.id
  type                = "repeat_escalation"
  position            = 2
}

# The alert's labels reach IRM's routes as commonLabels of the payload.
resource "grafana_oncall_route" "page" {
  integration_id      = grafana_oncall_integration.alerting.id
  escalation_chain_id = grafana_oncall_escalation_chain.page.id
  routing_type        = "jinja2"
  routing_regex       = "{{ payload.commonLabels.urgency == 'page' }}"
  position            = 0
}
