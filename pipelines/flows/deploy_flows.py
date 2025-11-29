import os
import dotenv
import sys

# Provide the Prefect API URL if needed (ie. local development)
if len(sys.argv) > 1:
    os.environ["PREFECT_API_URL"] = sys.argv[1]

IS_LOCAL_DEV = False
if not os.getenv("PREFECT_API_URL"):
    IS_LOCAL_DEV = True
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


@flow(name="trigger-deployment-job", log_prints=True)
def trigger_deployment_job_flow():
    """Trigger the Kubernetes deployment job to pull latest Prefect image and redeploy flows"""
    logger = get_run_logger()
    logger.info("Triggering Kubernetes deployment job to pull latest Prefect image...")
    
    from prefect_kubernetes import KubernetesJob
    from prefect_kubernetes.credentials import KubernetesCredentials
    from datetime import datetime, timezone
    from k8s_utils import sanitize_k8s_name
    
    k8s_creds = KubernetesCredentials.load("my-k8s-creds")
    epoch_secs = int(datetime.now(timezone.utc).timestamp())
    job_name = f"prefect-redeploy-{epoch_secs}"
    job_name = sanitize_k8s_name(job_name)
    
    logger.info(f"Creating job: {job_name}")
    
    job_spec = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": job_name},
        "spec": {
            "backoffLimit": 2,
            "activeDeadlineSeconds": 600,
            "ttlSecondsAfterFinished": 3600,
            "template": {
                "metadata": {"labels": {"app": "prefect-redeploy-job"}},
                "spec": {
                    "restartPolicy": "OnFailure",
                    "containers": [
                        {
                            "name": "prefect-redeploy",
                            "image": "ghcr.io/spencershepard/mlops-precision-lens/prefect:develop",
                            "imagePullPolicy": "Always",
                            "args": ["python", "deploy_flows.py"],
                            "env": [
                                {
                                    "name": "PREFECT_API_URL",
                                    "value": "http://prefect-server.prefect.svc.cluster.local:4200/api"
                                }
                            ],
                        }
                    ],
                },
            }
        },
    }
    
    k8s_job = KubernetesJob(
        v1_job=job_spec,
        credentials=k8s_creds,
        namespace="prefect"
    )
    
    run = k8s_job.trigger()
    logger.info("Job triggered, waiting for completion...")
    run.wait_for_completion()
    
    try:
        result = run.fetch_result()
        logger.info(f"Deployment job completed successfully!")
        logger.info(f"Job logs: {result}")
    except Exception as e:
        logger.error(f"Failed to fetch job logs: {e}")
        raise


def deploy_deployment_trigger_flow():
    """Deploy the deployment trigger flow to Prefect server"""
    print("Deploying deployment trigger flow...")

    deployment = trigger_deployment_job_flow.deploy(
        name="redeploy-with-latest-image",
        work_pool_name="my-pool",
        image="ghcr.io/spencershepard/mlops-precision-lens/prefect:develop",
        build=False,
        tags=["deployment", "admin", "manual"],
        concurrency_limit=1,
        description="Trigger K8s job to pull latest Prefect image and redeploy all flows",
        cron=None,  # Manual triggering only
    )
    return deployment


if __name__ == "__main__":
    # First run: deploy all flows
    deploy_all_flows_flow()
    
    # Then deploy the deployment trigger flow so it can be used from UI (only in K8s)
    if not IS_LOCAL_DEV:
        print("\n" + "="*60)
        print("Now deploying the deployment trigger flow...")
        print("="*60)
        deploy_deployment_trigger_flow()
        print("✅ Deployment trigger flow is now available in Prefect UI!")
        print("   Trigger 'redeploy-with-latest-image' to pull latest Prefect image and redeploy.")
    else:
        print("\n⏭️  Skipping K8s deployment trigger flow in local development mode.")
