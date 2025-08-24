# this downloads the latest model from mlflow registry and runs as an API
import os
import mlflow
from mlflow.tracking import MlflowClient
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import numpy as np
from sklearn.svm import SVC
from sklearn.model_selection import GridSearchCV
from PIL import Image
from io import BytesIO
import base64
from skimage.io import imread
from skimage.transform import resize
from dotenv import load_dotenv
import time
import logging
import pickle
from datetime import datetime

load_dotenv()
app = FastAPI()

print("Starting model prediction service...")
MLFLOW_URI = os.getenv("MLFLOW_URI")
if not MLFLOW_URI:
    raise ValueError("MLFLOW_URI environment variable is not set.")
MODEL_NAME = "Precision Lens Classifier"
CACHE_DIR = "cache"

print(f"Using cache directory: {CACHE_DIR}")
print(f"Setting MLflow tracking URI: {MLFLOW_URI}")
mlflow.set_tracking_uri(MLFLOW_URI)

# Global variable to cache the model
cached_model = None
cached_model_version = None

def save_model_to_disk(model, version):
    os.makedirs(CACHE_DIR, exist_ok=True)
    # Save model version
    with open(os.path.join(CACHE_DIR, "model_version.txt"), "w") as f:
        f.write(str(version))
    # Save model object
    with open(os.path.join(CACHE_DIR, "model.pkl"), "wb") as f:
        pickle.dump(model, f)

def load_model_from_disk():
    try:
        with open(os.path.join(CACHE_DIR, "model_version.txt"), "r") as f:
            version = f.read().strip()
        with open(os.path.join(CACHE_DIR, "model.pkl"), "rb") as f:
            model = pickle.load(f)
        return model, version
    except Exception:
        return None, None

def load_latest_model(model_name: str):
    client = MlflowClient()
    # Get the latest version of the model
    model_versions = client.search_model_versions(f"name='{model_name}'")
    if not model_versions:
        raise ValueError(f"No versions found for model '{model_name}'")

    # Select the highest version number
    latest_version_obj = max(model_versions, key=lambda x: int(x.version))
    latest_version = latest_version_obj.version
    print(f"Found {len(model_versions)} versions for model '{model_name}'. Loading the latest version: {latest_version}")
    print(f"Loading model from URI: models:/{model_name}/{latest_version}")

    global cached_model
    global cached_model_version

    if cached_model_version == latest_version:
        print("Using cached model from memory.")
        return cached_model, latest_version
    
    # Check if model is already on disk
    model_on_disk, model_on_disk_version = load_model_from_disk()
    if model_on_disk is not None and model_on_disk_version == latest_version:
        print("Using cached model from disk.")
        cached_model = model_on_disk
        cached_model_version = latest_version
        return model_on_disk, latest_version

    # Download the latest model from MLFlow
    max_retries = 3
    retry_delay = 2.0
    last_exception = None
    model_uri = f"models:/{model_name}/{latest_version}"
    for attempt in range(1, max_retries + 1):
        try:
            # Load the model as sklearn model to ensure predict_proba is available
            model = mlflow.sklearn.load_model(model_uri)
            save_model_to_disk(model, latest_version)
            cached_model = model
            cached_model_version = latest_version
            return model, latest_version
        except Exception as e:
            last_exception = e
            logging.error(f"Attempt {attempt} to load model failed: {e}")
            # If it's an artifact download error, log details
            if hasattr(e, "args") and e.args:
                logging.error(f"Artifact download error details: {e.args}")
            if attempt < max_retries:
                time.sleep(retry_delay)
    raise RuntimeError(f"Failed to load model after {max_retries} attempts: {last_exception}")


# Load model at startup
try:
    cached_model, cached_model_version = load_latest_model(MODEL_NAME)
    print("Model loaded successfully at startup")
except Exception as e:
    print(f"Failed to load model at startup: {e}")
    cached_model = None
    cached_model_version = None

def predict_image(image_path, classifier):
    img = imread(image_path)
    img = resize(img, (512, 512), anti_aliasing=True)
    if not img.shape == (512, 512, 3):
        raise ValueError(f"Image shape {img.shape} does not match training dimensions (512, 512, 3).")

    img_flattened = img.flatten().reshape(1, -1)  # Reshape for prediction
    prediction = classifier.predict(img_flattened)
    # Get confidence using predict_proba if available
    if hasattr(classifier, "predict_proba"):
        probabilities = classifier.predict_proba(img_flattened)
        confidence = float(np.max(probabilities))
    else:
        confidence = None
        raise ValueError("The classifier does not support probability predictions.")

    # save prediction and confidence as json for debugging
    import json
    with open("prediction_result.json", "w") as f:
        json.dump({"prediction": prediction.tolist(), "confidence": confidence}, f)

    return prediction, confidence

class ImagePayload(BaseModel):
        image: str


@app.post("/predict/")
async def predict(payload: ImagePayload):
    import base64
    from io import BytesIO
    from PIL import Image
    if not payload.image:
        return {"error": "No image provided in the request."}
    
    if cached_model is None:
        raise HTTPException(status_code=500, detail="Model not loaded. Try hitting /reload endpoint.")

    with mlflow.start_run(run_name="classifier_prediction", nested=True):
        mlflow.log_param("prediction_timestamp", str(np.datetime64('now')))
        
        image = payload.image
        if image.startswith("data:image/jpeg;base64,"):
            image = image.replace("data:image/jpeg;base64,", "")

        image_data = base64.b64decode(image)
        image = Image.open(BytesIO(image_data))
        image = image.resize((512, 512))
        safe_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        image_name = f"{safe_timestamp}.jpg"
        image_path = os.path.join(CACHE_DIR, image_name)
        image.save(image_path)
        prediction, confidence = predict_image(image_path, cached_model)
        if isinstance(prediction, np.ndarray):
            prediction = prediction.tolist()
        if isinstance(prediction, list) and len(prediction) == 1:
            prediction = prediction[0]
        mlflow.log_param("prediction_result", prediction)
        mlflow.log_metric("prediction_confidence", confidence)
        mlflow.log_artifact(image_path, artifact_path="input_images")
        # delete temporary image file
        os.remove(image_path)

        return {"prediction": prediction, "confidence": float(confidence)}
    
@app.get("/reload")
async def reload_model():
    global cached_model
    global cached_model_version
    try:
        cached_model, cached_model_version = load_latest_model(MODEL_NAME)
        return {"status": "success", "message": f"Model reloaded successfully: {cached_model_version}"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to reload model: {str(e)}"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "API is running and ready to accept requests."}

if __name__ == "__main__":
    import uvicorn
    print("Starting FastAPI server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)