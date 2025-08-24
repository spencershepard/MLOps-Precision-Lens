## Deploying Flow Changes
In production, we should use CI/CD to deploy flow changes. For now, we'll use `terraform apply --replace kubernetes_job.prefect_deployment_job` once changes are committed to the repository.

## Flow variables 
It's easy to manage flow variables in the Prefect UI.  ie.
`CLASSIFICATION_API_URL = Variable.get("CLASSIFICATION_API_URL", default="http://classifier.models.svc.cluster.local:8000/predict")`