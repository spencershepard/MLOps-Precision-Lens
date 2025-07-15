from flask import jsonify
import mlflow
import os

mlflow.set_tracking_uri(os.getenv('MLFLOW_URI'))

def get_model_choices(filter):
    """
    Fetches the list of available models from MLflow.
    """
    try:
        client = mlflow.tracking.MlflowClient()
        print(f"Fetching models with filter: {filter}")
        models = client.search_registered_models(filter_string=filter)
        model_names = [model.name for model in models]
        return model_names
    except Exception as e:
        print(f"Error fetching models: {e}")
