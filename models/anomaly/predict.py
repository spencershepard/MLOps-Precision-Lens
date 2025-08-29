import os
import mlflow
from mlflow.tracking import MlflowClient
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import numpy as np
from skimage.io import imread
from skimage.transform import resize
from PIL import Image
from io import BytesIO
import base64
from dotenv import load_dotenv
import time
import logging
import pickle
from datetime import datetime

load_dotenv()
app = FastAPI()

print("Starting anomaly detection prediction service...")
MLFLOW_URI = os.getenv("MLFLOW_URI")
if not MLFLOW_URI:
    raise ValueError("MLFLOW_URI environment variable is not set.")
CACHE_DIR = "cache"
SERVER_PORT = int(os.getenv("SERVER_PORT", 8000))

print(f"Using cache directory: {CACHE_DIR}")
print(f"Setting MLflow tracking URI: {MLFLOW_URI}")
mlflow.set_tracking_uri(MLFLOW_URI)

cached_model = None
cached_model_version = None
cached_model_name = None  # Track cached model name

def save_model_to_disk(model, model_name, version):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(os.path.join(CACHE_DIR, "model_version.txt"), "w") as f:
        f.write(str(version))
    with open(os.path.join(CACHE_DIR, "model_name.txt"), "w") as f:
        f.write(str(model_name))
    with open(os.path.join(CACHE_DIR, "model.pkl"), "wb") as f:
        pickle.dump(model, f)

def load_model_from_disk():
    try:
        with open(os.path.join(CACHE_DIR, "model_version.txt"), "r") as f:
            version = f.read().strip()
        with open(os.path.join(CACHE_DIR, "model_name.txt"), "r") as f:
            model_name = f.read().strip()
        with open(os.path.join(CACHE_DIR, "model.pkl"), "rb") as f:
            model = pickle.load(f)
        return model, model_name, version
    except Exception:
        return None, None, None

def load_latest_model(model_name: str):
    client = MlflowClient()
    model_versions = client.search_model_versions(f"name='{model_name}'")
    if not model_versions:
        raise ValueError(f"No versions found for model '{model_name}'")
    latest_version_obj = max(model_versions, key=lambda x: int(x.version))
    latest_version = latest_version_obj.version
    print(f"Found {len(model_versions)} versions for model '{model_name}'. Loading the latest version: {latest_version}")
    print(f"Loading model from URI: models:/{model_name}/{latest_version}")

    global cached_model
    global cached_model_version
    global cached_model_name

    if cached_model_name == model_name and cached_model_version == latest_version:
        print("Using cached model from memory.")
        return cached_model, cached_model_name, latest_version

    model_on_disk, model_on_disk_name, model_on_disk_version = load_model_from_disk()
    if (
        model_on_disk is not None
        and model_on_disk_name == model_name
        and model_on_disk_version == latest_version
    ):
        print("Using cached model from disk.")
        cached_model = model_on_disk
        cached_model_name = model_name
        cached_model_version = latest_version
        return model_on_disk, model_name, latest_version

    max_retries = 3
    retry_delay = 2.0
    last_exception = None
    model_uri = f"models:/{model_name}/{latest_version}"
    for attempt in range(1, max_retries + 1):
        try:
            model = mlflow.pytorch.load_model(model_uri)
            save_model_to_disk(model, model_name, latest_version)
            cached_model = model
            cached_model_name = model_name
            cached_model_version = latest_version
            return model, model_name, latest_version
        except Exception as e:
            last_exception = e
            logging.error(f"Attempt {attempt} to load model failed: {e}")
            if hasattr(e, "args") and e.args:
                logging.error(f"Artifact download error details: {e.args}")
            if attempt < max_retries:
                time.sleep(retry_delay)
    raise RuntimeError(f"Failed to load model after {max_retries} attempts: {last_exception}")

def predict_image(image_path, model):
    img = imread(image_path)
    img = resize(img, (512, 512), anti_aliasing=True)
    if not img.shape == (512, 512, 3):
        raise ValueError(f"Image shape {img.shape} does not match expected dimensions (512, 512, 3).")
    img_tensor = np.transpose(img, (2, 0, 1))  # [C, H, W]
    import torch
    img_tensor = torch.tensor(img_tensor, dtype=torch.float32).unsqueeze(0)  # [1, C, H, W]
    with torch.no_grad():
        outputs = model(img_tensor)
    # Assume model returns anomaly_map and score
    anomaly_map = outputs.get("anomaly_map", None)
    score = outputs.get("score", None)
    # Save prediction for debugging
    import json
    with open("anomaly_prediction_result.json", "w") as f:
        json.dump({"score": float(score) if score is not None else None}, f)
    return score, anomaly_map

class ImagePayload(BaseModel):
    image: str

@app.post("/predict/")
async def predict(payload: ImagePayload, model_name: str):
    if not payload.image:
        return {"error": "No image provided in the request."}
    global cached_model
    global cached_model_version
    global cached_model_name
    if not model_name:
        raise HTTPException(status_code=400, detail="model_name query parameter is required.")
    # Always load the requested model if not already loaded or version is outdated
    client = MlflowClient()
    model_versions = client.search_model_versions(f"name='{model_name}'")
    if not model_versions:
        raise HTTPException(status_code=500, detail=f"No versions found for model '{model_name}'")
    latest_version_obj = max(model_versions, key=lambda x: int(x.version))
    latest_version = latest_version_obj.version
    if cached_model_name != model_name or cached_model_version != latest_version:
        try:
            cached_model, cached_model_name, cached_model_version = load_latest_model(model_name)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load model '{model_name}': {str(e)}")
    if cached_model is None:
        raise HTTPException(status_code=500, detail="Model not loaded. Try hitting /reload endpoint.")
    with mlflow.start_run(run_name="anomaly_prediction", nested=True):
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
        score, anomaly_map = predict_image(image_path, cached_model)
        mlflow.log_param("prediction_score", float(score) if score is not None else None)
        mlflow.log_artifact(image_path, artifact_path="input_images")
        os.remove(image_path)
        return {"score": float(score) if score is not None else None}
    
@app.get("/reload")
async def reload_model(model_name: str):
    global cached_model
    global cached_model_version
    global cached_model_name
    if not model_name:
        return {"status": "error", "message": "model_name query parameter is required."}
    try:
        cached_model, cached_model_name, cached_model_version = load_latest_model(model_name)
        return {"status": "success", "message": f"Model reloaded successfully: {cached_model_name} v{cached_model_version}"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to reload model: {str(e)}"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "API is running and ready to accept requests."}

if __name__ == "__main__":
    import uvicorn
    print(f"Starting FastAPI server on port {SERVER_PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
