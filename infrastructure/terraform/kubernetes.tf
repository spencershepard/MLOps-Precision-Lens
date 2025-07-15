provider "kubernetes" {
  config_path = ".kubeconfig"
}


#use yaml file to deploy the service
# resource "kubernetes_manifest" "grafana_service" {
#   manifest = yamldecode(file("${path.module}/../k8s/service.yaml"))
# }
