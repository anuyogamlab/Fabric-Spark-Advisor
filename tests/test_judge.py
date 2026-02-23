"""
Unit tests for RecommendationJudge
"""
from agent.judge import RecommendationJudge, validate_recommendations


def test_judge_initialization():
    """Test that judge initializes without errors"""
    judge = RecommendationJudge()
    assert judge.client is not None
    assert judge.deployment is not None


def test_fallback_response():
    """Test fallback when LLM is unavailable"""
    judge = RecommendationJudge()
    
    recommendations = [
        {"text": "Test recommendation 1", "source": "kusto"},
        {"text": "Test recommendation 2", "source": "rag"},
        {"text": "Test recommendation 3", "source": "llm"}
    ]
    
    result = judge._create_fallback_response(
        "test_app",
        recommendations,
        "Test error"
    )
    
    assert result["application_id"] == "test_app"
    assert len(result["validated_recommendations"]) == 3
    assert result["overall_health"] == "warning"
    assert "error" in result


def test_prompt_building():
    """Test validation prompt construction"""
    judge = RecommendationJudge()
    
    recommendations = [
        {
            "text": "GC overhead high",
            "source": "kusto",
            "metadata": {"gc_overhead": 0.35}
        },
        {
            "text": "Enable NEE",
            "source": "rag",
            "source_url": "https://example.com"
        }
    ]
    
    context = {"duration_sec": 1200, "executor_efficiency": 0.28}
    
    prompt = judge._build_validation_prompt(
        "test_app",
        recommendations,
        context
    )
    
    assert "test_app" in prompt
    assert "GC overhead high" in prompt
    assert "Enable NEE" in prompt
    assert "Kusto Telemetry" in prompt
    assert "RAG Documentation" in prompt
    assert "duration_sec: 1200" in prompt


def test_system_prompt():
    """Test system prompt is defined"""
    judge = RecommendationJudge()
    prompt = judge._get_system_prompt()
    
    assert len(prompt) > 100
    assert "Spark" in prompt
    assert "telemetry" in prompt or "Kusto" in prompt
    assert "documentation" in prompt or "RAG" in prompt


def test_convenience_function():
    """Test the standalone validate_recommendations function"""
    recommendations = [
        {"text": "Test rec", "source": "kusto"}
    ]
    
    # This will use fallback if Azure OpenAI is not configured
    # Just ensure it doesn't crash
    try:
        result = validate_recommendations(
            "test_app",
            recommendations
        )
        assert "validated_recommendations" in result
    except Exception as e:
        # Expected if Azure OpenAI not configured
        assert "AZURE_OPENAI" in str(e) or "api_key" in str(e).lower()


if __name__ == "__main__":
    print("Running RecommendationJudge tests...")
    
    test_judge_initialization()
    print("✅ Judge initialization test passed")
    
    test_fallback_response()
    print("✅ Fallback response test passed")
    
    test_prompt_building()
    print("✅ Prompt building test passed")
    
    test_system_prompt()
    print("✅ System prompt test passed")
    
    test_convenience_function()
    print("✅ Convenience function test passed")
    
    print("\n✅ All tests passed!")
