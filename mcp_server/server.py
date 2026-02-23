"""
FastMCP Server for SparkAdvisor
Exposes Spark optimization recommendations via MCP protocol
"""
import asyncio
import sys
import logging
from typing import Any
from mcp.server.fastmcp import FastMCP

# Configure logging to suppress verbose Azure SDK logs
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)

# Handle both direct execution and module import
try:
    from .kusto_client import KustoClient
except ImportError:
    from kusto_client import KustoClient

# Initialize FastMCP server
mcp = FastMCP("SparkAdvisor")

# Global Kusto client (initialized on demand)
_kusto_client = None


def get_kusto_client() -> KustoClient:
    """Get or create Kusto client instance"""
    global _kusto_client
    if _kusto_client is None:
        _kusto_client = KustoClient()
    return _kusto_client


# ==================== MCP Tools ====================

@mcp.tool()
def get_sparklens_recommendations(application_id: str) -> dict[str, Any]:
    """
    Get Spark optimization recommendations for a specific application.
    
    Returns recommendations filtered by application_id with:
    - Issue description
    - Severity level (CRITICAL, HIGH, MEDIUM, LOW)
    - Recommended actions
    - Category (memory, shuffle, join, etc.)
    
    Args:
        application_id: The Spark application ID to get recommendations for
    
    Returns:
        Dictionary with recommendations list and metadata
    """
    client = get_kusto_client()
    recommendations = client.get_sparklens_recommendations(application_id)
    
    return {
        "application_id": application_id,
        "recommendation_count": len(recommendations),
        "recommendations": recommendations
    }


@mcp.tool()
def get_bad_practice_applications(min_violations: int = 3) -> dict[str, Any]:
    """
    Get applications with bad practices ranked by violation count.
    
    Aggregates across all apps and returns ranked list by violation count.
    Identifies applications with:
    - Low executor efficiency (<40%)
    - High GC overhead (>25%)
    - Poor parallelism (<40%)
    - Severe task skew (>3x)
    
    Args:
        min_violations: Minimum number of violations to include (default: 3)
    
    Returns:
        Dictionary with ranked list of applications and their violations
    """
    client = get_kusto_client()
    bad_apps = client.get_bad_practice_applications(min_violations)
    
    return {
        "min_violations": min_violations,
        "application_count": len(bad_apps),
        "applications": bad_apps
    }


@mcp.tool()
def get_application_summary(application_id: str) -> dict[str, Any]:
    """
    Get comprehensive application health summary.
    
    Joins spark logs with recommendations to provide health summary including:
    - Executor failures and efficiency
    - Shuffle spill metrics
    - GC overhead percentage
    - Task skew ratio
    - Performance grade (A/B/C/D)
    - Health status (HEALTHY/WARNING/CRITICAL)
    
    Args:
        application_id: The Spark application ID to summarize
    
    Returns:
        Dictionary with comprehensive health metrics and status
    """
    client = get_kusto_client()
    summary = client.get_application_summary(application_id)
    
    return {
        "application_id": application_id,
        "summary": summary
    }


@mcp.tool()
def get_fabric_recommendations(application_id: str) -> dict[str, Any]:
    """
    Get Microsoft Fabric-specific optimization recommendations for an application.
    
    Returns Fabric infrastructure and configuration recommendations including:
    - Native Execution Engine (NEE) enablement status and suggestions
    - High Concurrency mode recommendations
    - Delta Lake best practices:
        * Auto Compaction settings
        * Adaptive File Size tuning
        * V-Order optimization
        * Snapshot Acceleration
        * Extended Statistics collection
    - Resource Profile optimization (readHeavyForSpark, writeHeavy, etc.)
    - Driver vs Executor workload analysis
    - Cost optimization suggestions
    
    Args:
        application_id: The Spark application ID to get Fabric recommendations for
    
    Returns:
        Dictionary with Fabric-specific recommendations and metadata
    """
    client = get_kusto_client()
    recommendations = client.get_fabric_recommendations(application_id)
    
    return {
        "application_id": application_id,
        "recommendation_count": len(recommendations),
        "source": "fabric_analyzer",
        "recommendations": recommendations
    }


