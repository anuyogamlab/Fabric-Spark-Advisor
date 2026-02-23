# Azure Deployment Script - Deploy Spark Advisor to Azure Container Apps
# Uses .env file for credentials

param(
    [switch]$BuildOnly,
    [switch]$DeployOnly,
    [switch]$SkipBuild
)

# Load environment variables from .env file
if (-not (Test-Path ".env")) {
    Write-Host "❌ Error: .env file not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please create .env file:" -ForegroundColor Yellow
    Write-Host "  1. Copy .env.example to .env"
    Write-Host "  2. Fill in your credentials"
    Write-Host ""
    exit 1
}

Write-Host "📄 Loading credentials from .env..." -ForegroundColor Cyan
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.+)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

# Validate required variables
$required = @(
    "KUSTO_CLUSTER_URL",
    "KUSTO_DATABASE",
    "KUSTO_CLIENT_ID",
    "KUSTO_CLIENT_SECRET",
    "KUSTO_TENANT_ID",
    "AZURE_SEARCH_ENDPOINT",
    "AZURE_SEARCH_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY"
)

$missing = @()
foreach ($var in $required) {
    if (-not [Environment]::GetEnvironmentVariable($var)) {
        $missing += $var
    }
}

if ($missing.Count -gt 0) {
    Write-Host "❌ Missing required environment variables:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
    Write-Host ""
    Write-Host "Please update your .env file" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ All credentials loaded" -ForegroundColor Green

# Set Azure deployment variables (with defaults from .env or hardcoded)
$RESOURCE_GROUP = if ([Environment]::GetEnvironmentVariable("AZURE_RESOURCE_GROUP")) { [Environment]::GetEnvironmentVariable("AZURE_RESOURCE_GROUP") } else { "spark-advisor-rg" }
$LOCATION = if ([Environment]::GetEnvironmentVariable("AZURE_LOCATION")) { [Environment]::GetEnvironmentVariable("AZURE_LOCATION") } else { "eastus" }
$CONTAINERAPPS_ENV = if ([Environment]::GetEnvironmentVariable("AZURE_CONTAINERAPPS_ENV")) { [Environment]::GetEnvironmentVariable("AZURE_CONTAINERAPPS_ENV") } else { "spark-advisor-env" }
$APP_NAME = if ([Environment]::GetEnvironmentVariable("AZURE_APP_NAME")) { [Environment]::GetEnvironmentVariable("AZURE_APP_NAME") } else { "spark-advisor-mcp" }
$ACR_NAME = if ([Environment]::GetEnvironmentVariable("AZURE_ACR_NAME")) { [Environment]::GetEnvironmentVariable("AZURE_ACR_NAME") } else { "sparkadvisoracr" }

Write-Host ""
Write-Host "🚀 Deployment Configuration:" -ForegroundColor Cyan
Write-Host "  Resource Group: $RESOURCE_GROUP"
Write-Host "  Location: $LOCATION"
Write-Host "  App Name: $APP_NAME"
Write-Host "  ACR Name: $ACR_NAME"
Write-Host ""

# Check if Azure CLI is installed
Write-Host "🔍 Checking Azure CLI..." -ForegroundColor Cyan
try {
    $azVersion = az --version 2>&1 | Select-String "azure-cli" | Select-Object -First 1
    Write-Host "✅ Azure CLI found: $azVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Azure CLI not found. Please install: https://aka.ms/azure-cli" -ForegroundColor Red
    exit 1
}

# Check if Docker is installed
if (-not $DeployOnly) {
    Write-Host "🔍 Checking Docker..." -ForegroundColor Cyan
    try {
        $dockerVersion = docker --version
        Write-Host "✅ Docker found: $dockerVersion" -ForegroundColor Green
    } catch {
        Write-Host "❌ Docker not found. Please install: https://www.docker.com/products/docker-desktop" -ForegroundColor Red
        exit 1
    }
}

# Login to Azure
Write-Host ""
Write-Host "🔐 Logging into Azure..." -ForegroundColor Cyan
az login --output none

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Azure login failed" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Logged into Azure" -ForegroundColor Green

if (-not $BuildOnly -and -not $SkipBuild) {
    # Create resource group
    Write-Host ""
    Write-Host "📦 Creating resource group..." -ForegroundColor Cyan
    az group create --name $RESOURCE_GROUP --location $LOCATION --output none
    Write-Host "✅ Resource group ready" -ForegroundColor Green

    # Create Container Apps environment
    Write-Host ""
    Write-Host "🌍 Creating Container Apps environment..." -ForegroundColor Cyan
    $envExists = az containerapp env show --name $CONTAINERAPPS_ENV --resource-group $RESOURCE_GROUP 2>$null
    if (-not $envExists) {
        az containerapp env create `
            --name $CONTAINERAPPS_ENV `
            --resource-group $RESOURCE_GROUP `
            --location $LOCATION `
            --output none
        Write-Host "✅ Environment created" -ForegroundColor Green
    } else {
        Write-Host "✅ Environment already exists" -ForegroundColor Green
    }

    # Create Azure Container Registry
    Write-Host ""
    Write-Host "📦 Creating Azure Container Registry..." -ForegroundColor Cyan
    $acrExists = az acr show --name $ACR_NAME 2>$null
    if (-not $acrExists) {
        az acr create `
            --resource-group $RESOURCE_GROUP `
            --name $ACR_NAME `
            --sku Basic `
            --admin-enabled true `
            --output none
        Write-Host "✅ ACR created" -ForegroundColor Green
    } else {
        Write-Host "✅ ACR already exists" -ForegroundColor Green
    }
}

# Build and push Docker image
if (-not $DeployOnly) {
    Write-Host ""
    Write-Host "🔨 Building Docker image..." -ForegroundColor Cyan
    
    # Login to ACR
    az acr login --name $ACR_NAME
    
    $imageName = "$ACR_NAME.azurecr.io/spark-advisor-mcp:latest"
    
    docker build -t $imageName .
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Docker build failed" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Image built: $imageName" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "📤 Pushing image to ACR..." -ForegroundColor Cyan
    docker push $imageName
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Docker push failed" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Image pushed" -ForegroundColor Green
}

if ($BuildOnly) {
    Write-Host ""
    Write-Host "Build complete! (BuildOnly flag set, skipping deployment)" -ForegroundColor Green
    exit 0
}

# Get ACR credentials
Write-Host ""
Write-Host "🔐 Getting ACR credentials..." -ForegroundColor Cyan
$acrUsername = az acr credential show --name $ACR_NAME --query username -o tsv
$acrPassword = az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv

# Deploy container app
Write-Host ""
Write-Host "🚀 Deploying container app..." -ForegroundColor Cyan

$appExists = az containerapp show --name $APP_NAME --resource-group $RESOURCE_GROUP 2>$null

if (-not $appExists) {
    # Create new app
    az containerapp create `
        --name $APP_NAME `
        --resource-group $RESOURCE_GROUP `
        --environment $CONTAINERAPPS_ENV `
        --image "$ACR_NAME.azurecr.io/spark-advisor-mcp:latest" `
        --target-port 8000 `
        --ingress external `
        --registry-server "$ACR_NAME.azurecr.io" `
        --registry-username $acrUsername `
        --registry-password $acrPassword `
        --cpu 1.0 `
        --memory 2.0Gi `
        --min-replicas 1 `
        --max-replicas 3 `
        --env-vars `
            KUSTO_CLUSTER_URL="$env:KUSTO_CLUSTER_URL" `
            KUSTO_DATABASE="$env:KUSTO_DATABASE" `
            KUSTO_CLIENT_ID="$env:KUSTO_CLIENT_ID" `
            KUSTO_CLIENT_SECRET="secretref:kusto-secret" `
            KUSTO_TENANT_ID="$env:KUSTO_TENANT_ID" `
            AZURE_SEARCH_ENDPOINT="$env:AZURE_SEARCH_ENDPOINT" `
            AZURE_SEARCH_KEY="secretref:search-key" `
            AZURE_SEARCH_INDEX="$env:AZURE_SEARCH_INDEX" `
            AZURE_OPENAI_ENDPOINT="$env:AZURE_OPENAI_ENDPOINT" `
            AZURE_OPENAI_API_KEY="secretref:openai-key" `
            AZURE_OPENAI_DEPLOYMENT="$env:AZURE_OPENAI_DEPLOYMENT" `
            AZURE_OPENAI_API_VERSION="$env:AZURE_OPENAI_API_VERSION" `
        --secrets `
            kusto-secret="$env:KUSTO_CLIENT_SECRET" `
            search-key="$env:AZURE_SEARCH_KEY" `
            openai-key="$env:AZURE_OPENAI_API_KEY" `
        --output none
} else {
    # Update existing app
    Write-Host "ℹ️ App exists, updating..." -ForegroundColor Yellow
    az containerapp update `
        --name $APP_NAME `
        --resource-group $RESOURCE_GROUP `
        --image "$ACR_NAME.azurecr.io/spark-advisor-mcp:latest" `
        --output none
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Deployment failed" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Deployment complete!" -ForegroundColor Green

# Get the app URL
Write-Host ""
Write-Host "🌐 Getting application URL..." -ForegroundColor Cyan
$appUrl = az containerapp show `
    --name $APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --query properties.configuration.ingress.fqdn `
    -o tsv

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Green
Write-Host "DEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Your MCP Server URL:" -ForegroundColor Cyan
Write-Host "   https://$appUrl" -ForegroundColor White
Write-Host ""
Write-Host "📝 Use in Fabric Notebook:" -ForegroundColor Cyan
Write-Host "   from fabric_spark_advisor import SparkAdvisor" -ForegroundColor White
Write-Host "   advisor = SparkAdvisor('https://$appUrl')" -ForegroundColor White
Write-Host "   advisor.launch()" -ForegroundColor White
Write-Host ""
Write-Host "📊 Monitor logs:" -ForegroundColor Cyan
Write-Host "   az containerapp logs show --name $APP_NAME --resource-group $RESOURCE_GROUP --follow" -ForegroundColor White
Write-Host ""
Write-Host "🔧 Manage in Azure Portal:" -ForegroundColor Cyan
Write-Host "   https://portal.azure.com/#@/resource/subscriptions/.../resourceGroups/$RESOURCE_GROUP/providers/Microsoft.App/containerApps/$APP_NAME" -ForegroundColor White
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Green
