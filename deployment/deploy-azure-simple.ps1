# Azure Deployment Script - NO DOCKER REQUIRED
# Uses Azure Container Registry Tasks to build in the cloud

param(
    [switch]$DeployOnly
)

# Load environment variables from .env file
if (-not (Test-Path ".env")) {
    Write-Host "[ERROR] .env file not found!" -ForegroundColor Red
    exit 1
}

Write-Host "[INFO] Loading credentials from .env..." -ForegroundColor Cyan
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#][^=]+)=(.+)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

# Validate required variables
$required = @(
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "KUSTO_CLUSTER_URI",
    "KUSTO_DATABASE",
    "AZURE_SEARCH_ENDPOINT",
    "AZURE_SEARCH_KEY"
)

$missing = @()
foreach ($var in $required) {
    if (-not [Environment]::GetEnvironmentVariable($var)) {
        $missing += $var
    }
}

if ($missing.Count -gt 0) {
    Write-Host "[ERROR] Missing required environment variables:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
    exit 1
}

Write-Host "[OK] All credentials loaded" -ForegroundColor Green

# Set Azure deployment variables
$RESOURCE_GROUP = if ([Environment]::GetEnvironmentVariable("AZURE_RESOURCE_GROUP")) { [Environment]::GetEnvironmentVariable("AZURE_RESOURCE_GROUP") } else { "spark-advisor-rg" }
$LOCATION = if ([Environment]::GetEnvironmentVariable("AZURE_LOCATION")) { [Environment]::GetEnvironmentVariable("AZURE_LOCATION") } else { "eastus" }
$CONTAINERAPPS_ENV = if ([Environment]::GetEnvironmentVariable("AZURE_CONTAINERAPPS_ENV")) { [Environment]::GetEnvironmentVariable("AZURE_CONTAINERAPPS_ENV") } else { "spark-advisor-env" }
$APP_NAME = if ([Environment]::GetEnvironmentVariable("AZURE_APP_NAME")) { [Environment]::GetEnvironmentVariable("AZURE_APP_NAME") } else { "spark-advisor-mcp" }
$ACR_NAME = if ([Environment]::GetEnvironmentVariable("AZURE_ACR_NAME")) { [Environment]::GetEnvironmentVariable("AZURE_ACR_NAME") } else { "sparkadvisoracr" }

Write-Host ""
Write-Host "Deployment Configuration:" -ForegroundColor Cyan
Write-Host "  Resource Group: $RESOURCE_GROUP"
Write-Host "  Location: $LOCATION"
Write-Host "  App Name: $APP_NAME"
Write-Host "  ACR Name: $ACR_NAME"
Write-Host ""

# Check Azure CLI
Write-Host "[CHECK] Verifying Azure CLI..." -ForegroundColor Cyan
try {
    $azVersion = az --version 2>&1 | Select-String "azure-cli" | Select-Object -First 1
    Write-Host "[OK] Azure CLI found" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Azure CLI not found. Install from https://aka.ms/azure-cli" -ForegroundColor Red
    exit 1
}

# Login to Azure
Write-Host ""
Write-Host "[AZURE] Logging in..." -ForegroundColor Cyan
az login --output none

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Azure login failed" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Logged into Azure" -ForegroundColor Green

