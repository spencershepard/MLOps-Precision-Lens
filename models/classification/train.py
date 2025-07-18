import os
import pickle

import boto3
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import seaborn as sns
from dotenv import load_dotenv
from skimage.io import imread
from skimage.transform import resize
from sklearn.metrics import (accuracy_score, classification_report, 
                           confusion_matrix, precision_recall_fscore_support)
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.svm import SVC

print("Loading environment variables...")

load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
BUCKET_NAME = os.getenv('BUCKET_NAME')
if not BUCKET_NAME or not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    raise ValueError("Please set the BUCKET_NAME, AWS_ACCESS_KEY_ID, and AWS_SECRET_ACCESS_KEY in your environment.")
MLFLOW_URI = os.getenv('MLFLOW_URI')
CLASS_TRAINING_IMG_LIMIT= int(os.getenv("CLASS_TRAINING_IMG_LIMIT", 100))

cache_dir = "s3cache"
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

print("Setting up MLflow tracking...")
mlflow.set_tracking_uri(MLFLOW_URI)
mlflow.set_experiment("image-classification-s3")


# this will use training images from an s3 bucket with the following directory structure:
# s3://<bucket_name>/class/train/good/

def get_training_images_from_s3(bucket_name):
    """    Fetches training images from an S3 bucket with a specific directory structure.
    Args:
        bucket_name (str): The name of the S3 bucket.
    Returns:
        images (list): List of image local file paths.
        labels (list): List of corresponding labels for the images.
    """
    print(f"Fetching training images from S3 bucket: {bucket_name}")
    s3 = boto3.client('s3', 
                     aws_access_key_id=AWS_ACCESS_KEY_ID, 
                     aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
    response = s3.list_objects_v2(Bucket=bucket_name)
    images = []
    labels = []
    if 'Contents' not in response:
        print("No contents found in the specified S3 bucket.")
        return images, labels
    
    for obj in response['Contents']:
        key = obj['Key']
        class_name = key.split('/')[0]  # Assuming the structure is <class_name>/train/good/<image_name>
        split = key.split('/')[1] # This should be 'train' or 'test'
        if split == 'train':
            category = key.split('/')[2]  # This should be 'good' or other categories
            if category == 'good':
                if labels.count(class_name) >= CLASS_TRAINING_IMG_LIMIT:
                    print(f"Skipping {class_name} as it has reached the training limit.")
                    continue

                local_image_path = os.path.join(cache_dir, key.replace('/', '_'))
                label = class_name
                images.append(local_image_path)
                labels.append(label)
                print(f"Found image: {key} with label: {label}")

                # check if image already exists in cache
                
                if not os.path.exists(local_image_path):
                    # Download the image from S3
                    s3.download_file(bucket_name, key, local_image_path)
                    print(f"Downloaded {key} to {local_image_path}")
            else:
                continue 

    return images, labels


def prepare_data(images_paths, labels):
    _data = []
    _labels = []

    for image_path in images_paths:
        label = labels[images_paths.index(image_path)]
        if os.path.isfile(image_path):
            img = imread(image_path)
            img = resize(img, (512, 512), anti_aliasing=True)
            # Note: images may have different aspect ratios, so
            # without cropping or padding, resizing could distort the images
            flattened_img = img.flatten()
            if flattened_img.size == 512 * 512 * 3:  # Ensure the image is in RGB format
                print(f"Appending image to data: label: {label} path:{image_path}, shape: {img.shape}")
                _data.append(flattened_img)
                _labels.append(label)
        else:
            print(f"Image not found: {image_path}")

    # Log data preparation metrics
    unique_labels = np.unique(labels)
    label_counts = {label: labels.count(label) for label in unique_labels}
    
    mlflow.log_param("total_images_processed", len(_data))
    mlflow.log_param("unique_classes", len(unique_labels))
    mlflow.log_param("class_names", list(unique_labels))
    for label, count in label_counts.items():
        mlflow.log_metric(f"class_{label}_count", count)

    return np.asarray(_data), np.asarray(_labels)


def train_model(x_train, y_train):
    print("Training model...")
    param_grid = {
        'C': [0.1, 1, 10],
        'kernel': ['linear', 'rbf'],
        'gamma': ['scale', 'auto']
    }
    svc = SVC(probability=True) 
    grid_search = GridSearchCV(svc, param_grid, cv=3, verbose=2, n_jobs=-1)
    
    # Log grid search parameters
    mlflow.log_params({f"grid_{k}": str(v) for k, v in param_grid.items()})
    mlflow.log_param("model_type", "SVC")
    mlflow.log_param("cv_folds", 3)
    mlflow.log_param("training_size", len(x_train))
    mlflow.log_param("feature_size", x_train.shape[1])
    
    grid_search.fit(x_train, y_train)
    
    # Log best parameters and cross-validation results
    mlflow.log_params(grid_search.best_params_)
    mlflow.log_metric("best_cv_score", grid_search.best_score_)
    mlflow.log_metric("cv_std", grid_search.cv_results_['std_test_score'][grid_search.best_index_])
    
    # Log all CV results for analysis
    for i, (params, score) in enumerate(zip(grid_search.cv_results_['params'], 
                                          grid_search.cv_results_['mean_test_score'])):
        mlflow.log_metric(f"cv_score_{i}", score)
    
    print("Best parameters found:", grid_search.best_params_)
    return grid_search.best_estimator_


def evaluate_model(classifier, x_test, y_test, labels):
    y_pred = classifier.predict(x_test)
    
    # Calculate metrics
    accuracy = accuracy_score(y_test, y_pred)
    precision, recall, f1, support = precision_recall_fscore_support(y_test, y_pred, average='weighted')
    
    # Log evaluation metrics
    mlflow.log_metric("test_accuracy", accuracy)
    mlflow.log_metric("test_precision", precision)
    mlflow.log_metric("test_recall", recall)
    mlflow.log_metric("test_f1_score", f1)
    
    # Log per-class metrics
    precision_per_class, recall_per_class, f1_per_class, _ = precision_recall_fscore_support(
        y_test, y_pred, average=None, labels=labels
    )
    
    for i, label in enumerate(labels):
        mlflow.log_metric(f"precision_{label}", precision_per_class[i])
        mlflow.log_metric(f"recall_{label}", recall_per_class[i])
        mlflow.log_metric(f"f1_{label}", f1_per_class[i])
    
    # Log confusion matrix as artifact
    cm = confusion_matrix(y_test, y_pred)
    
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=labels, yticklabels=labels)
    plt.title('Confusion Matrix')
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    plt.tight_layout()
    
    confusion_matrix_path = os.path.join(cache_dir, "confusion_matrix.png")
    plt.savefig(confusion_matrix_path)
    mlflow.log_artifact(confusion_matrix_path)
    plt.close()
    
    # Log classification report as text artifact
    report = classification_report(y_test, y_pred, target_names=labels)
    report_path = os.path.join(cache_dir, "classification_report.txt")
    with open(report_path, 'w') as f:
        f.write(report)
    mlflow.log_artifact(report_path)
    
    print("Confusion Matrix:")
    print(cm)
    print("Classification Report:")
    print(report)
    print(f"Accuracy: {accuracy}")

