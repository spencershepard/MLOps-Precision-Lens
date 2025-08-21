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

FLOW_VERSION="1.0.1"
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
CLASS_TRAINING_IMG_LIMIT = Variable.get("CLASS_TRAINING_IMG_LIMIT", default="10")

PREFIX = ""

if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    raise ValueError("AWS credentials are not set in environment variables.")
if not BUCKET_NAME:
    raise ValueError("S3 bucket name is not set in environment variables.")

def sanitize_k8s_name(name: str, max_length=63):
    name = name.lower()
    # Replace invalid characters with '-'
    name = re.sub(r'[^a-z0-9\-\.]', '-', name)
    # Ensure starts/ends with alphanumeric
    name = re.sub(r'^[^a-z0-9]+', '', name)
    name = re.sub(r'[^a-z0-9]+$', '', name)
    # Truncate to max_length
    name = name[:max_length]
    # Ensure ends with alphanumeric after truncation
    name = re.sub(r'[^a-z0-9]+$', '', name)
    return name

@task
def list_new_s3_keys(since_minutes_ago=10):
    logger = get_run_logger()
    s3 = boto3.client('s3', 
                     region_name=AWS_REGION,
                     aws_access_key_id=AWS_ACCESS_KEY_ID, 
                     aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
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
    logger.info(f"Flow version: {FLOW_VERSION}")
    logger.info(f"Starting Kubernetes job using Prefect KubernetesJob")

    k8s_creds = KubernetesCredentials.load("my-k8s-creds")
    epoch_secs = int(datetime.now(timezone.utc).timestamp())
    job_name = f"train-classifier-{epoch_secs}-{s3_key}"

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
                            "name": "processor",
                            "image": "ghcr.io/spencershepard/mlops-precision-lens/classifier:develop",
                            "args": ["python", "-u", "train.py"], #ie override Dockerfile CMD
                            #"command": ["python", "train_classifier.py"], #ie override Dockerfile ENTRYPOINT
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
                                    "name": "AWS_REGION",
                                    "value": AWS_REGION
                                },
                                {
                                    "name": "MLFLOW_URI",
                                    "value": MLFLOW_URI
                                },
                                {
                                    "name": "CLASS_TRAINING_IMG_LIMIT",
                                    "value": CLASS_TRAINING_IMG_LIMIT
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


@task
def get_last_processed_time():
    try:
        return Variable.get("last_processed_s3_time")
    except Exception:
        return None

@task
def set_last_processed_time(new_time):
    Variable.set("last_processed_s3_time", new_time, overwrite=True)

@task
def any_new_s3_objects(last_time=None):
    logger = get_run_logger()
    s3 = boto3.client('s3', 
                     region_name=AWS_REGION,
                     aws_access_key_id=AWS_ACCESS_KEY_ID, 
                     aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=PREFIX)
    latest_time = last_time
    found_new = False
    obj_key = None
    for obj in response.get("Contents", []):
        obj_time = obj["LastModified"].isoformat()
        if last_time is None or obj_time > last_time:
            found_new = True
            if latest_time is None or obj_time > latest_time:
                latest_time = obj_time
                obj_key = obj["Key"]
    logger.info(f"Any new S3 objects? {found_new}")
    return found_new, latest_time, obj_key

@flow(name="s3-monitor-flow", log_prints=True)
def s3_monitor_flow():
    logger = get_run_logger()
    last_time = get_last_processed_time()
    found_new, latest_time, obj_key = any_new_s3_objects(last_time)
    if found_new:
        trigger_k8s_job(obj_key)
        if latest_time:
            set_last_processed_time(latest_time)
            logger.info(f"Updated last processed time to {latest_time}")
    else:
        logger.info("No new S3 objects to process.")

if __name__ == "__main__":
    s3_monitor_flow()