# SparkAdvisor Orchestrator

The orchestrator is the main agent that coordinates the entire Spark recommendation pipeline, integrating:
- **MCP Tools** (Kusto telemetry via SparkAdvisor server)
- **RAG** (Microsoft Fabric documentation)
- **LLM** (Azure OpenAI GPT-4o)
- **Judge** (Recommendation validation)
- **Chat Interface** (Conversational AI)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   SparkAdvisorOrchestrator                       │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ MCP Tools    │  │ RAG System   │  │ LLM (GPT-4o) │          │
│  │ (Kusto)      │  │ (AI Search)  │  │ (Azure OpenAI)│         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                  │
│         └──────────────────┼──────────────────┘                  │
│                            │                                     │
│                    ┌───────▼────────┐                            │
│                    │  LLM Judge     │                            │
│                    │  (Validation)  │                            │
│                    └───────┬────────┘                            │
│                            │                                     │
│                    ┌───────▼──────────┐                          │
│                    │ Validated Output │                          │
│                    └──────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

## Core Methods

### 1. `analyze_application(application_id: str)`

**Full pipeline analysis of a Spark application.**

**Pipeline Steps:**
1. **Kusto Telemetry**: Fetch Sparklens + Fabric recommendations
2. **Application Summary**: Get metrics (duration, executor efficiency, etc.)
3. **RAG Search**: Query documentation based on identified issues
4. **LLM Fallback**: Generate recommendations if RAG returns < 3 results
5. **Source Tagging**: Mark each recommendation with origin (kusto/rag/llm)
6. **Judge Validation**: Score confidence, detect contradictions, prioritize
7. **Return Results**: Validated recommendations with metadata

**Example:**
```python
from agent.orchestrator import SparkAdvisorOrchestrator
import asyncio

async def analyze():
    orchestrator = SparkAdvisorOrchestrator()
    result = await orchestrator.analyze_application("application_12345")
    
    print(f"Health: {result['overall_health']}")
    print(f"Recommendations: {len(result['validated_recommendations'])}")
    
    # Show top 3 by priority
    top_3 = sorted(result['validated_recommendations'], 
                   key=lambda x: x['priority'])[:3]
    for rec in top_3:
        print(f"[{rec['confidence']}] {rec['recommendation']}")

asyncio.run(analyze())
```

**Output Structure:**
```json
{
  "application_id": "application_12345",
  "overall_health": "warning",
  "summary": "2 high-priority issues detected...",
  "validated_recommendations": [
    {
      "recommendation": "Increase executor memory...",
      "source": "kusto",
      "confidence": "high",
      "priority": 1,
      "reasoning": "Telemetry shows GC overhead at 45%...",
      "action": "Set spark.executor.memory=8g",
      "is_generic": false,
      "contradicts": []
    }
  ],
  "detected_contradictions": [],
  "critical_count": 0,
  "warning_count": 2,
  "info_count": 1,
  "application_summary": { /* metrics */ },
  "source_counts": {
    "kusto": 2,
    "rag": 3,
    "llm": 0
  }
}
```

### 2. `find_bad_applications(min_violations: int = 3)`

**Find Spark applications with configuration bad practices.**

Returns ranked list of applications with ≥ `min_violations` anti-patterns.

**Example:**
```python
orchestrator = SparkAdvisorOrchestrator()
bad_apps = orchestrator.find_bad_applications(min_violations=5)

for app in bad_apps[:10]:  # Top 10 worst
    print(f"{app['severity_label']} {app['application_id']}")
    print(f"  Violations: {app['violation_count']}")
    print(f"  {app['brief_explanation']}")
```

**Output:**
```
🔴 CRITICAL application_12345
  Violations: 12
  🔴 CRITICAL: 12 bad practices detected. Review configuration and resource allocation.

🟡 WARNING application_67890
  Violations: 7
  🟡 WARNING: 7 bad practices detected. Review configuration and resource allocation.
```

### 3. `chat(user_message: str, context: dict = None)`

**Conversational interface with automatic tool invocation.**

- Detects intent from natural language
- Automatically triggers `analyze_application()` or `find_bad_applications()`
- Maintains chat history across conversation
- Can answer questions using RAG + LLM

**Example:**
```python
orchestrator = SparkAdvisorOrchestrator()

# Regular question
response = await orchestrator.chat(
    "What causes high GC overhead in Spark?"
)
print(response)

# Triggers automatic analysis
response = await orchestrator.chat(
    "Analyze application_12345"
)
# → Runs full pipeline and returns formatted results

# Triggers bad app search
response = await orchestrator.chat(
    "Show me apps with bad practices"
)
# → Calls find_bad_applications() and formats list
```

