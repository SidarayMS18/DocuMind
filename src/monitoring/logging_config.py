"""Comprehensive logging configuration for the application."""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

from src.config.settings import get_settings


def setup_logging(
    log_dir: Optional[str] = None,
    log_level: Optional[str] = None
) -> None:
    """
    Configure comprehensive application logging.
    
    Sets up multiple log handlers:
    - Console handler for stdout
    - Rotating file handler for application logs
    - Separate file handler for error logs
    - Separate file handler for audit logs
    
    Args:
        log_dir: Directory for log files (defaults to ./logs)
        log_level: Logging level (defaults to settings.log_level)
    """
    settings = get_settings()
    
    # Determine log level
    level_str = log_level or settings.log_level
    level = getattr(logging, level_str.upper(), logging.INFO)
    
    # Create log directory
    if log_dir is None:
        log_dir = "logs"
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # Application log file handler (rotating)
    app_log_file = log_path / "application.log"
    app_file_handler = logging.handlers.RotatingFileHandler(
        app_log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10,
        encoding='utf-8'
    )
    app_file_handler.setLevel(level)
    app_file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(app_file_handler)
    
    # Error log file handler (only errors and critical)
    error_log_file = log_path / "errors.log"
    error_file_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_file_handler)
    
    # Audit log handler (separate logger)
    audit_logger = logging.getLogger("audit")
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False  # Don't propagate to root logger
    
    audit_log_file = log_path / "audit.log"
    audit_file_handler = logging.handlers.RotatingFileHandler(
        audit_log_file,
        maxBytes=50 * 1024 * 1024,  # 50 MB
        backupCount=20,
        encoding='utf-8'
    )
    audit_file_handler.setLevel(logging.INFO)
    audit_formatter = logging.Formatter(
        '%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    audit_file_handler.setFormatter(audit_formatter)
    audit_logger.addHandler(audit_file_handler)
    
    # Performance log handler (separate logger)
    perf_logger = logging.getLogger("performance")
    perf_logger.setLevel(logging.INFO)
    perf_logger.propagate = False
    
    perf_log_file = log_path / "performance.log"
    perf_file_handler = logging.handlers.RotatingFileHandler(
        perf_log_file,
        maxBytes=20 * 1024 * 1024,  # 20 MB
        backupCount=10,
        encoding='utf-8'
    )
    perf_file_handler.setLevel(logging.INFO)
    perf_file_handler.setFormatter(detailed_formatter)
    perf_logger.addHandler(perf_file_handler)
    
    # Security log handler (separate logger)
    security_logger = logging.getLogger("security")
    security_logger.setLevel(logging.INFO)
    security_logger.propagate = False
    
    security_log_file = log_path / "security.log"
    security_file_handler = logging.handlers.RotatingFileHandler(
        security_log_file,
        maxBytes=20 * 1024 * 1024,  # 20 MB
        backupCount=10,
        encoding='utf-8'
    )
    security_file_handler.setLevel(logging.INFO)
    security_file_handler.setFormatter(detailed_formatter)
    security_logger.addHandler(security_file_handler)
    
    # Log startup message
    root_logger.info(f"Logging configured - Level: {level_str}, Directory: {log_path}")
    root_logger.info(f"Application: {settings.app_name} v{settings.app_version}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (typically __name__ of the module)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def get_audit_logger() -> logging.Logger:
    """Get the audit logger instance."""
    return logging.getLogger("audit")


def get_performance_logger() -> logging.Logger:
    """Get the performance logger instance."""
    return logging.getLogger("performance")


def get_security_logger() -> logging.Logger:
    """Get the security logger instance."""
    return logging.getLogger("security")
