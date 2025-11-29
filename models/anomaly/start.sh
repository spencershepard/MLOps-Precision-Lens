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

# Check if CUDA is available (informational only)
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"

# Create output filename with timestamp
TIMESTAMP=$(date +%Y%m%d%H%M%S)
OUTPUT_FILE="/app/output/output-${CATEGORY}-${TIMESTAMP}.ipynb"

echo "Starting papermill execution..."
echo "Parameters:"
echo "- bucket_name: $BUCKET_NAME"
echo "- category: $CATEGORY"
echo "- cache_directory: $CACHE_DIRECTORY"
echo "- max_epochs: $MAX_EPOCHS"
echo "Output will be saved to: $OUTPUT_FILE"

# Execute the notebook with papermill
papermill fastflow.ipynb "$OUTPUT_FILE" \
    -p bucket_name "$BUCKET_NAME" \
    -p category "$CATEGORY" \
    -p cache_directory "$CACHE_DIRECTORY" \
    -p max_epochs "$MAX_EPOCHS"

# Check papermill exit status
if [ $? -eq 0 ]; then
    echo "Notebook execution completed successfully"
    echo "Output saved to $OUTPUT_FILE"
    exit 0
else
    echo "Notebook execution failed"
    exit 1
fi