@mcp.tool()
def get_application_metrics(application_id: str) -> dict[str, Any]:
    """
    Get application performance metrics - CALL THIS FIRST to understand app profile.
    
    Returns key metrics including:
    - Executor Efficiency (0-1, <0.3 = CRITICAL)
    - GC Overhead (0-1, >0.25 = HIGH severity)
    - Task Skew Ratio (1x = perfect, >5x = severe, >10x = CRITICAL)
    - Parallelism Score (0-1, higher is better)
    - Job Type (1.0=STREAMING, 0.0=BATCH)
    - Driver Time % and Executor Time % (wall clock breakdown)
    - Application Duration (seconds)
    - Executor Count
    
    Use these metrics to determine severity and guide further analysis.
    
    Args:
        application_id: The Spark application ID to get metrics for
    
    Returns:
        Dictionary with performance metrics and severity assessment
    """
    client = get_kusto_client()
    metrics = client.get_application_metrics(application_id)
    
    return {
        "application_id": application_id,
        "metrics": metrics
    }


@mcp.tool()
def get_scaling_predictions(application_id: str) -> dict[str, Any]:
    """
    Get executor scaling impact predictions for an application.
    
    Shows predicted runtime and efficiency for different executor counts.
    Includes:
    - Executor multipliers (0.5x, 1.0x, 1.5x, 2.0x, etc.)
    - Estimated total duration
    - Estimated executor wall clock time
    - Speedup factor
    - Efficiency rating
    - Scaling recommendation
    - Bottleneck analysis
    
    Args:
        application_id: The Spark application ID to get predictions for
    
    Returns:
        Dictionary with scaling predictions and recommendations
    """
    client = get_kusto_client()
    predictions = client.get_scaling_predictions(application_id)
    
    return {
        "application_id": application_id,
        "prediction_count": len(predictions),
        "predictions": predictions
    }


@mcp.tool()
def get_application_metadata(application_id: str) -> dict[str, Any]:
    """
    Get application configuration metadata and Fabric settings.
    
    Returns configuration including:
    - spark.native.enabled (NEE status)
    - spark.fabric.resourceProfile (readHeavyForSpark, writeHeavy, etc.)
    - spark.sql.parquet.vorder.default (V-Order status)
    - isHighConcurrencyEnabled
    - Delta Lake properties (Auto Compaction, Optimize Write, etc.)
    - Executor min/max configuration
    - Artifact information
    
    Args:
        application_id: The Spark application ID to get metadata for
    
    Returns:
        Dictionary with configuration metadata
    """
    client = get_kusto_client()
    metadata = client.get_application_metadata(application_id)
    
    return {
        "application_id": application_id,
        "metadata": metadata
    }


@mcp.tool()
def get_stage_summary(application_id: str, stage_id: int = None) -> dict[str, Any]:
    """
    Get detailed stage-level task statistics for deep dive analysis.
    
    Returns stage metrics including:
    - Task counts (total, successful, failed)
    - Duration statistics (min, max, avg, p75)
    - Shuffle read/write volumes (MB and record counts)
    - Input/output data volumes
    - Executor utilization per stage
    - Stage execution time
    
    Useful for identifying specific bottleneck stages.
    
    Args:
        application_id: The Spark application ID
        stage_id: Optional specific stage ID to analyze (if None, returns all stages)
    
    Returns:
        Dictionary with stage-level performance details
    """
    client = get_kusto_client()
    stages = client.get_stage_summary(application_id, stage_id)
    
    return {
        "application_id": application_id,
        "stage_id": stage_id,
        "stage_count": len(stages),
        "stages": stages
    }


