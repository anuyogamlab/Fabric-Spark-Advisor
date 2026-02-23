# LLM Judge - Recommendation Validator

The LLM Judge validates and prioritizes Spark optimization recommendations from multiple sources using Azure OpenAI GPT-4o with structured output.

## Overview

The `RecommendationJudge` takes recommendations from three sources:
- **Kusto telemetry** (highest priority - actual performance data)
- **RAG documentation** (medium priority - best practices from Microsoft Fabric docs)
- **LLM generated** (lowest priority - general guidance)

It validates them by:
1. ✅ Detecting contradictions between recommendations
2. 📊 Scoring confidence (high/medium/low)
3. 🎯 Flagging generic vs application-specific advice
4. ⚡ Prioritizing data-driven over speculative recommendations
5. 🔧 Ensuring each recommendation has a clear action

## Usage

### Basic Example

```python
from agent.judge import validate_recommendations

recommendations = [
    {
        "text": "High GC overhead (35%). Increase spark.executor.memory to 8GB",
        "source": "kusto",  # kusto | rag | llm
        "metadata": {"gc_overhead": 0.35}
    },
    {
        "text": "Enable NEE: spark.native.enabled=true",
        "source": "rag",
        "source_url": "https://learn.microsoft.com/fabric/spark/..."
    },
    {
        "text": "Consider adding more executors",
        "source": "llm"
    }
]

context = {
    "duration_sec": 1200,
    "executor_efficiency": 0.28,
    "gc_overhead": 0.35
}

result = validate_recommendations(
    application_id="app_12345",
    recommendations=recommendations,
    context=context
)
```

### Output Structure

```json
{
  "application_id": "app_12345",
  "validated_recommendations": [
    {
      "recommendation": "High GC overhead detected...",
      "source": "kusto",
      "confidence": "high",
      "priority": 1,
      "reasoning": "Backed by telemetry data showing 35% GC overhead",
      "action": "Set spark.executor.memory=8g in Spark config",
      "is_generic": false,
      "contradicts": []
    }
  ],
  "summary": "Critical memory pressure detected. Immediate action recommended.",
  "critical_count": 1,
  "warning_count": 2,
  "info_count": 0,
  "overall_health": "warning",
  "detected_contradictions": [],
  "total_recommendations": 3,
  "sources_used": ["kusto", "rag", "llm"]
}
```

## Integration with MCP Tools

```python
from mcp_server.server import (
    get_sparklens_recommendations,
    get_fabric_recommendations
)
from agent.judge import validate_recommendations

# Fetch from MCP
app_id = "my_spark_app"
sparklens = get_sparklens_recommendations(app_id)
fabric = get_fabric_recommendations(app_id)

# Combine and format
recommendations = []

for rec in sparklens['recommendations']:
    recommendations.append({
        "text": rec['recommendation'],
        "source": "kusto",
        "metadata": {"table": "sparklens_recommedations"}
    })

for rec in fabric['recommendations']:
    recommendations.append({
        "text": rec['recommendation'],
        "source": "kusto",
        "metadata": {"table": "fabric_recommedations"}
    })

# Validate
validated = validate_recommendations(app_id, recommendations)

# Use top recommendations
for rec in validated['validated_recommendations'][:3]:
    print(f"[{rec['confidence']}] {rec['action']}")
```

## Validation Criteria

### Prioritization Rules
1. **Source priority**: Kusto > RAG > LLM
2. **Specificity**: Application-specific > Generic
3. **Actionability**: Concrete steps > Vague advice

### Confidence Scoring
- **HIGH**: Backed by telemetry or official docs, no contradictions
- **MEDIUM**: Based on best practices, minor uncertainties
- **LOW**: Generic advice, conflicts, or speculative

### Contradiction Detection
The judge identifies conflicting recommendations:
```python
{
  "detected_contradictions": [
    {
      "recommendation_1": "Add more executors to improve parallelism",
      "recommendation_2": "Driver-heavy workload - scale down to save costs",
      "explanation": "These recommendations conflict. Driver overhead makes scaling up ineffective."
    }
  ]
}
```

## Features

### Structured Output
Uses Azure OpenAI's JSON schema mode for reliable, typed responses:
```python
response_format={
    "type": "json_schema",
    "json_schema": {
        "name": "recommendation_validation",
        "strict": True,
        "schema": {...}
    }
}
```

### Fallback Handling
If LLM validation fails, provides basic prioritization:
- Kusto sources get priority 1
- RAG sources get priority 2  
- LLM sources get priority 3
- All marked as medium/low confidence

### Context-Aware
Optional application metrics improve validation:
```python
context = {
    "duration_sec": 1200,
    "executor_efficiency": 0.28,
    "gc_overhead": 0.35,
    "parallelism_score": 0.45,
    "task_skew_ratio": 3.2,
    "job_type": "batch"
}
```

## Configuration

Requires Azure OpenAI credentials in `.env`:
```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

## Testing

Run the demo to see validation in action:
```bash
python examples/judge_demo.py
```

This demonstrates:
1. Basic validation with mixed sources
2. Contradiction detection
3. Integration with real MCP data

## API Reference

### `RecommendationJudge`

#### `validate_recommendations(application_id, recommendations, context=None)`

**Parameters:**
- `application_id` (str): Spark application ID
- `recommendations` (List[Dict]): Recommendations to validate
  - Each dict must have: `text` or `recommendation`, `source`
  - Optional: `metadata`, `source_url`
- `context` (Dict, optional): Application metrics

**Returns:**
- Dict with validated recommendations, confidence scores, priorities

### Convenience Function

```python
from agent.judge import validate_recommendations

result = validate_recommendations(app_id, recs, context)
```

## Best Practices

1. **Always provide source tags** - Enables proper prioritization
2. **Include metadata** - Helps judge assess specificity
3. **Pass application context** - Improves relevance scoring
4. **Handle contradictions** - Check `detected_contradictions` field
5. **Sort by priority** - Recommendations are pre-sorted by importance

## Performance

- Typical latency: 2-5 seconds for 5-10 recommendations
- Uses GPT-4o with `temperature=0.3` for consistency
- Max tokens: 4000 (handles ~10-15 detailed recommendations)

## Error Handling

The judge gracefully degrades:
- LLM call fails → Returns basic source-based prioritization
- Invalid schema → Falls back to simple validation
- Missing context → Works with available data
- Empty recommendations → Returns empty validated list

## Future Enhancements

- [ ] Caching for repeated validations
- [ ] Batch validation for multiple apps
- [ ] Historical contradiction tracking
- [ ] Confidence calibration based on outcomes
- [ ] Multi-model ensemble validation
