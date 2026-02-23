# ⚡ Deploy to Azure in 3 Steps

## Step 1: Setup Credentials (2 min)

```powershell
# Copy example file
Copy-Item .env.example .env

# Edit with your credentials
notepad .env
```

Replace these placeholders in `.env`:
- `your-openai-resource` → Your Azure OpenAI name
- `your-openai-api-key-here` → Get from Azure Portal
- `your-cluster.kusto.fabric.microsoft.com` → Your Kusto/Eventhouse URL
- `your-search-service` → Your Azure AI Search name
- All other placeholder values

## Step 2: Deploy (10 min)

```powershell
# One command does everything!
.\deploy-azure.ps1
```

This will:
- ✅ Validate credentials
- ✅ Build Docker image
- ✅ Push to Azure Container Registry
- ✅ Deploy to Container Apps
- ✅ Show you the URL

## Step 3: Use in Fabric Notebook

After deployment, you'll see:
```
🌐 Your MCP Server URL:
   https://spark-advisor-mcp.eastus.azurecontainerapps.io
```

Use it:
```python
from fabric_spark_advisor import SparkAdvisor

advisor = SparkAdvisor('https://spark-advisor-mcp.eastus.azurecontainerapps.io')
advisor.launch()
```

## That's It! 🎉

See [AZURE_DEPLOY_QUICKSTART.md](AZURE_DEPLOY_QUICKSTART.md) for advanced options.
