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

locals {
  # Parse secrets.env into a map
  secrets = {
    for line in split("\n", data.local_file.secrets.content) :
    split("=", line)[0] => split("=", line)[1]
    if length(split("=", line)) == 2
  }
  # Parse config.env into a map
  config = {
    for line in split("\n", data.local_file.config.content) :
    split("=", line)[0] => split("=", line)[1]
    if length(split("=", line)) == 2
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
