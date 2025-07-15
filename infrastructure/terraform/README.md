# Development

### Kubeconfig
The Terraform Kubernetes modules require a .kubeconfig file in the terraform directory. Generate like this:
```bash
kubectl config view --raw --minify > .kubeconfig
```

## Monitoring with Prometheus and Grafana
This repository includes a Prometheus and Grafana stack for monitoring the cluster and applications

The default username and password for Grafana are `admin`/`prom-operator`.