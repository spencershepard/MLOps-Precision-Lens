from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from datetime import datetime, timedelta
import os
from airflow.models.connection import Connection

with DAG(
    dag_id='train_classifier_model',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['ml', 'training', 'classifier', 's3-trigger'],
    default_args={
        'retries': 1,
        'retry_delay': 120,
    }
) as dag:

    # Sensor to detect new data in S3 bucket, waiting for changes to stop before triggering training
    detect_new_data = S3KeySensor(
        task_id='detect_new_data',
        aws_conn_id='my-aws',
        bucket_name=os.getenv('BUCKET_NAME'),
        bucket_key='*.png',  # pattern based on your data files
        wildcard_match=True,  # Enable wildcard matching for detecting multiple files
        poke_interval=1 * 60,  # Check every seconds
    )

    train_model = KubernetesPodOperator(
        task_id="train_model",
        name="ml-training-job",
        namespace="default",
        image="ghcr.io/spencershepard/mlops-precision-lens/classifier:develop",
        cmds=["python", "train.py"],
        get_logs=True,
        is_delete_operator_pod=True,
    )

    # Define task dependencies
    detect_new_data >> train_model
