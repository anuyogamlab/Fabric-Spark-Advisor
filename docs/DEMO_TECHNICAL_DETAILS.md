# Spark Advisor Demo — Technical Architecture

## 📋 Executive Summary

**What we built:** An AI-powered Spark performance advisor that combines:
- **Kusto (Eventhouse)** for telemetry data
- **RAG** (Retrieval Augmented Generation) for official documentation
- **LLM Judge** for recommendation validation
- **MCP** (Model Context Protocol) for tool integration
- **Multi-interface access** (Chainlit UI, VS Code Agent, Python API)

---

## 🔧 Technology Stack

### Core Components

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **MCP Server** | FastMCP | 0.2.0 | Exposes Kusto tools to AI agents |
| **Orchestrator** | Semantic Kernel | 1.1.0 | Multi-step agent workflow |
| **LLM** | Azure OpenAI GPT-4o | - | Query generation, analysis, judge |
| **Vector Search** | Azure AI Search | 11.4.0 | RAG document retrieval |
| **Data Layer** | Azure Data Explorer (Kusto) | 4.4.0 | Spark telemetry storage |
| **Web UI** | Chainlit | 1.3.0+ | Interactive chat interface |
| **Auth** | Azure CLI | - | Unified credential provider |

---

## 🏗️ Architecture Layers

### Layer 1: Data Sources (Truth Tier)

```
┌─────────────────────────────────────────────────────────────┐
│  KUSTO EVENTHOUSE (Primary Data Source)                    │
│  ─────────────────────────────────────────────────────────  │
│  Tables:                                                    │
│    • sparklens_metrics        → Performance metrics        │
│    • sparklens_predictions    → Scaling what-if analysis   │
│    • sparklens_recommedations → SparkLens advice           │
│    • fabric_recommedations    → Fabric-specific tips       │
│    • SparkEventLogs           → Spark config (JSON blobs)  │
│                                                             │
│  Query: KQL (Kusto Query Language)                         │
│  Auth: Azure CLI credential                                │
└─────────────────────────────────────────────────────────────┘
```

### Layer 2: MCP Server (Tool Exposure)

```
┌─────────────────────────────────────────────────────────────┐
│  FASTMCP SERVER (spark_mcp_server.py)                      │
│  ─────────────────────────────────────────────────────────  │
│  Protocol: MCP (Model Context Protocol)                    │
│  Transport: stdio (standard input/output)                  │
│  Why stdio? ✓ Simple process-based communication          │
│             ✓ No network ports needed                      │
│             ✓ Perfect for VS Code agent integration        │
│                                                             │
│  Exposed Tools (5):                                        │
│    1. get_sparklens_recommendations(app_id)                │
│    2. get_fabric_recommendations(app_id)                   │
│    3. get_application_summary(app_id)                      │
│    4. get_bad_practice_applications(min_violations)        │
│    5. search_recommendations_by_category(category)         │
│                                                             │
│  Each tool → KQL query → Returns structured JSON          │
└─────────────────────────────────────────────────────────────┘
```

**Why stdio (not HTTP/SSE)?**
- ✅ **VS Code Copilot requires stdio** for MCP server integration
- ✅ **No port conflicts** — no need to manage HTTP ports
- ✅ **Process isolation** — Each client gets dedicated server instance
- ✅ **Security** — No exposed network endpoints
- ❌ Only works for local processes (not remote clients)

### Layer 3: RAG System (Documentation Context)

```
┌─────────────────────────────────────────────────────────────┐
│  AZURE AI SEARCH (RAG Document Store)                      │
│  ─────────────────────────────────────────────────────────  │
│  Index: spark-docs-index                                   │
│  Documents: 4 markdown files                               │
│    • Spark best practices                                  │
│    • Resource profile configurations                       │
│    • Driver mode optimization                              │
│    • Lakehouse table maintenance                           │
│                                                             │
│  Search: Vector + keyword hybrid search                    │
│  Embeddings: text-embedding-ada-002                        │
│  Query: orchestrator.retriever.search(query, top_k=5)      │
└─────────────────────────────────────────────────────────────┘
```

### Layer 4: Agent Orchestrator (Brain)

