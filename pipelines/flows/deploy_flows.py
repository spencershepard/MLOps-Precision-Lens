import os
import dotenv
import sys

# Provide the Prefect API URL if needed (ie. local development)
if len(sys.argv) > 1:
    os.environ["PREFECT_API_URL"] = sys.argv[1]

if not os.getenv("PREFECT_API_URL"):
    print("Running in local development mode.")
    os.environ["PREFECT_API_URL"] = "http://prefect-prefect-server:4200/api"
    
print(f"Using PREFECT_API_URL: {os.environ.get('PREFECT_API_URL', 'Not set')}")

# Load Prefect modules after setting PREFECT_API_URL
from prefect import flow, get_run_logger
from train_classifier_flow import s3_monitor_flow
from train_anomaly_flow import train_anomaly_flow

def deploy_classifier_training_flow():
    """Deploy the S3 monitor training flow to Prefect server"""
    print("Deploying S3 monitor training flow...")

    deployment = s3_monitor_flow.deploy(
        name="s3-triggered-classifier-training",
        work_pool_name="my-pool",
        image="ghcr.io/spencershepard/mlops-precision-lens/prefect:develop",
        build=False,  # If true, Prefect will build it's own image (slower)
        tags=["s3", "monitoring", "ml", "classifier-training"],
        concurrency_limit=1,
        description="Monitors S3 for new data and triggers ML classifier training jobs",
        cron=None,  # Manual triggering only
        # cron="*/5 * * * *",  # Uncomment to run every 5 minutes
    )
    return deployment


def deploy_anomaly_training_flow():
    """Deploy the anomaly training flow to Prefect server"""
    print("Deploying anomaly training flow...")

    deployment = train_anomaly_flow.deploy(
        name="manual-anomaly-training",
        work_pool_name="my-pool",
        image="ghcr.io/spencershepard/mlops-precision-lens/prefect:develop",
        build=False,  # If true, Prefect will build it's own image (slower)
        tags=["ml", "anomaly-training", "manual"],
        concurrency_limit=1,
        description="Manually triggered ML anomaly detection training jobs",
        cron=None,  # Manual triggering only
    )
    return deployment


@flow(name="deploy-all-flows", log_prints=True)
def deploy_all_flows_flow():
    logger = get_run_logger()
    try:
        deployment1 = deploy_classifier_training_flow()
        logger.info(f"✅ Classifier training flow deployed: {deployment1}")
        
        deployment2 = deploy_anomaly_training_flow()
        logger.info(f"✅ Anomaly training flow deployed: {deployment2}")
        
        logger.info("🚀 All flows deployed successfully!")
    except Exception as e:
        logger.error(f"❌ Deployment failed: {e}")
        raise

if __name__ == "__main__":
    deploy_all_flows_flow()
