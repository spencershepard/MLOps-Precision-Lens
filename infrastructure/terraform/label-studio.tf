#https://charts.heartex.com/
resource "kubernetes_namespace" "label_studio" {
  metadata {
    name = "label-studio"
  }
}

resource "kubernetes_secret" "label_studio_s3_credentials" {
  depends_on = [ kubernetes_namespace.label_studio ]
  metadata {
    name      = "label-studio-s3-credentials"
    namespace = kubernetes_namespace.label_studio.metadata[0].name
  }

  data = {
    access_key = var.label_studio_access_key
    secret_key = var.label_studio_secret_key
  }
}

resource "helm_release" "label_studio" {
  name       = "label-studio"
  repository = "https://charts.heartex.com/"
  chart      = "label-studio"
  namespace  = kubernetes_namespace.label_studio.metadata[0].name
  values     = [file("${path.module}/../k8s/charts/label-studio-values.yaml")]

  depends_on = [
    kubernetes_namespace.label_studio,
    kubernetes_secret.label_studio_s3_credentials
  ]
}