```
┌─────────────────────────────────────────────────────────────┐
│  SEMANTIC KERNEL ORCHESTRATOR (agent/orchestrator.py)      │
│  ─────────────────────────────────────────────────────────  │
│  Role: Multi-step reasoning agent                          │
│                                                             │
│  Pipeline:                                                  │
│    1. Intent Detection → Pattern matching on user query   │
│    2. Tool Selection   → Pick MCP tools or dynamic query   │
│    3. Data Retrieval   → Execute Kusto queries            │
│    4. RAG Enrichment   → Add documentation context         │
│    5. LLM Generation   → GPT-4o synthesis                  │
│    6. Judge Validation → Verify recommendations            │
│    7. Response Format  → Structured markdown output        │
│                                                             │
│  Key Features:                                             │
│    • Session management (multi-turn conversations)        │
│    • Reference resolution ("show me", "that app")         │
│    • Dynamic KQL generation (LLM generates queries)       │
│    • Feedback loop (stores user ratings)                  │
└─────────────────────────────────────────────────────────────┘
```

### Layer 5: LLM Judge (Quality Gate)

```
┌─────────────────────────────────────────────────────────────┐
│  LLM JUDGE (agent/judge.py)                                │
│  ─────────────────────────────────────────────────────────  │
│  Role: Validate and prioritize recommendations            │
│                                                             │
│  Inputs:                                                    │
│    • Kusto recommendations (sparklens + fabric)           │
│    • RAG documentation snippets                           │
│    • LLM-generated advice (if no Kusto data)              │
│                                                             │
│  Processing:                                               │
│    1. NEVER modify Kusto recommendations (preserve)       │
│    2. Score each recommendation (0-100)                    │
│    3. Assign priority (1=CRITICAL, 30=LOW)                │
│    4. Filter out generic/duplicate advice                  │
│    5. Add confidence scores                                │
│                                                             │
│  Output: validated_recommendations[] sorted by priority   │
└─────────────────────────────────────────────────────────────┘
```

**Critical Rule:** Judge NEVER changes Kusto data — only validates/prioritizes

---

## 🖥️ User Interfaces

### Interface 1: Chainlit Web UI (Primary)

```
┌─────────────────────────────────────────────────────────────┐
│  CHAINLIT UI (ui/app.py)                                   │
│  ─────────────────────────────────────────────────────────  │
│  Port: 8000                                                 │
│  Protocol: WebSocket (not stdio)                           │
│  Launch: chainlit run ui/app.py                            │
│                                                             │
│  Why Chainlit (not Gradio/Streamlit)?                     │
│  ✅ Built for AI chat interfaces (not general dashboards)  │
│  ✅ Async/await native (perfect for Semantic Kernel)       │
│  ✅ Action buttons (feedback: HELPFUL/NOT HELPFUL)         │
│  ✅ Multi-step progress indicators (cl.Step API)           │
│  ✅ Session management built-in                            │
│  ✅ Markdown + HTML rendering (rich formatting)            │
│  ✅ File uploads + integrations                            │
│                                                             │
│  Gradio would require:                                     │
│    • Manual session state handling                         │
│    • Custom async wrappers                                 │
│    • Less polished chat UX                                 │
│                                                             │
│  Streamlit would require:                                  │
│    • Page reloads on every interaction                     │
│    • No true async support                                 │
│    • Chat memory hack via st.session_state                 │
│                                                             │
│  Connection to MCP: INDIRECT                               │
│    Chainlit → orchestrator.py → MCP tools                 │
│    (Does NOT use stdio — direct Python imports)           │
└─────────────────────────────────────────────────────────────┘
```

**Does Chainlit use stdio?** 
- ❌ **No** — Chainlit is a web framework that runs on WebSocket
- It calls `orchestrator.py` directly as Python functions
- The orchestrator then uses MCP tools internally
- Only VS Code agent uses stdio to communicate with MCP server

### Interface 2: VS Code Copilot Agent

```
┌─────────────────────────────────────────────────────────────┐
│  VS CODE COPILOT CHAT                                      │
│  ─────────────────────────────────────────────────────────  │
│  Config: .vscode/settings.json                             │
│  {                                                          │
│    "mcp.servers": {                                        │
│      "spark-advisor": {                                   │
│        "command": "python",                               │
│        "args": ["spark_mcp_server.py"]                   │
│      }                                                     │
│    }                                                       │
│  }                                                         │
│                                                             │
│  Why stdio (not HTTP)?                                    │
│  ✅ VS Code MCP spec requires stdio transport              │
│  ✅ Auto process management (launches/kills server)        │
│  ✅ Isolated per workspace                                 │
│                                                             │
│  Flow:                                                      │
│    User: @workspace analyze app_123                       │
│      ↓                                                      │
│    VS Code Copilot → Launches spark_mcp_server.py         │
│      ↓                                                      │
│    MCP server → Executes KQL query → Returns JSON         │
│      ↓                                                      │
│    Copilot LLM → Formats response → Shows in chat         │
│                                                             │
│  Tools available: Same 5 MCP tools as Chainlit            │
└─────────────────────────────────────────────────────────────┘
```

