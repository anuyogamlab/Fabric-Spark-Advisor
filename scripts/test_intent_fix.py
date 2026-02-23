"""Test script to verify scaling intent detection fix."""
import re
import sys
sys.path.append(r'c:\Users\anuve\OneDrive - Microsoft\Documents\Spark Recommender MCP')

from ui.app import detect_intent

# Test queries that should trigger analyze_scaling
test_queries = [
    # Original failing query
    "application_1771446566369_0001 Will increasing executor improve perf",
    
    # Variations with -ing forms
    "application_123 increasing executors",
    "application_456 decreasing resources",
    "application_789 adding more executors",
    "application_999 will adding executors help",
    
    # Other patterns
    "application_111 will more executors improve performance",
    "application_222 can increasing resources boost performance",
    "application_333 should i increase executor count",
]

print("Testing Scaling Intent Detection\n" + "="*60)

for query in test_queries:
    result = detect_intent(query)
    intent = result.get("intent")
    params = result.get("params", {})
    
    status = "✅ PASS" if intent == "analyze_scaling" else "❌ FAIL"
    
    print(f"\nQuery: {query}")
    print(f"  {status} -> Intent: {intent} | Params: {params}")

print("\n" + "="*60)
print("Test complete!")
