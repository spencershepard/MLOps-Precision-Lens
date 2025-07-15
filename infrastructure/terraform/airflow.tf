resource "kubernetes_namespace" "airflow" {
  metadata {
    name = "airflow"
  }
}

resource "helm_release" "airflow" {
  name       = "airflow"
  repository = "https://airflow.apache.org"
  chart      = "airflow"
  namespace  = kubernetes_namespace.airflow.metadata[0].name
  depends_on = [kubernetes_namespace.airflow]
  values = [file("${path.module}/../k8s/charts/airflow-values.yaml")]
  timeout = 600
}