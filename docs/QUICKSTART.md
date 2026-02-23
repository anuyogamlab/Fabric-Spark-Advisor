# SparkAdvisor MCP Server - Quick Start Guide

## 🚀 Running the Server

### HTTP/SSE Mode (for VS Code connectivity on port 8000)

```bash
cd mcp_server
python server.py
```

This will start the SparkAdvisor MCP server on `http://0.0.0.0:8000` with SSE transport.

**Custom host/port:**
```bash
python server.py --host=localhost --port=8080
```

### In-Memory Mode (for notebook use)

```python
import sys
sys.path.append('/path/to/Spark Recommender MCP')

from mcp_server.server import run_in_memory

# Get tools as Python functions
tools = run_in_memory()

# Use tools directly
recommendations = tools['get_sparklens_recommendations']('your-app-id')
print(recommendations)
```

Or from command line:
```bash
python server.py --in-memory
```

## 🔧 Available MCP Tools

### 1. get_sparklens_recommendations(application_id: str)

Get Spark optimization recommendations for a specific application.

**Example:**
```python
result = get_sparklens_recommendations("application_1706789123456_0001")
# Returns:
# {
#   "application_id": "application_1706789123456_0001",
#   "recommendation_count": 5,
#   "recommendations": [
#     {
#       "app_id": "application_1706789123456_0001",
#       "recommendation": "🚨 CRITICAL: High GC overhead...",
#       "timestamp": "2026-02-22T10:30:00Z"
#     }
#   ]
# }
```

### 2. get_bad_practice_applications(min_violations: int = 3)

Get applications with bad practices ranked by violation count.

**Example:**
```python
result = get_bad_practice_applications(min_violations=3)
# Returns:
# {
#   "min_violations": 3,
#   "application_count": 12,
#   "applications": [
#     {
#       "app_id": "application_xxx",
#       "application_name": "MySparkJob",
#       "artifact_id": "notebook-123",
#       "violation_count": 5,
#       "issues": ["Executor Efficiency", "GC Overhead", "Task Skew Ratio"]
#     }
#   ]
# }
```

### 3. get_application_summary(application_id: str)

Get comprehensive application health summary.

**Example:**
```python
result = get_application_summary("application_1706789123456_0001")
# Returns:
# {
#   "application_id": "application_1706789123456_0001",
#   "summary": {
#     "app_id": "application_1706789123456_0001",
#     "app_name": "MySparkJob",
#     "health_status": "WARNING",
#     "performance_grade": "C",
#     "duration_sec": 1234.5,
#     "executor_count": 8,
#     "executor_efficiency": 0.45,
#     "gc_overhead_pct": 28.5,
#     "task_skew_ratio": 4.2,
#     "parallelism_score": 0.65,
#     "executor_config": "Min:2 Max:10",
#     "high_concurrency": false
#   }
# }
```

### 4. search_recommendations_by_category(category: str)

Search recommendations by category keyword.

**Supported categories:**
- `memory` - Memory and GC related issues
- `shuffle` - Shuffle operations and partitioning
- `join` - Join operations and broadcast
- `cpu` - CPU efficiency and executor utilization
- `skew` - Data skew and task imbalance
- `driver` - Driver coordination overhead
- `parallelism` - Task parallelism and cores
- `streaming` - Streaming-specific optimizations  
- `fabric` - Microsoft Fabric specific settings

**Example:**
```python
result = search_recommendations_by_category("memory")
# Returns:
# {
#   "category": "memory",
#   "recommendation_count": 23,
#   "recommendations": [
#     {
#       "app_id": "application_xxx",
#       "source": "sparklens",
#       "recommendation": "🚨 CRITICAL: High GC overhead (32.5%)",
#       "category": "memory"
#     }
#   ]
# }
```

## 🔐 Authentication

The Kusto client uses **managed identity** by default (recommended for Azure environments).

**Fallback to client secret** (when managed identity unavailable):

Add to your `.env` file:
```env
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id  
AZURE_CLIENT_SECRET=your-client-secret
```

## 🧪 Testing

Run the test suite:

```bash
python test_tools.py
```

This will test all 4 MCP tools against your Kusto database.

## 📊 Database Tables Used

The server queries these Kusto tables:

- **sparklens_recommedations** - Main recommendations
- **sparklens_metrics** - Application metrics
- **sparklens_metadata** - Application metadata
- **fabric_recommedations** - Fabric-specific recommendations

## 🐛 Troubleshooting

**Connection errors:**
1. Verify `.env` file has correct `KUSTO_CLUSTER_URI` and `KUSTO_DATABASE`
2. Check managed identity has read permissions on the Kusto database
3. If using client secret, verify tenant/client IDs are correct

**No recommendations found:**
- Ensure applications have been processed by the Spark monitoring pipeline
- Check application IDs match exactly (case-sensitive)

**Port already in use:**
```bash
python server.py --port=8080
```

## 📖 Example Notebook Usage

```python
# In a Jupyter notebook
import sys
sys.path.append('/path/to/Spark Recommender MCP')

from mcp_server.kusto_client import KustoClient

# Direct Kusto access
client = KustoClient()

# Get recommendations
recs = client.get_sparklens_recommendations('your-app-id')
for rec in recs:
    print(rec['recommendation'])

# Get health summary
summary = client.get_application_summary('your-app-id')
print(f"Health: {summary['health_status']}")
print(f"Grade: {summary['performance_grade']}")
```
