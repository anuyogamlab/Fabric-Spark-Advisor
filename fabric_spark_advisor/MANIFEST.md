# Fabric Spark Advisor - Package Manifest

## 📦 Complete Package Structure

```
fabric_spark_advisor/
├── fabric_spark_advisor/          # Main package
│   ├── __init__.py                # Package entry point
│   ├── advisor.py                 # SparkAdvisor main class
│   │
│   ├── client/                    # MCP client module
│   │   ├── __init__.py
│   │   └── mcp_client.py          # HTTP client for MCP server
│   │
│   ├── ui/                        # User interface module
│   │   ├── __init__.py
│   │   ├── gradio_app.py          # Gradio chat interface
│   │   ├── formatters.py          # Response formatting (HTML/Markdown)
│   │   └── intent.py              # Intent detection & app ID extraction
│   │
│   └── core/                      # Core utilities (future)
│       └── __init__.py
│
├── examples/                      # Example notebooks
│   └── quickstart.ipynb           # Getting started guide
│
├── tests/                         # Test suite (future)
│   ├── __init__.py
│   ├── test_client.py
│   ├── test_formatters.py
│   └── test_intent.py
│
├── setup.py                       # Package setup (setuptools)
├── pyproject.toml                 # Modern Python packaging config
├── requirements.txt               # Dependencies
├── README.md                      # Documentation
└── LICENSE                        # MIT License

```

---

## 🚀 Installation & Usage

### Install Package

```bash
# From source (development)
cd fabric_spark_advisor
pip install -e .

# Or build wheel
python -m build
pip install dist/fabric_spark_advisor-0.1.0-py3-none-any.whl
```

### Use in Notebook

```python
from fabric_spark_advisor import SparkAdvisor

advisor = SparkAdvisor(mcp_server_url="http://127.0.0.1:8000")
advisor.launch()
```

---

## 📋 Module Details

### `advisor.py` - Main Entry Point
**Class:** `SparkAdvisor`

**Methods:**
- `__init__(mcp_server_url, theme, session_id)` - Initialize
- `launch(inline, share, server_port, height)` - Start Gradio UI
- `analyze_application(app_id)` - Analyze app (async)
- `analyze_scaling(app_id)` - Scaling impact (async)
- `analyze_skew(app_id)` - Skew detection (async)
- `query(query_text)` - Natural language query (async)
- `close()` - Cleanup

### `client/mcp_client.py` - MCP Communication
**Class:** `MCPClient`

**Methods:**
- `call_tool(tool_name, parameters)` - Invoke MCP tool
- `list_tools()` - Get available tools
- `health_check()` - Check server status
- `close()` - Close connection

### `ui/gradio_app.py` - Chat Interface
**Function:** `create_gradio_interface(mcp_client, theme, chatbot_height)`

**Features:**
- Dark theme matching Chainlit
- Intent-based routing
- Session state management
- Example queries
- Real-time status display

### `ui/formatters.py` - Response Formatting
**Functions:**
- `format_app_analysis(result)` - Full app analysis
- `format_scaling_analysis(result)` - Scaling recommendations
- `format_skew_analysis(result)` - Skew detection results

**Output:** HTML/Markdown with styled cards, tables, badges

### `ui/intent.py` - Intent Detection
**Functions:**
- `detect_intent(message)` - Classify user query
- `extract_application_id(message)` - Extract app ID

**Intents Supported:**
- `analyze_app`
- `analyze_skew`
- `analyze_scaling`
- `show_bad_apps`
- `show_recent_apps`
- `show_driver_heavy`
- `show_memory_intensive`
- `general_chat`

---

## 🎯 Design Principles

### 1. **Clean Notebook Interface**
- Only 3 lines of code needed in notebook
- All complexity hidden in package
- No UX code exposed to end user

### 2. **M+N Architecture (via MCP)**
- Single MCP server → Multiple clients (web, notebook, CLI)
- Linear scaling, not M×N explosion
- Unified tool routing

