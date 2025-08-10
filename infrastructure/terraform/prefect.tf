provider "prefect" {
  endpoint = var.prefect_api_url
}

resource "prefect_variable" "mlflow_uri" {
  name  = "mlflow_uri"
  value = "http://mlflow.mlflow.svc.cluster.local:80"
}

resource "prefect_variable" "class_training_img_limit" {
  name  = "class_training_img_limit"
  value = "10"
}

resource "kubernetes_namespace" "prefect" {
  metadata {
    name = "prefect"
  }
}

resource "kubernetes_ingress_v1" "prefect" {
  metadata {
    name      = "prefect-ingress"
    namespace = kubernetes_namespace.prefect.metadata[0].name
    annotations = {
      "kubernetes.io/ingress.class"                = "nginx"
      "nginx.ingress.kubernetes.io/rewrite-target" = "/"
      "nginx.ingress.kubernetes.io/ssl-redirect"   = var.environment == "production" ? "true" : "false"
    }
  }

  spec {
    rule {
      host = var.prefect_domain
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = "prefect-server"
              port {
                number = 4200
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
        hosts       = [var.prefect_domain]
        secret_name = "prefect-tls"
      }
    }
  }

  depends_on = [kubernetes_namespace.prefect, helm_release.nginx_ingress]
}

resource "helm_release" "prefect-server" {
  name       = "prefect-server"
  repository = "https://prefecthq.github.io/prefect-helm"
  chart      = "prefect-server"
  namespace  = kubernetes_namespace.prefect.metadata[0].name
  depends_on = [kubernetes_namespace.prefect, kubernetes_ingress_v1.prefect]

  set = [
    {
      name  = "server.uiConfig.prefectUiApiUrl"
      value = var.prefect_api_url
    },
    {
      name  = "sqlite.enabled"
      value = "true"
    },
    {
      name  = "sqlite.persistence.enabled"
      value = "true"
    },
    {
      name  = "postgresql.enabled"
      value = "false"
    },
    {
      name  = "service.annotations.tailscale\\.com\\/expose"
      value = "true"
      type = "string"
    }
  ]
}


resource "helm_release" "prefect-worker" {
  name       = "prefect-worker"
  repository = "https://prefecthq.github.io/prefect-helm"
  chart      = "prefect-worker"
  namespace  = kubernetes_namespace.prefect.metadata[0].name
  depends_on = [kubernetes_namespace.prefect, kubernetes_ingress_v1.prefect, helm_release.prefect-server]

  set = [
    {
      name  = "worker.apiConfig"
      value = "selfHostedServer"
    },
    {
      name  = "worker.selfHostedServerApiConfig.apiUrl"
      value = "http://prefect-server.prefect.svc.cluster.local:4200/api"
    },
    {
      name  = "worker.config.workPool"
      value = "my-pool"
    }
  ]
}


resource "prefect_block" "aws_credentials" {
  depends_on = [
    kubernetes_namespace.prefect,
    kubernetes_ingress_v1.prefect,
    helm_release.prefect-server,
    helm_release.prefect-worker,
  ]
  data = jsonencode({
    aws_access_key_id     = local.secrets.AWS_ACCESS_KEY_ID
    aws_secret_access_key = local.secrets.AWS_SECRET_ACCESS_KEY
    aws_region            = local.secrets.AWS_REGION
  })
  name     = "my-aws"
  type_slug = "aws-credentials"
  
}

resource "prefect_block" "s3_bucket" {
  depends_on = [
    kubernetes_namespace.prefect,
    kubernetes_ingress_v1.prefect,
    helm_release.prefect-server,
    helm_release.prefect-worker,
    prefect_block.aws_credentials
  ]
  data = jsonencode({
    bucket_name = local.secrets.BUCKET_NAME
    credentials = prefect_block.aws_credentials.data
  })
  name     = "my-s3"
  type_slug = "s3-bucket"
}

resource "prefect_block" "kubernetes_cluster_config" {
  depends_on = [
    kubernetes_namespace.prefect,
    kubernetes_ingress_v1.prefect,
    helm_release.prefect-server,
    helm_release.prefect-worker,
  ]
  data = jsonencode({
    config = local.kubeconfig
    context_name = "docker-desktop"
  })
  name     = "my-cluster"
  type_slug = "kubernetes-cluster-config"
}

resource "prefect_block" "kubernetes_credentials" {
  depends_on = [
    kubernetes_namespace.prefect,
    kubernetes_ingress_v1.prefect,
    helm_release.prefect-server,
    helm_release.prefect-worker,
    prefect_block.kubernetes_cluster_config
  ]
  data = jsonencode({
    cluster_config = {
      config = local.kubeconfig,
      context_name = "docker-desktop"
    }
  })
  name     = "my-k8s-creds"
  type_slug = "kubernetes-credentials"
}

resource "kubernetes_job" "setup_prefect" {
  depends_on = [
    kubernetes_namespace.prefect,
    kubernetes_ingress_v1.prefect,
    helm_release.prefect-server,
    helm_release.prefect-worker,
    prefect_block.aws_credentials,
    prefect_block.s3_bucket,
    prefect_block.kubernetes_cluster_config,
    prefect_block.kubernetes_credentials,
  ]
  metadata {
    name      = "prefect-setup-job"
    namespace = kubernetes_namespace.prefect.metadata[0].name
  }

  spec {
    backoff_limit          = 2
    active_deadline_seconds = 600
    ttl_seconds_after_finished = 3600 # Time to wait before cleanup
    template {
      metadata {
        labels = {
          app = "prefect-setup-job"
        }
      }
      spec {
        container {
          name  = "prefect-setup-job"
          image = "ghcr.io/spencershepard/mlops-precision-lens/prefect:develop"
          image_pull_policy = "Always"
          args = ["/bin/bash", "-c", "prefect block register -m prefect_aws && prefect block register -m prefect_kubernetes"]
          env {
            name  = "PREFECT_API_URL"
            value = "http://prefect-server.prefect.svc.cluster.local:4200/api"
          }
        }
        restart_policy = "OnFailure"
      }
    }
  }
}


# # # In production, we may want to move deployments to CICD pipelines
resource "kubernetes_job" "prefect_deployment_job" {
  depends_on = [
    kubernetes_namespace.prefect,
    kubernetes_ingress_v1.prefect,
    helm_release.prefect-server,
    helm_release.prefect-worker,
    kubernetes_job.setup_prefect,
    prefect_block.aws_credentials,
    prefect_block.s3_bucket,
    prefect_block.kubernetes_cluster_config,
    prefect_block.kubernetes_credentials,
  ]
  metadata {
    name      = "prefect-deployment-jobs"
    namespace = kubernetes_namespace.prefect.metadata[0].name
  }

  spec {
    backoff_limit          = 2
    active_deadline_seconds = 600
    ttl_seconds_after_finished = 3600 # Time to wait before cleanup
    template {
      metadata {
        labels = {
          app = "prefect-deployment-job"
        }
      }
      spec {
        container {
          name  = "prefect-deployment-job"
          image = "ghcr.io/spencershepard/mlops-precision-lens/prefect:develop"
          image_pull_policy = "Always"
          args = ["python", "deploy_flows.py"]
          env {
            name  = "PREFECT_API_URL"
            value = "http://prefect-server.prefect.svc.cluster.local:4200/api"
          }
        }
        restart_policy = "OnFailure"
      }
    }
  }
  
}
