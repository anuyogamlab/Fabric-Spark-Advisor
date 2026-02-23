"""
MCP Client Wrapper for Orchestrator
Provides a clean interface to call MCP tools from the orchestrator.
"""
import json
from typing import Any, Dict, List, Optional

# Import MCP tools directly (they're decorated functions that can be called)
# This avoids subprocess overhead while maintaining single source of truth
import sys
from pathlib import Path

# Add parent directory to path to import spark_mcp_server
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Import MCP server tools
from spark_mcp_server import (
    get_spark_recommendations,
    get_worst_applications,
    get_full_application_report,
    get_common_bad_patterns,
    search_spark_docs,
    validate_recommendations,
    execute_kql_query
)


class MCPClientWrapper:
    """
    Wrapper for MCP server tools.
    
    This provides a clean interface for the orchestrator to call MCP tools.
    Instead of subprocess communication, we import the tool functions directly.
    
    Why this works:
    - MCP tools are just Python functions decorated with @mcp_server.tool()
    - The decorator makes them callable both via MCP protocol AND as regular functions
    - This maintains single source of truth (one implementation in spark_mcp_server.py)
    - Both VS Code agent (via stdio) and orchestrator (via direct import) use same code
    - Solves m×n problem: 2 clients → 1 MCP server implementation → 3 backends
    """
    
    def __init__(self):
        """Initialize MCP client wrapper."""
        pass
    
    # ==================== Kusto Tools ====================
    
    def get_spark_recommendations(self, application_id: str) -> List[Dict[str, Any]]:
        """Get SparkLens recommendations for an application."""
        result = get_spark_recommendations(application_id)
        return json.loads(result)
    
    def get_worst_applications(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """Get worst performing applications by violation count."""
        result = get_worst_applications(top_n)
        return json.loads(result)
    
    def get_full_application_report(self, application_id: str) -> Dict[str, Any]:
        """Get full health report for an application."""
        result = get_full_application_report(application_id)
        return json.loads(result)
    
    def get_common_bad_patterns(self) -> List[Dict[str, Any]]:
        """Get most common bad patterns across all applications."""
        result = get_common_bad_patterns()
        return json.loads(result)
    
    # Generic query execution (for methods not yet in MCP tools)
    def query_to_dict_list(self, query: str) -> List[Dict[str, Any]]:
        """Execute a generic KQL query and return results as list of dicts."""
        result = execute_kql_query(query)
        data = json.loads(result)
        if isinstance(data, dict) and "error" in data:
            raise ValueError(f"Query execution failed: {data['error']}")
        return data
    
    def execute_dynamic_query(self, query: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """Execute a dynamic query with result limiting."""
        limited_query = f"{query}\n| take {max_results}"
        return self.query_to_dict_list(limited_query)
    
    # Additional Kusto methods built on execute_kql_query
    def get_sparklens_recommendations(self, application_id: str) -> List[Dict[str, Any]]:
        """Get SparkLens recommendations (same as get_spark_recommendations)."""
        return self.get_spark_recommendations(application_id)
    
    def get_fabric_recommendations(self, application_id: str) -> List[Dict[str, Any]]:
        """Get Fabric-specific recommendations for an application."""
        query = f"""
        fabric_recommedations
        | where app_id == '{application_id}'
        | project app_id, recommendation, ingestion_time()
        """
        return self.query_to_dict_list(query)
    
    def get_application_summary(self, application_id: str) -> Dict[str, Any]:
        """Get application summary metrics."""
        result = get_full_application_report(application_id)
        data = json.loads(result)
        # Return a simplified summary from the full report
        return {
            "app_id": application_id,
            "recommendations_count": len(data.get("recommendations", [])),
            "fabric_recommendations_count": len(data.get("fabric_recommendations", [])),
            "has_summary": len(data.get("summary", [])) > 0,
            "has_predictions": len(data.get("predictions", [])) > 0,
        }
    
    def get_bad_practice_applications(self, min_violations: int = 3) -> List[Dict[str, Any]]:
        """Get applications with bad practices."""
        return self.get_worst_applications(min_violations)
    
    def get_recent_applications(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get applications from recent hours."""
        query = f"""
        let TimeWindow = ago({hours}h);
        sparklens_metadata
        | where ingestion_time() >= TimeWindow
        | distinct applicationId, applicationName, artifactId
        | project app_id = applicationId, app_name = applicationName, artifact_id = artifactId
        | take 100
        """
        return self.query_to_dict_list(query)
    
    def get_stage_summary(self, application_id: str, stage_id: int = None) -> List[Dict[str, Any]]:
        """Get stage-level summary for an application."""
        if stage_id is not None:
            query = f"""
            sparklens_summary
            | where applicationId == '{application_id}' and stageId == {stage_id}
            | project applicationId, stageId, taskCount, duration, inputBytes, outputBytes
            """
        else:
            query = f"""
            sparklens_summary
            | where applicationId == '{application_id}'
            | project applicationId, stageId, taskCount, duration, inputBytes, outputBytes
            | order by duration desc
            """
        return self.query_to_dict_list(query)
    
    def get_scaling_predictions(self, application_id: str) -> List[Dict[str, Any]]:
        """Get scaling predictions for an application."""
        query = f"""
        sparklens_predictions
        | where app_id == '{application_id}'
        | project app_id, ["Executor Multiplier"], duration, cores_per_executor
        | order by ["Executor Multiplier"] asc
        """
        return self.query_to_dict_list(query)
    
    def get_application_metrics(self, application_id: str) -> Dict[str, Any]:
        """Get key metrics for an application."""
        query = f"""
        sparklens_metrics
        | where app_id == '{application_id}'
        | summarize arg_max(value, *) by metric
        | project metric, value
        """
        results = self.query_to_dict_list(query)
        # Convert list of metric/value pairs to dict
        return {r["metric"]: r["value"] for r in results}
    
    def get_application_metadata(self, application_id: str) -> Dict[str, Any]:
        """Get application metadata."""
        query = f"""
        sparklens_metadata
        | where applicationId == '{application_id}'
        | take 1
        """
        results = self.query_to_dict_list(query)
        return results[0] if results else {}
    
    def get_database_schema(self) -> Dict[str, Any]:
        """Get database schema information."""
        query = """
        .show tables
        | project TableName
        """
        results = self.query_to_dict_list(query)
        return {"tables": [r["TableName"] for r in results]}
    
    # Aliased methods for compatibility
    def search(self, query: str, top_k: int = 5, category: Optional[str] = None):
        """Alias for search_spark_docs (RAG compatibility)."""
        return self.search_spark_docs(query, top_k, category)
    
    # ==================== RAG Tool ====================
    
    def search_spark_docs(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search Spark documentation using RAG.
        
        Args:
            query: Search query text
            top_k: Number of results to return (default: 5)
            category: Optional category filter
        
        Returns:
            List of matching documents with content, title, category, source_url, score
        """
        result = search_spark_docs(query, top_k, category)
        return json.loads(result)
    
    def get_context(
        self,
        query: str,
        top_k: int = 3,
        category: Optional[str] = None
    ) -> str:
        """
        Get formatted context string for RAG.
        
        Args:
            query: Search query
            top_k: Number of documents to retrieve
            category: Optional category filter
        
        Returns:
            Formatted context string
        """
        docs = self.search_spark_docs(query, top_k, category)
        
        if not docs:
            return "No relevant documentation found."
        
        context_parts = []
        for doc in docs:
            source_info = f"Source: {doc['source_url']}" if doc.get('source_url') else ""
            categories = ", ".join(doc.get('category', [])) if doc.get('category') else "uncategorized"
            
            context_parts.append(
                f"Document: {doc['title']}\n"
                f"Categories: {categories}\n"
                f"{source_info}\n"
                f"{doc['content']}"
            )
        
        return "\n\n---\n\n".join(context_parts)
    
    # ==================== LLM Judge Tool ====================
    
    def validate_recommendations(
        self,
        application_id: str,
        recommendations: List[Dict[str, Any]],
        application_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate and prioritize recommendations using LLM judge.
        
        Args:
            application_id: Spark application ID
            recommendations: List of dicts with keys: {text, source, metadata}
                            where source is "kusto" | "rag" | "llm"
            application_context: Optional dict with app metrics
        
        Returns:
            Dict with validated_recommendations, summary, health scores, contradictions
        """
        # Convert to JSON strings for MCP tool
        recs_json = json.dumps(recommendations)
        context_json = json.dumps(application_context) if application_context else None
        
        result = validate_recommendations(
            application_id=application_id,
            recommendations=recs_json,
            application_context=context_json
        )
        
        return json.loads(result)
    
    def close(self):
        """Close connections (no-op for direct import approach)."""
        pass


# Singleton instance for easy import
_mcp_client = None


def get_mcp_client() -> MCPClientWrapper:
    """Get or create singleton MCP client instance."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClientWrapper()
    return _mcp_client
