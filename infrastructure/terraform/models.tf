resource "kubernetes_namespace" "models" {
  metadata {
    name = "models"
  }
}

resource "kubernetes_persistent_volume_claim" "s3cache" {
  metadata {
    name      = "s3cache-pvc"
    namespace = kubernetes_namespace.models.metadata[0].name
  }
  spec {
    access_modes = ["ReadWriteMany"]
    resources {
      requests = {
        storage = "10Gi"
      }
    }
    storage_class_name = "hostpath"
  }
}

resource "kubernetes_deployment_v1" "classifier" {
  metadata {
    name      = "classifier"
    namespace = kubernetes_namespace.models.metadata[0].name
  }

  depends_on = [ kubernetes_namespace.models, kubernetes_persistent_volume_claim.s3cache ]

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "models"
      }
    }

    template {
      metadata {
        labels = {
          app = "models"
        }
      }

      spec {
        node_selector = {
          "kubernetes.io/hostname" = "docker-desktop"
        }

        volume {
          name = "s3cache"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.s3cache.metadata[0].name
          }
        }

        container {
          name  = "classifier"
          image = "ghcr.io/spencershepard/mlops-precision-lens/classifier:develop"
          args = [ "python", "-u", "predict.py" ]

          volume_mount {
            name      = "s3cache"
            mount_path = "/mnt/s3cache"
          }

          port {
            container_port = 8000
          }

          env {
            name  = "ENVIRONMENT"
            value = var.environment
          }

          env_from {
            config_map_ref {
              name = "models-config"
            }
          }

          env_from {
            secret_ref {
              name = "models-secrets"
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
    namespace = kubernetes_namespace.models.metadata[0].name
  }
  spec {
    selector = {
      app = "models"
    }
    port {
      port        = 8000
      target_port = 8000
      protocol    = "TCP"
    }
    type = "ClusterIP"
  }
}

resource "kubernetes_secret" "models_secrets" {
  metadata {
    name      = "models-secrets"
    namespace = kubernetes_namespace.models.metadata[0].name
  }
  data = local.secrets
}

resource "kubernetes_config_map" "models_config" {
  metadata {
    name      = "models-config"
    namespace = kubernetes_namespace.models.metadata[0].name
  }
  data = local.config
}

