"""
Spark Recommender Agent - Main Startup Script
Starts the MCP server (SSE, port 8000) and static HTML UI (port 7432).
"""
import os
import sys
import logging
import threading
import time
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging to suppress verbose Azure SDK logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Suppress verbose Azure SDK logs (keeps only WARNING and above)
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)


def start_mcp_server():
    """Start the MCP server in a background thread"""
    print("🚀 Starting MCP Server...")
    print("   Protocol: SSE (Server-Sent Events)")
    print("   Port: 8000")
    print("   URL: http://127.0.0.1:8000")
    print()
    
    try:
        # Import and run the MCP server using its built-in HTTP server
        from mcp_server.server import run_http_server
        
        # Run the SSE server (this blocks)
        run_http_server(host="127.0.0.1", port=8000)
    except Exception as e:
        print(f"❌ MCP Server failed to start: {e}")
        sys.exit(1)


def start_chat_server():
    """Serve static files + /api/chat POST endpoint on port 7432 via Starlette+uvicorn."""
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    from starlette.staticfiles import StaticFiles
    from starlette.responses import JSONResponse
    from starlette.requests import Request

    from agent.orchestrator import SparkAdvisorOrchestrator

    ui_dir = str(Path(__file__).parent / "ui")
    port = 7432

    print("\U0001f3a8 Starting Chat Server (Starlette + uvicorn)...")
    print(f"   Port: {port}")
    print(f"   URL: http://localhost:{port}/chat.html")
    print(f"   API: POST http://localhost:{port}/api/chat")
    print()

    # Single orchestrator instance — session state (chat_history) lives here
    orchestrator = SparkAdvisorOrchestrator()

    async def chat_endpoint(request: Request):
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

        message = body.get("message", "").strip()
        session_id = body.get("session_id", "default")

        if not message:
            return JSONResponse({"error": "No message provided"}, status_code=400)

        try:
            response_text = await orchestrator.chat(message, session_id=session_id)
            return JSONResponse({"response": response_text})
        except Exception as e:
            print(f"  \u274c chat() error: {e}")
            import traceback; traceback.print_exc()
            return JSONResponse({"error": str(e)}, status_code=500)

    from starlette.middleware.cors import CORSMiddleware

    routes = [
        Route("/api/chat", endpoint=chat_endpoint, methods=["POST"]),
        Mount("/", app=StaticFiles(directory=ui_dir, html=True)),
    ]

    app = Starlette(routes=routes)

    # Allow cross-origin requests from Fabric Notebooks, local dev, and any iframe
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["*"],
    )

    # Give MCP server time to start first
    time.sleep(2)

    try:
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
    except KeyboardInterrupt:
        print("\n\U0001f44b Shutting down Chat Server...")
    except Exception as e:
        print(f"\u274c Chat Server failed to start: {e}")
        sys.exit(1)


def check_environment():
    """Check if environment is properly configured"""
    print("🔍 Checking environment configuration...\n")
    
    # Check .env file
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        print("⚠️  WARNING: .env file not found!")
        print("   Copy .env.example to .env and configure your credentials.")
        print()
    
    # Check required environment variables
    required_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_DEPLOYMENT",
        "KUSTO_CLUSTER_URI",
        "KUSTO_DATABASE",
        "AZURE_SEARCH_ENDPOINT",
        "AZURE_SEARCH_KEY"
    ]
    
    from dotenv import load_dotenv
    load_dotenv()
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("⚠️  WARNING: Missing environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print()
        print("   Configure these in your .env file before running.")
        print()
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("\n👋 Exiting. Configure .env and try again.")
            sys.exit(0)
    else:
        print("✅ All environment variables configured!")
    
    print()


def print_banner():
    """Print startup banner"""
    banner = """
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║        🚀  SPARK RECOMMENDER AGENT  🚀                         ║
║                                                                ║
║    AI-Powered Spark Optimization for Microsoft Fabric         ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
"""
    print(banner)


def print_startup_complete():
    """Print startup complete message with URLs"""
    message = """
╔════════════════════════════════════════════════════════════════╗
║                    ✅  STARTUP COMPLETE!                       ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  📡 MCP Server:      http://127.0.0.1:8000                     ║
║      Protocol:       SSE (Server-Sent Events)                  ║
║      Tools:          15 skills registered                      ║
║                                                                ║
║  🎨 Spark Advisor UI: http://localhost:7432/chat.html          ║
║      Status:          Running                                  ║
║                                                                ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  💡 Quick Start:                                               ║
║     1. Open UI:     http://localhost:7432/chat.html            ║
║     2. Try:         "show top 5 slowest apps"                  ║
║     3. Analyze:     "analyze application_XXXX_XXXX"            ║
║                                                                ║
║  📚 VS Code Agent Mode:                                        ║
║     - MCP config in: .vscode/settings.json                     ║
║     - Tools available in: Copilot Chat                         ║
║                                                                ║
║  🛑 To stop: Press Ctrl+C                                      ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
"""
    print(message)


def main():
    """Main entry point"""
    print_banner()
    
    # Check environment
    check_environment()
    
    # Start MCP server in background thread
    mcp_thread = threading.Thread(target=start_mcp_server, daemon=True)
    mcp_thread.start()
    
    # Wait a moment for MCP server to start
    print("⏳ Waiting for MCP server to initialize...")
    time.sleep(3)
    
    # Print startup complete
    print_startup_complete()
    
    # Start Chat Server — static files + /api/chat endpoint (blocking)
    try:
        start_chat_server()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down Spark Recommender Agent...")
        print("   Stopping MCP server...")
        print("   Stopping Static UI...")
        print("\n✅ Goodbye!\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
