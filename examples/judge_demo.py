"""
Demo: LLM Judge for Recommendation Validation
Shows how the RecommendationJudge validates and prioritizes recommendations from multiple sources
"""
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.judge import RecommendationJudge, validate_recommendations


def demo_basic_validation():
    """Basic example with recommendations from different sources"""
    print("=" * 80)
    print("DEMO: Basic Recommendation Validation")
    print("=" * 80)
    
    recommendations = [
        {
            "text": "High GC overhead (35%) detected. Increase spark.executor.memory from 4GB to 8GB to reduce memory pressure.",
            "source": "kusto",
            "metadata": {
                "gc_overhead": 0.35,
                "current_memory": "4GB",
                "executor_count": 10
            }
        },
        {
            "text": "Enable Native Execution Engine (NEE) for 2-5x performance improvement on CPU-bound workloads. Set spark.native.enabled=true",
            "source": "rag",
            "source_url": "https://learn.microsoft.com/fabric/spark/native-execution-engine"
        },
        {
            "text": "Consider using more executors to improve parallelism",
            "source": "llm"
        },
        {
            "text": "Driver overhead is 85% of runtime. Reduce executor count and run on smaller cluster to save costs.",
            "source": "kusto",
            "metadata": {
                "driver_time_pct": 85,
                "executor_time_pct": 15
            }
        }
    ]
    
    context = {
        "duration_sec": 1200,
        "executor_efficiency": 0.28,
        "gc_overhead": 0.35,
        "parallelism_score": 0.45,
        "job_type": "batch"
    }
    
    try:
        result = validate_recommendations(
            application_id="demo_app_001",
            recommendations=recommendations,
            context=context
        )
        
        print(f"\n✅ Validation Complete!")
        print(f"\nApplication: {result['application_id']}")
        print(f"Overall Health: {result['overall_health'].upper()}")
        print(f"Summary: {result['summary']}")
        print(f"\nCounts:")
        print(f"  Critical: {result['critical_count']}")
        print(f"  Warning: {result['warning_count']}")
        print(f"  Info: {result.get('info_count', 0)}")
        print(f"  Total: {result['total_recommendations']}")
        
        if result.get('detected_contradictions'):
            print(f"\n⚠️  Contradictions Detected: {len(result['detected_contradictions'])}")
            for i, contradiction in enumerate(result['detected_contradictions'], 1):
                print(f"\n  {i}. {contradiction['explanation']}")
                print(f"     Rec 1: {contradiction['recommendation_1'][:80]}...")
                print(f"     Rec 2: {contradiction['recommendation_2'][:80]}...")
        
        print(f"\n📋 Validated Recommendations (by priority):\n")
        for i, rec in enumerate(result['validated_recommendations'], 1):
            confidence_emoji = {
                "high": "🟢",
                "medium": "🟡",
                "low": "🔴"
            }.get(rec['confidence'], "⚪")
            
            source_emoji = {
                "kusto": "📊",
                "rag": "📚",
                "llm": "🤖",
                "combined": "🔄"
            }.get(rec['source'], "❓")
            
            print(f"{i}. [{rec['priority']}] {confidence_emoji} {source_emoji} {rec['source'].upper()}")
            print(f"   {rec['recommendation'][:100]}...")
            print(f"   Confidence: {rec['confidence'].upper()}")
            if rec.get('is_generic'):
                print(f"   ⚠️  Generic recommendation (not app-specific)")
            print(f"   💡 Action: {rec['action'][:80]}...")
            print(f"   Reasoning: {rec['reasoning'][:100]}...")
            print()
        
        # Save full result
        output_file = "judge_demo_output.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"📄 Full results saved to: {output_file}\n")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def demo_contradiction_detection():
    """Example with conflicting recommendations"""
    print("\n" + "=" * 80)
    print("DEMO: Contradiction Detection")
    print("=" * 80)
    
    recommendations = [
        {
            "text": "Add more executors (scale from 10 to 20) to improve parallelism and reduce job duration",
            "source": "llm"
        },
        {
            "text": "Driver-heavy workload detected (90% driver time). Scale DOWN to single-node cluster to save costs. Adding executors won't help.",
            "source": "kusto",
            "metadata": {"driver_time_pct": 90, "executor_time_pct": 10}
        },
        {
            "text": "Task skew detected (10x variation). Repartition data before scaling executors.",
            "source": "rag",
            "source_url": "https://learn.microsoft.com/fabric/spark/best-practices"
        }
    ]
    
    try:
        result = validate_recommendations(
            application_id="demo_app_002",
            recommendations=recommendations
        )
        
        print(f"\n✅ Contradiction Analysis Complete!")
        print(f"\nDetected {len(result.get('detected_contradictions', []))} contradiction(s)")
        
        if result.get('detected_contradictions'):
            for contradiction in result['detected_contradictions']:
                print(f"\n⚠️  {contradiction['explanation']}")
        
        print(f"\n📋 Judge's Resolution:\n")
        top_rec = result['validated_recommendations'][0] if result['validated_recommendations'] else None
        if top_rec:
            print(f"Priority Recommendation (#{top_rec['priority']}):")
            print(f"  {top_rec['recommendation']}")
            print(f"\n  Reasoning: {top_rec['reasoning']}")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")


