from flask import jsonify
import mlflow
import os

MLFLOW_URI = os.getenv('MLFLOW_URI')
mlflow.set_tracking_uri(MLFLOW_URI)
print(f"MLflow tracking URI set to: {MLFLOW_URI}")

def get_model_choices(filter):
    """
    Fetches the list of available models from MLflow.
    """
    try:
        client = mlflow.tracking.MlflowClient()
        print(f"Fetching models with filter: {filter}")
        models = client.search_registered_models(filter_string=filter)
        model_names = [model.name for model in models]
        print(f"Found models: {model_names}")
        return model_names
    except Exception as e:
        print(f"Error fetching models: {e}")
