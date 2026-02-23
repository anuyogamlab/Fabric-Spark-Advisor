"""Check if recommendations exist for a specific application"""
from mcp_server.kusto_client import KustoClient

app_id = 'application_1771440802383_0001'
client = KustoClient()

print(f"\n🔍 Checking recommendations for: {app_id}")
print("=" * 60)

# Check SparkLens recommendations
sparklens = client.get_sparklens_recommendations(app_id)
print(f"\n📊 SparkLens Recommendations: {len(sparklens)} found")
if sparklens:
    for i, rec in enumerate(sparklens, 1):
        rec_text = rec.get('recommendation', 'N/A')
        print(f"  {i}. {rec_text[:150]}...")
else:
    print("  ❌ No SparkLens recommendations found")

# Check Fabric recommendations
fabric = client.get_fabric_recommendations(app_id)
print(f"\n🏭 Fabric Recommendations: {len(fabric)} found")
if fabric:
    for i, rec in enumerate(fabric, 1):
        rec_text = rec.get('recommendation', 'N/A')
        print(f"  {i}. {rec_text[:150]}...")
else:
    print("  ❌ No Fabric recommendations found")

# Check metrics to verify app exists
print(f"\n📈 Checking if app exists in metrics...")
metrics = client.get_application_metrics(app_id)
if 'error' in metrics:
    print(f"  ❌ App not found: {metrics['error']}")
else:
    print(f"  ✅ App exists - Duration: {metrics.get('duration_sec', 0):.1f}s, Severity: {metrics.get('severity', 'N/A')}")