## Integration with Components

### MCP Tools (Kusto Client)

The orchestrator uses `KustoClient` to call MCP tool equivalents:
- `get_sparklens_recommendations(app_id)` → Sparklens analysis
- `get_fabric_recommendations(app_id)` → Fabric-specific recommendations
- `get_application_summary(app_id)` → Application metrics
- `get_bad_practice_applications(min_violations)` → Applications with issues

**Note**: These directly call the Kusto client rather than going through the MCP server HTTP endpoints for efficiency. In production, you could switch to MCP client for remote access.

### RAG System (SparkDocRetriever)

Searches Microsoft Fabric Spark documentation:
```python
self.retriever.search(query, top_k=2, category="performance")
```

Categories available: `performance`, `configuration`, `delta`, `maintenance`, `best-practices`

### LLM Judge (RecommendationJudge)

Validates all recommendations:
```python
validated = self.judge.validate_recommendations(
    application_id=app_id,
    recommendations=all_recs,
    application_context=app_summary
)
```

Returns structured output with confidence scores, contradictions, and priorities.

### Semantic Kernel

Uses Semantic Kernel for:
- Azure OpenAI integration
- Chat history management
- Future plugin extensibility

## Prompt System

All prompts defined in `agent/prompts.py`:

| Prompt | Purpose |
|--------|---------|
| `ORCHESTRATOR_SYSTEM_PROMPT` | Main agent persona and capabilities |
| `JUDGE_SYSTEM_PROMPT` | Judge validation criteria |
| `RAG_QUERY_REWRITE_PROMPT` | Optimize search queries for RAG |
| `LLM_RECOMMENDATION_PROMPT` | Generate recommendations when data insufficient |
| `CHAT_SYSTEM_PROMPT` | Conversational agent behavior |
| `ANALYSIS_SUMMARY_PROMPT` | Format analysis results |
| `BAD_PRACTICES_PROMPT` | Explain bad practice violations |

## Running the Demo

```bash
python examples/orchestrator_demo.py
```

This runs 4 demos:
1. **Full Application Analysis** - Complete pipeline with real data
2. **Bad Applications** - Find and rank problematic apps
3. **Chat Interface** - Conversational interaction
4. **Convenience Function** - Simple API usage

## Error Handling

The orchestrator implements graceful degradation:
- If Kusto fails → continues with RAG + LLM only
- If RAG fails → uses LLM fallback
- If LLM fails → returns unvalidated recommendations
- If Judge fails → returns raw recommendations with metadata

All errors logged but don't stop the pipeline.

## Configuration

Set environment variables in `.env`:
```bash
# Azure OpenAI (required)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Kusto (required for telemetry)
KUSTO_CLUSTER_URI=https://your-cluster.kusto.windows.net
KUSTO_DATABASE=your-database

# Azure AI Search (required for RAG)
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_KEY=your-key
AZURE_SEARCH_INDEX=spark-docs-index
```

## Next Steps

1. **UI Integration**: Use orchestrator in Chainlit app (`ui/app.py`)
2. **Persistent Chat**: Store conversation history in database
3. **Feedback Loop**: Track which recommendations users implement
4. **Batch Analysis**: Analyze multiple applications in parallel
5. **Caching**: Cache RAG results for common issues
6. **Metrics**: Track judge accuracy and recommendation adoption

## API Reference

### SparkAdvisorOrchestrator

```python
class SparkAdvisorOrchestrator:
    def __init__(self):
        """Initialize orchestrator with Azure OpenAI, Kusto, RAG, and Judge."""
    
    async def analyze_application(self, application_id: str) -> Dict[str, Any]:
        """Run full pipeline analysis on a Spark application."""
    
    def find_bad_applications(self, min_violations: int = 3) -> List[Dict[str, Any]]:
        """Find applications with configuration bad practices."""
    
    async def chat(self, user_message: str, context: Optional[Dict] = None) -> str:
        """Conversational interface with auto tool invocation."""
```

### Convenience Functions

```python
async def analyze_spark_application(application_id: str) -> Dict[str, Any]:
    """Quick analysis without creating orchestrator instance."""
```

## Examples

See `examples/orchestrator_demo.py` for comprehensive usage examples covering all features.
