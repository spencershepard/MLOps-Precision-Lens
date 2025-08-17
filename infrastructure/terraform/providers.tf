terraform {
  backend "s3" {
    bucket         = "precision-lens-terraform-state"
    key            = "terraform/terraform.tfstate"
    region        = "us-east-1"
  }
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "3.0.1"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "2.37.1"
    }
    prefect = {
      source = "prefecthq/prefect"
      version = "2.83.0"
    }
  }
  
}