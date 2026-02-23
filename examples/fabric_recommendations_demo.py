"""
Demo: Using Fabric Recommendations

This example shows how to retrieve and analyze Microsoft Fabric-specific 
optimization recommendations for Spark applications.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mcp_server.kusto_client import KustoClient
from mcp_server.server import get_fabric_recommendations


def demo_fabric_recommendations():
    """
    Demonstrate retrieving Fabric-specific recommendations.
    
    Fabric recommendations include:
    - Native Execution Engine (NEE) enablement
    - High Concurrency mode optimization
    - Delta Lake best practices (Auto Compaction, V-Order, etc.)
    - Resource Profile recommendations
    - Cost optimization suggestions
    """
    print("="*80)
    print("FABRIC RECOMMENDATIONS DEMO")
    print("="*80)
    
    # Example 1: Get recommendations via MCP tool
    print("\n1️⃣  Using MCP Tool: get_fabric_recommendations()")
    print("-" * 80)
    
    app_id = "application_1234567890_0001"  # Replace with actual app ID
    
    try:
        result = get_fabric_recommendations(app_id)
        
        print(f"\nApplication: {result['application_id']}")
        print(f"Source: {result['source']}")
        print(f"Recommendation Count: {result['recommendation_count']}")
        
        if result['recommendations']:
            for i, rec in enumerate(result['recommendations'], 1):
                print(f"\n--- Recommendation {i} ---")
                rec_text = rec.get('recommendation', 'N/A')
                print(rec_text)
                print("-" * 80)
        else:
            print("\nNo Fabric recommendations found for this application.")
            print("This could mean:")
            print("  - Application hasn't been analyzed yet")
            print("  - No Fabric-specific optimizations needed")
            print("  - Application is already well-configured")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Ensure the application ID exists in the database")
        print("  2. Check that the analyzer has run and written fabric_recommedations")
        print("  3. Verify Kusto connection credentials")
    
    # Example 2: Direct Kusto query
    print("\n\n2️⃣  Using Kusto Client Directly")
    print("-" * 80)
    
    try:
        client = KustoClient()
        
        # Query all Fabric recommendations
        query = """
        fabric_recommedations
        | summarize 
            app_count = dcount(app_id),
            total_recommendations = count()
        """
        
        result = client.query_to_dict_list(query)
        if result:
            stats = result[0]
            print(f"\nDatabase Statistics:")
            print(f"  Applications with Fabric recommendations: {stats.get('app_count', 0)}")
            print(f"  Total Fabric recommendation records: {stats.get('total_recommendations', 0)}")
    
    except Exception as e:
        print(f"\n❌ Error querying stats: {e}")
    
    # Example 3: Search Fabric recommendations by pattern
    print("\n\n3️⃣  Searching for Specific Fabric Features")
    print("-" * 80)
    
    features = [
        ("NEE", "Native Execution Engine"),
        ("V-Order", "V-Order optimization"),
        ("Auto Compaction", "Delta table maintenance"),
        ("Resource Profile", "Compute resource configuration")
    ]
    
    try:
        client = KustoClient()
        
        for search_term, description in features:
            query = f"""
            fabric_recommedations
            | where recommendation has '{search_term}'
            | summarize app_count = dcount(app_id)
            """
            
            result = client.query_to_dict_list(query)
            if result:
                count = result[0].get('app_count', 0)
                print(f"\n  {description}:")
                print(f"    Applications: {count}")
    
    except Exception as e:
        print(f"\n❌ Error searching features: {e}")
    
    print("\n" + "="*80)
    print("DEMO COMPLETE")
    print("="*80)


def demo_combined_recommendations():
    """
    Show how to combine Sparklens and Fabric recommendations for a complete picture.
    """
    print("\n\n" + "="*80)
    print("COMBINED RECOMMENDATIONS DEMO")
    print("="*80)
    
    app_id = "application_1234567890_0001"  # Replace with actual app ID
    
    try:
        from mcp_server.server import get_sparklens_recommendations
        
        print(f"\nAnalyzing application: {app_id}\n")
        
        # Get both types of recommendations
        sparklens_result = get_sparklens_recommendations(app_id)
        fabric_result = get_fabric_recommendations(app_id)
        
        print("📊 RECOMMENDATION SUMMARY")
        print("-" * 80)
        print(f"Sparklens (Performance): {sparklens_result['recommendation_count']} recommendations")
        print(f"Fabric (Infrastructure): {fabric_result['recommendation_count']} recommendations")
        
        print("\n\n🔍 ANALYSIS BREAKDOWN")
        print("="*80)
        
        print("\n1. PERFORMANCE OPTIMIZATIONS (Sparklens)")
        print("-" * 80)
        if sparklens_result['recommendations']:
            for rec in sparklens_result['recommendations'][:3]:  # Show first 3
                print(f"\n{rec.get('recommendation', 'N/A')}\n")
        else:
            print("No performance issues detected ✅")
        
        print("\n2. INFRASTRUCTURE OPTIMIZATIONS (Fabric)")
        print("-" * 80)
        if fabric_result['recommendations']:
            for rec in fabric_result['recommendations']:
                print(f"\n{rec.get('recommendation', 'N/A')}\n")
        else:
            print("No Fabric configuration changes needed ✅")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    print("\n🌟 Fabric Recommendations Demo")
    print("This script demonstrates Fabric-specific optimization recommendations\n")
    
    # Run demos
    demo_fabric_recommendations()
    demo_combined_recommendations()
    
    print("\n\n💡 NEXT STEPS:")
    print("  1. Run the analyzer on your Spark applications")
    print("  2. Query fabric_recommedations table in Kusto")
    print("  3. Use the MCP server to integrate recommendations into your workflow")
    print("  4. Apply Fabric-specific optimizations to improve performance and cost")
