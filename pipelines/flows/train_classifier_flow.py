import boto3
import os
from datetime import datetime, timezone, timedelta
from kubernetes import client, config
import dotenv
import base64
import yaml

local_development = not os.getenv("PREFECT_API_URL")
if local_development:
    print("Running in local development mode.")
    os.environ["PREFECT_API_URL"] = "http://prefect.local:30080/api"
    print("PREFECT_API_URL not set in local environment, using default.")
    # Load environment variables from .env files
    secrets_path = "../../secrets.env"
    config_path = "../../config.env"
    if os.path.exists(secrets_path) and os.path.exists(config_path):
        dotenv.load_dotenv(secrets_path)
        dotenv.load_dotenv(config_path)
    else:
        print(f"Warning: {secrets_path} or {config_path} not found. Environment variables may not be set correctly.")

# Load Prefect after setting the environment variable
from prefect import flow, task, get_run_logger
from prefect.settings import PREFECT_API_URL
print(f"PREFECT_API_URL setting: {PREFECT_API_URL.value()}")

# AWS credentials and bucket configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
BUCKET_NAME = os.getenv("BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION")

PREFIX = ""

if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    raise ValueError("AWS credentials are not set in environment variables.")

@task
def get_env_vars():
    logger = get_run_logger()
    # get the os environment variables
    envvars = []
    for key, value in os.environ.items():
        envvars.append(f"{key}={value}")
    logger.info(f"Environment variables: {envvars}")

@task
def list_new_s3_keys(since_minutes_ago=10):
    logger = get_run_logger()
    s3 = boto3.client('s3', 
                     region_name=os.getenv('AWS_REGION'),
                     aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'), 
                     aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))
    since = datetime.now(timezone.utc) - timedelta(minutes=since_minutes_ago)

    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=PREFIX)
    new_keys = []

    for obj in response.get("Contents", []):
        if obj["LastModified"] > since:
            new_keys.append(obj["Key"])

    logger.info(f"Found {len(new_keys)} new S3 keys")
    return new_keys

@task
def trigger_k8s_job(s3_key: str):
    logger = get_run_logger()
    logger.info(f"Starting Kubernetes job")
    KUBECONFIG_B64 = os.getenv("KUBECONFIG_B64")
    logger.info(f"KUBECONFIG_B64 present: {KUBECONFIG_B64}")
    return # Leave in place for now
    
    if KUBECONFIG_B64:
        try:
            # Decode base64 kubeconfig content
            kubeconfig_content = base64.b64decode(KUBECONFIG_B64).decode('utf-8')
            # Parse YAML content directly
            kubeconfig_dict = yaml.safe_load(kubeconfig_content)
            # Load config from dictionary (in-memory, no files)
            config.load_kube_config_from_dict(kubeconfig_dict)
            logger.info("Using base64 encoded kubeconfig from memory")
        except Exception as e:
            logger.error(f"Failed to load kubeconfig from base64: {e}")
            raise
    else:
        # Fallback options
        try:
            config.load_incluster_config()
            logger.info("Using in-cluster config")
        except config.ConfigException:
            config.load_kube_config()
            logger.info("Using default kubeconfig file")

    batch = client.BatchV1Api()

    job_name = f"s3-process-{s3_key.replace('/', '-')[:50].lower()}"
    job_spec = client.V1Job(
        metadata=client.V1ObjectMeta(name=job_name),
        spec=client.V1JobSpec(
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"job": job_name}),
                spec=client.V1PodSpec(
                    restart_policy="Never",
                    containers=[
                        client.V1Container(
                            name="processor",
                            image="your-docker-image:tag",
                            args=[s3_key],
                        )
                    ],
                ),
            )
        ),
    )

    batch.create_namespaced_job(namespace="default", body=job_spec)
    logger.info(f"Created Kubernetes job: {job_name}")

@flow(name="s3-monitor-flow")
def s3_monitor_flow():
    logger = get_run_logger()
    get_env_vars()
    # new_keys = list_new_s3_keys()
    # if new_keys:
    #     trigger_k8s_job(new_keys[0])
    logger.info("Starting S3 monitor flow")
    trigger_k8s_job("example-s3-key")

def create_deployment():
    """Create and deploy the flow to the Prefect server"""
    deployment = s3_monitor_flow.deploy(
        name="s3-triggered-classifier-training",
        work_pool_name="my-pool",
        image="your-registry/mlops-precision-lens:latest",
        cron="0 * * * *",
        tags=["s3", "monitoring", "ml"],
    )
    print(f"Deployment created: {deployment}")
    return deployment

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "deploy":
        create_deployment()
    else:
        s3_monitor_flow()