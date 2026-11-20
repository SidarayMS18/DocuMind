"""Audit logging middleware for tracking API operations."""

import logging
import time
import json
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class AuditLogger:
    """Service for logging audit events."""
    
    def __init__(self, log_file: Optional[str] = None):
        """Initialize audit logger.
        
        Args:
            log_file: Optional file path for audit logs
        """
        self.log_file = log_file
        
        # Configure audit logger
        self.audit_logger = logging.getLogger("audit")
        self.audit_logger.setLevel(logging.INFO)
        
        # Add file handler if log file specified
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            self.audit_logger.addHandler(file_handler)
    
    def log_event(self, event_type: str, event_data: Dict[str, Any]):
        """Log an audit event.
        
        Args:
            event_type: Type of event (e.g., "document_upload", "query", "auth")
            event_data: Dictionary containing event details
        """
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            **event_data
        }
        
        # Log as JSON for easy parsing
        self.audit_logger.info(json.dumps(audit_entry))
    
    def log_request(self, request_data: Dict[str, Any]):
        """Log an API request."""
        self.log_event("api_request", request_data)
    
    def log_response(self, response_data: Dict[str, Any]):
        """Log an API response."""
        self.log_event("api_response", response_data)
    
    def log_authentication(self, auth_data: Dict[str, Any]):
        """Log an authentication event."""
        self.log_event("authentication", auth_data)
    
    def log_authorization(self, authz_data: Dict[str, Any]):
        """Log an authorization event."""
        self.log_event("authorization", authz_data)
    
    def log_error(self, error_data: Dict[str, Any]):
        """Log an error event."""
        self.log_event("error", error_data)


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware to audit log all API operations."""
    
    def __init__(self, app, audit_logger: Optional[AuditLogger] = None):
        """Initialize audit middleware.
        
        Args:
            app: FastAPI application
            audit_logger: Optional AuditLogger instance
        """
        super().__init__(app)
        self.audit_logger = audit_logger or AuditLogger()
        
        # Paths to exclude from audit logging
        self.excluded_paths = {"/health", "/docs", "/redoc", "/openapi.json"}
        
        # Sensitive fields to redact from logs
        self.sensitive_fields = {"password", "token", "api_key", "secret", "authorization"}
    
    async def dispatch(self, request: Request, call_next):
        """Process request and log audit information."""
        # Skip audit logging for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        start_time = time.time()
        
        # Extract request information
        request_data = await self._extract_request_data(request)
        
        # Log request
        self.audit_logger.log_request(request_data)
        
        # Process request
        try:
            response = await call_next(request)
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Log response
            response_data = {
                "request_id": request_data.get("request_id"),
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "processing_time_ms": processing_time_ms,
                "client_id": request_data.get("client_id"),
                "user": request_data.get("user")
            }
            
            self.audit_logger.log_response(response_data)
            
            # Add audit headers to response
            response.headers["X-Request-ID"] = request_data.get("request_id", "unknown")
            response.headers["X-Processing-Time-MS"] = str(processing_time_ms)
            
            return response
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Log error
            error_data = {
                "request_id": request_data.get("request_id"),
                "method": request.method,
                "path": request.url.path,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "processing_time_ms": processing_time_ms,
                "client_id": request_data.get("client_id"),
                "user": request_data.get("user")
            }
            
            self.audit_logger.log_error(error_data)
            
            # Re-raise the exception
            raise
    
    async def _extract_request_data(self, request: Request) -> Dict[str, Any]:
        """Extract relevant data from request for audit logging.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Dictionary with request data
        """
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", self._generate_request_id())
        
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Get authenticated user if available
        user = self._get_user_from_request(request)
        
        # Extract query parameters (redact sensitive fields)
        query_params = dict(request.query_params)
        query_params = self._redact_sensitive_data(query_params)
        
        # Extract headers (redact sensitive fields)
        headers = dict(request.headers)
        headers = self._redact_sensitive_data(headers)
        
        request_data = {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "method": request.method,
            "path": request.url.path,
            "query_params": query_params,
            "client_id": client_id,
            "user": user,
            "user_agent": request.headers.get("User-Agent"),
            "content_type": request.headers.get("Content-Type")
        }
        
        return request_data
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request."""
        # Try X-Forwarded-For header
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"
    
    def _get_user_from_request(self, request: Request) -> Optional[str]:
        """Extract authenticated user from request."""
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from src.api.auth import decode_access_token
                token = auth_header.split(" ")[1]
                token_data = decode_access_token(token)
                return token_data.username
            except Exception:
                return None
        return None
    
    def _redact_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive fields from data.
        
        Args:
            data: Dictionary that may contain sensitive data
            
        Returns:
            Dictionary with sensitive fields redacted
        """
        redacted = {}
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in self.sensitive_fields):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = value
        return redacted
    
    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        import uuid
        return str(uuid.uuid4())
