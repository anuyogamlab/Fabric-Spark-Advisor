# 🚀 Spark Recommender Agent

AI-powered Apache Spark optimization assistant for Microsoft Fabric, powered by:
- **MCP (Model Context Protocol)** for tool integration
- **Azure OpenAI GPT-4o** for intelligent recommendations
- **Azure AI Search** for RAG documentation retrieval
- **Azure Kusto** for telemetry analysis
- **Semantic Kernel** for agent orchestration
- **Chainlit** for interactive chat UI

## 📐 Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACES                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐     │
│  │  Chainlit UI     │  │  VS Code Agent   │  │  Fabric Notebook │     │
│  │  (Port 8501)     │  │  (Copilot Chat)  │  │  (Python)        │     │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘     │
│           │                     │                     │                 │
│           └─────────────────────┼─────────────────────┘                 │
│                                 │                                       │
└─────────────────────────────────┼───────────────────────────────────────┘
                                  │
┌─────────────────────────────────┼───────────────────────────────────────┐
│                    ORCHESTRATION LAYER                                  │
├─────────────────────────────────┼───────────────────────────────────────┤
│                                 ▼                                       │
│                  ┌──────────────────────────────┐                       │
│                  │  SparkAdvisorOrchestrator    │                       │
│                  │  (Semantic Kernel)           │                       │
│                  └──────────────┬───────────────┘                       │
│                                 │                                       │
│           ┌─────────────────────┼─────────────────────┐                 │
│           │                     │                     │                 │
│           ▼                     ▼                     ▼                 │
│  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐         │
│  │  MCP Tools     │   │  RAG System    │   │  LLM Judge     │         │
│  │  (5 tools)     │   │  (AI Search)   │   │  (GPT-4o)      │         │
│  └────────┬───────┘   └────────┬───────┘   └────────┬───────┘         │
│           │                     │                     │                 │
└───────────┼─────────────────────┼─────────────────────┼─────────────────┘
            │                     │                     │
┌───────────┼─────────────────────┼─────────────────────┼─────────────────┐
│                          DATA SOURCES                                   │
├───────────┼─────────────────────┼─────────────────────┼─────────────────┤
│           ▼                     ▼                     ▼                 │
│  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐         │
│  │ Azure Kusto    │   │ Azure AI Search│   │ Azure OpenAI   │         │
│  │ (Eventhouse)   │   │ (spark-docs)   │   │ (GPT-4o)       │         │
│  │                │   │                │   │                │         │
│  │ • Sparklens    │   │ • 5 Fabric     │   │ • Validation   │         │
│  │ • Fabric recs  │   │   Spark docs   │   │ • Generation   │         │
│  │ • App summary  │   │ • Category     │   │ • Reasoning    │         │
│  │ • Bad practices│   │   filtering    │   │                │         │
│  └────────────────┘   └────────────────┘   └────────────────┘         │
└─────────────────────────────────────────────────────────────────────────┘

                          DATA FLOW
                          
User Query → Intent Detection → Orchestrator
                                    ↓
          ┌─────────────────────────┼──────────────────────┐
          ▼                         ▼                      ▼
    Kusto Query               RAG Search              LLM Fallback
    (telemetry)              (documentation)         (generation)
          │                         │                      │
          └─────────────────────────┼──────────────────────┘
                                    ▼
                              LLM Judge
                            (validation)
                                    ▼
                          Validated Results
                                    ▼
                          User (formatted)
```

## 🚦 Quick Start

### 1️⃣ Install Dependencies

```bash
# Clone the repository
git clone <your-repo>
cd spark-recommender

# Install Python dependencies
pip install -r requirements.txt

# Or use conda
conda env create -f environment.yml
conda activate spark-recommender
```

### 2️⃣ Configure Environment

```bash
# Copy example .env file
cp .env.example .env

