# The project's own message template, so that every notification is short on a phone and
# links the catalogs (d009 #11). Terraform fills the two values the layout cannot read from
# an alert: the repository's base URL and the Loki data source of the Explore link.
resource "grafana_message_template" "notification" {
  name = "project_notification"
  template = templatefile("${path.module}/templates/notification.tmpl", {
    github_base_url     = var.github_base_url
    loki_datasource_uid = var.loki_datasource_uid
  })
}
