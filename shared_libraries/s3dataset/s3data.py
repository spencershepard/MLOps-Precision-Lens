import boto3
from botocore.exceptions import ClientError
import os
import base64
import sys
from pathlib import Path

## Directory structure:
# bucket/
#   main_category/
#     train/
#       good/
#     test/
#       good/
#       anomaly_category/

_AWS_CONFIG = {
    "aws_access_key_id": None,
    "aws_secret_access_key": None,
    "region_name": None,
}

def set_aws_config(access_key_id, secret_access_key, region_name=None):
    _AWS_CONFIG["aws_access_key_id"] = access_key_id
    _AWS_CONFIG["aws_secret_access_key"] = secret_access_key
    _AWS_CONFIG["region_name"] = region_name

def get_boto3_client():
    return boto3.client(
        's3',
        aws_access_key_id=_AWS_CONFIG["aws_access_key_id"],
        aws_secret_access_key=_AWS_CONFIG["aws_secret_access_key"],
        region_name=_AWS_CONFIG["region_name"]
    )

def get_directories(bucket_name):
    s3 = get_boto3_client()
    paginator = s3.get_paginator('list_objects_v2')
    directories = []

    try:
        for page in paginator.paginate(Bucket=bucket_name, Delimiter='/'):
            for prefix in page.get('CommonPrefixes', []):
                directories.append(prefix['Prefix'])
    except ClientError as e:
        print(f"Error listing directories: {e}")
    
    return directories

def get_dataset_structure(bucket_name):
    """Get the complete dataset structure from S3 bucket."""
    s3 = get_boto3_client()
    
    dataset_structure = {
        'train': {'good': []},
        'test': {'good': [], 'anomaly': []}
    }
    
    try:
        # List all objects in the bucket
        paginator = s3.get_paginator('list_objects_v2')
        
        for page in paginator.paginate(Bucket=bucket_name):
            for obj in page.get('Contents', []):
                key = obj['Key']
                
                # Skip directories (keys ending with /)
                if key.endswith('/'):
                    continue
                
                # Parse the path structure: main_category/train/good/file or main_category/test/anomaly_category/file
                path_parts = key.split('/')
                if len(path_parts) >= 4:  # main_category/split/category/file
                    main_category = path_parts[0]
                    split = path_parts[1]  # train or test
                    category = path_parts[2]  # good, bad, etc
                    
                    if split in dataset_structure:
                        if category == 'good':
                            dataset_structure[split]['good'].append(key)
                        elif category == 'bad' and split == 'test' and len(path_parts) >= 5:
                            # For bad/anomaly_category structure
                            dataset_structure[split]['anomaly'].append(key)
                        elif split == 'test' and category != 'good':
                            # Any other non-good category is considered anomaly for test set
                            dataset_structure[split]['anomaly'].append(key)
                            
    except ClientError as e:
        print(f"Error getting dataset structure: {e}")
    
    return dataset_structure

def download_file_from_s3(bucket_name, s3_key, local_path):
    """Download a file from S3 to local path."""
    s3 = get_boto3_client()
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        s3.download_file(bucket_name, s3_key, local_path)
        return True
    except ClientError as e:
        print(f"Error downloading file {s3_key}: {e}")
        return False
    
def upload_data_to_s3(bucket_name, local_path, main_category, split, category, image_bytes=None, filename=None):
    """Upload a file to S3. Image path structure: main_category/split/category/file."""
    s3 = boto3.client('s3', 
                     region_name=os.getenv('AWS_REGION'),
                     aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'), 
                     aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))
    
    if image_bytes and filename:
        # Handle raw bytes upload
        s3_key = f"{main_category}/{split}/{category}/{filename}"
        try:
            s3.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=image_bytes,
                ContentType='image/jpeg'
            )
            print(f"Uploaded bytes to {s3_key}")
            return True
        except ClientError as e:
            print(f"Error uploading bytes: {e}")
            return False
    else:
        # Original file upload logic
        s3_key = f"{main_category}/{split}/{category}/{os.path.basename(local_path)}"
        try:
            s3.upload_file(local_path, bucket_name, s3_key)
            print(f"Uploaded {local_path} to {s3_key}")
            return True
        except ClientError as e:
            print(f"Error uploading file {local_path}: {e}")
            return False