# Create resources
if (-not $DeployOnly) {
    Write-Host ""
    Write-Host "[AZURE] Checking resource group..." -ForegroundColor Cyan
    $rgExists = az group exists --name $RESOURCE_GROUP
    if ($rgExists -eq "true") {
        Write-Host "[OK] Using existing resource group: $RESOURCE_GROUP" -ForegroundColor Green
    } else {
        Write-Host "[INFO] Creating resource group..." -ForegroundColor Yellow
        az group create --name $RESOURCE_GROUP --location $LOCATION --output none
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Resource group created" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] Failed to create resource group" -ForegroundColor Red
            exit 1
        }
    }

    Write-Host ""
    Write-Host "[AZURE] Creating Container Apps environment..." -ForegroundColor Cyan
    $envExists = az containerapp env show --name $CONTAINERAPPS_ENV --resource-group $RESOURCE_GROUP 2>$null
    if (-not $envExists) {
        az containerapp env create `
            --name $CONTAINERAPPS_ENV `
            --resource-group $RESOURCE_GROUP `
            --location $LOCATION `
            --output none
        Write-Host "[OK] Environment created" -ForegroundColor Green
    } else {
        Write-Host "[OK] Environment exists" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "[AZURE] Creating Azure Container Registry..." -ForegroundColor Cyan
    $acrExists = az acr show --name $ACR_NAME 2>$null
    if (-not $acrExists) {
        az acr create `
            --resource-group $RESOURCE_GROUP `
            --name $ACR_NAME `
            --sku Basic `
            --admin-enabled true `
            --output none
        Write-Host "[OK] ACR created" -ForegroundColor Green
    } else {
        Write-Host "[OK] ACR exists" -ForegroundColor Green
    }
}

# Build in Azure (NO LOCAL DOCKER NEEDED!)
Write-Host ""
Write-Host "[ACR] Building image in Azure (no local Docker needed)..." -ForegroundColor Cyan
Write-Host "[INFO] This will take 5-10 minutes..." -ForegroundColor Yellow

az acr build `
    --registry $ACR_NAME `
    --image spark-advisor-mcp:latest `
    --file Dockerfile `
    . `
    --platform linux

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Azure build failed" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Image built in Azure" -ForegroundColor Green

# Get ACR credentials
Write-Host ""
Write-Host "[AZURE] Getting ACR credentials..." -ForegroundColor Cyan
$acrServer = "$ACR_NAME.azurecr.io"
$acrUsername = az acr credential show --name $ACR_NAME --query username -o tsv
$acrPassword = az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv

# Deploy container app
Write-Host ""
Write-Host "[AZURE] Deploying container app..." -ForegroundColor Cyan

$appExists = az containerapp show --name $APP_NAME --resource-group $RESOURCE_GROUP 2>$null

if (-not $appExists) {
    # Create new app
    Write-Host "[INFO] Creating new container app..." -ForegroundColor Yellow
    az containerapp create `
        --name $APP_NAME `
        --resource-group $RESOURCE_GROUP `
        --environment $CONTAINERAPPS_ENV `
        --image "$acrServer/spark-advisor-mcp:latest" `
        --target-port 8000 `
        --ingress external `
        --registry-server $acrServer `
        --registry-username $acrUsername `
        --registry-password $acrPassword `
        --cpu 1.0 `
        --memory 2.0Gi `
        --min-replicas 1 `
        --max-replicas 3 `
        --env-vars `
            AZURE_OPENAI_ENDPOINT="$env:AZURE_OPENAI_ENDPOINT" `
            AZURE_OPENAI_API_KEY="$env:AZURE_OPENAI_API_KEY" `
            AZURE_OPENAI_DEPLOYMENT="$env:AZURE_OPENAI_DEPLOYMENT" `
            AZURE_OPENAI_API_VERSION="$env:AZURE_OPENAI_API_VERSION" `
            KUSTO_CLUSTER_URI="$env:KUSTO_CLUSTER_URI" `
            KUSTO_DATABASE="$env:KUSTO_DATABASE" `
            AZURE_SEARCH_ENDPOINT="$env:AZURE_SEARCH_ENDPOINT" `
            AZURE_SEARCH_KEY="$env:AZURE_SEARCH_KEY" `
            AZURE_SEARCH_INDEX="$env:AZURE_SEARCH_INDEX" `
        --output none
} else {
    # Update existing app
    Write-Host "[INFO] Updating existing container app..." -ForegroundColor Yellow
    az containerapp update `
        --name $APP_NAME `
        --resource-group $RESOURCE_GROUP `
        --image "$acrServer/spark-advisor-mcp:latest" `
        --output none
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Deployment failed" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Deployment complete!" -ForegroundColor Green

# Get app URL
Write-Host ""
Write-Host "[INFO] Getting application URL..." -ForegroundColor Cyan
$appUrl = az containerapp show `
    --name $APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --query properties.configuration.ingress.fqdn `
    -o tsv

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Green
Write-Host " DEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Your MCP Server URL:" -ForegroundColor Cyan
Write-Host "  https://$appUrl" -ForegroundColor White
Write-Host ""
Write-Host "Use in Fabric Notebook:" -ForegroundColor Cyan
Write-Host "  from fabric_spark_advisor import SparkAdvisor" -ForegroundColor White
Write-Host "  advisor = SparkAdvisor('https://$appUrl')" -ForegroundColor White
Write-Host "  advisor.launch()" -ForegroundColor White
Write-Host ""
Write-Host "Monitor logs:" -ForegroundColor Cyan
Write-Host "  az containerapp logs show --name $APP_NAME --resource-group $RESOURCE_GROUP --follow" -ForegroundColor White
Write-Host ""
Write-Host "=======================================================" -ForegroundColor Green
