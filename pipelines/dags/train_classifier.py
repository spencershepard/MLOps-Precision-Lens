from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from datetime import datetime

with DAG(
    dag_id='train_classifier',
    start_date=datetime(2025, 1, 1),
    catchup=False,
) as dag:

    train_model = KubernetesPodOperator(
        task_id="train_classifier_task",
        name="classifier-training-job",
        namespace="default",
        image="ghcr.io/spencershepard/mlops-precision-lens/classifier-train:develop", 
        get_logs=True,
        is_delete_operator_pod=True,
        in_cluster=False,  # If Airflow is running inside the cluster, we can use a service account token (requires RBAC setup)
        kubernetes_conn_id="my-cluster", # This needs to be set up in Airflow connections (UI)
    )
