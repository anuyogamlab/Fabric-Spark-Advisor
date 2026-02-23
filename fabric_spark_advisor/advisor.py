"""
Main SparkAdvisor class - Entry point for notebook interface.
"""
import uuid
from typing import Optional, Dict, Any
from .client.mcp_client import MCPClient
from .ui.gradio_app import create_gradio_interface


class SparkAdvisor:
    """
    Fabric Spark Advisor - AI-powered Spark performance analysis.
    
    This class provides a clean notebook interface that connects to a local
    MCP server for unified tool routing (M+N architecture).
    
    Example:
        >>> advisor = SparkAdvisor(mcp_server_url="http://127.0.0.1:8000")
        >>> advisor.launch()  # Opens Gradio chat interface
        
        >>> # Or use programmatically:
        >>> result = await advisor.analyze_application("application_123")
    """
    
    def __init__(
        self,
        mcp_server_url: str = "http://127.0.0.1:8000",
        theme: str = "dark",
        session_id: Optional[str] = None
    ):
        """
        Initialize Spark Advisor with MCP server connection.
        
        Args:
            mcp_server_url: URL of MCP server. Can be:
                - Local: http://127.0.0.1:8000
                - ngrok: https://abc123.ngrok-free.app
                - Azure: https://spark-advisor.eastus.azurecontainerapps.io
            theme: UI theme ("dark" or "light", default: "dark")
            session_id: Optional session ID for tracking (auto-generated if not provided)
        
        Examples:
            >>> # ngrok tunnel
            >>> advisor = SparkAdvisor("https://abc123.ngrok-free.app")
            
            >>> # Azure Container Apps
            >>> advisor = SparkAdvisor("https://spark-advisor.eastus.azurecontainerapps.io")
        """
        self.mcp_client = MCPClient(
            server_url=mcp_server_url,
            session_id=session_id or f"notebook-{uuid.uuid4().hex[:8]}"
        )
        self.theme = theme
        self._gradio_interface = None
    
    def launch(
        self,
        inline: bool = True,
        share: bool = False,
        server_port: Optional[int] = None,
        height: int = 700
    ):
        """
        Launch Gradio chat interface for interactive querying.
        
        Args:
            inline: Show interface inline in notebook (default: True)
            share: Create public shareable link (default: False)
            server_port: Custom port for Gradio server (default: auto-assign)
            height: Height of chat interface in pixels (default: 700)
        
        Returns:
            Gradio app instance
        """
        if self._gradio_interface is None:
            self._gradio_interface = create_gradio_interface(
                mcp_client=self.mcp_client,
                theme=self.theme,
                chatbot_height=height
            )
        
        return self._gradio_interface.launch(
            inline=inline,
            share=share,
            server_port=server_port,
            quiet=True
        )
    
    async def analyze_application(self, application_id: str) -> Dict[str, Any]:
        """
        Analyze a Spark application programmatically (without UI).
        
        Args:
            application_id: The Spark application ID to analyze
        
        Returns:
            Dictionary containing analysis results with recommendations
        """
        return await self.mcp_client.call_tool(
            "analyze_application",
            {"application_id": application_id}
        )
    
    async def analyze_scaling(self, application_id: str) -> Dict[str, Any]:
        """
        Analyze scaling impact for a specific application.
        
        Args:
            application_id: The Spark application ID
        
        Returns:
            Dictionary with scaling recommendations and predictions
        """
        return await self.mcp_client.call_tool(
            "analyze_scaling_impact",
            {"application_id": application_id}
        )
    
    async def analyze_skew(self, application_id: str) -> Dict[str, Any]:
        """
        Analyze data skew for a specific application.
        
        Args:
            application_id: The Spark application ID
        
        Returns:
            Dictionary with skew analysis and stage-level recommendations
        """
        return await self.mcp_client.call_tool(
            "analyze_skew",
            {"application_id": application_id}
        )
    
    async def query(self, query_text: str) -> Dict[str, Any]:
        """
        Execute a natural language query against the knowledge base.
        
        Args:
            query_text: Natural language query
        
        Returns:
            Dictionary with query results
        """
        return await self.mcp_client.call_tool(
            "chat",
            {"message": query_text}
        )
    
    def close(self):
        """Close the Gradio interface if running."""
        if self._gradio_interface is not None:
            self._gradio_interface.close()
