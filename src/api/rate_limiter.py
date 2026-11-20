"""Rate limiting middleware for API protection."""

import logging
import time
from collections import defaultdict
from typing import Dict, Tuple
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Global rate limiter middleware instance for testing
_rate_limiter_middleware_instance = None


class RateLimiter:
    """Simple in-memory rate limiter using sliding window algorithm."""
    
    def __init__(self, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        """Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute per client
            requests_per_hour: Maximum requests per hour per client
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        
        # Store request timestamps: {client_id: [timestamp1, timestamp2, ...]}
        self.request_history: Dict[str, list[float]] = defaultdict(list)
        
        # Cleanup interval (seconds)
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
    
    def _cleanup_old_requests(self):
        """Remove old request records to prevent memory growth."""
        current_time = time.time()
        
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        # Remove requests older than 1 hour
        cutoff_time = current_time - 3600
        
        for client_id in list(self.request_history.keys()):
            self.request_history[client_id] = [
                ts for ts in self.request_history[client_id]
                if ts > cutoff_time
            ]
            
            # Remove empty entries
            if not self.request_history[client_id]:
                del self.request_history[client_id]
        
        self.last_cleanup = current_time
        logger.debug(f"Rate limiter cleanup completed. Active clients: {len(self.request_history)}")
    
    def check_rate_limit(self, client_id: str) -> Tuple[bool, Dict[str, int]]:
        """Check if client has exceeded rate limits.
        
        Args:
            client_id: Unique identifier for the client (IP address or user ID)
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
            - is_allowed: True if request is allowed, False if rate limit exceeded
            - rate_limit_info: Dictionary with rate limit details
        """
        current_time = time.time()
        
        # Periodic cleanup
        self._cleanup_old_requests()
        
        # Get request history for this client
        timestamps = self.request_history[client_id]
        
        # Count requests in the last minute
        minute_ago = current_time - 60
        requests_last_minute = sum(1 for ts in timestamps if ts > minute_ago)
        
        # Count requests in the last hour
        hour_ago = current_time - 3600
        requests_last_hour = sum(1 for ts in timestamps if ts > hour_ago)
        
        # Check limits
        minute_exceeded = requests_last_minute >= self.requests_per_minute
        hour_exceeded = requests_last_hour >= self.requests_per_hour
        
        rate_limit_info = {
            "requests_last_minute": requests_last_minute,
            "requests_last_hour": requests_last_hour,
            "limit_per_minute": self.requests_per_minute,
            "limit_per_hour": self.requests_per_hour,
            "minute_remaining": max(0, self.requests_per_minute - requests_last_minute),
            "hour_remaining": max(0, self.requests_per_hour - requests_last_hour)
        }
        
        if minute_exceeded:
            logger.warning(f"Rate limit exceeded for {client_id}: {requests_last_minute} requests in last minute")
            return False, rate_limit_info
        
        if hour_exceeded:
            logger.warning(f"Rate limit exceeded for {client_id}: {requests_last_hour} requests in last hour")
            return False, rate_limit_info
        
        # Record this request
        timestamps.append(current_time)
        
        return True, rate_limit_info
    
    def reset_client(self, client_id: str):
        """Reset rate limit for a specific client."""
        if client_id in self.request_history:
            del self.request_history[client_id]
            logger.info(f"Rate limit reset for client: {client_id}")
    
    def reset(self):
        """Reset all rate limit data."""
        self.request_history.clear()
        self.last_cleanup = time.time()
        logger.info("Rate limiter reset - all client data cleared")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limiting on API requests."""
    
    def __init__(self, app, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        """Initialize rate limit middleware.
        
        Args:
            app: FastAPI application
            requests_per_minute: Maximum requests per minute per client
            requests_per_hour: Maximum requests per hour per client
        """
        super().__init__(app)
        self.rate_limiter = RateLimiter(requests_per_minute, requests_per_hour)
        
        # Paths to exclude from rate limiting (e.g., health checks)
        self.excluded_paths = {"/health", "/docs", "/redoc", "/openapi.json"}
        
        # Store instance globally for testing
        global _rate_limiter_middleware_instance
        _rate_limiter_middleware_instance = self
    
    async def dispatch(self, request: Request, call_next):
        """Process request and enforce rate limiting."""
        # Skip rate limiting for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Get client identifier (IP address or authenticated user)
        client_id = self._get_client_id(request)
        
        # Check rate limit
        is_allowed, rate_limit_info = self.rate_limiter.check_rate_limit(client_id)
        
        if not is_allowed:
            # Calculate retry-after time
            retry_after = 60  # Default to 1 minute
            
            logger.warning(f"Rate limit exceeded for {client_id} on {request.url.path}")
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please try again later.",
                        "details": {
                            "retry_after_seconds": retry_after,
                            "requests_last_minute": rate_limit_info["requests_last_minute"],
                            "limit_per_minute": rate_limit_info["limit_per_minute"]
                        }
                    }
                },
                headers={"Retry-After": str(retry_after)}
            )
        
        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit-Minute"] = str(rate_limit_info["limit_per_minute"])
        response.headers["X-RateLimit-Remaining-Minute"] = str(rate_limit_info["minute_remaining"])
        response.headers["X-RateLimit-Limit-Hour"] = str(rate_limit_info["limit_per_hour"])
        response.headers["X-RateLimit-Remaining-Hour"] = str(rate_limit_info["hour_remaining"])
        
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """Get unique client identifier from request.
        
        Priority:
        1. Authenticated user ID (from JWT token)
        2. X-Forwarded-For header (for proxied requests)
        3. Client IP address
        
        Args:
            request: FastAPI request object
            
        Returns:
            Unique client identifier string
        """
        # Try to get authenticated user
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from src.api.auth import decode_access_token
                token = auth_header.split(" ")[1]
                token_data = decode_access_token(token)
                return f"user:{token_data.username}"
            except Exception:
                pass  # Fall back to IP-based identification
        
        # Try X-Forwarded-For header (for proxied requests)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            client_ip = forwarded_for.split(",")[0].strip()
            return f"ip:{client_ip}"
        
        # Fall back to direct client IP
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"


def get_rate_limiter_middleware():
    """Get the global rate limiter middleware instance for testing."""
    return _rate_limiter_middleware_instance