# Edit .env with your credentials
# Required:
#   - AZURE_OPENAI_ENDPOINT
#   - AZURE_OPENAI_API_KEY
#   - AZURE_OPENAI_DEPLOYMENT (e.g., gpt-4o)
#   - KUSTO_CLUSTER_URI
#   - KUSTO_DATABASE
#   - AZURE_SEARCH_ENDPOINT
#   - AZURE_SEARCH_KEY
#   - AZURE_SEARCH_INDEX
```

**Example .env:**
```bash
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4o

KUSTO_CLUSTER_URI=https://your-cluster.kusto.windows.net
KUSTO_DATABASE=SparkMonitoring

AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_KEY=your-key-here
AZURE_SEARCH_INDEX=spark-docs-index
```

### 3️⃣ Index Documentation (First Time Only)

```bash
# Index Fabric Spark documentation into Azure AI Search
python rag/indexer.py
```

This indexes 5 Microsoft Fabric Spark documentation files with category metadata.

### 4️⃣ Run the Application

```bash
# Start both MCP server and Chainlit UI
python run.py
```

**This starts:**
- 📡 **MCP Server** on http://127.0.0.1:8000 (SSE protocol)
- 🎨 **Chainlit UI** on http://localhost:8501

**Then open:** http://localhost:8501

## 💻 Usage

### Chainlit UI

The chat interface supports natural language queries:

**Analyze a specific application:**
```
analyze application_1771438258399_0001
```

**Find problematic applications:**
```
show bad apps
show driver heavy jobs
show memory intensive apps
```

**Find healthy applications:**
```
show well optimized apps
show apps that follow best practices
```

**Ask general questions:**
```
what causes high GC overhead?
how do I fix shuffle spill?
what is VOrder in Fabric?
```

### VS Code Agent Mode (GitHub Copilot)

The MCP server can be used directly in VS Code with GitHub Copilot Chat.

**Setup:**

1. MCP configuration is already in `.vscode/settings.json`
2. Restart VS Code
3. Open Copilot Chat
4. MCP tools are automatically available

**Available MCP Tools:**

1. `get_sparklens_recommendations(application_id)` - Sparklens analysis
2. `get_fabric_recommendations(application_id)` - Fabric-specific recommendations
3. `get_application_summary(application_id)` - Application metrics
4. `get_bad_practice_applications(min_violations)` - Apps with issues
5. `search_recommendations_by_category(category)` - Search by category

**Usage in Copilot Chat:**

```
@workspace Get Sparklens recommendations for application_12345

@workspace Find applications with at least 5 bad practices

@workspace Search for performance recommendations
```

### Python API

Use the orchestrator directly in your Python code:

```python
import asyncio
from agent.orchestrator import SparkAdvisorOrchestrator

async def main():
    orchestrator = SparkAdvisorOrchestrator()
    
    # Analyze an application
    result = await orchestrator.analyze_application("application_12345")
    print(f"Health: {result['overall_health']}")
    print(f"Recommendations: {len(result['validated_recommendations'])}")
    
    # Find bad applications
    bad_apps = orchestrator.find_bad_applications(min_violations=3)
    print(f"Found {len(bad_apps)} problematic applications")
    
    # Find driver-heavy apps
    driver_heavy = orchestrator.find_applications_by_pattern("driver_heavy")
    
    # Find healthy apps
    healthy = orchestrator.find_healthy_applications(min_score=80)

