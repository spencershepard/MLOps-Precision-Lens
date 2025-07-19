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


output "ingress_controller_ip" {
  value = var.environment == "production" ? "Check your cloud provider for LoadBalancer IP" : "Use localhost:30080 or your Kubernetes node IP:30080"
  description = "Ingress controller access information"
}
