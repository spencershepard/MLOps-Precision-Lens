provider "helm" {
  kubernetes = {
    config_path = ".kubeconfig"
  }
}

resource "helm_release" "kube_prometheus_stack" {
  name             = "monitoring"
  namespace        = "monitoring"
  create_namespace = true

  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  #version    = ""

  #values = [file("kube-prom-values.yaml")]
}
