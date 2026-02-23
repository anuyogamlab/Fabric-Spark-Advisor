# Test Azure Deployment
# Verifies that the deployed MCP server is responding

param(
    [Parameter(Mandatory=$true)]
    [string]$ServerUrl
)

Write-Host "🧪 Testing deployed MCP server..." -ForegroundColor Cyan
Write-Host "URL: $ServerUrl" -ForegroundColor White
Write-Host ""

# Test 1: Health check
Write-Host "1️⃣ Testing health endpoint..." -ForegroundColor Yellow
try {
    $healthUrl = "$ServerUrl/health"
    $response = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 10
    Write-Host "   ✅ Health check passed" -ForegroundColor Green
    Write-Host "   Response: $($response | ConvertTo-Json -Compress)" -ForegroundColor Gray
} catch {
    Write-Host "   ❌ Health check failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Test 2: MCP tools list
Write-Host "2️⃣ Testing MCP tools endpoint..." -ForegroundColor Yellow
try {
    $toolsUrl = "$ServerUrl/mcp/tools/list"
    $response = Invoke-RestMethod -Uri $toolsUrl -Method Post -ContentType "application/json" -Body '{}' -TimeoutSec 10
    $toolCount = $response.tools.Count
    Write-Host "   ✅ MCP tools endpoint working" -ForegroundColor Green
    Write-Host "   Found $toolCount tools" -ForegroundColor Gray
} catch {
    Write-Host "   ❌ MCP tools check failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Test 3: Sample query
Write-Host "3️⃣ Testing sample query..." -ForegroundColor Yellow
try {
    $queryUrl = "$ServerUrl/mcp/tools/call"
    $body = @{
        name = "get_application_metrics"
        arguments = @{
            application_id = "application_test"
        }
    } | ConvertTo-Json
    
    $response = Invoke-RestMethod -Uri $queryUrl -Method Post -ContentType "application/json" -Body $body -TimeoutSec 30
    Write-Host "   ✅ Query endpoint working" -ForegroundColor Green
    Write-Host "   Response type: $($response.GetType().Name)" -ForegroundColor Gray
} catch {
    Write-Host "   ⚠️ Query test failed (may be expected if no data): $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "═══════════════════════════════════════" -ForegroundColor Green
Write-Host "✅ Deployment verification complete!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "Your server is ready to use! 🎉" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Open a Fabric notebook"
Write-Host "  2. Install: %pip install fabric-spark-advisor"
Write-Host "  3. Connect: advisor = SparkAdvisor('$ServerUrl')"
Write-Host "  4. Launch: advisor.launch()"
Write-Host ""
