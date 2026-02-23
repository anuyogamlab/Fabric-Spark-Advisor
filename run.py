"""
Spark Recommender Agent - Main Startup Script
Starts both the MCP server and Chainlit UI
"""
import os
import sys
import logging
import threading
import time
import subprocess
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


def start_chainlit_ui():
    """Start the Chainlit UI"""
    print("🎨 Starting Chainlit UI...")
    print("   Port: 8501")
    print("   URL: http://localhost:8501")
    print()
    
    # Give MCP server time to start
    time.sleep(2)
    
    try:
        # Run Chainlit
        ui_path = Path(__file__).parent / "ui" / "app.py"
        subprocess.run(
            ["chainlit", "run", str(ui_path), "--port", "8501"],
            check=True
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down Chainlit UI...")
    except Exception as e:
        print(f"❌ Chainlit UI failed to start: {e}")
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
║      Tools:          5 tools registered                        ║
║                                                                ║
║  🎨 Chainlit UI:     http://localhost:8501                     ║
║      Status:         Running                                   ║
║                                                                ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  💡 Quick Start:                                               ║
║     1. Open UI:     http://localhost:8501                      ║
║     2. Try:         "show bad apps"                            ║
║     3. Analyze:     "analyze application_12345"                ║
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
    
    # Start Chainlit UI (blocking)
    try:
        start_chainlit_ui()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down Spark Recommender Agent...")
        print("   Stopping MCP server...")
        print("   Stopping Chainlit UI...")
        print("\n✅ Goodbye!\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
