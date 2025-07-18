provider "kubernetes" {
  config_path = ".kubeconfig"
}


# Read secrets.env and config.env files
data "local_file" "secrets" {
  filename = "${path.module}/../../secrets.env"
}

data "local_file" "config" {
  filename = "${path.module}/../../config.env"
}

## I'm not super confident in this env file parsing, so if trying to debug
## check the output debug blocks.  Also you could overwrite with 
## `kubectl create secret generic pl-secrets --from-env-file=secrets.env`
locals {
  # Parse secrets.env into a map, trimming whitespace and ignoring empty lines
  secrets = {
    for line in compact(split("\n", data.local_file.secrets.content)) :
    trimspace(split("=", line)[0]) => (
      # Remove surrounding quotes if present
      length(regexall("^\"(.*)\"$", trimspace(split("=", line)[1]))) > 0 
        ? replace(trimspace(split("=", line)[1]), "/^\"(.*)\"$/", "$1") 
        : trimspace(split("=", line)[1])
    )
    if length(split("=", line)) == 2 && trimspace(line) != ""
  }
  
  # Parse config.env into a map, trimming whitespace and ignoring empty lines
  config = {
    for line in compact(split("\n", data.local_file.config.content)) :
    trimspace(split("=", line)[0]) => (
      # Remove surrounding quotes if present
      length(regexall("^\"(.*)\"$", trimspace(split("=", line)[1]))) > 0 
        ? replace(trimspace(split("=", line)[1]), "/^\"(.*)\"$/", "$1") 
        : trimspace(split("=", line)[1])
    )
    if length(split("=", line)) == 2 && trimspace(line) != ""
  }
}

resource "kubernetes_secret" "pl_secrets" {
  metadata {
    name      = "pl-secrets"
    namespace = "default"
  }
  data = local.secrets
}

resource "kubernetes_config_map" "pl_config" {
  metadata {
    name      = "pl-config"
    namespace = "default"
  }
  data = local.config
}

output "config_map_debug" {
  value = {
    for key, value in local.config : key => {
      value       = value
      length      = length(value)
      byte_length = length(jsonencode(value)) - 2  # Subtract 2 for the quotes
      json_debug  = jsonencode(value)
    }
  }
  sensitive = false 
}

output "secrets_debug" {
  value = {
    for key, value in local.secrets : key => {
      length      = length(value)
      byte_length = length(jsonencode(value)) - 2  # Subtract 2 for the quotes
    }
  }
  sensitive = true
}
