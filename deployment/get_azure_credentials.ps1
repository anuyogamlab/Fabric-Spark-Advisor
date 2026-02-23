# Helper script to get Azure credentials for .env file
# Run this to get your tenant ID and subscription info

Write-Host "`n🔑 Getting Azure Credentials for SparkAdvisor" -ForegroundColor Cyan
Write-Host "=" * 60

# Check if Azure CLI is installed
try {
    $azVersion = az version 2>$null
    if ($LASTEXITCODE -ne 0) { throw }
    Write-Host "✅ Azure CLI found" -ForegroundColor Green
} catch {
    Write-Host "❌ Azure CLI not found. Install it from: https://aka.ms/install-azure-cli" -ForegroundColor Red
    exit 1
}

# Get current account info
Write-Host "`n1️⃣  Current Azure Account" -ForegroundColor Yellow
Write-Host "-" * 60
$account = az account show | ConvertFrom-Json

$tenantId = $account.tenantId
$subscriptionId = $account.id
$subscriptionName = $account.name

Write-Host "Tenant ID       : $tenantId" -ForegroundColor White
Write-Host "Subscription ID : $subscriptionId"
Write-Host "Subscription    : $subscriptionName"

# List app registrations in the tenant
Write-Host "`n2️⃣  Finding App Registrations" -ForegroundColor Yellow
Write-Host "-" * 60

$apps = az ad app list --query "[].{Name:displayName, AppId:appId}" | ConvertFrom-Json

if ($apps.Count -gt 0) {
    Write-Host "Found $($apps.Count) app registrations:`n"
    $apps | ForEach-Object { 
        Write-Host "  📱 $($_.Name)" -ForegroundColor Cyan
        Write-Host "     App ID: $($_.AppId)" -ForegroundColor Gray
    }
    
    Write-Host "`n💡 If one of these apps has access to your Kusto database," -ForegroundColor Yellow
    Write-Host "   you can use its App ID as AZURE_CLIENT_ID" -ForegroundColor Yellow
} else {
    Write-Host "No app registrations found in this tenant." -ForegroundColor Yellow
}

# Offer to create a new app registration
Write-Host "`n3️⃣  Create New App Registration (Optional)" -ForegroundColor Yellow
Write-Host "-" * 60

$createNew = Read-Host "Create new app registration for SparkAdvisor? (y/N)"

if ($createNew -eq 'y' -or $createNew -eq 'Y') {
    $appName = "SparkAdvisor-MCP-$(Get-Date -Format 'yyyyMMdd')"
    
    Write-Host "`nCreating app registration: $appName..."
    $newApp = az ad app create --display-name $appName | ConvertFrom-Json
    $appId = $newApp.appId
    
    Write-Host "✅ App created!" -ForegroundColor Green
    Write-Host "   App ID: $appId"
    
    # Create service principal
    Write-Host "`nCreating service principal..."
    az ad sp create --id $appId | Out-Null
    
    # Create client secret
    Write-Host "Creating client secret..."
    $credential = az ad app credential reset --id $appId --append | ConvertFrom-Json
    $clientSecret = $credential.password
    
    Write-Host "`n✅ Credentials Created!" -ForegroundColor Green
    Write-Host "=" * 60
    Write-Host "`n📋 Add these to your .env file:" -ForegroundColor Cyan
    Write-Host "`nAZURE_TENANT_ID=$tenantId" -ForegroundColor White
    Write-Host "AZURE_CLIENT_ID=$appId" -ForegroundColor White
    Write-Host "AZURE_CLIENT_SECRET=$clientSecret" -ForegroundColor White
    
    Write-Host "`n⚠️  IMPORTANT: Grant this app access to your Kusto database!" -ForegroundColor Yellow
    Write-Host "   1. Go to your Kusto database in Fabric" -ForegroundColor Yellow
    Write-Host "   2. Manage → Permissions → Add" -ForegroundColor Yellow
    Write-Host "   3. Search for: $appName" -ForegroundColor Yellow
    Write-Host "   4. Grant role: Database Viewer (or Admin)" -ForegroundColor Yellow
    
    # Ask if user wants to update .env automatically
    Write-Host "`n4️⃣  Update .env File" -ForegroundColor Yellow
    Write-Host "-" * 60
    $updateEnv = Read-Host "Automatically update .env file? (y/N)"
    
    if ($updateEnv -eq 'y' -or $updateEnv -eq 'Y') {
        $envFile = ".env"
        if (Test-Path $envFile) {
            $content = Get-Content $envFile -Raw
            $content = $content -replace 'AZURE_TENANT_ID=.*', "AZURE_TENANT_ID=$tenantId"
            $content = $content -replace 'AZURE_CLIENT_ID=.*', "AZURE_CLIENT_ID=$appId"
            $content = $content -replace 'AZURE_CLIENT_SECRET=.*', "AZURE_CLIENT_SECRET=$clientSecret"
            $content | Set-Content $envFile -NoNewline
            Write-Host "✅ .env file updated!" -ForegroundColor Green
        } else {
            Write-Host "❌ .env file not found. Please create it manually." -ForegroundColor Red
        }
    }
    
} else {
    Write-Host "`n💡 Manual Setup Instructions:" -ForegroundColor Yellow
    Write-Host "=" * 60
    Write-Host "`nIf you have an existing app registration with Kusto access:"
    Write-Host "1. Find the app in Azure Portal → Azure AD → App registrations"
    Write-Host "2. Copy the Application (client) ID"
    Write-Host "3. Go to Certificates & secrets → New client secret"
    Write-Host "4. Copy the secret value (only shown once!)"
    Write-Host "`nThen update your .env file:"
    Write-Host "`nAZURE_TENANT_ID=$tenantId" -ForegroundColor White
    Write-Host "AZURE_CLIENT_ID=<your-app-id>" -ForegroundColor Gray
    Write-Host "AZURE_CLIENT_SECRET=<your-client-secret>" -ForegroundColor Gray
}

Write-Host "`n✅ Done! Test your connection with:" -ForegroundColor Green
Write-Host "   python -c `"from mcp_server.kusto_client import KustoClient; KustoClient()`"`n"
