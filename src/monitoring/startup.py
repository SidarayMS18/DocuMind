"""Startup initialization for monitoring and logging services."""

import logging
from src.config.settings import get_settings
from src.monitoring.logging_config import setup_logging
from src.monitoring.alerting import get_alerting_service, AlertLevel
from src.monitoring.metrics_collector import get_metrics_collector


logger = logging.getLogger(__name__)


def initialize_monitoring():
    """
    Initialize all monitoring services.
    
    This should be called during application startup to:
    - Configure logging
    - Start metrics collection
    - Initialize alerting service
    """
    settings = get_settings()
    
    # Setup logging
    setup_logging(
        log_dir=settings.log_directory,
        log_level=settings.log_level
    )
    logger.info("Logging configured successfully")
    
    # Initialize alerting service
    if settings.enable_alerting:
        alerting_service = get_alerting_service()
        logger.info("Alerting service initialized")
        
        # Raise startup alert
        alerting_service.raise_alert(
            level=AlertLevel.INFO,
            title="Application Started",
            message=f"{settings.app_name} v{settings.app_version} started successfully",
            source="startup",
            metadata={
                "app_name": settings.app_name,
                "app_version": settings.app_version,
                "debug": settings.debug
            }
        )
    
    # Initialize and start metrics collection
    if settings.enable_metrics_collection:
        metrics_collector = get_metrics_collector()
        metrics_collector.start_collection()
        logger.info(f"Metrics collection started (interval: {settings.metrics_collection_interval}s)")
    
    logger.info("Monitoring initialization complete")


def shutdown_monitoring():
    """
    Shutdown monitoring services gracefully.
    
    This should be called during application shutdown.
    """
    settings = get_settings()
    
    logger.info("Shutting down monitoring services...")
    
    # Stop metrics collection
    if settings.enable_metrics_collection:
        metrics_collector = get_metrics_collector()
        metrics_collector.stop_collection()
        logger.info("Metrics collection stopped")
    
    # Raise shutdown alert
    if settings.enable_alerting:
        alerting_service = get_alerting_service()
        alerting_service.raise_alert(
            level=AlertLevel.INFO,
            title="Application Shutdown",
            message=f"{settings.app_name} shutting down",
            source="shutdown"
        )
    
    logger.info("Monitoring shutdown complete")
