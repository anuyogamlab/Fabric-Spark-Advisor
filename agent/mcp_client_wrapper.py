"""
MCP Client Wrapper — routes all Kusto tool calls through the MCP SSE transport.

Architecture:
  Plugin → MCPClientWrapper._call_mcp_tool()
         → SSE http://127.0.0.1:8000/sse
         → mcp_server/server.py  @mcp.tool()
         → KustoClient → Eventhouse

RAG (search_spark_docs) and Judge (validate_recommendations) remain as direct
imports from spark_mcp_server.py because they are NOT Kusto/MCP tools.

Sync/async bridge:
  Plugin @kernel_functions are synchronous.  MCP ClientSession is async.
  A dedicated background thread runs its own event loop; sync callers submit
  coroutines via asyncio.run_coroutine_threadsafe() and block on .result().
"""
import asyncio
import json
import logging
import threading
from typing import Any, Dict, List, Optional
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# SSE endpoint of the locally-running MCP server (started by run.py on port 8000)
_MCP_SSE_URL = "http://127.0.0.1:8000/sse"

# RAG + Judge: direct imports — not in mcp_server/server.py
_parent = Path(__file__).parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

# RAG: use SparkDocRetriever directly — avoids _LEGACY_AVAILABLE dependency
try:
    from rag.retriever import SparkDocRetriever as _SparkDocRetriever
    _RAG_AVAILABLE = True
except Exception as e:
    _RAG_AVAILABLE = False
    logger.warning(f"SparkDocRetriever not available — RAG disabled ({type(e).__name__}: {e})")

try:
    from spark_mcp_server import validate_recommendations as _validate_recommendations
    _LEGACY_AVAILABLE = True
except Exception as e:
    _LEGACY_AVAILABLE = False
    logger.warning(f"spark_mcp_server not available — Judge features disabled ({type(e).__name__}: {e})")


