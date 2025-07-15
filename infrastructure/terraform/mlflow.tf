
# data "template_file" "postgresql_values" {
#   template = file("${path.module}/postgresql-values.yaml.tmpl")
#   vars = {
#     db_user     = var.db_user
#     db_password = var.db_password
#     mlflow_db_name     = var.mlflow_db_name
#   }
# }

# resource "helm_release" "postgresql" {
#   name       = "mlflow-db"
#   repository = "https://charts.bitnami.com/bitnami"
#   chart      = "postgresql"
#   namespace  = kubernetes_namespace.mlflow.metadata[0].name
#   description = "Install complete"
#   values = [data.template_file.postgresql_values.rendered]
# }

resource "kubernetes_namespace" "mlflow" {
  metadata {
    name = "mlflow"
  }
}

resource "kubernetes_persistent_volume_claim" "mlflow_pvc" {
  metadata {
    name      = "mlflow-pvc"
    namespace = kubernetes_namespace.mlflow.metadata[0].name
  }
  
  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = "hostpath"
    resources {
      requests = {
        storage = "5Gi"
      }
    }
  }
}

resource "helm_release" "mlflow" {
  name       = "mlflow"
  repository = "https://community-charts.github.io/helm-charts"
  chart      = "mlflow"
  # version    = "5.1.0"
  namespace  = kubernetes_namespace.mlflow.metadata[0].name
  depends_on = [kubernetes_persistent_volume_claim.mlflow_pvc]
  values = [file("${path.module}/../k8s/charts/mlflow-values.yaml")]
}

#debug the rendered values

output "mlflow_values" {
  value = helm_release.mlflow.values
}