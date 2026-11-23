# Grafana's provider, configured only from variables (d009 R37).
provider "grafana" {
  url             = var.grafana_url
  auth            = var.grafana_auth
  sm_url          = var.grafana_sm_url
  sm_access_token = var.grafana_sm_access_token
}