def predict_image(classifier, image_path):
    """Predicts the class of a single image with confidence score."""
    img = imread(image_path)
    img = resize(img, (512, 512), anti_aliasing=True)
    flattened_img = img.flatten().reshape(1, -1)  # Reshape for a single sample
    prediction = classifier.predict(flattened_img)
    probabilities = classifier.predict_proba(flattened_img)
    confidence = np.max(probabilities)  # Highest probability as confidence
    return prediction[0], confidence



print("Starting image classification training...")

with mlflow.start_run(run_name="image_classification_training") as run:
    mlflow.sklearn.autolog()
    
    # Log environment and configuration
    mlflow.log_param("bucket_name", BUCKET_NAME)
    mlflow.log_param("class_training_limit", CLASS_TRAINING_IMG_LIMIT)
    mlflow.log_param("image_size", "512x512") 
    mlflow.log_param("test_split_ratio", 0.2)

    images, labels = get_training_images_from_s3(BUCKET_NAME)
    if not images or not labels:
        raise ValueError("No images or labels found. Please check the S3 bucket structure.")
    data, labels = prepare_data(images, labels)

    x_train, x_test, y_train, y_test = train_test_split(data, labels, shuffle=True, test_size=0.2, stratify=labels)
    # Note: stratify ensures that the class distribution is maintained in both train and test sets

    best_classifier = train_model(x_train, y_train)

    unique_labels = np.unique(labels)
    evaluate_model(best_classifier, x_test, y_test, unique_labels)
    
    # Create input example for model signature
    input_example = x_train[:1]  # Use first training sample as example
    
    # Log the model with input example to auto-infer signature
    mlflow.sklearn.log_model(
        best_classifier, 
        "best_classifier",
        input_example=input_example
    )
    
    # Save and log additional artifacts
    print("Saving and logging the best classifier model...")
    model_path = os.path.join(cache_dir, "best_classifier.pkl")
    pickle.dump(best_classifier, open(model_path, "wb"))
    mlflow.log_artifact(model_path)
    
    # Log model info
    print(f"MLflow Run ID: {run.info.run_id}")
    print(f"Model logged to: {mlflow.get_artifact_uri()}")