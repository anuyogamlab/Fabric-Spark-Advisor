"""
Pytest configuration and shared fixtures.

This module provides common fixtures and configuration for all tests.
"""
import pytest
import asyncio
from typing import Generator, Dict, Any
from unittest.mock import Mock, AsyncMock


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_kusto_client():
    """Mock Kusto client for testing."""
    client = Mock()
    client.get_application_summary = Mock(return_value={
        "app_id": "application_test_001",
        "app_name": "Test Application",
        "start_time": "2024-01-01T00:00:00Z",
        "end_time": "2024-01-01T01:00:00Z"
    })
    client.get_application_metrics = Mock(return_value=[
        {"metric": "Application Duration (sec)", "value": 300.0},
        {"metric": "Executor Efficiency", "value": 0.75},
        {"metric": "Driver Time %", "value": 15.0}
    ])
    client.get_spark_recommendations = Mock(return_value=[])
    client.get_fabric_recommendations = Mock(return_value=[])
    return client


@pytest.fixture
def mock_rag_retriever():
    """Mock RAG retriever for testing."""
    retriever = Mock()
    retriever.search = AsyncMock(return_value=[
        {
            "text": "Test RAG document content",
            "metadata": {
                "title": "Test Document",
                "source_url": "https://example.com/docs"
            }
        }
    ])
    return retriever


@pytest.fixture
def mock_openai_service():
    """Mock Azure OpenAI service for testing."""
    service = AsyncMock()
    service.get_chat_message_content = AsyncMock(
        return_value=Mock(content="Test LLM response")
    )
    return service


@pytest.fixture
def sample_application_data() -> Dict[str, Any]:
    """Sample application data for testing."""
    return {
        "app_id": "application_1771438258399_0001",
        "app_name": "TestSparkApp",
        "duration_sec": 300.0,
        "executor_efficiency": 0.75,
        "driver_time_pct": 15.0,
        "gc_overhead": 0.10,
        "task_skew_ratio": 2.5
    }


@pytest.fixture
def sample_recommendations() -> list:
    """Sample recommendations for testing."""
    return [
        {
            "recommendation": "Increase executor memory to 8GB",
            "severity": "HIGH",
            "category": "Memory",
            "source": "kusto",
            "priority": 10
        },
        {
            "recommendation": "Use VOrder for Delta tables",
            "severity": "MEDIUM",
            "category": "Optimization",
            "source": "rag",
            "priority": 20
        }
    ]


@pytest.fixture
def sample_scaling_predictions() -> list:
    """Sample scaling predictions for testing."""
    return [
        {"executor_count": 1, "duration_sec": 300.0},
        {"executor_count": 2, "duration_sec": 180.0},
        {"executor_count": 4, "duration_sec": 120.0},
        {"executor_count": 8, "duration_sec": 110.0}
    ]


@pytest.fixture
def sample_skew_data() -> list:
    """Sample skew analysis data for testing."""
    return [
        {
            "stage_id": 1,
            "task_imbalance": 5.2,
            "shuffle_imbalance": 3.1,
            "stage_duration_sec": 120.0,
            "severity": "HIGH"
        },
        {
            "stage_id": 2,
            "task_imbalance": 12.5,
            "shuffle_imbalance": 8.3,
            "stage_duration_sec": 180.0,
            "severity": "CRITICAL"
        }
    ]


# Test configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: unit tests")
    config.addinivalue_line("markers", "integration: integration tests")
    config.addinivalue_line("markers", "slow: slow running tests")
