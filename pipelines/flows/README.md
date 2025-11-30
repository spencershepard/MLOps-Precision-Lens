## Development of Flows
During development, we can run and test flows locally.  Just run the flow script directly. 

## Deploying Flow Changes
In production, we should use CI/CD to deploy flow changes. 

1) Commit and push changes to Github to trigger the build of our Prefect Docker image.
2a) Deploy flows by running 'deploy_flows.py' script locally or in a CI/CD pipeline.
OR..
2b) Use the Prefect UI to trigger the "redeploy-with-latest-image" deployment flow.

## Flow variables 
It's easy to manage flow variables in the Prefect UI.  ie.
`CLASSIFICATION_API_URL = Variable.get("CLASSIFICATION_API_URL", default="http://classifier.models.svc.cluster.local:8000/predict")`