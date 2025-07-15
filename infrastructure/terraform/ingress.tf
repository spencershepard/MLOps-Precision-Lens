# NGINX Ingress Controller
resource "helm_release" "nginx_ingress" {
  name             = "nginx-ingress"
  repository       = "https://kubernetes.github.io/ingress-nginx"
  chart            = "ingress-nginx"
  version          = "4.10.1"
  namespace        = "ingress-nginx"
  create_namespace = true

  values = [
    yamlencode({
      controller = {
        service = {
          type = var.environment == "production" ? "LoadBalancer" : "NodePort"
          nodePorts = var.environment == "production" ? {} : {
            http  = 30080
            https = 30443
          }
        }
        config = {
          "ssl-redirect"           = var.environment == "production" ? "true" : "false"
          "use-forwarded-headers" = "true"
          "client-max-body-size" = "256m" # Allow larger file uploads
        }
      }
    })
  ]
}

# MLflow Ingress
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

resource "kubernetes_ingress_v1" "airflow" {
  metadata {
    name      = "airflow-ingress"
    namespace = kubernetes_namespace.airflow.metadata[0].name
    annotations = {
      "kubernetes.io/ingress.class"                = "nginx"
      "nginx.ingress.kubernetes.io/rewrite-target" = "/"
      "nginx.ingress.kubernetes.io/ssl-redirect"   = var.environment == "production" ? "true" : "false"
    }
  }

  spec {
    rule {
      host = var.airflow_domain
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = "airflow-api-server"
              port {
                number = 8080
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
        hosts       = [var.airflow_domain]
        secret_name = "airflow-tls"
      }
    }
  }

  depends_on = [helm_release.nginx_ingress, helm_release.airflow]
}

# Output the access URL
output "mlflow_url" {
  value = var.environment == "production" ? "https://${var.mlflow_domain}" : "http://mlflow.local:30080"
  description = "URL to access MLflow"
}

output "ingress_controller_ip" {
  value = var.environment == "production" ? "Check your cloud provider for LoadBalancer IP" : "Use localhost:30080 or your Kubernetes node IP:30080"
  description = "Ingress controller access information"
}
