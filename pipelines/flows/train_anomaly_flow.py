import boto3
import os
from datetime import datetime, timezone, timedelta
from kubernetes import client, config
import dotenv
import base64
import prefect.input
import prefect.states
import yaml
import re

FLOW_VERSION="1.0.0"
os.environ.setdefault("PREFECT_LOGGING_LEVEL", "INFO")

local_development = not os.getenv("PREFECT_API_URL")
if local_development:
    print("Running in local development mode.")
    os.environ["PREFECT_API_URL"] = "http://prefect.local:30080/api"

# Load Prefect after setting the environment variable
from prefect import flow, task, get_run_logger
from prefect.settings import PREFECT_API_URL
from prefect_kubernetes import KubernetesJob
from prefect_kubernetes.credentials import KubernetesCredentials
from prefect.variables import Variable
print(f"PREFECT_API_URL setting: {PREFECT_API_URL.value()}")

from prefect_aws import AwsCredentials
from prefect_aws.s3 import S3Bucket
from k8s_utils import sanitize_k8s_name

aws_credentials_block = AwsCredentials.load("my-aws")
s3_bucket = S3Bucket.load("my-s3")

def _to_str(val):
    # Prefect SecretStr or plain string
    return val.get_secret_value() if hasattr(val, "get_secret_value") else val

AWS_ACCESS_KEY_ID = _to_str(aws_credentials_block.aws_access_key_id)
AWS_SECRET_ACCESS_KEY = _to_str(aws_credentials_block.aws_secret_access_key)
BUCKET_NAME = s3_bucket.bucket_name
AWS_REGION = aws_credentials_block.region_name

MLFLOW_URI = Variable.get("MLFLOW_URI", default="http://mlflow.mlflow.svc.cluster.local:80")
ANOMALY_CATEGORY = Variable.get("anomaly_category", default="XRFC-PCB-Quality")
MAX_EPOCHS = Variable.get("max_epochs", default="100")
CACHE_DIRECTORY = Variable.get("cache_directory", default="s3cache")

PREFIX = ""

if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    raise ValueError("AWS credentials are not set in environment variables.")
if not BUCKET_NAME:
    raise ValueError("S3 bucket name is not set in environment variables.")

@task
def trigger_k8s_job():
    logger = get_run_logger()
    logger.info(f"Flow version: {FLOW_VERSION}")
    logger.info(f"Starting Kubernetes job for anomaly training using Prefect KubernetesJob")

    k8s_creds = KubernetesCredentials.load("my-k8s-creds")
    epoch_secs = int(datetime.now(timezone.utc).timestamp())
    job_name = f"train-anomaly-{ANOMALY_CATEGORY}-{epoch_secs}"

    job_name = sanitize_k8s_name(job_name)
    logger.info(f"Job name: {job_name}")

    job_spec = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": job_name},
        "spec": {
            "template": {
                "metadata": {"labels": {"job": job_name}},
                "spec": {
                    "restartPolicy": "Never",
                    "containers": [
                        {
                            "name": "anomaly-trainer",
                            "image": "ghcr.io/spencershepard/mlops-precision-lens/anomaly-train:develop",
                            "env": [
                                {
                                    "name": "AWS_ACCESS_KEY_ID",
                                    "value": AWS_ACCESS_KEY_ID
                                },
                                {
                                    "name": "AWS_SECRET_ACCESS_KEY",
                                    "value": AWS_SECRET_ACCESS_KEY
                                },
                                {
                                    "name": "BUCKET_NAME",
                                    "value": BUCKET_NAME
                                },
                                {
                                    "name": "AWS_REGION_NAME",
                                    "value": AWS_REGION
                                },
                                {
                                    "name": "MLFLOW_URI",
                                    "value": MLFLOW_URI
                                },
                                {
                                    "name": "CATEGORY",
                                    "value": ANOMALY_CATEGORY
                                },
                                {
                                    "name": "MAX_EPOCHS",
                                    "value": MAX_EPOCHS
                                },
                                {
                                    "name": "CACHE_DIRECTORY",
                                    "value": CACHE_DIRECTORY
                                },
                            ],
                            "volumeMounts": [
                                {
                                    "name": "s3cache-volume",
                                    "mountPath": "/mnt/s3cache"
                                }
                            ],
                        }
                    ],
                    "volumes": [
                        {
                            "name": "s3cache-volume",
                            "persistentVolumeClaim": {
                                "claimName": "s3cache-pvc"
                            }
                        }
                    ],
                },
            }
        },
    }

    k8s_job = KubernetesJob(
        v1_job=job_spec,
        credentials=k8s_creds,
        namespace="models"
    )

    run = k8s_job.trigger()
    run.wait_for_completion()
    job_name = job_spec["metadata"]["name"]
    logger.info(f"job_name: {job_name}")
    # Fetch and log job results (logs from pods)
    try:
        result = run.fetch_result()
        logger.info(f"Kubernetes job logs: {result}")
    except Exception as e:
        logger.error(f"Failed to fetch job logs: {e}")


@flow(name="train-anomaly-flow", log_prints=True)
def train_anomaly_flow():
    logger = get_run_logger()
    logger.info("Starting anomaly detection training job...")
    trigger_k8s_job()
    logger.info("Anomaly detection training job triggered successfully.")

if __name__ == "__main__":
    train_anomaly_flow()
