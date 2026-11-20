"""Performance monitoring and metrics tracking for the API."""

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque
from datetime import datetime, timedelta
from threading import Lock
from functools import lru_cache


@dataclass
class QueryMetrics:
    """Metrics for a single query execution."""
    query_id: str
    query_text: str
    timestamp: datetime
    processing_time_ms: int
    search_time_ms: int
    llm_time_ms: int
    total_results: int
    cache_hit: bool
    user: Optional[str] = None


@dataclass
class PerformanceStats:
    """Aggregated performance statistics."""
    total_queries: int
    avg_processing_time_ms: float
    p50_processing_time_ms: float
    p95_processing_time_ms: float
    p99_processing_time_ms: float
    cache_hit_rate: float
    queries_per_minute: float
    slow_queries_count: int  # Queries > 2000ms


class PerformanceMonitor:
    """Tracks and reports performance metrics for query processing."""
    
    def __init__(self, max_history: int = 1000, slow_query_threshold_ms: int = 2000):
        """Initialize performance monitor.
        
        Args:
            max_history: Maximum number of query metrics to keep in memory
            slow_query_threshold_ms: Threshold for identifying slow queries
        """
        self.max_history = max_history
        self.slow_query_threshold_ms = slow_query_threshold_ms
        
        # Thread-safe storage for metrics
        self._lock = Lock()
        self._query_history: deque = deque(maxlen=max_history)
        self._slow_queries: deque = deque(maxlen=100)
        
        # Counters
        self._total_queries = 0
        self._cache_hits = 0
        
        logging.info(f"Initialized PerformanceMonitor with max_history={max_history}")
    
    def record_query(self, metrics: QueryMetrics):
        """Record metrics for a query execution."""
        with self._lock:
            self._query_history.append(metrics)
            self._total_queries += 1
            
            if metrics.cache_hit:
                self._cache_hits += 1
            
            # Track slow queries
            if metrics.processing_time_ms > self.slow_query_threshold_ms:
                self._slow_queries.append(metrics)
                logging.warning(
                    f"Slow query detected: {metrics.processing_time_ms}ms "
                    f"for query '{metrics.query_text[:50]}...'"
                )
    
    def get_stats(self, time_window_minutes: Optional[int] = None) -> PerformanceStats:
        """Get aggregated performance statistics.
        
        Args:
            time_window_minutes: If specified, only include queries from the last N minutes
        
        Returns:
            PerformanceStats object with aggregated metrics
        """
        with self._lock:
            queries = list(self._query_history)
        
        # Filter by time window if specified
        if time_window_minutes:
            cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
            queries = [q for q in queries if q.timestamp >= cutoff_time]
        
        if not queries:
            return PerformanceStats(
                total_queries=0,
                avg_processing_time_ms=0.0,
                p50_processing_time_ms=0.0,
                p95_processing_time_ms=0.0,
                p99_processing_time_ms=0.0,
                cache_hit_rate=0.0,
                queries_per_minute=0.0,
                slow_queries_count=0
            )
        
        # Calculate processing time statistics
        processing_times = sorted([q.processing_time_ms for q in queries])
        total_queries = len(queries)
        
        avg_time = sum(processing_times) / total_queries
        p50_time = self._percentile(processing_times, 50)
        p95_time = self._percentile(processing_times, 95)
        p99_time = self._percentile(processing_times, 99)
        
        # Calculate cache hit rate
        cache_hits = sum(1 for q in queries if q.cache_hit)
        cache_hit_rate = cache_hits / total_queries if total_queries > 0 else 0.0
        
        # Calculate queries per minute
        if len(queries) > 1:
            time_span = (queries[-1].timestamp - queries[0].timestamp).total_seconds() / 60
            queries_per_minute = total_queries / time_span if time_span > 0 else 0.0
        else:
            queries_per_minute = 0.0
        
        # Count slow queries
        slow_queries_count = sum(
            1 for q in queries if q.processing_time_ms > self.slow_query_threshold_ms
        )
        
        return PerformanceStats(
            total_queries=total_queries,
            avg_processing_time_ms=avg_time,
            p50_processing_time_ms=p50_time,
            p95_processing_time_ms=p95_time,
            p99_processing_time_ms=p99_time,
            cache_hit_rate=cache_hit_rate,
            queries_per_minute=queries_per_minute,
            slow_queries_count=slow_queries_count
        )
    
    def get_slow_queries(self, limit: int = 10) -> List[QueryMetrics]:
        """Get the most recent slow queries.
        
        Args:
            limit: Maximum number of slow queries to return
        
        Returns:
            List of QueryMetrics for slow queries
        """
        with self._lock:
            slow_queries = list(self._slow_queries)
        
        return slow_queries[-limit:]
    
    def get_query_breakdown(self) -> Dict[str, Any]:
        """Get detailed breakdown of query processing times."""
        with self._lock:
            queries = list(self._query_history)
        
        if not queries:
            return {
                "total_queries": 0,
                "avg_search_time_ms": 0.0,
                "avg_llm_time_ms": 0.0,
                "search_time_percentage": 0.0,
                "llm_time_percentage": 0.0
            }
        
        total_search_time = sum(q.search_time_ms for q in queries)
        total_llm_time = sum(q.llm_time_ms for q in queries)
        total_processing_time = sum(q.processing_time_ms for q in queries)
        
        avg_search_time = total_search_time / len(queries)
        avg_llm_time = total_llm_time / len(queries)
        
        search_percentage = (total_search_time / total_processing_time * 100) if total_processing_time > 0 else 0
        llm_percentage = (total_llm_time / total_processing_time * 100) if total_processing_time > 0 else 0
        
        return {
            "total_queries": len(queries),
            "avg_search_time_ms": avg_search_time,
            "avg_llm_time_ms": avg_llm_time,
            "search_time_percentage": search_percentage,
            "llm_time_percentage": llm_percentage
        }
    
    def reset_stats(self):
        """Reset all performance statistics."""
        with self._lock:
            self._query_history.clear()
            self._slow_queries.clear()
            self._total_queries = 0
            self._cache_hits = 0
        
        logging.info("Performance statistics reset")
    
    @staticmethod
    def _percentile(sorted_values: List[float], percentile: int) -> float:
        """Calculate percentile from sorted values."""
        if not sorted_values:
            return 0.0
        
        index = int(len(sorted_values) * percentile / 100)
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]


