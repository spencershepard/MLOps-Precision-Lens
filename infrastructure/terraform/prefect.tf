resource "kubernetes_namespace" "prefect" {
  metadata {
    name = "prefect"
  }
}

resource "helm_release" "prefect-server" {
  name       = "prefect-server"
  repository = "https://prefecthq.github.io/prefect-helm"
  chart      = "prefect-server"
  namespace  = kubernetes_namespace.prefect.metadata[0].name
  depends_on = [kubernetes_namespace.prefect]
  set = [{
    name  = "server.uiConfig.prefectUiApiUrl"
    value = "http://${ var.prefect_domain}:30080/api"
    }]
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

  depends_on = [helm_release.nginx_ingress, helm_release.prefect-server]
}

resource "helm_release" "prefect-worker" {
  name       = "prefect-worker"
  repository = "https://prefecthq.github.io/prefect-helm"
  chart      = "prefect-worker"
  namespace  = kubernetes_namespace.prefect.metadata[0].name
  depends_on = [kubernetes_namespace.prefect, helm_release.prefect-server]
  set = [{
    name  = "worker.apiConfig"
    value = "selfHostedServer"
    }, {
    name  = "worker.selfHostedServerApiConfig.apiUrl"
    value = "http://prefect-server.prefect.svc.cluster.local:4200/api"
    }, {
    name  = "worker.config.workPool"
    value = "my-pool"
  }]
}

# Create a one-time Kubernetes job to run our deployment script with our custom image
resource "kubernetes_job" "create_deployment" {
  depends_on = [ 
    helm_release.prefect-server,
    helm_release.prefect-worker,
    kubernetes_namespace.prefect
  ]
  metadata {
    name      = "deploy-script"
    namespace = kubernetes_namespace.prefect.metadata[0].name
  }

  spec {
    template {
      metadata {
        labels = {
          app = "deploy-script"
        }
      }
      spec {
        container {
          name  = "deploy-script"
          image = "ghcr.io/spencershepard/mlops-precision-lens/prefect:develop"
          command = [
            "/bin/sh",
            "-c",
            "python /app/deploy_flows.py"
          ]
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
