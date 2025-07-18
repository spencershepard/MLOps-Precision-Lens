from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from datetime import datetime

with DAG(
    dag_id='train_classifier',
    start_date=datetime(2025, 1, 1),
    schedule_interval=None,  # one-time manual trigger
    catchup=False,
    tags=['ml', 'training'],
) as dag:

    train_model = KubernetesPodOperator(
        task_id="train_model",
        name="ml-training-job",
        namespace="default",
        image="ghcr.io/spencershepard/mlops-precision-lens/classifier-train:develop", 
        get_logs=True,
        is_delete_operator_pod=True,
        max_active_runs=1
    )
