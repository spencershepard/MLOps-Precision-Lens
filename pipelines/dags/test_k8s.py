from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

default_args = {
    'owner': 'mlops-team',
    'start_date': datetime(2025, 7, 17),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'test_k8s_simple',
    default_args=default_args,
    description='Simple Kubernetes connection test',
    schedule=None,
    catchup=False,
    tags=['kubernetes', 'test'],
)

test_k8s = KubernetesPodOperator(
    name='test-pod',
    namespace='default',
    image='busybox:latest',
    cmds=['echo'],
    arguments=['Hello from Kubernetes!'],
    get_logs=True,
    is_delete_operator_pod=True,
    in_cluster=False,  # If Airflow is running inside the cluster, we can use a service account token (requires RBAC setup)
    kubernetes_conn_id="my-cluster", # This needs to be set up in Airflow connections (UI)
    dag=dag,
)