def demo_from_mcp_tools():
    """Example using actual MCP tools"""
    print("\n" + "=" * 80)
    print("DEMO: Validation with Real MCP Data")
    print("=" * 80)
    
    try:
        # Import MCP tools
        from mcp_server.server import (
            get_sparklens_recommendations,
            get_fabric_recommendations
        )
        from mcp_server.kusto_client import KustoClient
        
        # Get a real application ID
        client = KustoClient()
        apps = client.query_to_dict_list("""
            fabric_recommedations 
            | distinct app_id 
            | limit 1
        """)
        
        if not apps:
            print("No applications found in database. Skipping this demo.")
            return
        
        app_id = apps[0]['app_id']
        print(f"\nAnalyzing: {app_id}\n")
        
        # Fetch recommendations from MCP
        sparklens_result = get_sparklens_recommendations(app_id)
        fabric_result = get_fabric_recommendations(app_id)
        
        # Convert to judge format
        recommendations = []
        
        for rec in sparklens_result.get('recommendations', []):
            recommendations.append({
                "text": rec.get('recommendation', ''),
                "source": "kusto",
                "metadata": {"source_table": "sparklens_recommedations"}
            })
        
        for rec in fabric_result.get('recommendations', []):
            recommendations.append({
                "text": rec.get('recommendation', ''),
                "source": "kusto",
                "metadata": {"source_table": "fabric_recommedations"}
            })
        
        if not recommendations:
            print("No recommendations found for this application.")
            return
        
        print(f"Fetched {len(recommendations)} recommendations")
        
        # Validate with judge
        result = validate_recommendations(app_id, recommendations)
        
        print(f"\n✅ Validation Complete!")
        print(f"Overall Health: {result['overall_health'].upper()}")
        print(f"Top {min(3, len(result['validated_recommendations']))} Recommendations:\n")
        
        for i, rec in enumerate(result['validated_recommendations'][:3], 1):
            print(f"{i}. [{rec['confidence'].upper()}] {rec['recommendation'][:80]}...")
            print(f"   Action: {rec['action'][:80]}...\n")
    
    except ImportError:
        print("MCP server not available in path. Skipping this demo.")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n🔍 LLM Judge Demonstration")
    print("This shows how the RecommendationJudge validates Spark recommendations\n")
    
    # Run demos
    demo_basic_validation()
    demo_contradiction_detection()
    demo_from_mcp_tools()
    
    print("\n" + "=" * 80)
    print("✅ All demos complete!")
    print("=" * 80)
    print("\n💡 Next Steps:")
    print("  1. Integrate judge into agent/orchestrator.py workflow")
    print("  2. Use validated recommendations in UI")
    print("  3. Track confidence scores in analytics")