asyncio.run(main())
```

### Fabric Notebook

**Two ready-to-use notebooks for interactive Spark optimization:**

#### 🎯 Interactive UI Notebook (Recommended)
Full-featured chat interface with ipywidgets, feedback buttons, and rich formatting:

```python
# Open in Fabric: notebooks/FabricSparkAdvisor_Interactive.ipynb
# Features:
# - Interactive chat UI with back-and-forth conversations
# - Professional FSA branding and card layouts
# - Clickable feedback buttons (✅ Helpful, ❌ Not Helpful, ⚠️ Partial)
# - Real-time Kusto queries with rich visualizations
# - Session history and statistics
```

#### ⚡ Quick Start Notebook (Lightweight)
Simple function-based interface for fast queries:

```python
# Open in Fabric: notebooks/FabricSparkAdvisor_QuickStart.ipynb
# Features:
# - Lightweight, fast execution
# - Simple ask() function for queries
# - Direct Kusto query examples
# - Programmatic API access
```

**Installation in Fabric:**
1. Go to your Fabric workspace
2. Click **New** → **Import notebook**
3. Upload from `notebooks/` directory
4. Run Cell 1 to install dependencies:
   ```python
   %pip install ipywidgets pandas azure-kusto-data azure-kusto-ingest python-dotenv
   ```
5. Configure credentials (use Fabric secrets or environment variables)
6. Execute all cells to launch interactive UI

**See [notebooks/README.md](notebooks/README.md) for detailed setup instructions and examples.**

## 📦 Components

### MCP Server (`mcp_server/`)

FastMCP server exposing 5 tools for Spark analysis:
- **Port**: 8000
- **Protocol**: SSE (Server-Sent Events)
- **Tools**: 5 Kusto-backed tools
- **Config**: `.vscode/settings.json`

**Run standalone:**
```bash
python mcp_server/server.py
```

### Orchestrator (`agent/orchestrator.py`)

Semantic Kernel-based agent coordinating the full pipeline:
- Integrates MCP tools, RAG, LLM, and Judge
- 3 main methods:
  - `analyze_application(app_id)` - Full analysis pipeline
  - `find_bad_applications(min_violations)` - Find problematic apps
  - `chat(message)` - Conversational interface

### RAG System (`rag/`)

Azure AI Search-based documentation retrieval:
- **5 indexed documents** from Microsoft Learn
- **Category filtering**: performance, configuration, delta, maintenance
- **Metadata enrichment**: source URLs, categories

**Re-index:**
```bash
python rag/indexer.py
```

**Test retrieval:**
```bash
python examples/test_rag.py
```

### LLM Judge (`agent/judge.py`)

Azure OpenAI-based recommendation validator:
- **Structured output** using JSON Schema strict mode
- **Confidence scoring**: HIGH, MEDIUM, LOW
- **Contradiction detection** between recommendations
- **Priority assignment** (1-40 scale)
- **Fallback mode** when LLM unavailable

**Test judge:**
```bash
python examples/judge_demo.py
```

### UI (`ui/app.py`)

Chainlit chat interface:
- **7 intent types** with automatic detection
- **5 response formatters** for different views
- **Session tracking** with live stats
- **Follow-up actions** as clickable buttons
- **Quick-start actions** on launch

## 🧪 Testing & Demos

### Run All Demos

```bash
# Test MCP tools
python examples/test_tools.py

# Test RAG retrieval
python examples/test_rag.py

# Test LLM judge
python examples/judge_demo.py

# Test orchestrator
python examples/orchestrator_demo.py
```

### Individual Tests

```bash
# Test Kusto connection and queries
python mcp_server/kusto_client.py

# Test judge with real data
python agent/judge.py

# Test RAG search
python rag/retriever.py
```

## 🐳 Docker Deployment

Build and run with Docker:

```bash
# Build image
docker build -t spark-recommender .

# Run container
docker run -p 8000:8000 -p 8501:8501 \
  --env-file .env \
  spark-recommender
```

Deploy to Azure Container Apps:

```bash
# Build and push
az acr build --registry <your-acr> \
  --image spark-recommender:latest .

# Deploy to Container Apps
az containerapp create \
  --name spark-recommender \
  --resource-group <your-rg> \
  --environment <your-env> \
  --image <your-acr>.azurecr.io/spark-recommender:latest \
  --target-port 8501 \
  --ingress external \
  --env-vars-file .env
