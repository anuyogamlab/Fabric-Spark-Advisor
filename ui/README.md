# Chainlit UI for Spark Recommender Agent

Interactive chat interface for analyzing Apache Spark applications on Microsoft Fabric.

## Features

### 🎯 Intent Detection
The UI automatically detects what you want to do based on your message:

- **App Analysis**: "analyze app-123" or "recommendations for application_xyz"
- **Problem Detection**: "show bad apps", "driver heavy jobs", "memory issues"  
- **Best Practices**: "show healthy apps", "well optimized applications"
- **General Chat**: "what is shuffle spill?", "how do I fix GC overhead?"

### 📊 Response Formatting

- **Application Analysis**: Beautiful markdown with severity badges, confidence scores, source attribution
- **App Tables**: Sortable tables with health indicators (🟢🟡🔴)
- **Rankings**: Medal system for top performers (🥇🥈🥉)
- **Tips**: Contextual advice for each issue type

### 🔌 Session Tracking

The sidebar shows:
- Apps analyzed this session
- Total recommendations given
- Data sources used (Kusto, RAG, LLM)
- Session duration

### 💡 Smart Follow-ups

After each response, get suggested next actions as clickable buttons:
- "Analyze worst app"
- "How do I fix this?"
- "Compare with healthy apps"

## Running the UI

### Prerequisites

```bash
pip install chainlit
```

### Start the server

```bash
# From project root
chainlit run ui/app.py --port 8501
```

Then open: http://localhost:8501

## Usage Examples

### Analyze a Specific Application

```
analyze application_1771438258399_0001
```

**Returns:**
- Overall health status
- Detailed recommendations with priorities
- Source attribution (Kusto/RAG/LLM)
- Confidence scores
- Actionable next steps

### Find Problem Applications

```
show bad apps
```

**Returns:**
- Ranked list of apps with violations
- Severity indicators
- Violation counts

### Find Driver-Heavy Apps

```
show me driver heavy jobs
```

**Returns:**
- Apps with high driver CPU/memory
- Critical alerts for > 90% utilization
- Optimization tips

### Find Memory Issues

```
show memory intensive apps
```

**Returns:**
- Apps with memory spills
- GC overhead percentages
- Risk levels (HIGH/MEDIUM/LOW)

### Find Healthy Apps

```
show well optimized apps
```

**Returns:**
- Apps following best practices
- Health scores (0-100)
- Letter grades (A/B/C)
- Top 3 with medals

### Ask General Questions

```
what causes high GC overhead in Spark?
```

**Returns:**
- General guidance from LLM
- Links to relevant documentation
- Specific configuration recommendations

## Intent Classification

The UI uses keyword matching + regex to classify your intent:

| Intent | Triggers | Calls |
|--------|---------|-------|
| `analyze_app` | "analyze", "recommendations for", "issues" + app ID | `orchestrator.analyze_application(app_id)` |
| `show_bad_apps` | "bad apps", "problem apps", "worst apps" | `orchestrator.find_bad_applications()` |
| `show_driver_heavy` | "driver heavy", "driver cpu", "driver overhead" | `orchestrator.find_applications_by_pattern("driver_heavy")` |
| `show_memory_intensive` | "memory intensive", "OOM", "memory spill" | `orchestrator.find_applications_by_pattern("memory_intensive")` |
| `show_shuffle_issues` | "shuffle spill", "shuffle heavy" | `orchestrator.find_applications_by_pattern("shuffle_heavy")` |
| `show_best_practice_apps` | "best practices", "healthy apps", "well optimized" | `orchestrator.find_healthy_applications()` |
| `general_chat` | Everything else | `orchestrator.chat(message)` |

## Response Formatters

### Application Analysis

Formatted with:
- Health badge (🔴🟡🟢🌟)
- Recommendation summary by severity
- Top 10 recommendations with:
  - Priority number
  - Source emoji (📊 Kusto, 📚 RAG, 🤖 LLM)
  - Confidence level
  - Action steps
  - Generic warning if applicable

### Tables

