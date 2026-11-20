"""Tests for configuration settings."""

import pytest
from src.config.settings import Settings, get_settings


def test_settings_defaults():
    """Test default settings values."""
    settings = Settings()
    assert settings.app_name == "Enterprise Document Assistant"
    assert settings.app_version == "0.1.0"
    assert settings.debug is False
    assert settings.api_port == 8000
    assert settings.chunk_size_min == 500
    assert settings.chunk_size_max == 1000


def test_settings_config_methods(test_settings):
    """Test configuration helper methods."""
    azure_openai_config = test_settings.get_azure_openai_config()
    assert "azure_endpoint" in azure_openai_config
    assert azure_openai_config["azure_endpoint"] == "https://test.openai.azure.com/"
    
    storage_config = test_settings.get_azure_storage_config()
    assert "account_name" in storage_config
    assert storage_config["account_name"] == "test-storage"
    
    search_config = test_settings.get_azure_search_config()
    assert "endpoint" in search_config
    assert search_config["endpoint"] == "https://test.search.windows.net"


def test_get_settings_cached():
    """Test that get_settings returns cached instance."""
    settings1 = get_settings()
    settings2 = get_settings()
    assert settings1 is settings2