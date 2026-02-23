"""
Local Spark Advisor - In-notebook execution without external MCP server.

Use this when you want to run the advisor entirely within a Fabric notebook
without requiring an external server or ngrok tunnel.
"""
import os
import sys
from typing import Optional, Dict, Any

# Add parent directory to path to import from main package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class LocalSparkAdvisor:
    """
    In-notebook Spark Advisor that runs without an external MCP server.
    
    This class directly instantiates the orchestrator, Kusto client, and RAG retriever,
    eliminating the need for a separate server process. Ideal for Fabric notebooks.
    
    Example:
        >>> import os
        >>> from notebookutils import mssparkutils
        >>> 
        >>> # Set credentials from Fabric Key Vault
        >>> os.environ["KUSTO_CLUSTER_URL"] = mssparkutils.credentials.getSecret("kv", "kusto-url")
        >>> os.environ["AZURE_OPENAI_API_KEY"] = mssparkutils.credentials.getSecret("kv", "openai-key")
        >>> # ... set other required credentials
        >>> 
        >>> # Initialize advisor
        >>> advisor = LocalSparkAdvisor()
        >>> 
        >>> # Launch UI
        >>> advisor.launch_ui()
        >>> 
        >>> # Or use programmatically
        >>> result = await advisor.analyze_application("application_123")
    """
    
    def __init__(self, session_id: str = "notebook"):
        """
        Initialize Local Spark Advisor with direct component instantiation.
        
        Args:
            session_id: Session identifier for tracking (default: "notebook")
        
        Environment Variables Required:
            - KUSTO_CLUSTER_URL: Kusto cluster URL
            - KUSTO_DATABASE: Database name
            - KUSTO_CLIENT_ID: Service principal client ID
            - KUSTO_CLIENT_SECRET: Service principal secret
            - KUSTO_TENANT_ID: Azure AD tenant ID
            - AZURE_SEARCH_ENDPOINT: Azure AI Search endpoint
            - AZURE_SEARCH_KEY: Azure AI Search key
            - AZURE_SEARCH_INDEX: Index name (optional, default: spark-docs)
            - AZURE_OPENAI_ENDPOINT: Azure OpenAI endpoint
            - AZURE_OPENAI_API_KEY: Azure OpenAI key
            - AZURE_OPENAI_DEPLOYMENT: Deployment name (optional, default: gpt-4o)
            - AZURE_OPENAI_API_VERSION: API version (optional, default: 2024-02-01)
        
        Raises:
            ValueError: If required environment variables are missing
        """
        self._validate_environment()
        
        # Import components (lazy import to avoid import errors if not using this mode)
        try:
            from agent.orchestrator import SparkOrchestrator
            from rag.retriever import AzureSearchRetriever
            from tools.kusto_connector import KustoClient
        except ImportError as e:
            raise ImportError(
                "Failed to import required components. "
                "Make sure you have the full package installed with all dependencies. "
                f"Error: {e}"
            )
        
        # Initialize Kusto client
        print("🔌 Connecting to Kusto...")
        self.kusto_client = KustoClient(
            cluster_url=os.getenv("KUSTO_CLUSTER_URL"),
            database=os.getenv("KUSTO_DATABASE"),
            client_id=os.getenv("KUSTO_CLIENT_ID"),
            client_secret=os.getenv("KUSTO_CLIENT_SECRET"),
            tenant_id=os.getenv("KUSTO_TENANT_ID")
        )
        
        # Initialize RAG retriever
        print("📚 Connecting to Azure AI Search...")
        self.rag_retriever = AzureSearchRetriever(
            endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            api_key=os.getenv("AZURE_SEARCH_KEY"),
            index_name=os.getenv("AZURE_SEARCH_INDEX", "spark-docs")
        )
        
        # Initialize orchestrator
        print("🤖 Initializing AI orchestrator...")
        self.orchestrator = SparkOrchestrator(
            kusto_client=self.kusto_client,
            retriever=self.rag_retriever,
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_openai_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
        )
        
        self.session_id = session_id
        print(f"✅ Local Spark Advisor initialized (session: {session_id})")
    
    def _validate_environment(self):
        """Validate that all required environment variables are set."""
        required_vars = [
            "KUSTO_CLUSTER_URL",
            "KUSTO_DATABASE",
            "KUSTO_CLIENT_ID",
            "KUSTO_CLIENT_SECRET",
            "KUSTO_TENANT_ID",
            "AZURE_SEARCH_ENDPOINT",
            "AZURE_SEARCH_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_API_KEY",
        ]
        
        missing = [var for var in required_vars if not os.getenv(var)]
        
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}\\n\\n"
                "In Fabric notebooks, set these using:\\n"
                "  from notebookutils import mssparkutils\\n"
                "  os.environ['VAR_NAME'] = mssparkutils.credentials.getSecret('keyvault', 'secret-name')"
            )
    
    async def analyze_application(self, app_id: str) -> Dict[str, Any]:
        """
        Analyze a Spark application with full 3-tier validation.
        
        Args:
            app_id: Application ID (e.g., "application_1771446566369_0001")
        
        Returns:
            Dict with analysis results including:
                - overall_health: Health status (EXCELLENT/GOOD/FAIR/POOR)
                - summary: Executive summary
                - validated_recommendations: List of recommendations from Kusto/RAG/LLM
                - source_counts: Count of recommendations by source
        """
        print(f"🔍 Analyzing application: {app_id}")
        return await self.orchestrator.analyze_application(app_id, self.session_id)
    
    async def analyze_skew(self, app_id: str) -> str:
        """
        Analyze task and shuffle skew for an application.
        
        Args:
            app_id: Application ID
        
        Returns:
            Formatted skew analysis report
        """
        print(f"📊 Analyzing skew for: {app_id}")
        return await self.orchestrator.analyze_skew(app_id, self.session_id)
    
    async def analyze_scaling(self, app_id: str) -> str:
        """
        Analyze scaling impact (what-if analysis for adding executors).
        
        Args:
            app_id: Application ID
        
        Returns:
            Formatted scaling analysis report with cost-benefit analysis
        """
        print(f"📈 Analyzing scaling impact for: {app_id}")
        return await self.orchestrator.analyze_scaling_impact(app_id, self.session_id)
    
    async def chat(self, message: str) -> str:
        """
        Free-form conversational interface with query routing.
        
        Args:
            message: User message (e.g., "show me top 5 slowest apps")
        
        Returns:
            Formatted response (may include KQL queries, RAG docs, LLM analysis)
        """
        return await self.orchestrator.chat(message, self.session_id)
    
    def launch_ui(
        self,
        inline: bool = True,
        share: bool = False,
        server_port: Optional[int] = None
    ):
        """
        Launch Gradio chat interface.
        
        Args:
            inline: Display inline in notebook (default: True for Fabric notebooks)
            share: Create public share link (default: False)
            server_port: Port number (default: auto-assign)
        
        Returns:
            Gradio interface object
        """
        print("🚀 Launching Gradio UI...")
        
        # Import Gradio interface creator
        try:
            from ui.gradio_app import create_gradio_interface
        except ImportError:
            raise ImportError(
                "Gradio interface not available. "
                "Install with: pip install gradio"
            )
        
        # Create interface bound to this orchestrator
        interface = create_gradio_interface(
            orchestrator=self.orchestrator,
            session_id=self.session_id
        )
        
        # Launch with appropriate settings
        launch_kwargs = {
            "inline": inline,
            "share": share,
        }
        
        if server_port:
            launch_kwargs["server_port"] = server_port
        
        return interface.launch(**launch_kwargs)
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get session statistics.
        
        Returns:
            Dict with session info:
                - session_id: Current session ID
                - messages: Number of messages
                - current_app_id: Currently analyzed app (if any)
        """
        session = self.orchestrator.sessions.get(self.session_id, {})
        return {
            "session_id": self.session_id,
            "messages": len(session.get("messages", [])),
            "current_app_id": session.get("current_app_id"),
            "last_updated": session.get("last_updated"),
        }
