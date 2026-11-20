"""Tests for performance monitoring and caching functionality."""

import pytest
import time
from datetime import datetime, timedelta
from src.api.performance_monitor import (
    PerformanceMonitor,
    QueryCache,
    QueryMetrics,
    get_performance_monitor,
    get_query_cache
)


class TestPerformanceMonitor:
    """Test suite for PerformanceMonitor."""
    
    def test_record_query_metrics(self):
        """Test recording query metrics."""
        monitor = PerformanceMonitor(max_history=10)
        
        metrics = QueryMetrics(
            query_id="test-1",
            query_text="What is the capital of France?",
            timestamp=datetime.now(),
            processing_time_ms=150,
            search_time_ms=50,
            llm_time_ms=100,
            total_results=5,
            cache_hit=False,
            user="test_user"
        )
        
        monitor.record_query(metrics)
        stats = monitor.get_stats()
        
        assert stats.total_queries == 1
        assert stats.avg_processing_time_ms == 150
        assert stats.cache_hit_rate == 0.0
    
    def test_cache_hit_rate_calculation(self):
        """Test cache hit rate calculation."""
        monitor = PerformanceMonitor(max_history=10)
        
        # Record 3 queries, 2 with cache hits
        for i in range(3):
            metrics = QueryMetrics(
                query_id=f"test-{i}",
                query_text=f"Query {i}",
                timestamp=datetime.now(),
                processing_time_ms=100,
                search_time_ms=50,
                llm_time_ms=50,
                total_results=5,
                cache_hit=(i < 2),  # First 2 are cache hits
                user="test_user"
            )
            monitor.record_query(metrics)
        
        stats = monitor.get_stats()
        assert stats.total_queries == 3
        assert abs(stats.cache_hit_rate - 0.6667) < 0.01  # 2/3 = 0.6667
    
    def test_slow_query_detection(self):
        """Test slow query detection and tracking."""
        monitor = PerformanceMonitor(max_history=10, slow_query_threshold_ms=1000)
        
        # Record a slow query
        slow_metrics = QueryMetrics(
            query_id="slow-1",
            query_text="Slow query",
            timestamp=datetime.now(),
            processing_time_ms=2500,
            search_time_ms=1000,
            llm_time_ms=1500,
            total_results=5,
            cache_hit=False,
            user="test_user"
        )
        monitor.record_query(slow_metrics)
        
        # Record a fast query
        fast_metrics = QueryMetrics(
            query_id="fast-1",
            query_text="Fast query",
            timestamp=datetime.now(),
            processing_time_ms=150,
            search_time_ms=50,
            llm_time_ms=100,
            total_results=5,
            cache_hit=False,
            user="test_user"
        )
        monitor.record_query(fast_metrics)
        
        stats = monitor.get_stats()
        assert stats.slow_queries_count == 1
        
        slow_queries = monitor.get_slow_queries()
        assert len(slow_queries) == 1
        assert slow_queries[0].query_id == "slow-1"
    
    def test_percentile_calculations(self):
        """Test percentile calculations for processing times."""
        monitor = PerformanceMonitor(max_history=100)
        
        # Record queries with varying processing times
        processing_times = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        for i, time_ms in enumerate(processing_times):
            metrics = QueryMetrics(
                query_id=f"test-{i}",
                query_text=f"Query {i}",
                timestamp=datetime.now(),
                processing_time_ms=time_ms,
                search_time_ms=time_ms // 2,
                llm_time_ms=time_ms // 2,
                total_results=5,
                cache_hit=False,
                user="test_user"
            )
            monitor.record_query(metrics)
        
        stats = monitor.get_stats()
        # P50 should be around the median (550 for 10 values)
        assert 500 <= stats.p50_processing_time_ms <= 600
        assert stats.p95_processing_time_ms >= 900  # 95th percentile
        assert stats.p99_processing_time_ms >= 900  # 99th percentile
    
    def test_time_window_filtering(self):
        """Test filtering metrics by time window."""
        monitor = PerformanceMonitor(max_history=100)
        
        # Record old query (10 minutes ago)
        old_metrics = QueryMetrics(
            query_id="old-1",
            query_text="Old query",
            timestamp=datetime.now() - timedelta(minutes=10),
            processing_time_ms=100,
            search_time_ms=50,
            llm_time_ms=50,
            total_results=5,
            cache_hit=False,
            user="test_user"
        )
        monitor.record_query(old_metrics)
        
        # Record recent query
        recent_metrics = QueryMetrics(
            query_id="recent-1",
            query_text="Recent query",
            timestamp=datetime.now(),
            processing_time_ms=200,
            search_time_ms=100,
            llm_time_ms=100,
            total_results=5,
            cache_hit=False,
            user="test_user"
        )
        monitor.record_query(recent_metrics)
        
        # Get stats for last 5 minutes
        stats = monitor.get_stats(time_window_minutes=5)
        assert stats.total_queries == 1  # Only recent query
        assert stats.avg_processing_time_ms == 200
    
    def test_query_breakdown(self):
        """Test query processing time breakdown."""
        monitor = PerformanceMonitor(max_history=10)
        
        metrics = QueryMetrics(
            query_id="test-1",
            query_text="Test query",
            timestamp=datetime.now(),
            processing_time_ms=300,
            search_time_ms=100,
            llm_time_ms=200,
            total_results=5,
            cache_hit=False,
            user="test_user"
        )
        monitor.record_query(metrics)
        
        breakdown = monitor.get_query_breakdown()
        assert breakdown["total_queries"] == 1
        assert breakdown["avg_search_time_ms"] == 100
        assert breakdown["avg_llm_time_ms"] == 200
        assert abs(breakdown["search_time_percentage"] - 33.33) < 1
        assert abs(breakdown["llm_time_percentage"] - 66.67) < 1