def base64_dataurl_to_bytes(base64_url):
    """Convert a base64 data URL (ie HTMLCanvasElement.toDataURL()) to bytes. """
    # Remove the prefix and decode
    base64_data = base64_url.split(',')[1]
    return base64.b64decode(base64_data)

def get_dataset(bucket_name, prefix='', limit=None, cache_dir='s3cache', flat_cache=False, debug=False) -> tuple:
    """
    Fetches training images from an S3 bucket with a specific directory structure:
    bucket/
        main_category/
            train/
                good/
            test/
                good/
                anomaly_category/
    Args:
        bucket_name (str): The name of the S3 bucket.
        prefix (str): The prefix to filter objects in the bucket.
        limit (int): Maximum number of images to fetch per class.
        flat_cache (bool): Whether to use a flat cache directory structure (default: False).
    Returns:
        images (list): List of image local file paths.
        class_names (list): List of class names. (ie. 'cat', 'dog', etc.)
        tags (list): List of tags for the images (ie 'train', 'test').
        labels (list): List of corresponding labels for the images. (ie. 'good', 'bad', etc.)
    """
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    print(f"Fetching dataset from S3 bucket: {bucket_name}")
    s3 = get_boto3_client()
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    images = []
    class_names = []
    tags = []
    labels = []

    # For reporting purposes
    combined_categories = []
    cached_images = []
    downloaded_images = []
    skipped_images = []

    if 'Contents' not in response:
        print("No contents found in the specified S3 bucket.")
        return images, labels
    
    for obj in response['Contents']:
        key = obj['Key']
        if key.endswith('/'):
            continue
        if not key.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
            continue
        # Parse the key
        parts = key.split('/')
        if len(parts) < 4:
            skipped_images.append(key)
            continue

        class_name = parts[0]
        tag = parts[1]
        label = parts[2]
        image_name = parts[3]
        combined_category = f"{class_name}/{tag}/{label}"

        if tag not in ['train', 'test', 'ground_truth']:
            skipped_images.append(key)
            continue

        # check for limit of unique class_name, tag, label combinations
        #print(f"Checking if we have reached limit for class: {class_name}, tag: {tag}, label: {label} - current count: {class_names.count(class_name)}")
        if combined_categories.count(combined_category) >= limit:
            skipped_images.append(key)
            continue

        # Download the image to the local cache directory
        if flat_cache:
            local_file_name = key.replace('/', '_')
            local_directory = cache_dir
        else:
            local_directory = os.path.join(cache_dir, class_name, tag, label)
            local_file_name = image_name

        local_directory = Path(local_directory)

        if not local_directory.exists():
            local_directory.mkdir(parents=True, exist_ok=True)

        local_path = os.path.join(local_directory, local_file_name)
        
        if not os.path.exists(local_path):
            try:
                s3.download_file(bucket_name, key, local_path)
                downloaded_images.append(local_path)
            except ClientError as e:
                print(f"Error downloading {key}: {e}")
                continue
        else:
            cached_images.append(local_path)

        images.append(local_path)
        class_names.append(class_name)
        labels.append(label)
        tags.append(tag)
        combined_categories.append(combined_category)

        sys.stdout.write(f"\rDownloaded: {len(downloaded_images)} Cached: {len(cached_images)} Ignored: {len(skipped_images)}")
        sys.stdout.flush()

    print("")
    if(debug):
        for i, class_name in enumerate(class_names):
            print(f"Class: {class_name}  Tag: {tags[i]}   Label: {labels[i]}   Image: {images[i]}")

    return images, class_names, labels, tags

if __name__ == "__main__":
    import dotenv
    import os

    dotenv.load_dotenv("secrets.env")
    dotenv.load_dotenv("config.env")
    set_aws_config(
        access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION')
    )
    bucket_name = os.getenv('BUCKET_NAME')
    if not bucket_name:
        print("Bucket name not found in environment variables.")
        exit(1)
    
    directories = get_directories(bucket_name)
    
    if directories:
        print("Directories in S3 bucket:")
        for directory in directories:
            print(directory)
    else:
        print("No directories found or an error occurred.")

    get_dataset(bucket_name, limit=5, cache_dir='s3cachenested', flat_cache=False, debug=True, prefix='bottle')