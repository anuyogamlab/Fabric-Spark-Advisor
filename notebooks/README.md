# 📓 Fabric Spark Advisor — Notebooks

Interactive Jupyter notebooks for using the Fabric Spark Advisor directly within Microsoft Fabric notebooks or local Jupyter environments.

---

## 📋 Available Notebooks

### 1. `FabricSparkAdvisor_Interactive.ipynb` ⭐ Recommended

**Full-featured interactive chat UI for Spark optimization**

✅ **Features:**
- Rich ipywidgets-based chat interface
- Back-and-forth conversation with context retention
- Professional FSA branding and card layouts
- Clickable feedback buttons (✅ Helpful, ❌ Not Helpful, ⚠️ Partial)
- Real-time Kusto queries for live telemetry data
- 3-tier source priority (Kusto → RAG → LLM)
- Session statistics and conversation history

🎯 **Use Cases:**
- Analyze Spark applications interactively
- Explore performance metrics and recommendations
- Provide feedback to improve future recommendations
- Run ad-hoc queries against telemetry data

📦 **Dependencies:**
```bash
pip install ipywidgets pandas azure-kusto-data azure-kusto-ingest python-dotenv
```

🚀 **Quick Start:**
1. Open the notebook in Jupyter or VS Code
2. Run cells 1-3 to initialize the Spark Advisor
3. Run cell 5 to launch the interactive chat UI
4. Type your query and click 🚀 Send

---

### 2. `FabricSparkAdvisor_QuickStart.ipynb`

**Lightweight notebook for fast queries**

✅ **Features:**
- Simple `ask()` function interface
- Pre-configured common queries cheat sheet
- Direct Kusto query examples
- Programmatic API access
- Feedback save function
- Minimal dependencies

🎯 **Use Cases:**
- Quick one-off queries during development
- Direct API exploration
- Custom KQL query execution
- Lightweight performance testing

📦 **Dependencies:**
```bash
pip install pandas azure-kusto-data azure-kusto-ingest python-dotenv
```

🚀 **Quick Start:**
1. Open the notebook
2. Run cells 1-2 to initialize
3. Run cell 3 to create the `ask()` helper function
4. Use `ask("your query")` in any cell

---

### 3. `spark_recommender.ipynb`

**Original development notebook**

This is the original notebook used during early development. Consider using the newer notebooks above for a better experience.

---

## 🔧 Setup Instructions

### For Microsoft Fabric Notebooks

1. **Upload Notebook:**
   - Go to your Fabric workspace
   - Click **New** → **Import notebook**
   - Select your preferred notebook:
     - `FabricSparkAdvisor_Interactive.ipynb` (full UI)
     - `FabricSparkAdvisor_QuickStart.ipynb` (lightweight)

2. **Install Dependencies:**
   ```python
   %pip install ipywidgets pandas azure-kusto-data azure-kusto-ingest python-dotenv
   ```

3. **Set Environment Variables:**
   - Use Fabric notebook secrets or environment variables
   - Required: `KUSTO_CLUSTER`, `KUSTO_DATABASE`, `KUSTO_CLIENT_ID`, `KUSTO_CLIENT_SECRET`, `KUSTO_TENANT_ID`
   - Optional: `OPENAI_API_KEY` (for LLM recommendations)

4. **Run the Notebook:**
   - Execute all cells sequentially
   - **Interactive notebook**: Chat UI appears in cell 5
   - **QuickStart notebook**: Use `ask()` function in any cell after cell 3

### For Local Jupyter

1. **Clone Repository:**
   ```bash
   git clone <repo-url>
   cd "Spark Recommender MCP"
   ```

2. **Create Virtual Environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install jupyter ipywidgets
   ```

4. **Configure `.env` File:**
   ```env
   KUSTO_CLUSTER=https://your-cluster.kusto.windows.net
   KUSTO_DATABASE=your-database
   KUSTO_CLIENT_ID=your-client-id
   KUSTO_CLIENT_SECRET=your-client-secret
   KUSTO_TENANT_ID=your-tenant-id
   OPENAI_API_KEY=your-openai-key
   ```

5. **Start Jupyter:**
   ```bash
   # Interactive UI notebook
   jupyter notebook notebooks/FabricSparkAdvisor_Interactive.ipynb
   
   # Or QuickStart notebook
   jupyter notebook notebooks/FabricSparkAdvisor_QuickStart.ipynb
   ```

---

## 💡 Example Queries

Try these in the interactive chat UI:

```
analyze application_1771441543262_0001
show top 5 slowest applications
find streaming jobs
what is VOrder?
show bad practice apps
how do I optimize shuffle operations?
```

---

## 🎨 UI Features

### Professional Branding
- FSA logo with gradient accent bar
- Dark theme (#080C10 background, #0D1318 paper)
- Color-coded recommendation cards:
  - 🔴 Red borders → CRITICAL severity
  - 🟡 Yellow borders → HIGH severity
  - 🔵 Blue borders → MEDIUM severity
  - 🟢 Green borders → LOW severity

### Source Badges
- 🟢 **KUSTO** badge → Verified data from Eventhouse
- 🔵 **RAG** badge → Official Microsoft documentation
- 🟣 **LLM** badge → AI-generated suggestions (with warning box)

### Feedback Buttons
- ✅ **Helpful** → Recommendation worked well
- ❌ **Not Helpful** → Recommendation didn't apply
- ⚠️ **Partially Helpful** → Some parts useful, some not

All feedback is saved to the `sparkagent_feedback` table in Kusto for continuous learning.

---

## 📊 Direct API Access

For advanced users who prefer programmatic access:

```python
# Get top 5 slowest apps
query = 'sparklens_metrics | where metric == "Total Executor Time (sec)" | top 5 by value desc'
results = kusto_client.execute_query(query)

# Analyze specific application
app_id = "application_1771441543262_0001"
spark_recs = orchestrator.get_spark_recommendations(app_id)
fabric_recs = orchestrator.get_fabric_recommendations(app_id)

# Get RAG documentation
docs = orchestrator.search_documentation("VOrder optimization")
```

---

## 🔒 Security Best Practices

1. **Never commit credentials** to version control
2. Use **Managed Identity** or **Service Principal** for production
3. Store secrets in **Azure Key Vault** or Fabric **notebook secrets**
4. Rotate credentials regularly
5. Use least-privilege access for Kusto database

---

## 🐛 Troubleshooting

### Issue: "Module not found" error
**Solution:** Run `%pip install ipywidgets pandas azure-kusto-data` in the notebook

### Issue: "Authentication failed"
**Solution:** Verify `.env` file has correct Kusto credentials, or use Fabric secrets

### Issue: Widgets not displaying
**Solution:** Enable Jupyter widgets: `jupyter nbextension enable --py widgetsnbextension`

### Issue: "No data found in Kusto"
**Solution:** Verify Kusto database contains `sparklens_metrics` and related tables

---

## 📚 Additional Resources

- **Architecture Documentation**: [../ARCHITECTURE.md](../ARCHITECTURE.md)
- **MCP Tools Reference**: [../components/TOOL_REFERENCE.md](../components/TOOL_REFERENCE.md)
- **Hallucination Prevention**: [../components/HALLUCINATION_PREVENTION.md](../components/HALLUCINATION_PREVENTION.md)
- **Feedback Learning Strategy**: [../mcp_server/feedback_learning_strategy.md](../mcp_server/feedback_learning_strategy.md)

---

## 🤝 Contributing

Found a bug or have a feature request? Please open an issue or submit a pull request!

---

**Built with ❤️ by the Fabric Spark Advisor Team**
