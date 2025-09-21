import os
import dotenv
import sys

# Provide the Prefect API URL if needed (ie. local development)
if len(sys.argv) > 1:
    os.environ["PREFECT_API_URL"] = sys.argv[1]
    
print(f"Using PREFECT_API_URL: {os.environ.get('PREFECT_API_URL', 'Not set')}")

# Load Prefect modules after setting PREFECT_API_URL
from train_classifier_flow import s3_monitor_flow
from cleanup_late_runs_flow import cleanup_late_runs_flow  # <-- Add import

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

def deploy_cleanup_late_runs_flow():
    """Deploy the cleanup late Prefect runs flow to Prefect server"""
    print("Deploying cleanup late Prefect runs flow...")

    deployment = cleanup_late_runs_flow.deploy(
        name="cleanup-late-prefect-runs",
        work_pool_name="my-pool",
        image="ghcr.io/spencershepard/mlops-precision-lens/prefect:develop",
        cron="0 * * * *",  # Run every hour
        build=False,
        tags=["cleanup", "prefect", "maintenance"],
        concurrency_limit=1,
        description="Cancels stuck or late Prefect runs older than threshold"
    )

    print(f"✅ Deployment created successfully: {deployment}")
    return deployment

def main():
    try:
        deploy_classifier_training_flow()
        deploy_cleanup_late_runs_flow()  # <-- Add this line
        print("🚀 All flows deployed successfully!")
    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        raise

if __name__ == "__main__":
    main()
