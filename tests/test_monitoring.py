"""Tests for monitoring and alerting services."""

import pytest
import time
from datetime import datetime, timedelta, timezone

from src.monitoring.alerting import AlertingService, AlertLevel, Alert
from src.monitoring.metrics_collector import MetricsCollector


class TestAlertingService:
    """Tests for AlertingService."""
    
    def test_raise_alert(self):
        """Test raising an alert."""
        service = AlertingService()
        
        alert = service.raise_alert(
            level=AlertLevel.WARNING,
            title="Test Alert",
            message="This is a test alert",
            source="test_module",
            metadata={"key": "value"}
        )
        
        assert alert is not None
        assert alert.level == AlertLevel.WARNING
        assert alert.title == "Test Alert"
        assert alert.message == "This is a test alert"
        assert alert.source == "test_module"
        assert alert.metadata["key"] == "value"
        assert not alert.resolved
    
    def test_get_active_alerts(self):
        """Test retrieving active alerts."""
        service = AlertingService()
        
        # Raise multiple alerts
        alert1 = service.raise_alert(
            AlertLevel.ERROR, "Error 1", "Message 1", "source1"
        )
        alert2 = service.raise_alert(
            AlertLevel.WARNING, "Warning 1", "Message 2", "source2"
        )
        
        # Get all active alerts
        active = service.get_active_alerts()
        assert len(active) == 2
        
        # Filter by level
        errors = service.get_active_alerts(level=AlertLevel.ERROR)
        assert len(errors) == 1
        assert errors[0].title == "Error 1"
        
        # Filter by source
        source1_alerts = service.get_active_alerts(source="source1")
        assert len(source1_alerts) == 1
        assert source1_alerts[0].source == "source1"
    
    def test_resolve_alert(self):
        """Test resolving an alert."""
        service = AlertingService()
        
        alert = service.raise_alert(
            AlertLevel.INFO, "Test", "Message", "source"
        )
        
        # Resolve the alert
        result = service.resolve_alert(alert.alert_id)
        assert result is True
        
        # Check it's no longer active
        active = service.get_active_alerts()
        assert len(active) == 0
    
    def test_alert_summary(self):
        """Test getting alert summary."""
        service = AlertingService()
        
        # Raise various alerts
        service.raise_alert(AlertLevel.ERROR, "Error 1", "Msg", "source1")
        service.raise_alert(AlertLevel.ERROR, "Error 2", "Msg", "source1")
        service.raise_alert(AlertLevel.WARNING, "Warning 1", "Msg", "source2")
        
        summary = service.get_alert_summary()
        
        assert summary["total_alerts"] == 3
        assert summary["active_alerts"] == 3
        assert summary["by_level"]["error"] == 2
        assert summary["by_level"]["warning"] == 1
        assert summary["by_source"]["source1"] == 2
        assert summary["by_source"]["source2"] == 1
    
    def test_alert_handler(self):
        """Test alert handler callback."""
        service = AlertingService()
        
        # Track handler calls
        handler_calls = []
        
        def test_handler(alert: Alert):
            handler_calls.append(alert)
        
        service.add_handler(test_handler)
        
        # Raise alert
        alert = service.raise_alert(
            AlertLevel.INFO, "Test", "Message", "source"
        )
        
        # Verify handler was called
        assert len(handler_calls) == 1
        assert handler_calls[0].alert_id == alert.alert_id


class TestMetricsCollector:
    """Tests for MetricsCollector."""
    
    def test_collect_system_metrics(self):
        """Test collecting system metrics."""
        collector = MetricsCollector()
        
        metrics = collector.collect_system_metrics()
        
        assert metrics is not None
        assert metrics.cpu_percent >= 0
        assert metrics.memory_percent >= 0
        assert metrics.disk_usage_percent >= 0
    
    def test_collect_application_metrics(self):
        """Test collecting application metrics."""
        collector = MetricsCollector()
        
        # Record some activity
        collector.increment_request()
        collector.record_response_time(100.0)
        collector.decrement_request()
        collector.increment_queries_processed()
        
        metrics = collector.collect_application_metrics()
        
        assert metrics is not None
        assert metrics.total_requests == 1
        assert metrics.active_requests == 0
        assert metrics.queries_processed == 1
    
    def test_request_counters(self):
        """Test request counter methods."""
        collector = MetricsCollector()
        
        # Increment requests
        collector.increment_request()
        collector.increment_request()
        
        metrics = collector.collect_application_metrics()
        assert metrics.active_requests == 2
        assert metrics.total_requests == 2
        
        # Decrement one
        collector.decrement_request()
        metrics = collector.collect_application_metrics()
        assert metrics.active_requests == 1
        assert metrics.total_requests == 2
    
    def test_cache_metrics(self):
        """Test cache hit/miss tracking."""
        collector = MetricsCollector()
        
        # Record cache hits and misses
        collector.record_cache_hit()
        collector.record_cache_hit()
        collector.record_cache_miss()
        
        metrics = collector.collect_application_metrics()
        
        # Cache hit rate should be 2/3 = 0.666...
        assert 0.6 < metrics.cache_hit_rate < 0.7
    
    def test_response_time_tracking(self):
        """Test response time recording."""
        collector = MetricsCollector()
        
        # Record response times
        collector.record_response_time(100.0)
        collector.record_response_time(200.0)
        collector.record_response_time(300.0)
        
        metrics = collector.collect_application_metrics()
        
        # Average should be 200ms
        assert metrics.avg_response_time_ms == 200.0
    
    def test_metrics_summary(self):
        """Test getting metrics summary."""
        collector = MetricsCollector()
        
        # Collect some metrics
        collector.collect_system_metrics()
        collector.increment_request()
        collector.collect_application_metrics()
        
        summary = collector.get_metrics_summary()
        
        assert "timestamp" in summary
        assert "system" in summary
        assert "application" in summary
        assert summary["application"]["total_requests"] == 1
    
    def test_reset_counters(self):
        """Test resetting application counters."""
        collector = MetricsCollector()
        
        # Record some activity
        collector.increment_request()
        collector.increment_queries_processed()
        collector.record_cache_hit()
        
        # Reset
        collector.reset_counters()
        
        metrics = collector.collect_application_metrics()
        assert metrics.total_requests == 0
        assert metrics.queries_processed == 0
        assert metrics.cache_hit_rate == 0.0
