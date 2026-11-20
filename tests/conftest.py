"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.config.settings import Settings
from src.api.performance_monitor import get_query_cache
from src.api.rate_limiter import get_rate_limiter_middleware


@pytest.fixture(autouse=True)
def reset_test_state():
    """Reset test state before each test."""
    # Clear query cache
    cache = get_query_cache()
    cache.clear()
    
    # Reset rate limiter
    rate_limiter_middleware = get_rate_limiter_middleware()
    if rate_limiter_middleware and hasattr(rate_limiter_middleware, 'rate_limiter'):
        rate_limiter_middleware.rate_limiter.reset()
    
    yield
    
    # Cleanup after test
    cache.clear()


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def test_settings():
    """Create test settings."""
    return Settings(
        debug=True,
        azure_openai_endpoint="https://test.openai.azure.com/",
        azure_openai_api_key="test-key",
        azure_storage_account_name="test-storage",
        azure_storage_account_key="test-key",
        azure_search_endpoint="https://test.search.windows.net",
        azure_search_api_key="test-key"
    )


@pytest.fixture
def sample_pdf_bytes():
    """Sample PDF file content for testing."""
    # This would be replaced with actual PDF bytes in real tests
    return b"sample pdf content"