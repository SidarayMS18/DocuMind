"""Alerting service for system errors and performance issues."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
from collections import defaultdict, deque
from threading import Lock


logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Represents a system alert."""
    alert_id: str
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class AlertingService:
    """Service for managing system alerts and notifications."""
    
    def __init__(self, max_alerts: int = 1000):
        """
        Initialize alerting service.
        
        Args:
            max_alerts: Maximum number of alerts to keep in memory
        """
        self.max_alerts = max_alerts
        
        # Thread-safe storage
        self._lock = Lock()
        self._alerts: deque = deque(maxlen=max_alerts)
        self._alert_counts: Dict[str, int] = defaultdict(int)
        self._last_alert_time: Dict[str, datetime] = {}
        
        # Alert handlers (callbacks)
        self._handlers: List[Callable[[Alert], None]] = []
        
        # Alert suppression settings
        self._suppression_window_seconds = 300  # 5 minutes
        self._max_alerts_per_window = 10
        
        logger.info(f"Initialized AlertingService with max_alerts={max_alerts}")
    
    def add_handler(self, handler: Callable[[Alert], None]):
        """
        Add a handler function to be called when alerts are raised.
        
        Args:
            handler: Callback function that takes an Alert object
        """
        self._handlers.append(handler)
        logger.info(f"Added alert handler: {handler.__name__}")
    
    def raise_alert(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Alert:
        """
        Raise a new alert.
        
        Args:
            level: Alert severity level
            title: Short alert title
            message: Detailed alert message
            source: Source component that raised the alert
            metadata: Optional additional metadata
        
        Returns:
            Created Alert object
        """
        # Check if alert should be suppressed
        alert_key = f"{source}:{title}"
        if self._should_suppress_alert(alert_key):
            logger.debug(f"Alert suppressed: {alert_key}")
            return None
        
        # Create alert
        alert = Alert(
            alert_id=self._generate_alert_id(),
            level=level,
            title=title,
            message=message,
            timestamp=datetime.now(timezone.utc),
            source=source,
            metadata=metadata or {}
        )
        
        # Store alert
        with self._lock:
            self._alerts.append(alert)
            self._alert_counts[alert_key] += 1
            self._last_alert_time[alert_key] = alert.timestamp
        
        # Log alert
        log_level = self._get_log_level(level)
        logger.log(
            log_level,
            f"Alert raised: [{level.value.upper()}] {title} - {message} (source: {source})"
        )
        
        # Call handlers
        for handler in self._handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Error in alert handler {handler.__name__}: {e}")
        
        return alert
    
    def resolve_alert(self, alert_id: str) -> bool:
        """
        Mark an alert as resolved.
        
        Args:
            alert_id: ID of the alert to resolve
        
        Returns:
            True if alert was found and resolved
        """
        with self._lock:
            for alert in self._alerts:
                if alert.alert_id == alert_id and not alert.resolved:
                    alert.resolved = True
                    alert.resolved_at = datetime.now(timezone.utc)
                    logger.info(f"Alert resolved: {alert_id}")
                    return True
        return False
    
    def get_active_alerts(
        self,
        level: Optional[AlertLevel] = None,
        source: Optional[str] = None
    ) -> List[Alert]:
        """
        Get all active (unresolved) alerts.
        
        Args:
            level: Optional filter by alert level
            source: Optional filter by source
        
        Returns:
            List of active alerts
        """
        with self._lock:
            alerts = [a for a in self._alerts if not a.resolved]
        
        # Apply filters
        if level:
            alerts = [a for a in alerts if a.level == level]
        if source:
            alerts = [a for a in alerts if a.source == source]
        
        return alerts
    
    def get_recent_alerts(
        self,
        hours: int = 24,
        level: Optional[AlertLevel] = None
    ) -> List[Alert]:
        """
        Get alerts from the last N hours.
        
        Args:
            hours: Number of hours to look back
            level: Optional filter by alert level
        
        Returns:
            List of recent alerts
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        with self._lock:
            alerts = [a for a in self._alerts if a.timestamp >= cutoff_time]
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        return alerts
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics of alerts.
        
        Returns:
            Dictionary with alert statistics
        """
        with self._lock:
            alerts = list(self._alerts)
        
        total_alerts = len(alerts)
        active_alerts = sum(1 for a in alerts if not a.resolved)
        
        # Count by level
        level_counts = defaultdict(int)
        for alert in alerts:
            level_counts[alert.level.value] += 1
        
        # Count by source
        source_counts = defaultdict(int)
        for alert in alerts:
            source_counts[alert.source] += 1
        
        # Recent alerts (last hour)
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_alerts = sum(1 for a in alerts if a.timestamp >= recent_cutoff)
        
        return {
            "total_alerts": total_alerts,
            "active_alerts": active_alerts,
            "resolved_alerts": total_alerts - active_alerts,
            "recent_alerts_1h": recent_alerts,
            "by_level": dict(level_counts),
            "by_source": dict(source_counts)
        }
    
    def clear_resolved_alerts(self, older_than_hours: int = 24):
        """
        Clear resolved alerts older than specified hours.
        
        Args:
            older_than_hours: Remove resolved alerts older than this many hours
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        
        with self._lock:
            # Keep only unresolved alerts or recently resolved ones
            self._alerts = deque(
                (a for a in self._alerts if not a.resolved or a.resolved_at >= cutoff_time),
                maxlen=self.max_alerts
            )
        
        logger.info(f"Cleared resolved alerts older than {older_than_hours} hours")
    
    def _should_suppress_alert(self, alert_key: str) -> bool:
        """
        Check if an alert should be suppressed based on rate limiting.
        
        Args:
            alert_key: Unique key for the alert type
        
        Returns:
            True if alert should be suppressed
        """
        with self._lock:
            # Check if we've seen this alert recently
            if alert_key not in self._last_alert_time:
                return False
            
            last_time = self._last_alert_time[alert_key]
            time_since_last = (datetime.now(timezone.utc) - last_time).total_seconds()
            
            # If within suppression window, check count
            if time_since_last < self._suppression_window_seconds:
                count = self._alert_counts.get(alert_key, 0)
                if count >= self._max_alerts_per_window:
                    return True
            else:
                # Reset count if outside window
                self._alert_counts[alert_key] = 0
        
        return False
    
    @staticmethod
    def _generate_alert_id() -> str:
        """Generate a unique alert ID."""
        import uuid
        return str(uuid.uuid4())
    
    @staticmethod
    def _get_log_level(alert_level: AlertLevel) -> int:
        """Convert alert level to logging level."""
        mapping = {
            AlertLevel.INFO: logging.INFO,
            AlertLevel.WARNING: logging.WARNING,
            AlertLevel.ERROR: logging.ERROR,
            AlertLevel.CRITICAL: logging.CRITICAL
        }
        return mapping.get(alert_level, logging.INFO)


# Alert handler implementations

def log_alert_handler(alert: Alert):
    """Handler that logs alerts to the security logger."""
    security_logger = logging.getLogger("security")
    log_level = AlertingService._get_log_level(alert.level)
    security_logger.log(
        log_level,
        f"ALERT: [{alert.level.value.upper()}] {alert.title} - {alert.message} "
        f"(source: {alert.source}, id: {alert.alert_id})"
    )


def console_alert_handler(alert: Alert):
    """Handler that prints critical alerts to console."""
    if alert.level in (AlertLevel.ERROR, AlertLevel.CRITICAL):
        print(f"\n{'='*80}")
        print(f"ALERT: {alert.level.value.upper()}")
        print(f"Title: {alert.title}")
        print(f"Message: {alert.message}")
        print(f"Source: {alert.source}")
        print(f"Time: {alert.timestamp}")
        print(f"{'='*80}\n")


# Global instance
_alerting_service: Optional[AlertingService] = None


def get_alerting_service() -> AlertingService:
    """Get or create the global alerting service instance."""
    global _alerting_service
    if _alerting_service is None:
        _alerting_service = AlertingService()
        # Add default handlers
        _alerting_service.add_handler(log_alert_handler)
        _alerting_service.add_handler(console_alert_handler)
    return _alerting_service
