"""
MCP Client for communicating with local MCP server.

Supports both HTTP and Server-Sent Events (SSE) for tool invocation.
"""
import httpx
import json
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin


class MCPClient:
    """
    Client for interacting with MCP (Model Context Protocol) server.
    
    Connects to a local MCP server that exposes Spark analysis tools
    (Kusto queries, RAG search, LLM orchestration) via unified interface.
    """
    
    def __init__(
        self,
        server_url: str,
        session_id: str,
        timeout: float = 120.0
    ):
        """
        Initialize MCP client.
        
        Args:
            server_url: Base URL of MCP server (e.g., "http://127.0.0.1:8000")
            session_id: Unique session identifier for tracking
            timeout: Request timeout in seconds (default: 120)
        """
        self.server_url = server_url.rstrip("/")
        self.session_id = session_id
        self.timeout = timeout
        self._client = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy initialization of HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def call_tool(
        self,
        tool_name: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call an MCP server tool.
        
        Args:
            tool_name: Name of the tool to invoke (e.g., "analyze_application")
            parameters: Tool parameters as dictionary
        
        Returns:
            Tool execution result as dictionary
        
        Raises:
            httpx.HTTPError: If request fails
            ValueError: If server returns error response
        """
        endpoint = urljoin(self.server_url, f"/tool/{tool_name}")
        
        payload = {
            "name": tool_name,
            "arguments": parameters or {},
            "session_id": self.session_id
        }
        
        try:
            response = await self.client.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Check for error in response
            if isinstance(result, dict) and result.get("error"):
                raise ValueError(f"MCP tool error: {result['error']}")
            
            return result
            
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to call MCP tool '{tool_name}': {str(e)}")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all available tools from MCP server.
        
        Returns:
            List of tool definitions with names, descriptions, and parameters
        """
        endpoint = urljoin(self.server_url, "/tools/list")
        
        try:
            response = await self.client.get(endpoint)
            response.raise_for_status()
            return response.json().get("tools", [])
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to list MCP tools: {str(e)}")
    
    async def health_check(self) -> bool:
        """
        Check if MCP server is healthy and reachable.
        
        Returns:
            True if server is healthy, False otherwise
        """
        try:
            endpoint = urljoin(self.server_url, "/health")
            response = await self.client.get(endpoint, timeout=5.0)
            return response.status_code == 200
        except:
            return False
    
    async def close(self):
        """Close the HTTP client connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