@mcp.tool()
def search_recommendations_by_category(category: str) -> dict[str, Any]:
    """
    Search and filter recommendations by category.
    
    Supported categories:
    - memory: Memory and GC related issues
    - shuffle: Shuffle operations and partitioning
    - join: Join operations and broadcast
    - cpu: CPU efficiency and executor utilization
    - skew: Data skew and task imbalance
    - driver: Driver coordination overhead
    - parallelism: Task parallelism and cores
    - streaming: Streaming-specific optimizations
    - fabric: Microsoft Fabric specific settings
    
    Args:
        category: Category keyword to filter by (memory, shuffle, join, etc.)
    
    Returns:
        Dictionary with matching recommendations across all applications
    """
    client = get_kusto_client()
    recommendations = client.search_recommendations_by_category(category)
    
    return {
        "category": category,
        "recommendation_count": len(recommendations),
        "recommendations": recommendations
    }


# ==================== Server Modes ====================

def run_http_server(host: str = "0.0.0.0", port: int = 8000):
    """Run server with SSE transport for VS Code connectivity"""
    print(f"🚀 SparkAdvisor MCP server running on http://{host}:{port}")
    print(f"📊 Connected to Kusto: {get_kusto_client().cluster_uri}")
    print(f"🗄️  Database: {get_kusto_client().database}")
    print("\n✅ Available MCP Tools:")
    print("   1. get_application_metrics(application_id) - CALL FIRST for app profiling")
    print("   2. get_sparklens_recommendations(application_id)")
    print("   3. get_fabric_recommendations(application_id)")
    print("   4. get_scaling_predictions(application_id)")
    print("   5. get_application_metadata(application_id)")
    print("   6. get_stage_summary(application_id, stage_id=None)")
    print("   7. get_bad_practice_applications(min_violations)")
    print("   8. get_application_summary(application_id)")
    print("   9. search_recommendations_by_category(category)")
    print("\n🔗 Ready for MCP client connections via SSE")
    
    # FastMCP run is synchronous
    mcp.run(transport="sse")


def run_in_memory():
    """Run in-memory mode for notebook use"""
    print("📓 SparkAdvisor MCP server running in-memory mode (notebook)")
    print(f"📊 Connected to Kusto: {get_kusto_client().cluster_uri}")
    print(f"🗄️  Database: {get_kusto_client().database}")
    print("\n✅ Tools available as Python functions:")
    print("   - get_application_metrics(application_id) - CALL FIRST")
    print("   - get_sparklens_recommendations(application_id)")
    print("   - get_fabric_recommendations(application_id)")
    print("   - get_scaling_predictions(application_id)")
    print("   - get_application_metadata(application_id)")
    print("   - get_stage_summary(application_id, stage_id=None)")
    print("   - get_bad_practice_applications(min_violations)")
    print("   - get_application_summary(application_id)")
    print("   - search_recommendations_by_category(category)")
    
    # Return the tools for notebook use
    return {
        "get_application_metrics": get_application_metrics,
        "get_sparklens_recommendations": get_sparklens_recommendations,
        "get_fabric_recommendations": get_fabric_recommendations,
        "get_scaling_predictions": get_scaling_predictions,
        "get_application_metadata": get_application_metadata,
        "get_stage_summary": get_stage_summary,
        "get_bad_practice_applications": get_bad_practice_applications,
        "get_application_summary": get_application_summary,
        "search_recommendations_by_category": search_recommendations_by_category,
        "kusto_client": get_kusto_client()
    }


def main():
    """Main entry point with mode detection"""
    
    # Check for in_memory flag
    if "--in-memory" in sys.argv or "--notebook" in sys.argv:
        tools = run_in_memory()
        # Store in global scope for interactive use
        globals().update(tools)
        return
    
    # Parse host and port
    host = "0.0.0.0"
    port = 8000
    
    for arg in sys.argv:
        if arg.startswith("--host="):
            host = arg.split("=")[1]
        elif arg.startswith("--port="):
            port = int(arg.split("=")[1])
    
    # Run HTTP/SSE server
    run_http_server(host=host, port=port)


if __name__ == "__main__":
    main()
