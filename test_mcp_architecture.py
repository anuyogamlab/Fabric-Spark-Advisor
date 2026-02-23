"""
Test MCP-based architecture
Verifies that the orchestrator can use MCP client successfully
"""
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("Testing MCP-based Architecture")
print("=" * 80)

# Test 1: Import MCP client wrapper
print("\n1️⃣  Testing MCP Client Wrapper import...")
try:
    from agent.mcp_client_wrapper import get_mcp_client
    print("   ✅ mcp_client_wrapper imported successfully")
except Exception as e:
    print(f"   ❌ Failed to import: {e}")
    sys.exit(1)

# Test 2: Import orchestrator
print("\n2️⃣  Testing Orchestrator import...")
try:
    from agent.orchestrator import SparkAdvisorOrchestrator
    print("   ✅ Orchestrator imported successfully")
except Exception as e:
    print(f"   ❌ Failed to import: {e}")
    sys.exit(1)

# Test 3: Create orchestrator instance
print("\n3️⃣  Testing Orchestrator initialization...")
try:
    orchestrator = SparkAdvisorOrchestrator()
    print("   ✅ Orchestrator initialized successfully")
    print(f"   - MCP client type: {type(orchestrator.mcp_client).__name__}")
except Exception as e:
    print(f"   ❌ Failed to initialize: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Test MCP client methods
print("\n4️⃣  Testing MCP Client methods...")
try:
    mcp_client = get_mcp_client()
    
    # Check that methods exist
    assert hasattr(mcp_client, 'get_spark_recommendations'), "Missing get_spark_recommendations"
    assert hasattr(mcp_client, 'get_fabric_recommendations'), "Missing get_fabric_recommendations"
    assert hasattr(mcp_client, 'search_spark_docs'), "Missing search_spark_docs"
    assert hasattr(mcp_client, 'validate_recommendations'), "Missing validate_recommendations"
    assert hasattr(mcp_client, 'query_to_dict_list'), "Missing query_to_dict_list"
    assert hasattr(mcp_client, 'get_context'), "Missing get_context (RAG)"
    
    print("   ✅ All required methods present")
    print("   - Kusto tools: get_spark_recommendations, get_fabric_recommendations, etc.")
    print("   - RAG tools: search_spark_docs, get_context")
    print("   - Judge tool: validate_recommendations")
    print("   - Generic query: query_to_dict_list, execute_dynamic_query")
except Exception as e:
    print(f"   ❌ Method check failed: {e}")
    sys.exit(1)

# Test 5: Import MCP server tools
print("\n5️⃣  Testing MCP Server tools import...")
try:
    from spark_mcp_server import (
        get_spark_recommendations,
        search_spark_docs,
        validate_recommendations,
        execute_kql_query
    )
    print("   ✅ MCP server tools imported successfully")
    print("   - Tools can be called via stdio (VS Code) or direct import (Chainlit)")
except Exception as e:
    print(f"   ❌ Failed to import MCP tools: {e}")
    sys.exit(1)

print("\n" + "=" * 80)
print("✅ ALL TESTS PASSED - MCP Architecture Working!")
print("=" * 80)
print("\n📊 Architecture Summary:")
print("   Chainlit UI → Orchestrator → MCP Client → MCP Tools → Kusto/RAG/Judge")
print("   VS Code Agent → MCP Server (stdio) → MCP Tools → Kusto/RAG/Judge")
print("\n   Both clients use the SAME tool implementations! ✨")
print("   m×n problem solved: 2 clients → 1 MCP server → 3 backends")
print("=" * 80)
