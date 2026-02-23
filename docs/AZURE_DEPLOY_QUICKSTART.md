# 🚀 Quick Azure Deployment Guide

## Prerequisites (One-time Setup)

1. **Azure CLI**: https://aka.ms/azure-cli
2. **Docker Desktop**: https://www.docker.com/products/docker-desktop
3. **Azure Subscription**: Get one at https://azure.com

---

## Step 1: Create .env File (2 minutes)

```powershell
# Copy the example
cp .env.example .env

# Edit .env with your credentials
notepad .env
```

Fill in these values:

```ini
# From your Kusto cluster
KUSTO_CLUSTER_URL=https://yourcluster.kusto.windows.net
KUSTO_DATABASE=YourDatabase
KUSTO_CLIENT_ID=your-app-registration-client-id
KUSTO_CLIENT_SECRET=your-client-secret
KUSTO_TENANT_ID=your-tenant-id

# From Azure AI Search
AZURE_SEARCH_ENDPOINT=https://yoursearch.search.windows.net
AZURE_SEARCH_KEY=your-admin-key
AZURE_SEARCH_INDEX=spark-docs

# From Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://youropenai.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

---

## Step 2: Deploy to Azure (One Command!)

```powershell
# Deploy everything (build + push + deploy)
.\deploy-azure.ps1
```

That's it! The script will:
1. ✅ Validate your .env credentials
2. ✅ Login to Azure
3. ✅ Create resource group
4. ✅ Create Container Apps environment
5. ✅ Create Container Registry
6. ✅ Build Docker image
7. ✅ Push to registry
8. ✅ Deploy container app
9. ✅ Show your URL

---

## Step 3: Use in Fabric Notebook

After deployment completes, you'll see:

```
🌐 Your MCP Server URL:
   https://spark-advisor-mcp.eastus.azurecontainerapps.io
```

Copy that URL and use in your notebook:

```python
from fabric_spark_advisor import SparkAdvisor

advisor = SparkAdvisor('https://spark-advisor-mcp.eastus.azurecontainerapps.io')
advisor.launch()
```

---

## Advanced Options

### Build Only (Test Dockerfile)
```powershell
.\deploy-azure.ps1 -BuildOnly
```

### Deploy Only (After Build)
```powershell
.\deploy-azure.ps1 -DeployOnly
```

### Update Existing Deployment
```powershell
# After code changes, rebuild and update
.\deploy-azure.ps1
```

---

## Monitoring & Troubleshooting

### View Logs
```powershell
az containerapp logs show --name spark-advisor-mcp --resource-group spark-advisor-rg --follow
```

### Check Status
```powershell
az containerapp show --name spark-advisor-mcp --resource-group spark-advisor-rg --query properties.runningStatus
```

### Restart App
```powershell
az containerapp revision restart --name spark-advisor-mcp --resource-group spark-advisor-rg
```

### View in Portal
```powershell
# Open Azure Portal to your app
az containerapp browse --name spark-advisor-mcp --resource-group spark-advisor-rg
```

---

## Cost Estimation

**Azure Container Apps (Consumption)**:
- 180,000 vCPU-seconds free/month
- After that: ~$0.000012 per vCPU-second
- **Estimated: $10-30/month** for typical usage

**What you pay for**:
- Container Apps compute
- Container Registry storage (~$5/month)
- Outbound data transfer (usually minimal)

**What's FREE**:
- First 180K vCPU-seconds
- Inbound data transfer
- Azure Monitor basic metrics

---

## Cleanup (Delete Everything)

```powershell
# Delete entire resource group
az group delete --name spark-advisor-rg --yes --no-wait
```

---

## Security Best Practices

### ✅ DO
- Use `.env` for local development
- Keep `.env` out of git (already in .gitignore)
- Rotate secrets regularly
- Use HTTPS only (Container Apps provides this)

### ⚠️ CONSIDER
- Use Azure Key Vault for production secrets
- Enable Managed Identity instead of client secrets
- Set up Azure AD authentication for the endpoint

### ❌ DON'T
- Commit .env to git
- Share .env file
- Use same credentials for dev and prod

---

## Updating Deployment

### After Code Changes

```powershell
# Simple: Just run deploy again
.\deploy-azure.ps1

# The script will:
# - Build new image with :latest tag
# - Push to ACR
# - Container Apps auto-detects and updates
```

### Change Environment Variables

```powershell
# Update .env file
notepad .env

# Redeploy
.\deploy-azure.ps1 -DeployOnly
```

---

## FAQ

**Q: How long does first deployment take?**  
A: ~10-15 minutes (building image takes longest)

**Q: Do I need to rebuild for every deployment?**  
A: Only if code changed. For config changes, use `-DeployOnly`

**Q: Can I use a different region?**  
A: Yes! Edit `AZURE_LOCATION` in .env before deploying

**Q: How do I scale up?**  
A: Edit deploy-azure.ps1, change `--min-replicas` and `--max-replicas`

**Q: Can multiple people use the same deployment?**  
A: Yes! Share the URL, everyone can connect

**Q: How secure is this?**  
A: HTTPS by default. For enterprise, add Azure AD auth (see Azure docs)

---

## Next Steps

1. ✅ Deploy using `.\deploy-azure.ps1`
2. ✅ Copy the URL
3. ✅ Use in Fabric notebooks
4. ✅ Share URL with team
5. ✅ Monitor with Azure Portal

🎉 That's it! Your Spark Advisor is now production-ready!