```

## 📁 Project Structure

```
spark-recommender/
├── agent/                      # Orchestrator & Judge
│   ├── orchestrator.py        # Main orchestration agent
│   ├── judge.py               # LLM recommendation validator
│   ├── prompts.py             # System prompts
│   ├── JUDGE_README.md        # Judge documentation
│   └── ORCHESTRATOR_README.md # Orchestrator docs
├── mcp_server/                # MCP Server
│   ├── server.py              # FastMCP server (5 tools)
│   ├── kusto_client.py        # Kusto/Eventhouse client
│   └── __init__.py
├── rag/                       # RAG System
│   ├── indexer.py             # Index docs to AI Search
│   ├── retriever.py           # Search & retrieve docs
│   ├── docs/                  # Markdown documentation
│   │   ├── *.md              # 5 Fabric Spark docs
│   │   └── metadata.json     # Doc metadata
│   └── README.md
├── ui/                        # Chainlit UI
│   ├── app.py                 # Chat interface
│   └── README.md              # UI documentation
├── examples/                  # Demos & Tests
│   ├── test_tools.py          # Test MCP tools
│   ├── test_rag.py            # Test RAG retrieval
│   ├── judge_demo.py          # Test LLM judge
│   └── orchestrator_demo.py   # Test orchestrator
├── .vscode/
│   └── settings.json          # MCP configuration for VS Code
├── run.py                     # Main startup script
├── Dockerfile                 # Container image
├── requirements.txt           # Python dependencies
├── .env.example               # Example environment config
├── .env                       # Your credentials (gitignored)
└── README.md                  # This file
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint | `https://your.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | API key | `abc123...` |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name | `gpt-4o` |
| `KUSTO_CLUSTER_URI` | Kusto cluster URL | `https://cluster.kusto.windows.net` |
| `KUSTO_DATABASE` | Database name | `SparkMonitoring` |
| `AZURE_SEARCH_ENDPOINT` | AI Search endpoint | `https://search.search.windows.net` |
| `AZURE_SEARCH_KEY` | Search API key | `xyz789...` |
| `AZURE_SEARCH_INDEX` | Index name | `spark-docs-index` |

### MCP Server Configuration

Located in `.vscode/settings.json`:

```json
{
  "mcp.servers": {
    "spark-advisor": {
      "command": "python",
      "args": ["mcp_server/server.py"],
      "type": "sse",
      "url": "http://127.0.0.1:8000"
    }
  }
}
```

## 🚨 Troubleshooting

### MCP Server won't start
- Check port 8000 is not in use
- Verify `.env` has Kusto credentials
- Test Kusto connection: `python mcp_server/kusto_client.py`

### Chainlit UI shows errors
- Ensure MCP server is running first
- Check port 8501 is available
- Verify Azure OpenAI credentials: `AZURE_OPENAI_*`

### RAG returns no results
- Re-index documents: `python rag/indexer.py`
- Check `AZURE_SEARCH_*` credentials
- Verify index name matches `.env`

### Judge validation fails
- Check `AZURE_OPENAI_DEPLOYMENT` exists
- Verify API version is `2024-08-01-preview` or later
- Test: `python examples/judge_demo.py`

### Authentication errors
- For Kusto: Use `az login` (Azure CLI credential as fallback)
- For OpenAI: Check API key is valid
- For Search: Regenerate admin key if needed

## 📖 Documentation

Detailed documentation for each component:

- **MCP Server**: `.vscode/settings.json` for configuration
- **Orchestrator**: `agent/ORCHESTRATOR_README.md`
- **Judge**: `agent/JUDGE_README.md`
- **RAG System**: `rag/README.md`
- **UI**: `ui/README.md`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests in `examples/`
5. Submit a pull request

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- **Microsoft Fabric** for Spark runtime and Eventhouse
- **Azure OpenAI** for GPT-4o LLM
- **FastMCP** for MCP server framework
- **Semantic Kernel** for agent orchestration
- **Chainlit** for chat UI framework

---

**Built with ❤️ for the Spark community**

For questions or issues, please open a GitHub issue or contact the maintainers.
