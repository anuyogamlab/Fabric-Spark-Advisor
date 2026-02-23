"""Quick test to check application metrics"""
from mcp_server.kusto_client import KustoClient

app_id = 'application_1771443955490_0001'
client = KustoClient()
metrics = client.get_application_metrics(app_id)

if 'error' in metrics:
    print(f"❌ Application NOT found: {metrics['error']}")
else:
    print(f"✅ Application EXISTS: {app_id}")
    print(f"\n📊 Key Metrics:")
    print(f"   Duration: {metrics.get('duration_sec', 0):.1f} sec ({metrics.get('duration_sec', 0)/60:.1f} min)")
    print(f"   Severity: {metrics.get('severity', 'UNKNOWN')}")
    print(f"   Grade: {metrics.get('grade', 'N/A')}")
    print(f"   Efficiency: {metrics.get('executor_efficiency', 0)*100:.1f}%")
    print(f"   Driver Time: {metrics.get('driver_time_pct', 0):.1f}%")
    print(f"   GC Overhead: {metrics.get('gc_overhead', 0)*100:.1f}%")
    print(f"   Executors: {int(metrics.get('executor_count', 0))}")
    print(f"\n💡 Recommendation: Try 'are there any skews in {app_id}' or 'will scaling help {app_id}'")
