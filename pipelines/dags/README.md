## Configure Airflow

Airflow is installed via this repository's Terraform configuration. Once running, login to the UI (ie airflow.local:30080) and create a new connection for Kubernetes.

Generate your kubeconfig file with the following command:

```bash
kubectl config -o json view --raw
```

Then paste into the UI to create a new connection.