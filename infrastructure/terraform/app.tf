resource "kubernetes_namespace" "pl-app" {
  metadata {
    name = "pl-app"
  }
}

resource "kubernetes_ingress_v1" "pl-app" {
  metadata {
    name      = "pl-app-ingress"
    namespace = kubernetes_namespace.pl-app.metadata[0].name
    annotations = {
      "kubernetes.io/ingress.class"                = "nginx"
      "nginx.ingress.kubernetes.io/rewrite-target" = "/"
      "nginx.ingress.kubernetes.io/ssl-redirect"   = var.environment == "production" ? "true" : "false"
    }
  }

  spec {
    rule {
      host = var.pl_app_domain
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = "pl-app"
              port {
                number = 8050
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
        hosts       = [var.pl_app_domain]
        secret_name = "pl-app-tls"
      }
    }
  }

  depends_on = [helm_release.nginx_ingress, kubernetes_namespace.pl-app]
}


resource "kubernetes_deployment_v1" "pl-app" {
  metadata {
    name      = "pl-app"
    namespace = kubernetes_namespace.pl-app.metadata[0].name
  }

  depends_on = [ kubernetes_namespace.pl-app ]

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "pl-app"
      }
    }

    template {
      metadata {
        labels = {
          app = "pl-app"
        }
      }

      spec {
        container {
          name  = "pl-app"
          image = "ghcr.io/spencershepard/mlops-precision-lens/precision-lens:develop"

          port {
            container_port = 8050
          }

          env {
            name  = "ENVIRONMENT"
            value = var.environment
          }

          env_from {
            config_map_ref {
              name = "pl-config"
            }
          }

          env_from {
            secret_ref {
              name = "pl-secrets"
            }
          }

        }

      }
    }
  }
}

resource "kubernetes_secret" "pl_app_secrets" {
  metadata {
    name      = "pl-secrets"
    namespace = kubernetes_namespace.pl-app.metadata[0].name
  }
  data = local.secrets
}

resource "kubernetes_config_map" "pl_app_config" {
  metadata {
    name      = "pl-config"
    namespace = kubernetes_namespace.pl-app.metadata[0].name
  }
  data = local.config
}