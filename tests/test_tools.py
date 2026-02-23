"""
Test script for SparkAdvisor MCP tools

This script demonstrates how to use the SparkAdvisor tools
both in notebook mode and via direct function calls.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mcp_server.server import (
    get_sparklens_recommendations,
    get_fabric_recommendations,
    get_bad_practice_applications,
    get_application_summary,
    search_recommendations_by_category
)


def test_get_recommendations():
    """Test getting recommendations for a specific application"""
    print("\n" + "="*80)
    print("TEST: get_sparklens_recommendations")
    print("="*80)
    
    # Replace with an actual application ID from your database
    app_id = "application_1234567890_0001"
    
    try:
        result = get_sparklens_recommendations(app_id)
        print(f"\n✅ Found {result['recommendation_count']} recommendations for {app_id}")
        
        if result['recommendations']:
            print(f"\n📋 First recommendation:")
            rec = result['recommendations'][0]
            for key, value in rec.items():
                print(f"   {key}: {value}")
    except Exception as e:
        print(f"❌ Error: {e}")


def test_get_fabric_recommendations():
    """Test getting Fabric-specific recommendations for an application"""
    print("\n" + "="*80)
    print("TEST: get_fabric_recommendations")
    print("="*80)
    
    # Replace with an actual application ID from your database
    app_id = "application_1234567890_0001"
    
    try:
        result = get_fabric_recommendations(app_id)
        print(f"\n✅ Found {result['recommendation_count']} Fabric recommendations for {app_id}")
        print(f"   Source: {result['source']}")
        
        if result['recommendations']:
            print(f"\n📋 Fabric Recommendation Preview:")
            rec = result['recommendations'][0]
            rec_text = rec.get('recommendation', 'N/A')
            # Print first 500 chars
            preview = rec_text[:500] + "..." if len(rec_text) > 500 else rec_text
            print(f"   {preview}")
    except Exception as e:
        print(f"❌ Error: {e}")


def test_bad_practice_apps():
    """Test getting applications with bad practices"""
    print("\n" + "="*80)
    print("TEST: get_bad_practice_applications")
    print("="*80)
    
    try:
        result = get_bad_practice_applications(min_violations=2)
        print(f"\n✅ Found {result['application_count']} applications with violations")
        
        if result['applications']:
            print(f"\n📋 Top 3 worst applications:")
            for i, app in enumerate(result['applications'][:3], 1):
                print(f"\n   {i}. Application: {app.get('app_id', 'N/A')}")
                print(f"      Violations: {app.get('violation_count', 0)}")
                print(f"      Issues: {app.get('issues', 'N/A')}")
    except Exception as e:
        print(f"❌ Error: {e}")


def test_application_summary():
    """Test getting application summary"""
    print("\n" + "="*80)
    print("TEST: get_application_summary")
    print("="*80)
    
    # Replace with an actual application ID
    app_id = "application_1234567890_0001"
    
    try:
        result = get_application_summary(app_id)
        summary = result['summary']
        
        print(f"\n✅ Application Summary for {app_id}")
        print(f"\n   Health Status: {summary.get('health_status', 'UNKNOWN')}")
        print(f"   Performance Grade: {summary.get('performance_grade', 'N/A')}")
        print(f"   Duration: {summary.get('duration_sec', 0):.1f}s")
        print(f"   Executor Efficiency: {summary.get('executor_efficiency', 0):.1%}")
        print(f"   GC Overhead: {summary.get('gc_overhead_pct', 0):.1f}%")
        print(f"   Task Skew Ratio: {summary.get('task_skew_ratio', 1.0):.2f}x")
    except Exception as e:
        print(f"❌ Error: {e}")


def test_search_by_category():
    """Test searching recommendations by category"""
    print("\n" + "="*80)
    print("TEST: search_recommendations_by_category")
    print("="*80)
    
    categories = ["memory", "shuffle", "cpu", "skew"]
    
    for category in categories:
        try:
            result = search_recommendations_by_category(category)
            print(f"\n✅ Category '{category}': {result['recommendation_count']} recommendations")
            
            if result['recommendations'] and result['recommendation_count'] > 0:
                rec = result['recommendations'][0]
                print(f"   Example: {rec.get('app_id', 'N/A')} - {rec.get('source', 'N/A')}")
        except Exception as e:
            print(f"❌ Category '{category}' error: {e}")


if __name__ == "__main__":
    print("\n🚀 SparkAdvisor MCP Tools Test Suite")
    print("="*80)
    
    # Run tests
    test_get_recommendations()
    test_get_fabric_recommendations()
    test_bad_practice_apps()
    test_application_summary()
    test_search_by_category()
    
    print("\n" + "="*80)
    print("✅ Test suite completed!")
    print("="*80)