All tables include:
- Clean markdown formatting
- Trend indicators (🟢🟡🔴)
- Smart number formatting (GB, MB, K)
- Row limits (top 15-20)
- Contextual tips

### Special Formatters

- **Driver Heavy**: Shows CPU%, Memory%, Alert levels (🚨⚠️)
- **Memory Issues**: Shows spill in GB, GC%, Risk levels
- **Healthy Apps**: Shows medals (🥇🥈🥉), grades (A/B/C), health scores

## Session State

Tracks across the conversation:
```python
{
    "last_analyzed_app": "application_123",
    "apps_analyzed_count": 5,
    "total_recommendations": 23,
    "sources_used": {
        "kusto": True,
        "rag": True,
        "llm": False
    },
    "session_start": datetime.now()
}
```

Updated after analyze_app intent and displayed in sidebar.

## Follow-up Actions

Context-aware suggestions based on what you just did:

**After analyzing an app:**
- 🔍 Find Similar Apps
- 🛠️ Fix Top Issue
- 📊 Compare with Best

**After showing bad apps:**
- 🔍 Analyze Worst App
- ✅ Show Healthy Apps
- 📈 Common Issues

**After showing driver-heavy apps:**
- 💾 Memory Issues
- 🛠️ Fix Driver Overhead
- 🔀 Shuffle Issues

## Architecture

```
User Message
    ↓
detect_intent(message)
    ↓
get_loading_message(intent)
    ↓
Route to orchestrator method:
  - analyze_application(app_id)
  - find_bad_applications(min_violations)
  - find_applications_by_pattern(pattern)
  - find_healthy_applications(min_score)
  - chat(message)
    ↓
Format response:
  - format_app_analysis(result)
  - format_app_table(apps, title, columns)
  - format_driver_heavy_table(apps)
  - format_memory_table(apps)
  - format_healthy_apps_table(apps)
    ↓
Send response + sidebar + follow-up actions
```

## Customization

### Add New Intent

1. **Update detect_intent():**
   ```python
   if "my trigger" in message_lower:
       return {
           "intent": "my_new_intent",
           "params": {"param1": value}
       }
   ```

2. **Add loading message:**
   ```python
   "my_new_intent": "🔄 Processing your request..."
   ```

3. **Add handler in main():**
   ```python
   elif intent == "my_new_intent":
       result = orchestrator.my_method(params["param1"])
       response_text = format_my_response(result)
   ```

4. **Add follow-up actions:**
   ```python
   elif intent == "my_new_intent":
       return [
           cl.Action(name="follow_up", value="...", label="...")
       ]
   ```

### Customize Formatters

All formatters are in the `# RESPONSE FORMATTERS` section.

Modify:
- Badge emojis
- Table columns
- Severity thresholds
- Number formatting
- Tips and warnings

### Adjust Session Tracking

Update `initialize_session_state()` and `update_session_state()` to track additional metrics.

## Troubleshooting

### Orchestrator not found
Ensure Python path is set correctly:
```python
sys.path.insert(0, str(Path(__file__).parent.parent))
```

### Intent not detected
Check trigger keywords in `detect_intent()` and add variations.

### Tables not formatted correctly
Verify column names match Kusto query results.

### Loading message stuck
Check for exceptions in orchestrator methods - add try/except.

## Next Steps

1. **Add more intents**: Cost analysis, performance trends, comparison views
2. **Enhance formatters**: Charts, graphs, visualizations
3. **Persistent history**: Save conversations to database
4. **User feedback**: Rating system for recommendations
5. **Advanced search**: Natural language query parsing
6. **Export**: Download recommendations as CSV/PDF
7. **Scheduling**: Set up recurring analyses

## Demo

Run the demo:
```bash
chainlit run ui/app.py --port 8501
```

Then try:
1. Click "Find Problem Apps" button
2. Type: "analyze application_1771438258399_0001"
3. Click follow-up action: "Show Healthy Apps"
4. Ask: "what causes shuffle spill?"

You'll see the full intent detection → routing → formatting → follow-up workflow!
