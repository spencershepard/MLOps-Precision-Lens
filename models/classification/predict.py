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
load_dotenv()
app = FastAPI()

print("Starting model prediction service...")
MLFLOW_URI = os.getenv("MLFLOW_URI")
if not MLFLOW_URI:
    raise ValueError("MLFLOW_URI environment variable is not set.")
model_name = "Precision Lens Classifier"
cache_dir = "s3cache"
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)
mlflow.set_tracking_uri(MLFLOW_URI)

# Global variable to cache the model
cached_model = None

def load_latest_model(model_name: str):
    client = MlflowClient()
    # Get the latest version of the model
    model_versions = client.search_model_versions(f"name='{model_name}'")
    if not model_versions:
        raise ValueError(f"No versions found for model '{model_name}'")
    
    latest_version = max(model_versions, key=lambda x: x.version)
    model_uri = f"models:/{model_name}/{latest_version.version}"
    print(f"Loading model from URI: {model_uri}")
    
    # Load the model
    model = mlflow.pyfunc.load_model(model_uri)
    return model

def get_model():
    global cached_model
    if cached_model is None:
        cached_model = load_latest_model(model_name)
    return cached_model

# Load model at startup
try:
    cached_model = load_latest_model(model_name)
    print("Model loaded successfully at startup")
except Exception as e:
    print(f"Failed to load model at startup: {e}")
    cached_model = None

def predict_image(image_path, classifier):
    img = imread(image_path)
    #reshape
    img = resize(img, (512, 512), anti_aliasing=True)
    if not img.shape == (512, 512, 3):
        raise ValueError(f"Image shape {img.shape} does not match training dimensions (512, 512, 3).")

    img_flattened = img.flatten().reshape(1, -1)  # Reshape for prediction
    prediction = classifier.predict(img_flattened)
    
    # Try to get confidence score
    try:
        confidence_scores = classifier.predict_proba(img_flattened)
        confidence = np.max(confidence_scores)
    except AttributeError:
        confidence = 1.0  # Default confidence if predict_proba not available
    
    return prediction[0], confidence

class ImagePayload(BaseModel):
        image: str

@app.post("/predict/")
async def predict(payload: ImagePayload):
    import base64
    from io import BytesIO
    from PIL import Image
    if not payload.image:
        return {"error": "No image provided in the request."}
    
    best_classifier = get_model()
    if best_classifier is None:
        raise HTTPException(status_code=500, detail="Model not loaded. Try hitting /reload endpoint.")

    with mlflow.start_run(run_name="prediction_request", nested=True):
        mlflow.log_param("prediction_timestamp", str(np.datetime64('now')))
        
        image = payload.image
        if image.startswith("data:image/jpeg;base64,"):
            image = image.replace("data:image/jpeg;base64,", "")

        image_data = base64.b64decode(image)
        image = Image.open(BytesIO(image_data))
        image = image.resize((512, 512))
        image_path = os.path.join(cache_dir, "temp_image.jpg")
        image.save(image_path)
        prediction, confidence = predict_image(image_path, best_classifier)
        
        mlflow.log_param("prediction_result", prediction)
        mlflow.log_metric("prediction_confidence", confidence)
        
        return {"prediction": prediction, "confidence": float(confidence)}
    
@app.get("/reload")
async def reload_model():
    global cached_model
    try:
        cached_model = load_latest_model(model_name)
        return {"status": "success", "message": "Model reloaded successfully"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to reload model: {str(e)}"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "API is running and ready to accept requests."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)