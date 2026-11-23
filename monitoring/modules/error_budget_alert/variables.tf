# The inputs of ALR6's rule group for one system (d009, Error budget alert module).

variable "system" {
  description = "Bike sharing system the alert covers, as capture's events name it in `system`."
  type        = string
}

variable "target" {
  description = "The system's DQM7 target as a fraction; its budget is 1 - target."
  type        = number

  validation {
    condition     = var.target > 0 && var.target < 1
    error_message = "target is a fraction between 0 and 1."
  }
}

variable "folder_uid" {
  description = "Grafana folder that holds the rule group."
  type        = string
}

variable "loki_datasource_uid" {
  description = "Loki data source the queries run on."
  type        = string
}

variable "capture_silent_s" {
  description = "Seconds with no capture event after which ALR8 fires; the rules hold only while capture has an event within them, so a broken send never pages for data that R2 holds."
  type        = number
}
