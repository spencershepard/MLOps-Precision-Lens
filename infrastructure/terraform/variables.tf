# variable "db_user" {
#   type = string
#   sensitive = true
# }

# variable "db_password" {
#   type = string
#   sensitive = true
# }

# variable "mlflow_db_name" {
#   type = string
#   default = "mlflow"
# }

# variable "mlflow_artifact_root" {
#   type = string
#   description = "Artifact storage path (e.g. s3://bucket/path or file:///mlruns)"
# }

# variable "mlflow_auth_password" {
#   type = string
#   sensitive = true
#   description = "Password for MLflow UI authentication (must be longer than 12 characters)"
  
#   validation {
#     condition     = length(var.mlflow_auth_password) > 12
#     error_message = "MLflow admin password must be longer than 12 characters."
#   }
# }

variable "environment" {
  type        = string
  description = "Environment name (development, staging, production)"
  default     = "development"
  
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be one of: development, staging, production."
  }
}

variable "base_domain" {
  type        = string
  description = "Base domain for production deployments (e.g., company.com)"
  default     = "local"
}

variable "mlflow_domain" {
  type        = string
  description = "Domain name for MLflow in production (e.g., mlflow.company.com)"
  default     = "mlflow.local"
}

variable "label_studio_domain" {
  type        = string
  description = "Domain name for Label Studio in production (e.g., label-studio.company.com)"
  default     = "labelstudio.local"
}

variable "airflow_domain" {
  type        = string
  description = "Domain name for Airflow in production (e.g., airflow.company.com)"
  default     = "airflow.local"
}

variable "prefect_domain" {
  type        = string
  description = "Domain name for Prefect in production (e.g., prefect.company.com)"
  default     = "prefect.local"
}

variable "pl_app_domain" {
  type        = string
  description = "Domain name for Precision Lens app in production (e.g., pl.company.com)"
  default     = "precision-lens.local"
}

variable "label_studio_access_key" {
  type        = string
  description = "Access key for Label Studio S3"
  default     = ""
  sensitive   = true
}

variable "label_studio_secret_key" {
  type        = string
  description = "Secret key for Label Studio S3"
  default     = ""
  sensitive   = true
}