"""
Quick test script for dynamic query generation
"""
import asyncio
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

async def test_dynamic_query():
    """Test the dynamic query generation with a real query"""
    from agent.orchestrator import SparkAdvisorOrchestrator
    from mcp_server.kusto_client import KustoClient
    
    # Initialize
    print("🔧 Initializing orchestrator...")
    orchestrator = SparkAdvisorOrchestrator()
    
    # Test query
    user_question = "show me the 5 applications that took most amount of time"
    print(f"\n📝 Testing query: '{user_question}'")
    print("=" * 80)
    
    # Step 1: Check schema discovery
    print("\n1️⃣ Checking schema discovery...")
    schema = orchestrator.get_cached_schema()
    if schema:
        print(f"   ✅ Found {len(schema)} tables:")
        for table_name, columns in schema.items():
            print(f"      - {table_name} ({len(columns)} columns)")
    else:
        print("   ❌ Schema discovery failed")
        return
    
    # Step 2: Generate KQL query
    print("\n2️⃣ Generating KQL query...")
    query = await orchestrator.generate_dynamic_kql_query(user_question)
    if query:
        print(f"   ✅ Generated query:")
        print("   " + "-" * 76)
        for line in query.split("\n"):
            print(f"   {line}")
        print("   " + "-" * 76)
    else:
        print("   ❌ Query generation failed")
        return
    
    # Step 3: Validate query safety
    print("\n3️⃣ Validating query safety...")
    kusto_client = KustoClient(
        cluster_uri=os.getenv("KUSTO_CLUSTER"),
        database=os.getenv("KUSTO_DATABASE")
    )
    is_safe, error_msg = kusto_client.validate_query_safety(query)
    if is_safe:
        print(f"   ✅ Query is safe (read-only)")
    else:
        print(f"   ❌ Query validation failed: {error_msg}")
        return
    
    # Step 4: Execute query
    print("\n4️⃣ Executing query...")
    try:
        results, executed_query = await orchestrator.execute_dynamic_query(user_question)
        if results:
            print(f"   ✅ Query executed successfully!")
            print(f"   📊 Result count: {len(results)} rows")
            print("\n   Sample results (first 3 rows):")
            for i, row in enumerate(results[:3], 1):
                print(f"\n   Row {i}:")
                for key, value in row.items():
                    # Truncate long values
                    str_value = str(value)
                    if len(str_value) > 100:
                        str_value = str_value[:97] + "..."
                    print(f"      {key}: {str_value}")
        else:
            print("   ⚠️ No results returned")
    except Exception as e:
        print(f"   ❌ Execution failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("✅ Test complete!")

if __name__ == "__main__":
    asyncio.run(test_dynamic_query())
