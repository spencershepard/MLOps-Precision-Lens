from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

k = KubernetesPodOperator(
    name="hello-dry-run",
    image="debian",
    cmds=["bash", "-cx"],
    arguments=["echo", "10"],
    labels={"foo": "bar"},
    do_xcom_push=True,
    in_cluster=True,
)

k.dry_run()