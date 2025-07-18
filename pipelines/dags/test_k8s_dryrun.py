from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

k = KubernetesPodOperator(
    name="hello-dry-run",
    image="debian",
    cmds=["bash", "-cx"],
    arguments=["echo", "10"],
    labels={"foo": "bar"},
    do_xcom_push=True,
    is_delete_operator_pod=True,
    in_cluster=False,  # If Airflow is running inside the cluster, we can use a service account token (requires RBAC setup)
    kubernetes_conn_id="my-cluster", # This needs to be set up in Airflow connections (UI),
)

k.dry_run()