class QueryCache:
    """LRU cache for query results with TTL support."""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        """Initialize query cache.
        
        Args:
            max_size: Maximum number of cached queries
            ttl_seconds: Time-to-live for cached entries in seconds
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        
        self._lock = Lock()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_order: deque = deque()
        
        logging.info(f"Initialized QueryCache with max_size={max_size}, ttl={ttl_seconds}s")
    
    def get(self, query_key: str) -> Optional[Any]:
        """Get cached result for a query.
        
        Args:
            query_key: Cache key for the query
        
        Returns:
            Cached result if found and not expired, None otherwise
        """
        with self._lock:
            if query_key not in self._cache:
                return None
            
            entry = self._cache[query_key]
            
            # Check if entry has expired
            if time.time() - entry["timestamp"] > self.ttl_seconds:
                del self._cache[query_key]
                return None
            
            # Update access order for LRU
            if query_key in self._access_order:
                self._access_order.remove(query_key)
            self._access_order.append(query_key)
            
            entry["hits"] += 1
            return entry["result"]
    
    def set(self, query_key: str, result: Any):
        """Cache a query result.
        
        Args:
            query_key: Cache key for the query
            result: Result to cache
        """
        with self._lock:
            # Evict oldest entry if cache is full
            if len(self._cache) >= self.max_size and query_key not in self._cache:
                oldest_key = self._access_order.popleft()
                del self._cache[oldest_key]
            
            # Add or update entry
            self._cache[query_key] = {
                "result": result,
                "timestamp": time.time(),
                "hits": 0
            }
            
            # Update access order
            if query_key in self._access_order:
                self._access_order.remove(query_key)
            self._access_order.append(query_key)
    
    def invalidate(self, query_key: str):
        """Invalidate a specific cache entry.
        
        Args:
            query_key: Cache key to invalidate
        """
        with self._lock:
            if query_key in self._cache:
                del self._cache[query_key]
                if query_key in self._access_order:
                    self._access_order.remove(query_key)
    
    def clear(self):
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
        
        logging.info("Query cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total_entries = len(self._cache)
            total_hits = sum(entry["hits"] for entry in self._cache.values())
            
            # Calculate average age of entries
            current_time = time.time()
            ages = [current_time - entry["timestamp"] for entry in self._cache.values()]
            avg_age_seconds = sum(ages) / len(ages) if ages else 0
            
            return {
                "total_entries": total_entries,
                "max_size": self.max_size,
                "total_hits": total_hits,
                "avg_age_seconds": avg_age_seconds,
                "ttl_seconds": self.ttl_seconds
            }


# Global instances
_performance_monitor: Optional[PerformanceMonitor] = None
_query_cache: Optional[QueryCache] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create the global performance monitor instance."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def get_query_cache() -> QueryCache:
    """Get or create the global query cache instance."""
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache()
    return _query_cache
