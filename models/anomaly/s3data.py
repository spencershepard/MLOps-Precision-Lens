import boto3
from botocore.exceptions import ClientError
import os
import dotenv
import base64
from pathlib import Path

dotenv.load_dotenv()

# directory structure will be like:
# bucket > train 
#           > good
#        > test
#           > good (optional)
#           > bad1
#           > bad2


def get_directories(bucket_name):
    s3 = boto3.client('s3', 
                     region_name=os.getenv('AWS_REGION'),
                     aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'), 
                     aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))

    paginator = s3.get_paginator('list_objects_v2')
    directories = []

    try:
        for page in paginator.paginate(Bucket=bucket_name, Delimiter='/'):
            for prefix in page.get('CommonPrefixes', []):
                directories.append(prefix['Prefix'])
    except ClientError as e:
        print(f"Error listing directories: {e}")
    
    return directories

def get_dataset_structure(bucket_name, main_category=None):
    """Get the complete dataset structure from S3 bucket for a specific main category."""
    s3 = boto3.client('s3', 
                     region_name=os.getenv('AWS_REGION'),
                     aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'), 
                     aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))
    
    dataset_structure = {
        'train': {'good': []},
        'test': {'good': [], 'anomaly': []}
    }
    
    # Track available categories for logging
    available_categories = set()
    
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
                    category_name = path_parts[0]
                    available_categories.add(category_name)
                    
                    # If main_category is specified, only process files from that category
                    if main_category and category_name != main_category:
                        continue
                    
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
        
        # Print available categories
        print(f"Available categories in bucket '{bucket_name}': {sorted(available_categories)}")
        if main_category:
            if main_category in available_categories:
                print(f"Processing category: {main_category}")
            else:
                print(f"Warning: Specified category '{main_category}' not found in bucket")
                            
    except ClientError as e:
        print(f"Error getting dataset structure: {e}")
    
    return dataset_structure

def download_file_from_s3(bucket_name, s3_key, local_path):
    """Download a file from S3 to local path."""
    s3 = boto3.client('s3', 
                     region_name=os.getenv('AWS_REGION'),
                     aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'), 
                     aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))
    
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

def download_if_needed(bucket_name, s3_key: str, local_path: Path) -> bool:
        if local_path.exists():
            return True
        
        try:
            return download_file_from_s3(
                bucket_name, 
                s3_key, 
                str(local_path)
            )
        except Exception as e:
            print(f"Error downloading {s3_key}: {e}")
            return False
        
def cache_dataset(bucket_name, dataset_name, dataset_structure, cache_dir):
    """Cache the dataset structure to local files:
    ie. cache_dir/dataset_name/train/good/file
    """
    cache_path = Path(cache_dir) / dataset_name
    cache_path.mkdir(parents=True, exist_ok=True)
    
    for split, categories in dataset_structure.items():
        split_path = cache_path / split
        split_path.mkdir(exist_ok=True)
        
        for category, files in categories.items():
            category_path = split_path / category
            category_path.mkdir(exist_ok=True)
            
            for file in files:
                local_file_path = category_path / Path(file).name
                if not download_if_needed(bucket_name, file, local_file_path):
                    print(f"Failed to download {file} to {local_file_path}")

if __name__ == "__main__":
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

    #upload_data_to_s3(bucket_name, 'testupload.png', 'main_category', 'train', 'good')
    dataset_structure = get_dataset_structure(bucket_name, main_category='webcam')
    print("Dataset structure:", dataset_structure)
    cache_dataset(bucket_name, 'webcam', dataset_structure, 'cached_dataset')