### Interface 3: Python API

```python
# Direct orchestrator usage (for notebooks, automation)
from agent.orchestrator import SparkAdvisorOrchestrator

async def main():
    orchestrator = SparkAdvisorOrchestrator()
    result = await orchestrator.analyze_application("app_123")
    print(result["summary"])
```

---

## 🔄 Data Flow Example

**User Query:** "Show me apps that took most amount of time"

### Chainlit UI Flow:
```
User Browser
  → WebSocket (port 8000)
    → Chainlit (ui/app.py)
      → detect_intent("most time")
        → orchestrator.chat()
          → Pattern: "most time" → top apps query
            → KQL: sparklens_predictions | where "Current" 
              → Kusto API (Azure CLI auth)
                ← Returns: [{app_id, duration, executors}]
              ← Parse results
            ← Format markdown table
          ← LLM adds context (optional)
        ← Returns response text
      ← Renders in chat UI
    ← WebSocket sends HTML/markdown
  ← Browser displays formatted table
```

### VS Code Agent Flow:
```
User (@workspace query)
  → VS Code Copilot
    → Launches: python spark_mcp_server.py
      → stdio: {"method": "tools/call", "params": {...}}
        → KQL query execution
          → Kusto API
            ← Returns JSON
          ← Formats response
        ← stdio: {"result": {...}}
      → Copilot LLM synthesizes natural language
    ← Shows in chat panel
```

---

## 🎯 Key Technical Decisions

### 1. Why MCP (Model Context Protocol)?

**What is MCP?**
- Open protocol for exposing tools/data to AI agents
- Created by Anthropic, adopted by VS Code, Claude, others
- Alternative to OpenAI function calling (works across LLMs)

**Why we chose it:**
- ✅ **Standardized** — Works with multiple AI clients (not vendor-locked)
- ✅ **Composable** — Can combine multiple MCP servers
- ✅ **Type-safe** — Tools have JSON schema definitions
- ✅ **Discoverable** — Agents can list available tools
- ✅ **VS Code integration** — First-class support in Copilot

**FastMCP specifically:**
- Lightweight Python implementation
- Decorator-based tool registration (`@mcp.tool()`)
- Built-in stdio transport
- Minimal boilerplate

### 2. Why Chainlit for UI?

| Feature | Chainlit | Gradio | Streamlit |
|---------|----------|--------|-----------|
| Chat-first UI | ✅ Native | ⚠️ Custom | ⚠️ Custom |
| Async/await | ✅ Native | ❌ No | ❌ No |
| Streaming responses | ✅ Built-in | ⚠️ Manual | ⚠️ Manual |
| Action buttons | ✅ cl.Action | ⚠️ Manual | ✅ st.button |
| Session management | ✅ cl.user_session | ❌ Manual | ✅ st.session_state |
| Progress steps | ✅ cl.Step | ❌ No | ⚠️ st.spinner |
| HTML rendering | ✅ Full | ⚠️ Limited | ⚠️ Limited |
| File uploads | ✅ Built-in | ✅ Built-in | ✅ Built-in |
| Page reload on interaction | ❌ No | ❌ No | ✅ **Yes** (dealbreaker) |

**Decision:** Chainlit wins for **async-first chat experiences**

### 3. Why stdio for VS Code (not HTTP)?

**Options considered:**

| Transport | Pros | Cons | Use Case |
|-----------|------|------|----------|
| **stdio** | Simple, no ports, VS Code native | Local only | ✅ VS Code agent |
| **SSE (HTTP)** | Remote access, web-friendly | Port management, auth | Chainlit UI |
| **WebSocket** | Bi-directional, real-time | Complex, state management | Future: multi-client |

**Why we use stdio for VS Code:**
- That's what VS Code MCP spec requires
- Auto process lifecycle management
- No CORS/auth complexity

**Why Chainlit doesn't use stdio:**
- It's a web server (needs HTTP/WebSocket)
- Multiple concurrent users
- Stateful connections

### 4. Why Kusto (not SQL/MongoDB)?

