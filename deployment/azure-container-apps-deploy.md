# Deploy MCP Server to Azure Container Apps

## Overview
Deploy the Spark Advisor MCP server to Azure Container Apps so Fabric notebooks can connect from the cloud.

---

## Prerequisites
- Azure subscription
- Azure CLI installed: `az --version`
- Docker installed (for building container)

---

## Step 1: Create Dockerfile

```dockerfile
# File: Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose MCP server port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Run MCP server
CMD ["python", "spark_mcp_server.py"]
```

---

## Step 2: Set Environment Variables

Create `.env` file with your secrets (DO NOT commit this):

```bash
# Kusto connection
KUSTO_CLUSTER_URL=https://your-cluster.kusto.windows.net
KUSTO_DATABASE=YourDatabase
KUSTO_CLIENT_ID=your-client-id
KUSTO_CLIENT_SECRET=your-client-secret
KUSTO_TENANT_ID=your-tenant-id

# Azure AI Search (RAG)
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_KEY=your-search-key
AZURE_SEARCH_INDEX=spark-docs

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_API_KEY=your-openai-key
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-01
```

---

## Step 3: Deploy to Azure Container Apps

```bash
# Login to Azure
az login

# Set variables
RESOURCE_GROUP="spark-advisor-rg"
LOCATION="eastus"
CONTAINERAPPS_ENV="spark-advisor-env"
APP_NAME="spark-advisor-mcp"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Container Apps environment
az containerapp env create \
  --name $CONTAINERAPPS_ENV \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

# Build and push container to Azure Container Registry (ACR)
ACR_NAME="sparkadvisoracr"
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic \
  --admin-enabled true

# Login to ACR
az acr login --name $ACR_NAME

# Build and push image
docker build -t $ACR_NAME.azurecr.io/spark-advisor-mcp:latest .
docker push $ACR_NAME.azurecr.io/spark-advisor-mcp:latest

# Get ACR credentials
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)

# Deploy container app
az containerapp create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment $CONTAINERAPPS_ENV \
  --image $ACR_NAME.azurecr.io/spark-advisor-mcp:latest \
  --target-port 8000 \
  --ingress external \
  --registry-server $ACR_NAME.azurecr.io \
  --registry-username $ACR_USERNAME \
  --registry-password $ACR_PASSWORD \
  --env-vars \
    KUSTO_CLUSTER_URL=$KUSTO_CLUSTER_URL \
    KUSTO_DATABASE=$KUSTO_DATABASE \
    KUSTO_CLIENT_ID=$KUSTO_CLIENT_ID \
    KUSTO_CLIENT_SECRET=$KUSTO_CLIENT_SECRET \
    KUSTO_TENANT_ID=$KUSTO_TENANT_ID \
    AZURE_SEARCH_ENDPOINT=$AZURE_SEARCH_ENDPOINT \
    AZURE_SEARCH_KEY=$AZURE_SEARCH_KEY \
    AZURE_SEARCH_INDEX=$AZURE_SEARCH_INDEX \
    AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT \
    AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY \
    AZURE_OPENAI_DEPLOYMENT=$AZURE_OPENAI_DEPLOYMENT \
    AZURE_OPENAI_API_VERSION=$AZURE_OPENAI_API_VERSION

# Get the public URL
az containerapp show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn \
  -o tsv
```

---

## Step 4: Use in Fabric Notebook

```python
# Install wheel package in Fabric notebook
%pip install fabric-spark-advisor

from fabric_spark_advisor import SparkAdvisor

# Connect to Azure-hosted MCP server
advisor = SparkAdvisor(
    mcp_server_url="https://spark-advisor-mcp.eastus.azurecontainerapps.io"
)

advisor.launch()
```

---

## Cost Estimation

**Azure Container Apps (Consumption Plan):**
- First 180,000 vCPU-seconds free per month
- Then $0.000012 per vCPU-second
- Estimated: **~$10-30/month** for light usage

**Alternative: Azure App Service (Basic B1):**
- $13.14/month for 1 core, 1.75GB RAM
- More predictable pricing

---

## Security Best Practices

1. **Use Managed Identity** instead of connection strings:
   ```bash
   az containerapp identity assign --name $APP_NAME --resource-group $RESOURCE_GROUP --system-assigned
   ```

2. **Store secrets in Key Vault**:
   ```bash
   az keyvault create --name spark-advisor-kv --resource-group $RESOURCE_GROUP
   az keyvault secret set --vault-name spark-advisor-kv --name kusto-client-secret --value $KUSTO_CLIENT_SECRET
   ```

3. **Enable authentication** (restrict to your tenant):
   ```bash
   az containerapp auth update \
     --name $APP_NAME \
     --resource-group $RESOURCE_GROUP \
     --enabled true \
     --action AllowAnonymous  # Change to Redirect for auth
   ```

---

## Monitoring

```bash
# View logs
az containerapp logs show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --follow

# View metrics
az monitor metrics list \
  --resource $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --resource-type Microsoft.App/containerApps \
  --metric Requests
```

---

## Update Deployment

```bash
# Rebuild and push new image
docker build -t $ACR_NAME.azurecr.io/spark-advisor-mcp:v2 .
docker push $ACR_NAME.azurecr.io/spark-advisor-mcp:v2

# Update container app
az containerapp update \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --image $ACR_NAME.azurecr.io/spark-advisor-mcp:v2
```
