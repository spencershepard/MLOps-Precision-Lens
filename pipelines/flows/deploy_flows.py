import os
import dotenv
from train_classifier_flow import s3_monitor_flow

# Set up environment variables
in_cluster = os.getenv("KUBERNETES_SERVICE_HOST")
if not in_cluster:
    print("Running deployment in local mode.")
    if not os.getenv("PREFECT_API_URL"):
        print("PREFECT_API_URL not set in local environment, using default.")
        os.environ["PREFECT_API_URL"] = "http://prefect.local:30080/api"
    # Load environment variables from .env files
    secrets_path = "../../secrets.env"
    config_path = "../../config.env"
    if os.path.exists(secrets_path) and os.path.exists(config_path):
        dotenv.load_dotenv(secrets_path)
        dotenv.load_dotenv(config_path)
    else:
        print(f"Warning: {secrets_path} or {config_path} not found. Environment variables may not be set correctly.")

def deploy_classifier_training_flow():
    """Deploy the S3 monitor training flow to Prefect server"""
    print("Deploying S3 monitor training flow...")

    deployment = s3_monitor_flow.deploy(
        name="s3-triggered-classifier-training",
        work_pool_name="my-pool",
        image="ghcr.io/spencershepard/mlops-precision-lens/prefect:develop",
        cron="*/2 * * * *",  # Run every 2 mins
        build=False,  # If true, Prefect will build it's own image (slower)
        tags=["s3", "monitoring", "ml", "classifier-training"],
        concurrency_limit=1,
        description="Monitors S3 for new data and triggers ML classifier training jobs"
    )
    
    print(f"✅ Deployment created successfully: {deployment}")
    return deployment

def main():
    try:
        deploy_classifier_training_flow()
        print("🚀 All flows deployed successfully!")
    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        raise

if __name__ == "__main__":
    main()
