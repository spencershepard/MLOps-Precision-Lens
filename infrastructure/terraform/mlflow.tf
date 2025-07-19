
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


resource "kubernetes_ingress_v1" "mlflow" {
  metadata {
    name      = "mlflow-ingress"
    namespace = kubernetes_namespace.mlflow.metadata[0].name
    annotations = {
      "kubernetes.io/ingress.class"                = "nginx"
      "nginx.ingress.kubernetes.io/rewrite-target" = "/"
      "nginx.ingress.kubernetes.io/ssl-redirect"   = var.environment == "production" ? "true" : "false"
      "nginx.ingress.kubernetes.io/proxy-body-size" = "256m"
      "nginx.ingress.kubernetes.io/proxy-read-timeout" = "600"
      "nginx.ingress.kubernetes.io/proxy-send-timeout" = "600"
    }
  }

  spec {
    rule {
      host = var.mlflow_domain
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = helm_release.mlflow.name
              port {
                number = 80
              }
            }
          }
        }
      }
    }

    # TLS configuration for production
    dynamic "tls" {
      for_each = var.environment == "production" ? [1] : []
      content {
        hosts       = [var.mlflow_domain]
        secret_name = "mlflow-tls"
      }
    }
  }

  depends_on = [helm_release.nginx_ingress, helm_release.mlflow]
}


output "mlflow_url" {
  value = var.environment == "production" ? "https://${var.mlflow_domain}" : "http://mlflow.local:30080"
  description = "URL to access MLflow"
}

#debug the rendered values

# output "mlflow_values" {
#   value = helm_release.mlflow.values
# }