class MCPClientWrapper:
    """
    Routes all Kusto data calls through the MCP protocol (SSE transport).

    Benefits over direct Python imports:
    - Single source of truth: mcp_server/server.py is the authoritative server
    - VS Code agent and chat backend use identical tool implementations
    - Proper MCP semantics: tool discovery, structured errors, unified logging
    - Future-proof: can point at a remote server by changing _MCP_SSE_URL
    """

    def __init__(self, server_url: str = _MCP_SSE_URL):
        self._server_url = server_url
        # Dedicated event loop in a daemon thread for sync→async bridging
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, daemon=True, name="mcp-client-loop"
        )
        self._thread.start()

    # ─────────────────────────────────────────────────────────────────────────
    # Core MCP protocol call — all Kusto tools go through here
    # ─────────────────────────────────────────────────────────────────────────

    def _call_mcp_tool(self, tool_name: str, args: dict, timeout: int = 60) -> Any:
        """Synchronously call an MCP tool via SSE transport and return parsed result."""
        future = asyncio.run_coroutine_threadsafe(
            self._async_call_tool(tool_name, args), self._loop
        )
        return future.result(timeout=timeout)

    async def _async_call_tool(self, tool_name: str, args: dict) -> Any:
        from mcp.client.sse import sse_client
        from mcp import ClientSession
        async with sse_client(self._server_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
                if result.isError:
                    err = result.content[0].text if result.content else "unknown error"
                    raise ValueError(f"MCP tool '{tool_name}' returned error: {err}")
                return json.loads(result.content[0].text)

    # ─────────────────────────────────────────────────────────────────────────
    # Kusto tools — all go through the MCP protocol
    # ─────────────────────────────────────────────────────────────────────────

    def query_to_dict_list(self, query: str) -> List[Dict[str, Any]]:
        """Execute a KQL query via execute_kql_query MCP tool → returns row list."""
        result = self._call_mcp_tool("execute_kql_query", {"query": query})
        if "error" in result:
            raise ValueError(f"KQL query failed: {result['error']}")
        return result.get("rows", [])

    def execute_dynamic_query(self, query: str, max_results: int = 100) -> List[Dict[str, Any]]:
        return self.query_to_dict_list(f"{query}\n| take {max_results}")

    def get_sparklens_recommendations(self, application_id: str) -> List[Dict[str, Any]]:
        result = self._call_mcp_tool("get_sparklens_recommendations", {"application_id": application_id})
        return result.get("recommendations", [])

    def get_spark_recommendations(self, application_id: str) -> List[Dict[str, Any]]:
        """Alias for get_sparklens_recommendations."""
        return self.get_sparklens_recommendations(application_id)

    def get_fabric_recommendations(self, application_id: str) -> List[Dict[str, Any]]:
        result = self._call_mcp_tool("get_fabric_recommendations", {"application_id": application_id})
        return result.get("recommendations", [])

    def get_application_metrics(self, application_id: str) -> Dict[str, Any]:
        result = self._call_mcp_tool("get_application_metrics", {"application_id": application_id})
        return result.get("metrics", {})

    def get_application_metadata(self, application_id: str) -> Dict[str, Any]:
        result = self._call_mcp_tool("get_application_metadata", {"application_id": application_id})
        return result.get("metadata", {})

    def get_scaling_predictions(self, application_id: str) -> List[Dict[str, Any]]:
        result = self._call_mcp_tool("get_scaling_predictions", {"application_id": application_id})
        return result.get("predictions", [])

    def get_stage_summary(self, application_id: str, stage_id: int = None) -> List[Dict[str, Any]]:
        args: Dict[str, Any] = {"application_id": application_id}
        if stage_id is not None:
            args["stage_id"] = stage_id
        result = self._call_mcp_tool("get_stage_summary", args)
        return result.get("stages", [])

    def get_bad_practice_applications(self, min_violations: int = 3) -> List[Dict[str, Any]]:
        result = self._call_mcp_tool("get_bad_practice_applications", {"min_violations": min_violations})
        return result.get("applications", [])

    def get_worst_applications(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """Alias for get_bad_practice_applications."""
        return self.get_bad_practice_applications(top_n)

    def get_application_summary(self, application_id: str) -> Dict[str, Any]:
        result = self._call_mcp_tool("get_application_summary", {"application_id": application_id})
        return result.get("summary", {})

    def get_full_application_report(self, application_id: str) -> Dict[str, Any]:
        """Alias for get_application_summary."""
        return self.get_application_summary(application_id)

    def get_application_trend(self, application_name: str, days: int = 7) -> List[Dict[str, Any]]:
        result = self._call_mcp_tool(
            "get_application_trend", {"application_name": application_name, "days": days}
        )
        return result.get("trend", [])

    def get_common_bad_patterns(self) -> List[Dict[str, Any]]:
        return self.get_bad_practice_applications(min_violations=1)

    def get_recent_applications(self, hours: int = 24) -> List[Dict[str, Any]]:
        query = f"""let TimeWindow = ago({hours}h);
sparklens_metadata
| where ingestion_time() >= TimeWindow
| distinct applicationId, applicationName, artifactId
| project app_id = applicationId, app_name = applicationName, artifact_id = artifactId
| take 100"""
        return self.query_to_dict_list(query)

    def get_database_schema(self) -> Dict[str, Any]:
        results = self.query_to_dict_list(".show tables | project TableName")
        return {"tables": [r.get("TableName", "") for r in results]}

    # ─────────────────────────────────────────────────────────────────────────
    # RAG — uses SparkDocRetriever directly (no spark_mcp_server dependency)
    # ─────────────────────────────────────────────────────────────────────────

    def search_spark_docs(
        self, query: str, top_k: int = 5, category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if not _RAG_AVAILABLE:
            logger.warning("RAG not available — SparkDocRetriever import failed")
            return []
        try:
            retriever = _SparkDocRetriever()
            return retriever.search(query, top_k=top_k, category=category)
        except Exception as e:
            logger.warning(f"RAG search failed: {e}")
            return []

    def search(self, query: str, top_k: int = 5, category: Optional[str] = None):
        return self.search_spark_docs(query, top_k, category)

    def get_context(self, query: str, top_k: int = 3, category: Optional[str] = None) -> str:
        docs = self.search_spark_docs(query, top_k, category)
        if not docs:
            return "No relevant documentation found."
        parts = []
        for doc in docs:
            src = f"Source: {doc['source_url']}" if doc.get("source_url") else ""
            cats = ", ".join(doc.get("category", [])) if doc.get("category") else "uncategorized"
            parts.append(
                f"Document: {doc['title']}\nCategories: {cats}\n{src}\n{doc['content']}"
            )
        return "\n\n---\n\n".join(parts)

    # ─────────────────────────────────────────────────────────────────────────
    # Judge — direct import (not a Kusto/MCP tool)
    # ─────────────────────────────────────────────────────────────────────────

    def validate_recommendations(
        self,
        application_id: str,
        recommendations: List[Dict[str, Any]],
        application_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not _LEGACY_AVAILABLE:
            return {"validated_recommendations": recommendations}
        recs_json = json.dumps(recommendations)
        context_json = json.dumps(application_context) if application_context else None
        result = _validate_recommendations(
            application_id=application_id,
            recommendations=recs_json,
            application_context=context_json,
        )
        return json.loads(result)

    def close(self):
        """Stop the background event loop thread."""
        self._loop.call_soon_threadsafe(self._loop.stop)


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

_mcp_client: Optional[MCPClientWrapper] = None


def get_mcp_client() -> MCPClientWrapper:
    """Get or create the singleton MCPClientWrapper instance."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClientWrapper()
    return _mcp_client
