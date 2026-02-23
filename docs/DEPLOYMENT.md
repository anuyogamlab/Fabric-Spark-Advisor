# Deployment Guide

This guide covers deploying the Spark Recommender Agent to various environments.

## 🐳 Docker Deployment

### Local Docker

```bash
# Build the image
docker build -t spark-recommender:latest .

# Run the container
docker run -p 8000:8000 -p 8501:8501 \
  --env-file .env \
  --name spark-recommender \
  spark-recommender:latest

# Access:
# - UI: http://localhost:8501
# - MCP Server: http://localhost:8000
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  spark-recommender:
    build: .
    ports:
      - "8000:8000"
      - "8501:8501"
    env_file:
      - .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

Run with:
```bash
docker-compose up -d
```

## ☁️ Azure Container Apps

### Prerequisites

```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login
az login

# Set subscription
az account set --subscription <your-subscription-id>
```

### Create Azure Resources

```bash
# Variables
RESOURCE_GROUP="spark-recommender-rg"
LOCATION="eastus"
ACR_NAME="sparkrecacr"  # Must be globally unique
CONTAINER_APP_ENV="spark-recommender-env"
CONTAINER_APP_NAME="spark-recommender"

# Create resource group
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION

# Create Azure Container Registry
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic \
  --admin-enabled true

# Create Container Apps environment
az containerapp env create \
  --name $CONTAINER_APP_ENV \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION
```

### Build and Push Image

```bash
# Get ACR credentials
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)

# Login to ACR
az acr login --name $ACR_NAME

# Build and push using ACR task (recommended)
az acr build \
  --registry $ACR_NAME \
  --image spark-recommender:latest \
  --file Dockerfile \
  .

# Or build locally and push
# docker build -t $ACR_NAME.azurecr.io/spark-recommender:latest .
# docker push $ACR_NAME.azurecr.io/spark-recommender:latest
```

### Deploy Container App

```bash
# Create container app with environment variables
az containerapp create \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment $CONTAINER_APP_ENV \
  --image $ACR_NAME.azurecr.io/spark-recommender:latest \
  --target-port 8501 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 1.0 \
  --memory 2.0Gi \
  --registry-server $ACR_NAME.azurecr.io \
  --registry-username $ACR_USERNAME \
  --registry-password $ACR_PASSWORD \
  --secrets \
    azure-openai-endpoint=$AZURE_OPENAI_ENDPOINT \
    azure-openai-key=$AZURE_OPENAI_API_KEY \
    kusto-cluster=$KUSTO_CLUSTER_URI \
    azure-search-key=$AZURE_SEARCH_KEY \
  --env-vars \
    AZURE_OPENAI_ENDPOINT=secretref:azure-openai-endpoint \
    AZURE_OPENAI_API_KEY=secretref:azure-openai-key \
    AZURE_OPENAI_DEPLOYMENT=gpt-4o \
    KUSTO_CLUSTER_URI=secretref:kusto-cluster \
    KUSTO_DATABASE="Spark Monitoring" \
    AZURE_SEARCH_ENDPOINT=$AZURE_SEARCH_ENDPOINT \
    AZURE_SEARCH_KEY=secretref:azure-search-key \
    AZURE_SEARCH_INDEX=spark-docs-index

# Get the app URL
az containerapp show \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn \
  -o tsv
```

### Update Existing Deployment

```bash
# Rebuild and push new image
az acr build \
  --registry $ACR_NAME \
  --image spark-recommender:latest \
  --file Dockerfile \
  .

# Update container app
az containerapp update \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --image $ACR_NAME.azurecr.io/spark-recommender:latest
```

### Monitoring

```bash
# View logs
az containerapp logs show \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --tail 100 \
  --follow

# View metrics
az monitor metrics list \
  --resource /subscriptions/<subscription-id>/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.App/containerApps/$CONTAINER_APP_NAME \
  --metric "Requests"

# View container status
az containerapp show \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query properties.runningStatus
```

## 🌐 Azure Web App

Alternative deployment to Azure Web App for Containers:

```bash
# Create App Service Plan
az appservice plan create \
  --name spark-recommender-plan \
  --resource-group $RESOURCE_GROUP \
  --is-linux \
  --sku B1

# Create Web App
az webapp create \
  --name spark-recommender-app \
  --resource-group $RESOURCE_GROUP \
  --plan spark-recommender-plan \
  --deployment-container-image-name $ACR_NAME.azurecr.io/spark-recommender:latest

# Configure container registry
az webapp config container set \
  --name spark-recommender-app \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name $ACR_NAME.azurecr.io/spark-recommender:latest \
  --docker-registry-server-url https://$ACR_NAME.azurecr.io \
  --docker-registry-server-user $ACR_USERNAME \
  --docker-registry-server-password $ACR_PASSWORD