### 3. **Consistent UX**
- Same formatters as Chainlit web UI
- Same intent detection logic
- Same 3-tier validation (Kusto → RAG → LLM)

### 4. **Expert Rules First**
- SparkLens heuristics (expert-defined)
- Official Microsoft docs (RAG)
- LLM orchestration (not guessing)

---

## 🔧 Development Workflow

### Build Package
```bash
python -m build
```

### Run Tests
```bash
pytest tests/
```

### Format Code
```bash
black fabric_spark_advisor/
```

### Type Check
```bash
mypy fabric_spark_advisor/
```

---

## 📊 Dependencies

### Core (Required)
- `gradio>=4.0.0` - Chat UI framework
- `httpx>=0.25.0` - HTTP client (async support)

### Development (Optional)
- `pytest>=7.0.0` - Testing
- `pytest-asyncio>=0.21.0` - Async test support
- `black>=23.0.0` - Code formatting
- `flake8>=6.0.0` - Linting
- `mypy>=1.0.0` - Type checking

---

## 🎓 Example Workflow

### 1. User opens notebook
```python
from fabric_spark_advisor import SparkAdvisor
advisor = SparkAdvisor()
advisor.launch()
```

### 2. User types: "analyze application_123"
1. **Intent Detection** - Detects `analyze_app` intent
2. **MCP Call** - `await mcp_client.call_tool("get_application_analysis", {...})`
3. **MCP Server** - Routes to orchestrator → Kusto + RAG + LLM
4. **Formatting** - `format_app_analysis(result)` → Styled HTML
5. **Display** - Gradio renders in chat interface

### 3. User types: "are there any skews in this application"
1. **Intent Detection** - Detects `analyze_skew` + extracts app ID from context
2. **MCP Call** - `await mcp_client.call_tool("analyze_skew", {...})`
3. **MCP Server** - Fetches stage summary → Calculates imbalances → LLM analysis
4. **Formatting** - `format_skew_analysis(result)` → Stage tables + recommendations
5. **Display** - Shows problematic stages with severity icons

---

## 🔒 Security Considerations

- MCP server runs **locally** (localhost:8000)
- No external network calls required
- Session IDs are UUID-based
- No sensitive data stored in package

---

## 🚢 Deployment Options

### Option 1: PyPI Distribution
```bash
# Build wheel
python -m build

# Upload to PyPI (when ready)
twine upload dist/*
```

### Option 2: Internal Artifact Feed
```bash
# Build wheel
python -m build

# Upload to Azure Artifacts or private registry
```

### Option 3: Direct Install from Git
```bash
pip install git+https://github.com/microsoft/fabric-spark-advisor.git@main#subdirectory=fabric_spark_advisor
```

---

## 📈 Future Enhancements

### Planned Features
- [ ] CLI interface (`spark-advisor analyze app_123`)
- [ ] Streaming applications support
- [ ] Cost estimation integration
- [ ] Custom rule definitions
- [ ] Export reports (PDF/Excel)
- [ ] Multi-workspace support

### Under Consideration
- Fabric notebook native integration (no Gradio)
- Real-time monitoring dashboard  
- Alerting on critical issues
- Integration with DevOps pipelines

---

## 🤝 Contributing

See main repo [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.

Key areas for contribution:
- New formatters for additional analyses
- Additional intent patterns
- Performance optimizations
- Documentation improvements

---

## 📝 Version History

### v0.1.0 (Current)
- Initial release
- Gradio chat interface
- MCP client integration
- 3-tier validation
- Skew + scaling analysis
- Intent detection

---

**Built with best practices:**
- ✅ Clean architecture (separation of concerns)
- ✅ Type hints throughout
- ✅ Async/await pattern
- ✅ Modular design
- ✅ Comprehensive documentation
- ✅ Example-driven

---

Questions? Open an issue or check the README!
