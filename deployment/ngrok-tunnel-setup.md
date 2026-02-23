# Use ngrok Tunnel for Fabric Notebook Development

## Overview
Expose your local MCP server to the internet using ngrok, allowing Fabric notebooks to connect during development.

---

## Prerequisites
- Local MCP server running on `http://127.0.0.1:8000`
- ngrok account (free tier works): https://ngrok.com/

---

## Step 1: Install ngrok

### Windows (PowerShell)
```powershell
# Using Chocolatey
choco install ngrok

# Or download from https://ngrok.com/download
```

### macOS
```bash
brew install ngrok
```

### Linux
```bash
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok
```

---

## Step 2: Configure ngrok

```bash
# Get your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
ngrok config add-authtoken YOUR_AUTHTOKEN
```

---

## Step 3: Start Local MCP Server

```powershell
# Terminal 1: Start MCP server locally
cd "c:\Users\anuve\OneDrive - Microsoft\Documents\Spark Recommender MCP"
python spark_mcp_server.py
```

Server should be running on `http://127.0.0.1:8000`

---

## Step 4: Create ngrok Tunnel

```powershell
# Terminal 2: Expose port 8000 to the internet
ngrok http 8000
```

You'll see output like:
```
Session Status                online
Account                       Your Name (Plan: Free)
Version                       3.5.0
Region                        United States (us)
Latency                       -
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://abc123def456.ngrok-free.app -> http://localhost:8000

Connections                   ttl     opn     rt1     rt5     p50     p90
                              0       0       0.00    0.00    0.00    0.00
```

**Copy the Forwarding URL** (e.g., `https://abc123def456.ngrok-free.app`)

---

## Step 5: Use in Fabric Notebook

```python
# In Fabric notebook
%pip install fabric-spark-advisor

from fabric_spark_advisor import SparkAdvisor

# Connect to ngrok tunnel URL
advisor = SparkAdvisor(
    mcp_server_url="https://abc123def456.ngrok-free.app"
)

advisor.launch()
```

---

## Pro Tips

### 1. **Use Static Domain** (ngrok Pro/Team only)
```bash
ngrok http 8000 --domain=spark-advisor.ngrok.io
```

### 2. **Add Authentication** (recommended for security)
```bash
ngrok http 8000 --basic-auth "username:password"
```

Then in notebook:
```python
advisor = SparkAdvisor(
    mcp_server_url="https://abc123def456.ngrok-free.app",
    headers={"Authorization": "Basic dXNlcm5hbWU6cGFzc3dvcmQ="}  # base64 encoded
)
```

### 3. **Monitor Requests**
Visit http://127.0.0.1:4040 to see all HTTP requests in real-time

### 4. **Keep Tunnel Alive**
```bash
# Run in background (Windows)
Start-Process -NoNewWindow ngrok http 8000

# Linux/Mac
nohup ngrok http 8000 &
```

---

## Limitations (Free Tier)

- ⚠️ **URL changes every restart** - Need to update notebook each time
- ⚠️ **40 connections/minute limit**
- ⚠️ **Max 1 tunnel** at a time
- ✅ **Good for:** Development, demos, testing
- ❌ **Not for:** Production, team usage

**Upgrade to ngrok Pro ($8/month)** for:
- Static domains
- Multiple tunnels
- No connection limits
- Custom branding

---

## Alternative: VS Code Port Forwarding

If you use VS Code with GitHub account:

1. Run server locally
2. In VS Code: `Ports` tab → Forward port 8000
3. Set visibility to "Public"
4. Get URL like: `https://abc123-8000.app.github.dev`

**Pros:** Free, built into VS Code  
**Cons:** Requires VS Code running, GitHub connection

---

## Troubleshooting

### Issue: "ERR_NGROK_3200: Tunnel not found"
**Solution:** Restart ngrok tunnel

### Issue: "429 Too Many Requests"
**Solution:** Wait 1 minute (free tier rate limit)

### Issue: Notebook can't connect
**Solution:** Check firewall, verify ngrok is running, test URL in browser
