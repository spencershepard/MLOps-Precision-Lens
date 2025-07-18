from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeysUnchangedSensor
from datetime import datetime, timedelta
import os
from airflow.models.connection import Connection


conn = Connection(
    conn_id="my-aws-connection",
    conn_type="aws",
    login=os.getenv("AWS_ACCESS_KEY_ID"),  # Reference to AWS Access Key ID
    password=os.getenv("AWS_SECRET_ACCESS_KEY"),  # Reference to AWS Secret Access Key
    extra={
        "region_name": os.getenv("AWS_REGION"),
    },
)

with DAG(
    dag_id='train_classifier_model',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['ml', 'training', 'classifier'],
    default_args={
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
    }
) as dag:

    # Sensor to detect new data in S3 bucket, waiting for changes to stop before triggering training
    detect_new_data = S3KeysUnchangedSensor(
        aws_conn_id='my-aws-connection',
        task_id='detect_new_data',
        bucket_name=os.getenv('BUCKET_NAME'),
        bucket_key='*.png',  # pattern based on your data files
        wildcard_match=True,  # Enable wildcard matching for detecting multiple files
        poke_interval=1 * 60,  # Check every seconds
        inactivity_period=10,  # Wait for inactivity before triggering
    )

    train_model = KubernetesPodOperator(
        task_id="train_model",
        name="ml-training-job",
        namespace="default",
        image="ghcr.io/spencershepard/mlops-precision-lens/classifier-train:develop",
        cmds=["python", "train.py"],
        get_logs=True,
        is_delete_operator_pod=True,
    )

    # Define task dependencies
    detect_new_data >> train_model
