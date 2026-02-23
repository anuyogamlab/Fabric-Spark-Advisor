# Run MCP Server Inside Fabric Notebook

## Overview
Start the MCP server directly inside the Fabric notebook, eliminating external dependencies. Server runs on notebook's localhost.

---

## Approach 1: Lightweight Server (Recommended)

Package the essentials (Kusto client, RAG, Orchestrator) without full MCP server overhead.

### Updated Wheel Package

```python
# fabric_spark_advisor/local_server.py
"""
Lightweight local server that runs in-notebook.
No MCP overhead - direct Python API.
"""
from agent.orchestrator import SparkOrchestrator
from rag.retriever import AzureSearchRetriever
from tools.kusto_connector import KustoClient
import os


class LocalSparkAdvisor:
    """
    In-notebook Spark Advisor - No external server needed.
    
    Automatically connects to Kusto/RAG/OpenAI using environment variables.
    """
    
    def __init__(self, session_id: str = "notebook"):
        # Initialize Kusto
        self.kusto_client = KustoClient(
            cluster_url=os.getenv("KUSTO_CLUSTER_URL"),
            database=os.getenv("KUSTO_DATABASE"),
            client_id=os.getenv("KUSTO_CLIENT_ID"),
            client_secret=os.getenv("KUSTO_CLIENT_SECRET"),
            tenant_id=os.getenv("KUSTO_TENANT_ID")
        )
        
        # Initialize RAG
        self.rag_retriever = AzureSearchRetriever(
            endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            api_key=os.getenv("AZURE_SEARCH_KEY"),
            index_name=os.getenv("AZURE_SEARCH_INDEX", "spark-docs")
        )
        
        # Initialize Orchestrator
        self.orchestrator = SparkOrchestrator(
            kusto_client=self.kusto_client,
            retriever=self.rag_retriever,
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_openai_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        )
        
        self.session_id = session_id
    
    async def analyze_application(self, app_id: str):
        """Analyze a Spark application."""
        return await self.orchestrator.analyze_application(app_id, self.session_id)
    
    async def analyze_skew(self, app_id: str):
        """Analyze task/shuffle skew."""
        return await self.orchestrator.analyze_skew(app_id, self.session_id)
    
    async def analyze_scaling(self, app_id: str):
        """Analyze scaling impact."""
        return await self.orchestrator.analyze_scaling_impact(app_id, self.session_id)
    
    async def chat(self, message: str):
        """Free-form chat."""
        return await self.orchestrator.chat(message, self.session_id)
    
    def launch_ui(self):
        """Launch Gradio UI."""
        from .ui.gradio_app import create_gradio_interface
        interface = create_gradio_interface(self.orchestrator, self.session_id)
        return interface.launch(inline=True, share=False)
```

---

## Approach 2: Full MCP Server (Advanced)

Run the actual FastMCP server in a background thread.

```python
# fabric_spark_advisor/embedded_server.py
"""
Embedded MCP server for notebook environments.
Runs FastMCP in background thread.
"""
import asyncio
import threading
from typing import Optional
from mcp_server.spark_mcp_server import create_mcp_server
import uvicorn


class EmbeddedMCPServer:
    """
    MCP server that runs in a background thread within the notebook.
    """
    
    def __init__(self, port: int = 8000):
        self.port = port
        self.server_thread: Optional[threading.Thread] = None
        self.server_url = f"http://127.0.0.1:{port}"
        self._running = False
    
    def start(self):
        """Start the MCP server in a background thread."""
        if self._running:
            print(f"⚠️ Server already running on {self.server_url}")
            return
        
        def run_server():
            # Create FastMCP server
            app = create_mcp_server()
            
            # Run with uvicorn
            config = uvicorn.Config(
                app,
                host="127.0.0.1",
                port=self.port,
                log_level="warning"
            )
            server = uvicorn.Server(config)
            asyncio.run(server.serve())
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self._running = True
        
        print(f"✅ MCP Server started on {self.server_url}")
        
        # Give server time to start
        import time
        time.sleep(2)
    
    def stop(self):
        """Stop the server (not truly stoppable due to thread limitations)."""
        print("⚠️ Note: Background server will stop when notebook kernel restarts")
```

---

## Usage in Fabric Notebook

### Lightweight Version (Recommended)

```python
# Cell 1: Install package
%pip install fabric-spark-advisor

# Cell 2: Set credentials (using Fabric secrets)
import os

# Option A: From Fabric Key Vault
from notebookutils import mssparkutils
os.environ["KUSTO_CLIENT_ID"] = mssparkutils.credentials.getSecret("keyvault-name", "kusto-client-id")
os.environ["KUSTO_CLIENT_SECRET"] = mssparkutils.credentials.getSecret("keyvault-name", "kusto-client-secret")
os.environ["AZURE_OPENAI_API_KEY"] = mssparkutils.credentials.getSecret("keyvault-name", "openai-key")
# ... set other vars

# Option B: From environment (if pre-configured)
# Credentials already set at workspace level

# Cell 3: Use advisor
from fabric_spark_advisor import LocalSparkAdvisor

advisor = LocalSparkAdvisor()

# Launch UI
advisor.launch_ui()

# Or use programmatically
result = await advisor.analyze_application("application_1771446566369_0001")
print(result)
```

### Full MCP Server Version

```python
# Cell 1: Install package
%pip install fabric-spark-advisor

# Cell 2: Start embedded server
from fabric_spark_advisor import EmbeddedMCPServer, SparkAdvisor

# Start server in background
server = EmbeddedMCPServer(port=8000)
server.start()

# Cell 3: Connect to embedded server
advisor = SparkAdvisor(mcp_server_url="http://127.0.0.1:8000")
advisor.launch()
```

---

## Pros & Cons

### Lightweight (LocalSparkAdvisor)
✅ **Pros:**
- No server overhead
- Simpler dependency chain
- Faster initialization
- Direct API access

❌ **Cons:**
- Duplicates orchestrator code
- No multi-client support
- Harder to update

### Embedded MCP Server
✅ **Pros:**
- Same code as web UI
- True M+N architecture
- Can serve multiple notebook cells

❌ **Cons:**
- Higher memory usage
- Threading complexity
- Harder to debug

---

## Recommended: Hybrid Approach

1. **Development:** Use ngrok tunnel (fastest iteration)
2. **Production:** Deploy to Azure Container Apps (reliable, scalable)
3. **Offline/Demos:** Use LocalSparkAdvisor (no dependencies)

---

## Security Note

When running in Fabric notebooks, credentials are automatically available via:
- **Managed Identity**: Best for Kusto/Storage/Key Vault
- **Key Vault**: Store OpenAI keys, client secrets
- **Environment Variables**: Set at workspace level

Never hardcode secrets in notebooks!