class TestQueryCache:
    """Test suite for QueryCache."""
    
    def test_cache_set_and_get(self):
        """Test basic cache set and get operations."""
        cache = QueryCache(max_size=10, ttl_seconds=60)
        
        cache.set("query1", {"result": "answer1"})
        result = cache.get("query1")
        
        assert result is not None
        assert result["result"] == "answer1"
    
    def test_cache_miss(self):
        """Test cache miss for non-existent key."""
        cache = QueryCache(max_size=10, ttl_seconds=60)
        
        result = cache.get("nonexistent")
        assert result is None
    
    def test_cache_ttl_expiration(self):
        """Test cache entry expiration based on TTL."""
        cache = QueryCache(max_size=10, ttl_seconds=1)
        
        cache.set("query1", {"result": "answer1"})
        
        # Should be available immediately
        result = cache.get("query1")
        assert result is not None
        
        # Wait for TTL to expire
        time.sleep(1.5)
        
        # Should be expired now
        result = cache.get("query1")
        assert result is None
    
    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = QueryCache(max_size=3, ttl_seconds=60)
        
        # Fill cache to capacity
        cache.set("query1", {"result": "answer1"})
        cache.set("query2", {"result": "answer2"})
        cache.set("query3", {"result": "answer3"})
        
        # Add one more, should evict oldest (query1)
        cache.set("query4", {"result": "answer4"})
        
        # query1 should be evicted
        assert cache.get("query1") is None
        
        # Others should still be present
        assert cache.get("query2") is not None
        assert cache.get("query3") is not None
        assert cache.get("query4") is not None
    
    def test_cache_access_order_update(self):
        """Test that accessing an entry updates its position in LRU order."""
        cache = QueryCache(max_size=3, ttl_seconds=60)
        
        cache.set("query1", {"result": "answer1"})
        cache.set("query2", {"result": "answer2"})
        cache.set("query3", {"result": "answer3"})
        
        # Access query1 to make it most recently used
        cache.get("query1")
        
        # Add query4, should evict query2 (oldest)
        cache.set("query4", {"result": "answer4"})
        
        # query2 should be evicted, query1 should still be present
        assert cache.get("query2") is None
        assert cache.get("query1") is not None
    
    def test_cache_invalidate(self):
        """Test cache invalidation."""
        cache = QueryCache(max_size=10, ttl_seconds=60)
        
        cache.set("query1", {"result": "answer1"})
        assert cache.get("query1") is not None
        
        cache.invalidate("query1")
        assert cache.get("query1") is None
    
    def test_cache_clear(self):
        """Test clearing all cache entries."""
        cache = QueryCache(max_size=10, ttl_seconds=60)
        
        cache.set("query1", {"result": "answer1"})
        cache.set("query2", {"result": "answer2"})
        
        cache.clear()
        
        assert cache.get("query1") is None
        assert cache.get("query2") is None
    
    def test_cache_stats(self):
        """Test cache statistics."""
        cache = QueryCache(max_size=10, ttl_seconds=60)
        
        cache.set("query1", {"result": "answer1"})
        cache.set("query2", {"result": "answer2"})
        
        # Access query1 multiple times
        cache.get("query1")
        cache.get("query1")
        
        stats = cache.get_stats()
        assert stats["total_entries"] == 2
        assert stats["max_size"] == 10
        assert stats["total_hits"] == 2
        assert stats["ttl_seconds"] == 60


class TestGlobalInstances:
    """Test global instance getters."""
    
    def test_get_performance_monitor_singleton(self):
        """Test that get_performance_monitor returns singleton instance."""
        monitor1 = get_performance_monitor()
        monitor2 = get_performance_monitor()
        
        assert monitor1 is monitor2
    
    def test_get_query_cache_singleton(self):
        """Test that get_query_cache returns singleton instance."""
        cache1 = get_query_cache()
        cache2 = get_query_cache()
        
        assert cache1 is cache2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
