"""Metrics collection for system monitoring and observability."""

import logging
import psutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from collections import deque
from threading import Lock, Thread
import json


logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """System resource metrics snapshot."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_used_gb: float
    disk_free_gb: float


@dataclass
class ApplicationMetrics:
    """Application-level metrics."""
    timestamp: datetime
    active_requests: int
    total_requests: int
    error_count: int
    avg_response_time_ms: float
    cache_hit_rate: float
    documents_indexed: int
    queries_processed: int


class MetricsCollector:
    """Collects and stores system and application metrics."""
    
    def __init__(self, max_history: int = 1000, collection_interval_seconds: int = 60):
        """
        Initialize metrics collector.
        
        Args:
            max_history: Maximum number of metric snapshots to keep
            collection_interval_seconds: Interval for automatic metric collection
        """
        self.max_history = max_history
        self.collection_interval = collection_interval_seconds
        
        # Thread-safe storage
        self._lock = Lock()
        self._system_metrics: deque = deque(maxlen=max_history)
        self._app_metrics: deque = deque(maxlen=max_history)
        
        # Application counters
        self._active_requests = 0
        self._total_requests = 0
        self._error_count = 0
        self._response_times: deque = deque(maxlen=1000)
        self._cache_hits = 0
        self._cache_misses = 0
        self._documents_indexed = 0
        self._queries_processed = 0
        
        # Background collection thread
        self._collection_thread: Optional[Thread] = None
        self._collecting = False
        
        logger.info(f"Initialized MetricsCollector with max_history={max_history}")
    
    def start_collection(self):
        """Start automatic metric collection in background thread."""
        if self._collecting:
            logger.warning("Metrics collection already running")
            return
        
        self._collecting = True
        self._collection_thread = Thread(target=self._collect_loop, daemon=True)
        self._collection_thread.start()
        logger.info("Started automatic metrics collection")
    
    def stop_collection(self):
        """Stop automatic metric collection."""
        self._collecting = False
        if self._collection_thread:
            self._collection_thread.join(timeout=5)
        logger.info("Stopped automatic metrics collection")
    
    def _collect_loop(self):
        """Background loop for collecting metrics."""
        while self._collecting:
            try:
                self.collect_system_metrics()
                self.collect_application_metrics()
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
            
            time.sleep(self.collection_interval)
    
    def collect_system_metrics(self) -> SystemMetrics:
        """
        Collect current system resource metrics.
        
        Returns:
            SystemMetrics snapshot
        """
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used / (1024 * 1024)
            memory_available_mb = memory.available / (1024 * 1024)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percent = disk.percent
            disk_used_gb = disk.used / (1024 * 1024 * 1024)
            disk_free_gb = disk.free / (1024 * 1024 * 1024)
            
            metrics = SystemMetrics(
                timestamp=datetime.now(timezone.utc),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                memory_available_mb=memory_available_mb,
                disk_usage_percent=disk_usage_percent,
                disk_used_gb=disk_used_gb,
                disk_free_gb=disk_free_gb
            )
            
            with self._lock:
                self._system_metrics.append(metrics)
            
            # Log warnings for high resource usage
            if cpu_percent > 80:
                logger.warning(f"High CPU usage: {cpu_percent}%")
            if memory_percent > 85:
                logger.warning(f"High memory usage: {memory_percent}%")
            if disk_usage_percent > 90:
                logger.warning(f"High disk usage: {disk_usage_percent}%")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            raise
    
    def collect_application_metrics(self) -> ApplicationMetrics:
        """
        Collect current application metrics.
        
        Returns:
            ApplicationMetrics snapshot
        """
        with self._lock:
            # Calculate average response time
            avg_response_time = (
                sum(self._response_times) / len(self._response_times)
                if self._response_times else 0.0
            )
            
            # Calculate cache hit rate
            total_cache_requests = self._cache_hits + self._cache_misses
            cache_hit_rate = (
                self._cache_hits / total_cache_requests
                if total_cache_requests > 0 else 0.0
            )
            
            metrics = ApplicationMetrics(
                timestamp=datetime.now(timezone.utc),
                active_requests=self._active_requests,
                total_requests=self._total_requests,
                error_count=self._error_count,
                avg_response_time_ms=avg_response_time,
                cache_hit_rate=cache_hit_rate,
                documents_indexed=self._documents_indexed,
                queries_processed=self._queries_processed
            )
            
            self._app_metrics.append(metrics)
        
        return metrics
    
    # Counter methods
    
    def increment_request(self):
        """Increment active and total request counters."""
        with self._lock:
            self._active_requests += 1
            self._total_requests += 1
    
    def decrement_request(self):
        """Decrement active request counter."""
        with self._lock:
            self._active_requests = max(0, self._active_requests - 1)
    
    def record_response_time(self, response_time_ms: float):
        """Record a response time measurement."""
        with self._lock:
            self._response_times.append(response_time_ms)
    
    def increment_error(self):
        """Increment error counter."""
        with self._lock:
            self._error_count += 1
    
    def record_cache_hit(self):
        """Record a cache hit."""
        with self._lock:
            self._cache_hits += 1
    
    def record_cache_miss(self):
        """Record a cache miss."""
        with self._lock:
            self._cache_misses += 1
    
    def increment_documents_indexed(self, count: int = 1):
        """Increment documents indexed counter."""
        with self._lock:
            self._documents_indexed += count
    
    def increment_queries_processed(self, count: int = 1):
        """Increment queries processed counter."""
        with self._lock:
            self._queries_processed += count
    
    # Query methods
    
    def get_current_system_metrics(self) -> Optional[SystemMetrics]:
        """Get the most recent system metrics."""
        with self._lock:
            return self._system_metrics[-1] if self._system_metrics else None
    
    def get_current_application_metrics(self) -> Optional[ApplicationMetrics]:
        """Get the most recent application metrics."""
        with self._lock:
            return self._app_metrics[-1] if self._app_metrics else None
    
    def get_system_metrics_history(self, limit: int = 100) -> List[SystemMetrics]:
        """Get recent system metrics history."""
        with self._lock:
            return list(self._system_metrics)[-limit:]
    
    def get_application_metrics_history(self, limit: int = 100) -> List[ApplicationMetrics]:
        """Get recent application metrics history."""
        with self._lock:
            return list(self._app_metrics)[-limit:]
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive metrics summary.
        
        Returns:
            Dictionary with current and aggregated metrics
        """
        system_metrics = self.get_current_system_metrics()
        app_metrics = self.get_current_application_metrics()
        
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system": {
                "cpu_percent": system_metrics.cpu_percent if system_metrics else 0,
                "memory_percent": system_metrics.memory_percent if system_metrics else 0,
                "disk_usage_percent": system_metrics.disk_usage_percent if system_metrics else 0
            } if system_metrics else {},
            "application": {
                "active_requests": app_metrics.active_requests if app_metrics else 0,
                "total_requests": app_metrics.total_requests if app_metrics else 0,
                "error_count": app_metrics.error_count if app_metrics else 0,
                "avg_response_time_ms": app_metrics.avg_response_time_ms if app_metrics else 0,
                "cache_hit_rate": app_metrics.cache_hit_rate if app_metrics else 0,
                "documents_indexed": app_metrics.documents_indexed if app_metrics else 0,
                "queries_processed": app_metrics.queries_processed if app_metrics else 0
            } if app_metrics else {}
        }
        
        return summary
    
    def export_metrics_json(self, filepath: str):
        """
        Export metrics to JSON file.
        
        Args:
            filepath: Path to output JSON file
        """
        summary = self.get_metrics_summary()
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Exported metrics to {filepath}")
    
    def reset_counters(self):
        """Reset all application counters."""
        with self._lock:
            self._total_requests = 0
            self._error_count = 0
            self._cache_hits = 0
            self._cache_misses = 0
            self._documents_indexed = 0
            self._queries_processed = 0
            self._response_times.clear()
        
        logger.info("Reset application metrics counters")


# Global instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
