# Fabric Spark Advisor 🔥

AI-powered Spark performance analysis for Microsoft Fabric workloads.

Clean notebook interface with **expert-defined rules** + **LLM orchestration** + **unified M+N architecture** via MCP.

---

## Why This Design?

```
┌─────────────────────────────────────────────────┐
│  YOUR DATA FIRST → EXPERT RULES → OFFICIAL DOCS │
│  LLM validates and orchestrates (doesn't guess) │
└─────────────────────────────────────────────────┘
```

**Key differentiator:** Recommendations come from performance engineering expertise encoded in SparkLens heuristics, not AI hallucination.

---

## Features

✅ **3-Tier Validation**
- **TIER 1:** Kusto telemetry (ground truth)
- **TIER 2:** Official Microsoft docs (RAG)
- **TIER 3:** LLM fallback (only when needed)

✅ **Specialized Analysis**
- Skew detection (task/shuffle imbalance)
- Scaling impact (should you add executors?)
- Driver bottleneck detection
- Memory pressure analysis

✅ **M+N Architecture**
- Single MCP server → Multiple consumers (web UI, notebook, CLI)
- No M×N integration explosion
- Linear scaling, not quadratic

---

## Installation

### From PyPI (when published)
```bash
pip install fabric-spark-advisor
```

### From Source
```bash
git clone https://github.com/microsoft/fabric-spark-advisor
cd fabric-spark-advisor/fabric_spark_advisor
pip install -e .
```

---

## Quick Start

### ⚡ Option 1: ngrok Tunnel (Dev/Testing)

```python
# On your machine: ngrok http 8000
# Then in Fabric notebook:

from fabric_spark_advisor import SparkAdvisor

advisor = SparkAdvisor(
    mcp_server_url="https://abc123.ngrok-free.app"  # Your ngrok URL
)
advisor.launch()
```

### ☁️ Option 2: Azure Container Apps (Production)

```python
# After deploying to Azure (see deployment/azure-container-apps-deploy.md)

from fabric_spark_advisor import SparkAdvisor

advisor = SparkAdvisor(
    mcp_server_url="https://spark-advisor.eastus.azurecontainerapps.io"
)
advisor.launch()
```

### 📓 Option 3: In-Notebook (Self-Contained)

```python
# Set credentials from Fabric Key Vault first
import os
from notebookutils import mssparkutils

os.environ["KUSTO_CLUSTER_URL"] = mssparkutils.credentials.getSecret("kv", "kusto-url")
# ... set other creds

from fabric_spark_advisor import LocalSparkAdvisor

advisor = LocalSparkAdvisor()
advisor.launch_ui()
```

**See `examples/fabric-notebook-deployment-guide.ipynb` for complete examples!**

That's it! 🎉 Just **3 lines of code** in your notebook.

---

## Usage Examples

### Interactive Chat Interface

```python
advisor.launch()
```

Then ask questions:
- `analyze application_1771438258399_0001`
- `are there any skews in this application`
- `will adding more executors help`
- `show applications with bad practices`

### Programmatic API

```python
# Analyze application
result = await advisor.analyze_application("application_123")

# Check scaling impact
scaling = await advisor.analyze_scaling("application_123")

# Detect skew
skew = await advisor.analyze_skew("application_123")

# Natural language query
response = await advisor.query("show recent apps")
```

---

## Architecture

```
┌──────────────────┐
│  Fabric Notebook │  ← 3-line interface
└────────┬─────────┘
         │
         ▼
┌────────────────────────────────┐
│  Wheel Package                 │
│  (fabric-spark-advisor)        │
│                                │
│  ├── MCP Client (HTTP)         │
│  ├── Gradio UI (all UX code)   │
│  ├── Formatters (same as web)  │
│  └── Intent detection          │
└────────┬───────────────────────┘
         │
         ▼
┌────────────────────────────────┐
│  MCP Server (localhost:8000)   │
│  Unified tool routing (M+N)    │
└────────────────────────────────┘
```

**Benefits:**
- ✅ No UX code in notebooks
- ✅ Same MCP server for web + notebook + CLI
- ✅ Consistent formatting across all interfaces
- ✅ Expert rules + official docs + LLM orchestration

---

## Configuration

### Custom MCP Server URL
```python
advisor = SparkAdvisor(
    mcp_server_url="http://custom-host:8080"
)
```

### UI Customization
```python
advisor.launch(
    inline=True,          # Show inline in notebook
    share=False,          # Create public link
    server_port=7860,     # Custom port
    height=800            # Chat interface height
)
```

### Session Management
```python
advisor = SparkAdvisor(
    session_id="my-session-id"  # Track across restarts
)
```

---

## Development

### Project Structure
```
fabric_spark_advisor/
├── __init__.py              # Package entry point
├── advisor.py               # Main SparkAdvisor class
├── client/
│   └── mcp_client.py        # MCP HTTP client
├── ui/
│   ├── gradio_app.py        # Gradio interface
│   ├── formatters.py        # Response formatters
│   └── intent.py            # Intent detection
└── setup.py
```

### Run Tests
```bash
pytest tests/
```

### Build Wheel
```bash
python -m build
```

---

## Comparison: Just LLM vs This Design

| Aspect | Just LLM | Fabric Spark Advisor |
|--------|----------|---------------------|
| Data source | Training data (stale) | Live Kusto telemetry |
| Recommendations | Generic guesses | Expert-defined rules |
| Validation | None | 3-tier (Kusto → RAG → LLM) |
| Scalability | M×N integrations | M+N via MCP |
| Cost | High (every query = LLM call) | Low (LLM fallback only) |
| Accuracy | Prone to hallucination | Data-driven + verified |

**Key Point:** We use LLM to **orchestrate** expert knowledge, not replace it.

---

## Troubleshooting

### MCP Server Not Running
```
Error: Failed to call MCP tool: Connection refused
```
**Fix:** Start MCP server first:
```bash
python spark_mcp_server.py
```

### Application Not Found
```
Error: No data found for application_123
```
**Fix:** Verify app ID format:
```python
# Correct format
advisor.analyze_application("application_1771438258399_0001")
```

### Gradio Won't Launch in Notebook
**Fix:** Ensure you're in a notebook environment (Jupyter, VS Code, Fabric):
```python
advisor.launch(inline=True)  # Force inline display
```

---

## License

MIT License - see LICENSE file for details

---

## Contributing

Contributions welcome! Please:
1. Fork the repo
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## Support

- **Issues:** https://github.com/microsoft/fabric-spark-advisor/issues
- **Docs:** https://github.com/microsoft/fabric-spark-advisor/README.md

---

Built with ❤️ by Microsoft
