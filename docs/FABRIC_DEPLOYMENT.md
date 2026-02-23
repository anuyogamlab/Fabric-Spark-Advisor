# 🚀 Fabric Notebook Deployment Guide

## The Challenge

**Fabric notebooks run in the cloud** (Microsoft's managed compute), not on your local machine. This means they **cannot** directly call `http://127.0.0.1:8000` (localhost) to reach your MCP server.

---

## 🎯 Three Deployment Solutions

| Solution | Best For | Setup | Cost | Reliability |
|----------|----------|-------|------|-------------|
| **1. ngrok Tunnel** | Dev/Testing | 2 min | Free | Medium |
| **2. Azure Container Apps** | Production | 15 min | $10-30/mo | High |
| **3. In-Notebook** | Demos/Offline | 1 min | Free | High |

---

## 1️⃣ ngrok Tunnel (Fastest Setup)

### How It Works
```
Your Machine (localhost:8000) 
    ↓ 
ngrok tunnel 
    ↓ 
Public URL (https://abc123.ngrok-free.app) 
    ↓ 
Fabric Notebook (cloud)
```

### Setup

**On Your Machine:**
```powershell
# Terminal 1: Start MCP server
python spark_mcp_server.py

# Terminal 2: Create tunnel
ngrok http 8000
# Copy URL: https://abc123.ngrok-free.app
```

**In Fabric Notebook:**
```python
from fabric_spark_advisor import SparkAdvisor

advisor = SparkAdvisor(
    mcp_server_url="https://abc123.ngrok-free.app"  # ← YOUR ngrok URL
)
advisor.launch()
```

### Pros & Cons

✅ **Pros:**
- Ultra-fast setup (2 minutes)
- No Azure resources needed
- Free tier available
- See requests in real-time (http://127.0.0.1:4040)

❌ **Cons:**
- URL changes every restart (free tier)
- 40 connections/minute limit (free tier)
- Must keep local server + ngrok running
- Not suitable for team use

### When to Use
- **Development:** Quick iteration cycles
- **Testing:** Before Azure deployment
- **Demos:** Short presentations

**Full Guide:** `deployment/ngrok-tunnel-setup.md`

---

## 2️⃣ Azure Container Apps (Production Ready)

### How It Works
```
Docker Image → Azure Container Registry
    ↓
Azure Container Apps (auto-scaling)
    ↓
Static Public URL (https://spark-advisor.eastus.azurecontainerapps.io)
    ↓
Fabric Notebooks (cloud)
```

### Setup

**Build & Deploy:**
```bash
# See deployment/azure-container-apps-deploy.md for full script

# Quick deploy
az containerapp create \
  --name spark-advisor-mcp \
  --resource-group spark-advisor-rg \
  --image youracr.azurecr.io/spark-advisor:latest \
  --target-port 8000 \
  --ingress external

# Get URL
az containerapp show --name spark-advisor-mcp \
  --query properties.configuration.ingress.fqdn -o tsv
```

**In Fabric Notebook:**
```python
from fabric_spark_advisor import SparkAdvisor

advisor = SparkAdvisor(
    mcp_server_url="https://spark-advisor.eastus.azurecontainerapps.io"
)
advisor.launch()
```

### Pros & Cons

✅ **Pros:**
- **Static URL** (never changes)
- **Auto-scaling** (handles load spikes)
- **High availability** (99.95% SLA)
- **Team access** (everyone uses same URL)
- **Monitoring/logging** (Azure Monitor built-in)
- **Security** (Azure AD, Key Vault, Managed Identity)

❌ **Cons:**
- Costs $10-30/month
- Initial setup takes 15 minutes
- Requires Azure subscription

### When to Use
- **Production:** Team usage
- **Reliability:** Need 24/7 availability
- **Scale:** Multiple concurrent users
- **Security:** Enterprise requirements

**Full Guide:** `deployment/azure-container-apps-deploy.md`

---

## 3️⃣ In-Notebook Execution (Self-Contained)

### How It Works
```
Fabric Notebook
    ↓
LocalSparkAdvisor (runs in same process)
    ↓
Direct Python API calls
    ↓
Kusto/RAG/OpenAI (cloud services)
```

No external server needed!

### Setup

**In Fabric Notebook:**
```python
# Step 1: Configure credentials from Key Vault
import os
from notebookutils import mssparkutils

KEYVAULT = "your-keyvault-name"

os.environ["KUSTO_CLUSTER_URL"] = mssparkutils.credentials.getSecret(KEYVAULT, "kusto-url")
os.environ["KUSTO_CLIENT_ID"] = mssparkutils.credentials.getSecret(KEYVAULT, "kusto-id")
os.environ["KUSTO_CLIENT_SECRET"] = mssparkutils.credentials.getSecret(KEYVAULT, "kusto-secret")
os.environ["KUSTO_TENANT_ID"] = mssparkutils.credentials.getSecret(KEYVAULT, "tenant-id")
os.environ["KUSTO_DATABASE"] = "YourDatabase"

os.environ["AZURE_OPENAI_ENDPOINT"] = mssparkutils.credentials.getSecret(KEYVAULT, "openai-endpoint")
os.environ["AZURE_OPENAI_API_KEY"] = mssparkutils.credentials.getSecret(KEYVAULT, "openai-key")
os.environ["AZURE_OPENAI_DEPLOYMENT"] = "gpt-4o"

os.environ["AZURE_SEARCH_ENDPOINT"] = mssparkutils.credentials.getSecret(KEYVAULT, "search-endpoint")
os.environ["AZURE_SEARCH_KEY"] = mssparkutils.credentials.getSecret(KEYVAULT, "search-key")
os.environ["AZURE_SEARCH_INDEX"] = "spark-docs"

# Step 2: Launch advisor
from fabric_spark_advisor import LocalSparkAdvisor

advisor = LocalSparkAdvisor()

# Option A: UI
advisor.launch_ui()

# Option B: Programmatic
result = await advisor.analyze_application("application_123")
print(result)
```

### Pros & Cons

✅ **Pros:**
- **No external dependencies** (runs entirely in notebook)
- **No server management** (nothing to deploy)
- **Free** (only pay for Fabric compute)
- **Offline capable** (if Kusto/OpenAI reachable)
- **Simple** (one Python object)

❌ **Cons:**
- Credentials must be configured per notebook
- Slower startup (initializes Kusto/RAG each time)
- Not shared (each notebook is isolated)
- Higher memory usage in notebook

### When to Use
- **Demos:** Stakeholder presentations
- **Offline:** No internet access for server
- **One-off:** Single analysis tasks
- **Learning:** Understanding how it works

**Full Guide:** `deployment/in-notebook-server.md`

---

## 🎯 Decision Matrix

### Choose ngrok if:
- ✅ You're the only user
- ✅ Need fast feedback loop
- ✅ Developing/testing features
- ✅ Short-term usage
- ❌ Don't mind URL changing

### Choose Azure if:
- ✅ Multiple team members
- ✅ Production workloads
- ✅ Need 24/7 availability
- ✅ Enterprise security required
- ✅ Budget for $10-30/month

### Choose In-Notebook if:
- ✅ Demoing to stakeholders
- ✅ No deployment allowed
- ✅ One-time analysis
- ✅ Learning/experimenting
- ❌ Don't need shared access

---

## 📊 Comparison Table

| Feature | ngrok | Azure | In-Notebook |
|---------|-------|-------|-------------|
| **Setup Time** | 2 min | 15 min | 1 min |
| **Monthly Cost** | Free | $10-30 | Free |
| **URL Stability** | Changes | Static | N/A |
| **Team Access** | No | Yes | No |
| **Availability** | Depends on you | 99.95% SLA | Per notebook |
| **Performance** | Good | Excellent | Good |
| **Security** | Basic | Enterprise | Notebook-level |
| **Monitoring** | ngrok UI | Azure Monitor | None |
| **Scalability** | 1 user | Auto-scale | 1 notebook |

---

## 🔐 Security Best Practices

### All Options
1. **Never hardcode credentials** in notebooks or code
2. Use **HTTPS only** (all options support it)
3. **Rotate secrets** regularly

### ngrok Specific
```bash
# Add authentication
ngrok http 8000 --basic-auth "user:password"
```

### Azure Specific
```bash
# Use Managed Identity instead of secrets
az containerapp identity assign --system-assigned

# Store secrets in Key Vault
az keyvault secret set --vault-name kv --name kusto-secret --value $SECRET
```

### In-Notebook Specific
```python
# Always use Fabric Key Vault
from notebookutils import mssparkutils
secret = mssparkutils.credentials.getSecret("keyvault", "secret-name")

# NEVER do this:
# os.environ["SECRET"] = "hardcoded-value"  ❌ WRONG!
```

---

## 🚀 Quick Start

### For Impatient Developers
```python
# 1. Install package
%pip install fabric-spark-advisor

# 2. Pick your poison:

# A) ngrok (if server + tunnel running locally)
from fabric_spark_advisor import SparkAdvisor
advisor = SparkAdvisor("https://abc123.ngrok-free.app")
advisor.launch()

# B) Azure (if deployed)
from fabric_spark_advisor import SparkAdvisor
advisor = SparkAdvisor("https://spark-advisor.eastus.azurecontainerapps.io")
advisor.launch()

# C) In-notebook (if creds configured)
from fabric_spark_advisor import LocalSparkAdvisor
advisor = LocalSparkAdvisor()
advisor.launch_ui()
```

---

## 📚 Next Steps

1. **Choose deployment option** using decision matrix above
2. **Follow setup guide:**
   - ngrok: `deployment/ngrok-tunnel-setup.md`
   - Azure: `deployment/azure-container-apps-deploy.md`
   - In-Notebook: `deployment/in-notebook-server.md`
3. **Try example notebook:** `examples/fabric-notebook-deployment-guide.ipynb`
4. **Analyze Spark apps!** 🎉

---

## 💡 Pro Tips

### Hybrid Approach (Recommended)
1. **Development:** Use ngrok (fast iteration)
2. **Staging:** Deploy to Azure (test production setup)
3. **Production:** Use Azure (team access)
4. **Demos:** Use in-notebook (no dependencies)

### Cost Optimization
- **Azure:** Use Consumption plan, not dedicated
- **ngrok:** Free tier is fine for dev
- **In-Notebook:** No extra cost beyond Fabric compute

### Performance
- **Azure:** Closest region to Fabric workspace
- **ngrok:** Wired connection > WiFi
- **In-Notebook:** Larger Fabric pool = faster init

---

## ❓ FAQ

**Q: Can I use localhost from Fabric notebook?**  
A: No. Fabric notebooks run in Azure cloud, not your machine.

**Q: Which is fastest?**  
A: Azure (dedicated server). In-notebook has startup overhead.

**Q: Which is cheapest?**  
A: ngrok or in-notebook (both free).

**Q: Which is most reliable?**  
A: Azure Container Apps (99.95% SLA).

**Q: Can I switch between options?**  
A: Yes! Just change the `mcp_server_url` or use `LocalSparkAdvisor`.

**Q: Do I need Docker for ngrok?**  
A: No. Only Azure deployment needs Docker.

---

## 🐛 Troubleshooting

### ngrok: "Tunnel not found"
- **Solution:** Restart ngrok tunnel

### Azure: "502 Bad Gateway"
- **Solution:** Check container logs: `az containerapp logs show --follow`

### In-Notebook: "Missing environment variables"
- **Solution:** Set all required vars from Key Vault (see error message)

### All: "Connection refused"
- **Solution:** Verify server is running, check firewall, test URL in browser

---

## 📞 Support

- **Issues:** https://github.com/your-repo/issues
- **Docs:** This repo's `/deployment/` folder
- **Examples:** `/fabric_spark_advisor/examples/`