# Set environment variables
az webapp config appsettings set \
  --name spark-recommender-app \
  --resource-group $RESOURCE_GROUP \
  --settings \
    AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT \
    AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY \
    AZURE_OPENAI_DEPLOYMENT=gpt-4o \
    KUSTO_CLUSTER_URI=$KUSTO_CLUSTER_URI \
    KUSTO_DATABASE="Spark Monitoring" \
    AZURE_SEARCH_ENDPOINT=$AZURE_SEARCH_ENDPOINT \
    AZURE_SEARCH_KEY=$AZURE_SEARCH_KEY \
    AZURE_SEARCH_INDEX=spark-docs-index

# Enable container logging
az webapp log config \
  --name spark-recommender-app \
  --resource-group $RESOURCE_GROUP \
  --docker-container-logging filesystem
```

## 🎯 Kubernetes (AKS)

For Kubernetes deployment:

### Create deployment.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: spark-recommender
spec:
  replicas: 2
  selector:
    matchLabels:
      app: spark-recommender
  template:
    metadata:
      labels:
        app: spark-recommender
    spec:
      containers:
      - name: spark-recommender
        image: <ACR_NAME>.azurecr.io/spark-recommender:latest
        ports:
        - containerPort: 8501
        - containerPort: 8000
        env:
        - name: AZURE_OPENAI_ENDPOINT
          valueFrom:
            secretKeyRef:
              name: spark-recommender-secrets
              key: azure-openai-endpoint
        - name: AZURE_OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: spark-recommender-secrets
              key: azure-openai-key
        - name: AZURE_OPENAI_DEPLOYMENT
          value: "gpt-4o"
        # ... other env vars
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 1000m
            memory: 2Gi
        livenessProbe:
          httpGet:
            path: /
            port: 8501
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 8501
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: spark-recommender-service
spec:
  type: LoadBalancer
  ports:
  - name: ui
    port: 80
    targetPort: 8501
  - name: mcp
    port: 8000
    targetPort: 8000
  selector:
    app: spark-recommender
```

Apply with:
```bash
kubectl apply -f deployment.yaml
```

## 🔐 Security Best Practices

### Secrets Management

**For Azure Container Apps:**
```bash
# Use Key Vault references
az containerapp secret set \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --secrets \
    azure-openai-key=keyvaultref:https://<vault>.vault.azure.net/secrets/<secret>,identityref:<identity-id>
```

**For Kubernetes:**
```bash
# Create secrets
kubectl create secret generic spark-recommender-secrets \
  --from-literal=azure-openai-endpoint=$AZURE_OPENAI_ENDPOINT \
  --from-literal=azure-openai-key=$AZURE_OPENAI_API_KEY \
  --from-literal=kusto-cluster=$KUSTO_CLUSTER_URI \
  --from-literal=azure-search-key=$AZURE_SEARCH_KEY
```

### Managed Identity

Enable managed identity for passwordless auth to Azure services:

```bash
# Enable system-assigned identity
az containerapp identity assign \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --system-assigned

# Get principal ID
PRINCIPAL_ID=$(az containerapp identity show \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)

# Grant access to Key Vault
az keyvault set-policy \
  --name <your-keyvault> \
  --object-id $PRINCIPAL_ID \
  --secret-permissions get list
```

## 📊 Monitoring & Logging

### Application Insights

```bash
# Create Application Insights
az monitor app-insights component create \
  --app spark-recommender-insights \
  --location $LOCATION \
  --resource-group $RESOURCE_GROUP

# Get instrumentation key
APPINSIGHTS_KEY=$(az monitor app-insights component show \
  --app spark-recommender-insights \
  --resource-group $RESOURCE_GROUP \
  --query instrumentationKey -o tsv)

# Add to container app
az containerapp update \
  --name $CONTAINER_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --set-env-vars \
    APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=$APPINSIGHTS_KEY"
```

### Log Analytics

```bash
# Query logs
az monitor log-analytics query \
  --workspace <workspace-id> \
  --analytics-query "ContainerAppConsoleLogs_CL | where ContainerAppName_s == 'spark-recommender' | order by TimeGenerated desc | take 100"
```

## 🔄 CI/CD with GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Azure Container Apps

on:
  push:
    branches: [main]

env:
  ACR_NAME: sparkrecacr
  RESOURCE_GROUP: spark-recommender-rg
  CONTAINER_APP_NAME: spark-recommender

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Azure Login
      uses: azure/login@v1
      with:
        creds: ${{ secrets.AZURE_CREDENTIALS }}
    
    - name: Build and push image
      run: |
        az acr build \
          --registry ${{ env.ACR_NAME }} \
          --image spark-recommender:${{ github.sha }} \
          --image spark-recommender:latest \
          .
    
    - name: Deploy to Container Apps
      run: |
        az containerapp update \
          --name ${{ env.CONTAINER_APP_NAME }} \
          --resource-group ${{ env.RESOURCE_GROUP }} \
          --image ${{ env.ACR_NAME }}.azurecr.io/spark-recommender:${{ github.sha }}
```

## 🧹 Cleanup

```bash
# Delete everything
az group delete --name $RESOURCE_GROUP --yes --no-wait

# Or delete individual resources
az containerapp delete --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --yes
az acr delete --name $ACR_NAME --resource-group $RESOURCE_GROUP --yes
```

---

For more deployment options and troubleshooting, see the main [README.md](README.md).
