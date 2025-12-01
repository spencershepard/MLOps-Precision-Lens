# Setup NVIDIA Device Plugin for Kubernetes
# This enables GPU access for pods in your Kubernetes cluster

Write-Host "Installing NVIDIA Device Plugin for Kubernetes..." -ForegroundColor Green

# Deploy the NVIDIA device plugin daemonset
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.17.0/deployments/static/nvidia-device-plugin.yml

# Wait for the daemonset to be ready
Write-Host "`nWaiting for NVIDIA device plugin to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Check the status
Write-Host "`nChecking NVIDIA device plugin status:" -ForegroundColor Cyan
kubectl get daemonset -n kube-system nvidia-device-plugin-daemonset

# Check if GPUs are now visible to Kubernetes
Write-Host "`nChecking node GPU capacity:" -ForegroundColor Cyan
kubectl get nodes -o json | ConvertFrom-Json | ForEach-Object {
    $node = $_.items[0]
    $gpuCapacity = $node.status.capacity.'nvidia.com/gpu'
    if ($gpuCapacity) {
        Write-Host "Node has $gpuCapacity GPU(s) available" -ForegroundColor Green
    } else {
        Write-Host "No GPUs detected on node" -ForegroundColor Red
        Write-Host "This might be normal if GPUs take time to register" -ForegroundColor Yellow
    }
}

Write-Host "`nNVIDIA Device Plugin installation complete!" -ForegroundColor Green
Write-Host "You may need to wait a minute for GPUs to be registered with the cluster." -ForegroundColor Yellow

