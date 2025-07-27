resource "kubernetes_namespace" "classifier" {
  metadata {
    name = "classifier"
  }
}

resource "kubernetes_ingress_v1" "classifier" {
  metadata {
    name      = "classifier-ingress"
    namespace = kubernetes_namespace.classifier.metadata[0].name
    annotations = {
      "kubernetes.io/ingress.class"                = "nginx"
      "nginx.ingress.kubernetes.io/rewrite-target" = "/"
      "nginx.ingress.kubernetes.io/ssl-redirect"   = var.environment == "production" ? "true" : "false"
    }
  }

  spec {
    rule {
      host = var.classifier_domain
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = "classifier"
              port {
                number = 8000
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
        hosts       = [var.classifier_domain]
        secret_name = "classifier-tls"
      }
    }
  }

  depends_on = [helm_release.nginx_ingress, kubernetes_namespace.classifier]
}


resource "kubernetes_deployment_v1" "classifier" {
  metadata {
    name      = "classifier"
    namespace = kubernetes_namespace.classifier.metadata[0].name
  }

  depends_on = [ kubernetes_namespace.classifier ]

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "classifier"
      }
    }

    template {
      metadata {
        labels = {
          app = "classifier"
        }
      }

      spec {
        container {
          name  = "classifier"
          image = "ghcr.io/spencershepard/mlops-precision-lens/classifier:develop"

          port {
            container_port = 8000
          }

          env {
            name  = "ENVIRONMENT"
            value = var.environment
          }

          env_from {
            config_map_ref {
              name = "classifier-config"
            }
          }

          env_from {
            secret_ref {
              name = "classifier-secrets"
            }
          }

        }

      }
    }
  }
}

resource "kubernetes_service" "classifier" {
  metadata {
    name      = "classifier"
    namespace = kubernetes_namespace.classifier.metadata[0].name
  }
  spec {
    selector = {
      app = "classifier"
    }
    port {
      port        = 8000
      target_port = 8000
      protocol    = "TCP"
    }
    type = "ClusterIP"
  }
}

resource "kubernetes_secret" "classifier_secrets" {
  metadata {
    name      = "classifier-secrets"
    namespace = kubernetes_namespace.classifier.metadata[0].name
  }
  data = local.secrets
}

resource "kubernetes_config_map" "classifier_config" {
  metadata {
    name      = "classifier-config"
    namespace = kubernetes_namespace.classifier.metadata[0].name
  }
  data = local.config
}