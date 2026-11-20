"""Application settings and configuration management."""

from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application settings
    app_name: str = Field(default="Enterprise Document Assistant", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    
    # API settings
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_workers: int = Field(default=1, description="Number of API workers")
    
    # Azure OpenAI settings
    azure_openai_endpoint: Optional[str] = Field(default=None, description="Azure OpenAI endpoint")
    azure_openai_api_key: Optional[str] = Field(default=None, description="Azure OpenAI API key")
    azure_openai_api_version: str = Field(default="2023-12-01-preview", description="Azure OpenAI API version")
    azure_openai_deployment_name: Optional[str] = Field(default=None, description="Azure OpenAI deployment name")
    azure_openai_embedding_deployment: Optional[str] = Field(default=None, description="Azure OpenAI embedding deployment")
    
    # Azure Storage settings
    azure_storage_account_name: Optional[str] = Field(default=None, description="Azure Storage account name")
    azure_storage_account_key: Optional[str] = Field(default=None, description="Azure Storage account key")
    azure_storage_container_name: str = Field(default="documents", description="Azure Storage container name")
    
    # Azure AI Search settings
    azure_search_endpoint: Optional[str] = Field(default=None, description="Azure AI Search endpoint")
    azure_search_api_key: Optional[str] = Field(default=None, description="Azure AI Search API key")
    azure_search_index_name: str = Field(default="document-index", description="Azure AI Search index name")
    
    # Document processing settings
    chunk_size_min: int = Field(default=500, description="Minimum chunk size in tokens")
    chunk_size_max: int = Field(default=1000, description="Maximum chunk size in tokens")
    chunk_overlap: int = Field(default=100, description="Overlap between chunks in tokens")
    
    # Search settings
    max_search_results: int = Field(default=10, description="Maximum number of search results")
    similarity_threshold: float = Field(default=0.7, description="Minimum similarity threshold for results")
    
    # Security settings
    secret_key: str = Field(default="your-secret-key-change-in-production", description="Secret key for JWT")
    access_token_expire_minutes: int = Field(default=30, description="Access token expiration time in minutes")
    
    # Logging settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Log format")
    log_directory: str = Field(default="logs", description="Directory for log files")
    
    # Performance settings
    max_file_size_mb: int = Field(default=50, description="Maximum file size in MB")
    request_timeout_seconds: int = Field(default=30, description="Request timeout in seconds")
    
    # Monitoring settings
    enable_metrics_collection: bool = Field(default=True, description="Enable automatic metrics collection")
    metrics_collection_interval: int = Field(default=60, description="Metrics collection interval in seconds")
    enable_alerting: bool = Field(default=True, description="Enable alerting service")
    alert_suppression_window: int = Field(default=300, description="Alert suppression window in seconds")
    
    def get_azure_openai_config(self) -> dict:
        """Get Azure OpenAI configuration dictionary."""
        return {
            "azure_endpoint": self.azure_openai_endpoint,
            "api_key": self.azure_openai_api_key,
            "api_version": self.azure_openai_api_version,
            "azure_deployment": self.azure_openai_deployment_name,
        }
    
    def get_azure_storage_config(self) -> dict:
        """Get Azure Storage configuration dictionary."""
        return {
            "account_name": self.azure_storage_account_name,
            "account_key": self.azure_storage_account_key,
            "container_name": self.azure_storage_container_name,
        }
    
    def get_azure_search_config(self) -> dict:
        """Get Azure AI Search configuration dictionary."""
        return {
            "endpoint": self.azure_search_endpoint,
            "api_key": self.azure_search_api_key,
            "index_name": self.azure_search_index_name,
        }


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()