| Feature | Kusto | PostgreSQL | MongoDB |
|---------|-------|------------|---------|
| Time-series queries | ✅ Optimized | ⚠️ Slow | ❌ Poor |
| Petabyte scale | ✅ Native | ❌ No | ❌ No |
| Fabric integration | ✅ Built-in | ❌ No | ❌ No |
| KQL language | ✅ Powerful | SQL | JSON queries |
| Summarize/pivot | ✅ Native | ⚠️ Complex | ⚠️ Aggregation framework |

**Decision:** Kusto is **purpose-built for Spark telemetry analytics**

---

## 📊 Demo Flow Recommendation

### Part 1: Architecture Overview (5 min)
1. Show architecture diagram (5 layers)
2. Explain data flow: Kusto → MCP → Orchestrator → UI
3. Highlight key tech: FastMCP, Semantic Kernel, Chainlit

### Part 2: Chainlit UI Demo (10 min)
1. **Query 1:** "Show me apps that took most amount of time"
   - Show: Intent detection, Kusto query, formatted results
   - Highlight: Numeric sorting fix (1.0x Current row, duration parsing)

2. **Query 2:** "Analyze application_1771441543262_0001"
   - Show: Progress steps (📊 Fetching Kusto → 📚 RAG → 🤖 LLM)
   - Highlight: 3-tier output (Kusto ✅ → RAG 📚 → LLM ⚠️)

3. **Query 3:** "How many executor cores did app_XXX run with?"
   - Show: JSON parsing from SparkEventLogs
   - Highlight: Fixed column names (AppId, PropertiesJson)

4. **Feedback:** Click "HELPFUL" button
   - Show: Feedback stored for future ranking

### Part 3: VS Code Agent Demo (5 min)
1. Open VS Code Copilot Chat
2. Type: `@workspace analyze application_1771441543262_0001`
3. Show: MCP server auto-starts (stdio)
4. Show: Same tools, different interface

### Part 4: Technical Deep Dive (10 min)
1. **Show code:** `spark_mcp_server.py`
   - FastMCP decorator: `@mcp_server.tool()`
   - KQL query generation
   - JSON response structure

2. **Show code:** `agent/orchestrator.py`
   - Intent detection logic
   - Dynamic query generation (LLM creates KQL)
   - Judge validation pipeline

3. **Show code:** `.vscode/settings.json`
   - MCP configuration
   - stdio vs HTTP difference

### Part 5: Q&A Topics
- "Can we add more MCP tools?" → Yes, decorator pattern
- "Can we use other LLMs?" → Yes, Semantic Kernel abstraction
- "Can we deploy Chainlit to production?" → Yes, Docker + Azure Container Apps
- "How do we add more RAG docs?" → Run `rag/indexer.py`

---

## 🚀 Key Takeaways for Your Audience

1. **MCP is a game-changer** for building AI agents
   - Standardized tool protocol
   - Works across multiple AI platforms
   - Easy to extend (just add `@mcp.tool()`)

2. **Semantic Kernel** provides enterprise-grade orchestration
   - Multi-step reasoning
   - Session management
   - Pluggable LLMs

3. **Chainlit** is the best choice for AI chat UIs
   - Async-first (unlike Streamlit)
   - Chat-native (unlike Gradio)
   - Production-ready

4. **Kusto + RAG + LLM Judge** ensures quality
   - Tier 1: Ground truth (Kusto) — never modified
   - Tier 2: Official docs (RAG) — adds context
   - Tier 3: LLM fallback — clearly labeled

5. **Multi-interface support** maximizes reach
   - Analysts → Chainlit web UI
   - Developers → VS Code agent
   - Automation → Python API

---

## 📁 File Reference for Demo

**Core files to show:**
- `spark_mcp_server.py` — MCP tool definitions (150 lines)
- `agent/orchestrator.py` — Intent detection + orchestration (1800 lines)
- `agent/judge.py` — LLM validation logic (400 lines)
- `ui/app.py` — Chainlit interface (2000 lines)
- `.vscode/settings.json` — VS Code MCP config (5 lines)

**Key features to demo:**
- Typo tolerance: "analyz" works (fuzzy matching)
- Progress indicators: cl.Step API shows real-time status
- Feedback buttons: HELPFUL/NOT HELPFUL/PARTIAL
- Multi-source display: Kusto ✅ | RAG 📚 | LLM ⚠️

---

Good luck with your demo! 🎤
