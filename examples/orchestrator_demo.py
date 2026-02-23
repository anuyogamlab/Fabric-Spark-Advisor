"""
Orchestrator Demo
Demonstrates the SparkAdvisorOrchestrator agent in action
"""
import asyncio
import json
from agent.orchestrator import SparkAdvisorOrchestrator, analyze_spark_application


async def demo_1_analyze_application():
    """Demo 1: Analyze a specific Spark application"""
    print("=" * 80)
    print("DEMO 1: Full Application Analysis Pipeline")
    print("=" * 80)
    
    orchestrator = SparkAdvisorOrchestrator()
    
    # Analyze a real application from Kusto
    # You can change this to any application_id from your Kusto database
    app_id = "application_1771438258399_0001"
    
    result = await orchestrator.analyze_application(app_id)
    
    # Display results
    print("\n" + "=" * 80)
    print("ANALYSIS RESULTS")
    print("=" * 80)
    print(f"\nApplication: {result.get('application_id', 'unknown')}")
    print(f"Overall Health: {result.get('overall_health', 'unknown').upper()}")
    print(f"Summary: {result.get('summary', 'N/A')}")
    
    print(f"\n📊 Source Breakdown:")
    sources = result.get('source_counts', {})
    print(f"  - Kusto (Telemetry): {sources.get('kusto', 0)} recommendations")
    print(f"  - RAG (Documentation): {sources.get('rag', 0)} recommendations")
    print(f"  - LLM (Generated): {sources.get('llm', 0)} recommendations")
    
    # Show validated recommendations
    recs = result.get('validated_recommendations', [])
    print(f"\n✅ Validated Recommendations ({len(recs)} total):")
    
    # Group by confidence
    high = [r for r in recs if r.get('confidence', '').lower() == 'high']
    medium = [r for r in recs if r.get('confidence', '').lower() == 'medium']
    low = [r for r in recs if r.get('confidence', '').lower() == 'low']
    
    print(f"\n  🟢 HIGH Confidence: {len(high)}")
    for rec in high[:3]:  # Show top 3
        print(f"     - {rec.get('recommendation', rec.get('text', ''))[:100]}...")
    
    print(f"\n  🟡 MEDIUM Confidence: {len(medium)}")
    for rec in medium[:2]:  # Show top 2
        print(f"     - {rec.get('recommendation', rec.get('text', ''))[:100]}...")
    
    print(f"\n  🔴 LOW Confidence: {len(low)}")
    
    # Show contradictions if any
    contradictions = result.get('detected_contradictions', [])
    if contradictions:
        print(f"\n⚠️  Contradictions Detected: {len(contradictions)}")
        for c in contradictions:
            print(f"  - {c.get('explanation', 'Unknown conflict')}")
    
    # Save detailed results
    output_file = "orchestrator_analysis_output.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n📄 Full results saved to: {output_file}")


async def demo_2_find_bad_applications():
    """Demo 2: Find applications with bad practices"""
    print("\n\n" + "=" * 80)
    print("DEMO 2: Find Applications with Bad Practices")
    print("=" * 80)
    
    orchestrator = SparkAdvisorOrchestrator()
    
    # Find apps with at least 3 violations
    bad_apps = orchestrator.find_bad_applications(min_violations=3)
    
    if not bad_apps:
        print("\n✅ No applications found with significant bad practices!")
        return
    
    print(f"\nFound {len(bad_apps)} applications:\n")
    
    for i, app in enumerate(bad_apps[:5], 1):  # Show top 5
        app_id = app.get('application_id', 'unknown')
        violations = app.get('violation_count', 0)
        severity = app.get('severity_label', '')
        explanation = app.get('brief_explanation', '')
        
        print(f"{i}. {severity} {app_id}")
        print(f"   Violations: {violations}")
        print(f"   {explanation}\n")
    
    if len(bad_apps) > 5:
        print(f"... and {len(bad_apps) - 5} more applications")


async def demo_3_chat_interface():
    """Demo 3: Interactive chat with the orchestrator"""
    print("\n\n" + "=" * 80)
    print("DEMO 3: Chat Interface")
    print("=" * 80)
    
    orchestrator = SparkAdvisorOrchestrator()
    
    # Simulate a conversation
    conversations = [
        "What are common causes of high GC overhead in Spark?",
        "How can I optimize Delta Lake table maintenance?",
        "Should I increase executor memory if GC overhead is 35%?",
    ]
    
    print("\n💬 Starting conversation with SparkAdvisor...\n")
    
    for user_msg in conversations:
        print(f"👤 User: {user_msg}")
        response = await orchestrator.chat(user_msg)
        print(f"🤖 SparkAdvisor: {response[:300]}...")  # Truncate for readability
        print()
    
    # Now try triggering automatic analysis
    print("\n👤 User: Analyze application_1771438258399_0001")
    response = await orchestrator.chat("analyze application_1771438258399_0001")
    print(f"🤖 SparkAdvisor:\n{response}\n")
    
    # Ask about bad applications
    print("\n👤 User: Show me applications with bad practices")
    response = await orchestrator.chat("show me bad practice applications")
    print(f"🤖 SparkAdvisor:\n{response[:500]}...\n")


async def demo_4_convenience_function():
    """Demo 4: Using the convenience function"""
    print("\n\n" + "=" * 80)
    print("DEMO 4: Convenience Function")
    print("=" * 80)
    
    print("\nUsing analyze_spark_application() convenience function...")
    
    result = await analyze_spark_application("application_1771438258399_0001")
    
    print(f"\n✅ Analysis complete!")
    print(f"   Health: {result.get('overall_health', 'unknown')}")
    print(f"   Recommendations: {len(result.get('validated_recommendations', []))}")
    print(f"   Sources used: {list(result.get('source_counts', {}).keys())}")


async def main():
    """Run all demos"""
    print("\n🚀 SparkAdvisor Orchestrator Demo\n")
    print("This demonstrates the full pipeline:")
    print("  1. Kusto telemetry → Sparklens + Fabric recommendations")
    print("  2. RAG documentation search")
    print("  3. LLM fallback generation")
    print("  4. Judge validation and prioritization")
    print("  5. Interactive chat interface")
    
    try:
        # Run each demo
        await demo_1_analyze_application()
        await demo_2_find_bad_applications()
        await demo_3_chat_interface()
        await demo_4_convenience_function()
        
        print("\n\n" + "=" * 80)
        print("✅ All demos complete!")
        print("=" * 80)
        print("\n💡 Next Steps:")
        print("  1. Integrate orchestrator into Chainlit UI (ui/app.py)")
        print("  2. Add persistent chat history storage")
        print("  3. Implement feedback loops for judge improvements")
        print("  4. Create Jupyter notebook for data scientists")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
