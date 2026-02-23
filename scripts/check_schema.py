"""Simple schema check using existing Kusto connection"""
from mcp_server.kusto_client import KustoClient
import os
from dotenv import load_dotenv

load_dotenv()

def check_schema():
    """Check what tables and columns are available"""
    print("🔍 Checking Kusto database schema...")
    print("=" * 80)
    
    # KustoClient reads from environment variables
    client = KustoClient()
    
    try:
        schema = client.get_database_schema()
        
        print(f"\n✅ Found {len(schema)} tables:\n")
        
        for table_name, columns in schema.items():
            print(f"📋 {table_name} ({len(columns)} columns)")
            
            # Show first 10 columns
            for col in columns[:10]:
                print(f"   - {col['name']:40} ({col['type']})")
            
            if len(columns) > 10:
                print(f"   ... and {len(columns) - 10} more columns\n")
            else:
                print()
        
        # Highlight metrics table for the test query
        if 'sparklens_metrics' in schema:
            print("=" * 80)
            print("📊 For query 'top 5 apps by time', relevant table:")
            print("\n   sparklens_metrics should contain:")
            metrics_cols = schema['sparklens_metrics']
            for col in metrics_cols:
                if col['name'] in ['app_id', 'metric', 'value']:
                    print(f"   ✅ {col['name']:20} ({col['type']})")
            
            print("\n   Expected metric name: 'Application Duration (sec)'")
        
    except Exception as e:
        print(f"❌ Schema discovery failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_schema()
