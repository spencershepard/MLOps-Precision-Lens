import os
import dotenv
from train_classifier_flow import s3_monitor_flow

# Load environment variables for deployment
local_development = not os.getenv("PREFECT_API_URL")
if local_development:
    print("Running deployment in local development mode.")
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
        cron="0 * * * *",  # Run every hour
        build=True,  # Build from existing Dockerfile in the current directory
        tags=["s3", "monitoring", "ml", "classifier-training"],
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
