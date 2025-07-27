# Development Setup Script for Local Domain Access
# Run this as Administrator to set up local domain resolution

# Add local domain entries to hosts file
$hostsFile = "C:\Windows\System32\drivers\etc\hosts"
$entries = @(
    "127.0.0.1 mlflow.local",
    "127.0.0.1 grafana.local",
    "127.0.0.1 labelstudio.local",
    "127.0.0.1 airflow.local",
    "127.0.0.1 prefect.local",
    "127.0.0.1 precision-lens.local",
)

Write-Host "Setting up local domains for development..." -ForegroundColor Green

# Backup hosts file
Copy-Item $hostsFile "$hostsFile.backup" -Force
Write-Host "Backed up hosts file to $hostsFile.backup" -ForegroundColor Yellow

# Check if entries already exist and add if not
$currentHosts = Get-Content $hostsFile
foreach ($entry in $entries) {
    if ($currentHosts -notcontains $entry) {
        Add-Content $hostsFile $entry
        Write-Host "Added: $entry" -ForegroundColor Green
    } else {
        Write-Host "Already exists: $entry" -ForegroundColor Yellow
    }
}

Write-Host "`nTo remove these entries later, restore from:" -ForegroundColor Yellow
Write-Host "$hostsFile.backup" -ForegroundColor White
