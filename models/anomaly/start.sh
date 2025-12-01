#!/bin/bash
# Startup script to validate environment and run the notebook

# Check for required environment variables
required_vars=("BUCKET_NAME" "AWS_ACCESS_KEY_ID" "AWS_SECRET_ACCESS_KEY" "AWS_REGION_NAME")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: Required environment variable $var is not set"
        exit 1
    fi
done

echo "Environment validation passed"

# Check if CUDA is available and fail if not
echo "Checking CUDA availability..."
if ! python -c "import torch; import sys; sys.exit(0 if torch.cuda.is_available() else 1)"; then
    echo "Error: CUDA is not available. GPU training requires CUDA."
    echo "Please ensure:"
    echo "  1. NVIDIA device plugin is deployed in Kubernetes"
    echo "  2. Pod has nvidia.com/gpu resource requests"
    echo "  3. NVIDIA drivers are installed on the host"
    exit 1
fi
echo "CUDA is available"

# Create output filename with timestamp
TIMESTAMP=$(date +%Y%m%d%H%M%S)
OUTPUT_FILE="/app/output/output-${CATEGORY}-${TIMESTAMP}.ipynb"

echo "Starting papermill execution..."
echo "Environment variables:"
echo "- BUCKET_NAME: $BUCKET_NAME"
echo "- CATEGORY: $CATEGORY"
echo "- CACHE_DIRECTORY: $CACHE_DIRECTORY"
echo "- MAX_EPOCHS: $MAX_EPOCHS"
echo "Output will be saved to: $OUTPUT_FILE"

# Execute the notebook with papermill (using environment variables, no parameters)
papermill fastflow.ipynb "$OUTPUT_FILE" --no-input

# Check papermill exit status
if [ $? -eq 0 ]; then
    echo "Notebook execution completed successfully"
    echo "Output saved to $OUTPUT_FILE"
    exit 0
else
    echo "Notebook execution failed"
    exit 1
fi