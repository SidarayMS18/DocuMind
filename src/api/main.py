"""Main FastAPI application entry point."""

from fastapi import FastAPI, HTTPException, UploadFile, File, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import timedelta, datetime
import uvicorn
import logging
import uuid
import time
import io

from src.config.settings import get_settings
from src.processing.document_processor import DocumentProcessor
from src.search.embedding_service import EmbeddingService
from src.search.vector_database import VectorDatabase
from src.search.query_processor import QueryProcessor
from src.llm.llm_service import LLMService
from src.llm.citation_service import CitationService
from src.api.auth import (
    get_current_active_user, 
    get_optional_user, 
    create_access_token,
    User
)
from src.api.rate_limiter import RateLimitMiddleware
from src.api.audit_logger import AuditMiddleware, AuditLogger
from src.api.performance_monitor import (
    get_performance_monitor,
    get_query_cache,
    QueryMetrics
)
from src.monitoring.startup import initialize_monitoring, shutdown_monitoring
from src.monitoring.alerting import get_alerting_service, AlertLevel
from src.monitoring.metrics_collector import get_metrics_collector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Pydantic models for API requests/responses
class QueryRequest(BaseModel):
    """Request model for document queries."""
    query: str = Field(..., min_length=1, max_length=1000, description="User query string")
    max_results: Optional[int] = Field(default=5, ge=1, le=20, description="Maximum number of results")
    search_type: Optional[str] = Field(default="hybrid", pattern="^(vector|hybrid)$", description="Search type")
    stream: Optional[bool] = Field(default=False, description="Enable streaming response")


class SourceAttributionResponse(BaseModel):
    """Source attribution information for API response."""
    document_name: str
    page_number: int
    highlighted_image_url: str
    text_excerpt: str
    relevance_score: float


class QueryResponse(BaseModel):
    """Response model for document queries."""
    answer: str
    sources: List[SourceAttributionResponse]
    confidence_score: float
    processing_time_ms: int
    grounded: bool = Field(default=True, description="Whether response is grounded in sources")
    model_name: Optional[str] = Field(default=None, description="LLM model used")


class DocumentUploadResponse(BaseModel):
    """Response model for document upload."""
    document_id: str
    filename: str
    status: str
    message: str
    chunks_created: int
    processing_time_ms: int
    metadata: Dict[str, Any]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    services: Dict[str, str]


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: Dict[str, Any]


class LoginRequest(BaseModel):
    """Login request model."""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str
    expires_in: int


# Initialize FastAPI app
app = FastAPI(
    title="Enterprise Document Assistant",
    description="RAG system for querying proprietary documents with visual highlighting",
    version="0.1.0",
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not Found"},
        429: {"model": ErrorResponse, "description": "Too Many Requests"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
    }
)

# Add security middleware
settings = get_settings()

# Add audit logging middleware
audit_logger = AuditLogger(log_file="audit.log" if not settings.debug else None)
app.add_middleware(AuditMiddleware, audit_logger=audit_logger)

# Add rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=60,
    requests_per_hour=1000
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services (lazy loading to avoid startup issues)
_services = {}


@app.on_event("startup")
async def startup_event():
    """Initialize monitoring and services on application startup."""
    try:
        initialize_monitoring()
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup monitoring and services on application shutdown."""
    try:
        shutdown_monitoring()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def get_service(service_name: str):
    """Get or initialize a service."""
    if service_name not in _services:
        settings = get_settings()
        
        if service_name == "document_processor":
            _services[service_name] = DocumentProcessor(
                chunk_size_min=settings.chunk_size_min,
                chunk_size_max=settings.chunk_size_max
            )
        elif service_name == "embedding_service":
            _services[service_name] = EmbeddingService()
        elif service_name == "vector_db":
            _services[service_name] = VectorDatabase()
        elif service_name == "query_processor":
            _services[service_name] = QueryProcessor()
        elif service_name == "llm_service":
            _services[service_name] = LLMService()
        elif service_name == "citation_service":
            _services[service_name] = CitationService()
        else:
            raise ValueError(f"Unknown service: {service_name}")
    
    return _services[service_name]


@app.post("/auth/login", response_model=TokenResponse, tags=["Authentication"])
async def login(request: LoginRequest):
    """Authenticate user and return JWT token.
    
    This is a simplified implementation. In production, you would:
    1. Validate credentials against a database
    2. Implement proper password hashing
    3. Add account lockout after failed attempts
    4. Implement refresh tokens
    """
    # Simplified authentication - in production, validate against database
    # For demo purposes, accept any username/password combination
    if not request.username or not request.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_CREDENTIALS",
                    "message": "Invalid username or password"
                }
            }
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": request.username, "scopes": ["read", "write"]},
        expires_delta=access_token_expires
    )
    
    logger.info(f"User {request.username} authenticated successfully")
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60
    )


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint to verify service status."""
    settings = get_settings()
    
    # Check service configurations
    services_status = {
        "api": "healthy",
        "azure_openai": "configured" if settings.azure_openai_endpoint else "not_configured",
        "azure_storage": "configured" if settings.azure_storage_account_name else "not_configured",
        "azure_search": "configured" if settings.azure_search_endpoint else "not_configured",
    }
    
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        services=services_status
    )


@app.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Documents"]
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Upload and process a new PDF document.
    
    This endpoint:
    1. Validates the uploaded file is a PDF
    2. Extracts text with coordinates
    3. Chunks the document
    4. Generates embeddings
    5. Stores in vector database
    
    Authentication is optional but recommended for production use.
    """
    start_time = time.time()
    
    try:
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_FILE_TYPE",
                        "message": "Only PDF files are supported",
                        "details": {"filename": file.filename}
                    }
                }
            )
        
        # Check file size
        settings = get_settings()
        content = await file.read()
        file_size_mb = len(content) / (1024 * 1024)
        
        if file_size_mb > settings.max_file_size_mb:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "error": {
                        "code": "FILE_TOO_LARGE",
                        "message": f"File size exceeds maximum of {settings.max_file_size_mb}MB",
                        "details": {"file_size_mb": file_size_mb}
                    }
                }
            )
        
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Process document
        doc_processor = get_service("document_processor")
        processing_result = doc_processor.process_document(content, document_id)
        
        if not processing_result.success:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {
                        "code": "PROCESSING_FAILED",
                        "message": processing_result.error_message or "Document processing failed",
                        "details": {"document_id": document_id}
                    }
                }
            )
        
        # Generate embeddings for chunks
        embedding_service = get_service("embedding_service")
        embeddings = embedding_service.generate_embeddings(processing_result.chunks)
        
        # Update chunks with embeddings
        for chunk, embedding in zip(processing_result.chunks, embeddings):
            chunk.embedding = embedding.vector
        
        # Store in vector database
        vector_db = get_service("vector_db")
        index_result = vector_db.index_documents(embeddings)
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        user_info = f" by user {current_user.username}" if current_user else ""
        logger.info(f"Successfully processed document {document_id} ({file.filename}){user_info} "
                   f"in {processing_time_ms}ms: {len(processing_result.chunks)} chunks created")
        
        return DocumentUploadResponse(
            document_id=document_id,
            filename=file.filename,
            status="success",
            message="Document processed and indexed successfully",
            chunks_created=len(processing_result.chunks),
            processing_time_ms=processing_time_ms,
            metadata={
                **processing_result.metadata,
                "file_size_mb": round(file_size_mb, 2),
                "indexed_chunks": index_result.indexed_count if hasattr(index_result, 'indexed_count') else len(processing_result.chunks),
                "uploaded_by": current_user.username if current_user else "anonymous"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        processing_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Document upload failed after {processing_time_ms}ms: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred during document processing",
                    "details": {"error": str(e)}
                }
            }
        )


@app.post("/query", response_model=QueryResponse, tags=["Query"])
async def query_documents(
    request: QueryRequest,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Query documents and return AI-generated response with sources.
    
    This endpoint:
    1. Processes and validates the query
    2. Searches for relevant document chunks (with caching)
    3. Generates an AI response using retrieved context
    4. Returns response with source citations and highlighted images
    
    Authentication is optional but recommended for production use.
    """
    start_time = time.time()
    search_start_time = start_time
    llm_start_time = start_time
    cache_hit = False
    
    try:
        # Generate cache key
        cache_key = f"{request.query}:{request.max_results}:{request.search_type}"
        query_cache = get_query_cache()
        
        # Check cache first
        cached_result = query_cache.get(cache_key)
        if cached_result:
            cache_hit = True
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Record metrics
            performance_monitor = get_performance_monitor()
            metrics = QueryMetrics(
                query_id=str(uuid.uuid4()),
                query_text=request.query,
                timestamp=datetime.now(),
                processing_time_ms=processing_time_ms,
                search_time_ms=0,
                llm_time_ms=0,
                total_results=len(cached_result["sources"]),
                cache_hit=True,
                user=current_user.username if current_user else None
            )
            performance_monitor.record_query(metrics)
            
            user_info = f" by user {current_user.username}" if current_user else ""
            logger.info(f"Query processed{user_info} in {processing_time_ms}ms (cache hit)")
            
            return QueryResponse(**cached_result, processing_time_ms=processing_time_ms)
        
        # Process query and search
        search_start_time = time.time()
        query_processor = get_service("query_processor")
        query_result = query_processor.process_query(
            request.query,
            k=request.max_results,
            search_type=request.search_type
        )
        search_time_ms = int((time.time() - search_start_time) * 1000)
        
        if not query_result.results:
            # No results found
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            response_data = {
                "answer": "I couldn't find any relevant information in the documents to answer your question.",
                "sources": [],
                "confidence_score": 0.0,
                "grounded": True,
                "model_name": "N/A"
            }
            
            # Cache the result
            query_cache.set(cache_key, response_data)
            
            # Record metrics
            performance_monitor = get_performance_monitor()
            metrics = QueryMetrics(
                query_id=str(uuid.uuid4()),
                query_text=request.query,
                timestamp=datetime.now(),
                processing_time_ms=processing_time_ms,
                search_time_ms=search_time_ms,
                llm_time_ms=0,
                total_results=0,
                cache_hit=False,
                user=current_user.username if current_user else None
            )
            performance_monitor.record_query(metrics)
            
            return QueryResponse(**response_data, processing_time_ms=processing_time_ms)
        
        # Generate response using LLM
        llm_start_time = time.time()
        llm_service = get_service("llm_service")
        llm_response = llm_service.generate_response(request.query, query_result.results)
        llm_time_ms = int((time.time() - llm_start_time) * 1000)
        
        # Format sources for API response
        sources = []
        for source in llm_response.sources:
            sources.append(SourceAttributionResponse(
                document_name=source.document_name,
                page_number=source.page_number,
                highlighted_image_url=source.highlighted_image_url or "",
                text_excerpt=source.text_excerpt,
                relevance_score=source.relevance_score
            ))
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        response_data = {
            "answer": llm_response.text,
            "sources": [s.model_dump() for s in sources],
            "confidence_score": llm_response.confidence_score,
            "grounded": llm_response.grounded,
            "model_name": llm_response.model_name
        }
        
        # Cache the result
        query_cache.set(cache_key, response_data)
        
        # Record metrics
        performance_monitor = get_performance_monitor()
        metrics = QueryMetrics(
            query_id=str(uuid.uuid4()),
            query_text=request.query,
            timestamp=datetime.now(),
            processing_time_ms=processing_time_ms,
            search_time_ms=search_time_ms,
            llm_time_ms=llm_time_ms,
            total_results=len(sources),
            cache_hit=False,
            user=current_user.username if current_user else None
        )
        performance_monitor.record_query(metrics)
        
        user_info = f" by user {current_user.username}" if current_user else ""
        logger.info(f"Query processed{user_info} in {processing_time_ms}ms: "
                   f"{len(sources)} sources, grounded={llm_response.grounded}, "
                   f"search={search_time_ms}ms, llm={llm_time_ms}ms")
        
        return QueryResponse(
            answer=llm_response.text,
            sources=sources,
            confidence_score=llm_response.confidence_score,
            processing_time_ms=processing_time_ms,
            grounded=llm_response.grounded,
            model_name=llm_response.model_name
        )
        
    except Exception as e:
        processing_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Query processing failed after {processing_time_ms}ms: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "QUERY_FAILED",
                    "message": "An error occurred while processing your query",
                    "details": {"error": str(e)}
                }
            }
        )


@app.get("/documents/{document_id}/page/{page_num}", tags=["Documents"])
async def get_highlighted_page(
    document_id: str,
    page_num: int,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Retrieve a highlighted page image for a specific document.
    
    Returns a PNG image with text highlighting overlays.
    
    Authentication is optional but recommended for production use.
    """
    try:
        # This would retrieve the document from storage and render the page
        # For now, return a placeholder response
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={
                "error": {
                    "code": "NOT_IMPLEMENTED",
                    "message": "Highlighted page retrieval not yet implemented",
                    "details": {
                        "document_id": document_id,
                        "page_num": page_num
                    }
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve highlighted page: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "RETRIEVAL_FAILED",
                    "message": "Failed to retrieve highlighted page",
                    "details": {"error": str(e)}
                }
            }
        )


@app.get("/status", tags=["Health"])
async def get_status():
    """Get detailed system status and configuration."""
    try:
        settings = get_settings()
        
        # Get service statuses
        service_statuses = {}
        
        try:
            llm_service = get_service("llm_service")
            service_statuses["llm"] = llm_service.get_service_status()
        except Exception as e:
            service_statuses["llm"] = {"error": str(e)}
        
        try:
            query_processor = get_service("query_processor")
            service_statuses["search"] = query_processor.get_search_statistics()
        except Exception as e:
            service_statuses["search"] = {"error": str(e)}
        
        return {
            "status": "operational",
            "version": "0.1.0",
            "configuration": {
                "chunk_size_range": f"{settings.chunk_size_min}-{settings.chunk_size_max}",
                "max_search_results": settings.max_search_results,
                "max_file_size_mb": settings.max_file_size_mb,
                "request_timeout_seconds": settings.request_timeout_seconds
            },
            "services": service_statuses
        }
        
    except Exception as e:
        logger.error(f"Status check failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }


@app.get("/metrics/performance", tags=["Metrics"])
async def get_performance_metrics(
    time_window_minutes: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Get performance metrics and statistics.
    
    Args:
        time_window_minutes: Optional time window to filter metrics (e.g., last 60 minutes)
    
    Returns:
        Performance statistics including response times, cache hit rates, and query counts
    """
    try:
        performance_monitor = get_performance_monitor()
        stats = performance_monitor.get_stats(time_window_minutes)
        breakdown = performance_monitor.get_query_breakdown()
        
        return {
            "performance_stats": {
                "total_queries": stats.total_queries,
                "avg_processing_time_ms": round(stats.avg_processing_time_ms, 2),
                "p50_processing_time_ms": round(stats.p50_processing_time_ms, 2),
                "p95_processing_time_ms": round(stats.p95_processing_time_ms, 2),
                "p99_processing_time_ms": round(stats.p99_processing_time_ms, 2),
                "cache_hit_rate": round(stats.cache_hit_rate * 100, 2),
                "queries_per_minute": round(stats.queries_per_minute, 2),
                "slow_queries_count": stats.slow_queries_count
            },
            "query_breakdown": breakdown,
            "time_window_minutes": time_window_minutes or "all"
        }
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "METRICS_FAILED",
                    "message": "Failed to retrieve performance metrics",
                    "details": {"error": str(e)}
                }
            }
        )


@app.get("/metrics/cache", tags=["Metrics"])
async def get_cache_metrics(current_user: Optional[User] = Depends(get_optional_user)):
    """Get query cache statistics.
    
    Returns:
        Cache statistics including size, hit rate, and entry information
    """
    try:
        query_cache = get_query_cache()
        cache_stats = query_cache.get_stats()
        
        return {
            "cache_stats": cache_stats,
            "utilization_percentage": round(
                (cache_stats["total_entries"] / cache_stats["max_size"]) * 100, 2
            )
        }
    except Exception as e:
        logger.error(f"Failed to get cache metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "CACHE_METRICS_FAILED",
                    "message": "Failed to retrieve cache metrics",
                    "details": {"error": str(e)}
                }
            }
        )


@app.get("/metrics/slow-queries", tags=["Metrics"])
async def get_slow_queries(
    limit: int = 10,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Get recent slow queries for performance analysis.
    
    Args:
        limit: Maximum number of slow queries to return (default: 10)
    
    Returns:
        List of slow queries with timing information
    """
    try:
        performance_monitor = get_performance_monitor()
        slow_queries = performance_monitor.get_slow_queries(limit)
        
        return {
            "slow_queries": [
                {
                    "query_id": q.query_id,
                    "query_text": q.query_text[:100],  # Truncate for display
                    "timestamp": q.timestamp.isoformat(),
                    "processing_time_ms": q.processing_time_ms,
                    "search_time_ms": q.search_time_ms,
                    "llm_time_ms": q.llm_time_ms,
                    "user": q.user
                }
                for q in slow_queries
            ],
            "count": len(slow_queries)
        }
    except Exception as e:
        logger.error(f"Failed to get slow queries: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "SLOW_QUERIES_FAILED",
                    "message": "Failed to retrieve slow queries",
                    "details": {"error": str(e)}
                }
            }
        )


@app.post("/cache/clear", tags=["Admin"])
async def clear_cache(current_user: Optional[User] = Depends(get_optional_user)):
    """Clear the query cache.
    
    Requires authentication. Use this to force fresh results for all queries.
    """
    try:
        query_cache = get_query_cache()
        query_cache.clear()
        
        user_info = f" by user {current_user.username}" if current_user else ""
        logger.info(f"Query cache cleared{user_info}")
        
        return {
            "status": "success",
            "message": "Query cache cleared successfully"
        }
    except Exception as e:
        logger.error(f"Failed to clear cache: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "CACHE_CLEAR_FAILED",
                    "message": "Failed to clear cache",
                    "details": {"error": str(e)}
                }
            }
        )


@app.get("/metrics/system", tags=["Metrics"])
async def get_system_metrics(current_user: Optional[User] = Depends(get_optional_user)):
    """Get current system resource metrics.
    
    Returns CPU, memory, and disk usage information.
    """
    try:
        metrics_collector = get_metrics_collector()
        system_metrics = metrics_collector.get_current_system_metrics()
        
        if not system_metrics:
            return {"message": "No system metrics available yet"}
        
        return {
            "timestamp": system_metrics.timestamp.isoformat(),
            "cpu_percent": round(system_metrics.cpu_percent, 2),
            "memory": {
                "percent": round(system_metrics.memory_percent, 2),
                "used_mb": round(system_metrics.memory_used_mb, 2),
                "available_mb": round(system_metrics.memory_available_mb, 2)
            },
            "disk": {
                "percent": round(system_metrics.disk_usage_percent, 2),
                "used_gb": round(system_metrics.disk_used_gb, 2),
                "free_gb": round(system_metrics.disk_free_gb, 2)
            }
        }
    except Exception as e:
        logger.error(f"Failed to get system metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "SYSTEM_METRICS_FAILED",
                    "message": "Failed to retrieve system metrics",
                    "details": {"error": str(e)}
                }
            }
        )


@app.get("/metrics/application", tags=["Metrics"])
async def get_application_metrics(current_user: Optional[User] = Depends(get_optional_user)):
    """Get current application metrics.
    
    Returns request counts, response times, and processing statistics.
    """
    try:
        metrics_collector = get_metrics_collector()
        app_metrics = metrics_collector.get_current_application_metrics()
        
        if not app_metrics:
            return {"message": "No application metrics available yet"}
        
        return {
            "timestamp": app_metrics.timestamp.isoformat(),
            "requests": {
                "active": app_metrics.active_requests,
                "total": app_metrics.total_requests,
                "errors": app_metrics.error_count
            },
            "performance": {
                "avg_response_time_ms": round(app_metrics.avg_response_time_ms, 2),
                "cache_hit_rate": round(app_metrics.cache_hit_rate * 100, 2)
            },
            "processing": {
                "documents_indexed": app_metrics.documents_indexed,
                "queries_processed": app_metrics.queries_processed
            }
        }
    except Exception as e:
        logger.error(f"Failed to get application metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "APP_METRICS_FAILED",
                    "message": "Failed to retrieve application metrics",
                    "details": {"error": str(e)}
                }
            }
        )


@app.get("/alerts", tags=["Monitoring"])
async def get_alerts(
    level: Optional[str] = None,
    source: Optional[str] = None,
    hours: int = 24,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Get system alerts.
    
    Args:
        level: Filter by alert level (info, warning, error, critical)
        source: Filter by alert source
        hours: Number of hours to look back (default: 24)
    
    Returns:
        List of alerts matching the criteria
    """
    try:
        alerting_service = get_alerting_service()
        
        # Parse level if provided
        alert_level = None
        if level:
            try:
                alert_level = AlertLevel(level.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": {
                            "code": "INVALID_LEVEL",
                            "message": f"Invalid alert level: {level}. Must be one of: info, warning, error, critical"
                        }
                    }
                )
        
        # Get alerts
        alerts = alerting_service.get_recent_alerts(hours=hours, level=alert_level)
        
        # Apply source filter if provided
        if source:
            alerts = [a for a in alerts if a.source == source]
        
        return {
            "alerts": [
                {
                    "alert_id": a.alert_id,
                    "level": a.level.value,
                    "title": a.title,
                    "message": a.message,
                    "timestamp": a.timestamp.isoformat(),
                    "source": a.source,
                    "resolved": a.resolved,
                    "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
                    "metadata": a.metadata
                }
                for a in alerts
            ],
            "count": len(alerts),
            "filters": {
                "level": level,
                "source": source,
                "hours": hours
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get alerts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "ALERTS_FAILED",
                    "message": "Failed to retrieve alerts",
                    "details": {"error": str(e)}
                }
            }
        )


@app.get("/alerts/summary", tags=["Monitoring"])
async def get_alerts_summary(current_user: Optional[User] = Depends(get_optional_user)):
    """Get summary of system alerts.
    
    Returns aggregated alert statistics.
    """
    try:
        alerting_service = get_alerting_service()
        summary = alerting_service.get_alert_summary()
        
        return summary
    except Exception as e:
        logger.error(f"Failed to get alert summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "ALERT_SUMMARY_FAILED",
                    "message": "Failed to retrieve alert summary",
                    "details": {"error": str(e)}
                }
            }
        )


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Template-Driven Document Generation Endpoints
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import Form
from fastapi.responses import FileResponse
from src.structuring.content_structurer import ContentStructurer
from src.template.template_engine import TemplateEngine
from src.generation.document_generator import DocumentGeneratorService
from src.automation.n8n_client import N8nClient


# Pydantic models for generation
class GenerateFromQueryRequest(BaseModel):
    """Request to generate a document from a RAG query."""
    query: str = Field(..., min_length=1, max_length=1000)
    output_format: str = Field(default="pdf", pattern="^(pdf|ppt|pptx|excel|xlsx)$")
    template: Optional[str] = Field(default=None, description="Custom HTML/text template with {{placeholders}}")
    max_results: Optional[int] = Field(default=5, ge=1, le=20)
    use_n8n: Optional[bool] = Field(default=False, description="Route through n8n workflow")


class GenerateFromDataRequest(BaseModel):
    """Request to generate a document from pre-structured JSON data."""
    data: Dict[str, Any] = Field(..., description="Structured document data")
    output_format: str = Field(default="pdf", pattern="^(pdf|ppt|pptx|excel|xlsx)$")
    template: Optional[str] = Field(default=None)
    use_n8n: Optional[bool] = Field(default=False)


class StructureRequest(BaseModel):
    """Request to structure raw text into JSON."""
    text: str = Field(..., min_length=1)
    query: Optional[str] = Field(default="")


class TemplateValidateRequest(BaseModel):
    """Request to validate a template against data."""
    template: str
    data: Dict[str, Any]


# Lazy-loaded generation services
_gen_services: Dict[str, Any] = {}


def get_gen_service(name: str):
    if name not in _gen_services:
        if name == "structurer":
            _gen_services[name] = ContentStructurer()
        elif name == "template_engine":
            _gen_services[name] = TemplateEngine()
        elif name == "doc_generator":
            _gen_services[name] = DocumentGeneratorService()
        elif name == "n8n_client":
            n8n_url = getattr(get_settings(), "n8n_webhook_url", "http://localhost:5678")
            _gen_services[name] = N8nClient(webhook_base_url=n8n_url)
    return _gen_services[name]


@app.post("/generate/from-query", tags=["Document Generation"])
async def generate_from_query(
    request: GenerateFromQueryRequest,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Full pipeline: Query RAG → Structure → Apply Template → Generate Document.

    Steps:
    1. Run RAG query on indexed documents
    2. Structure the LLM answer into sections (title, abstract, methodology, etc.)
    3. Apply user template (or default) with placeholder mapping
    4. Generate PDF / PPT / Excel and return as download
    """
    import time
    start = time.time()

    try:
        # Step 1: RAG query
        query_processor = get_service("query_processor")
        query_result = query_processor.process_query(request.query, k=request.max_results)

        llm_answer = ""
        sources_list = []

        if query_result.results:
            llm_service = get_service("llm_service")
            llm_response = llm_service.generate_response(request.query, query_result.results)
            llm_answer = llm_response.text
            sources_list = [
                {"document_name": s.document_name, "text_excerpt": s.text_excerpt}
                for s in llm_response.sources
            ]
        else:
            llm_answer = f"No documents found for query: {request.query}"

        # Step 2: Structure
        structurer = get_gen_service("structurer")
        structured = structurer.structure_from_llm_response(llm_answer, sources_list)
        data = structured.to_dict()

        # Step 3: Template mapping
        template_engine = get_gen_service("template_engine")
        final_template = request.template

        if final_template:
            mapping = template_engine.map_data_to_template(final_template, data, request.output_format)
            if not mapping.success:
                raise HTTPException(status_code=400, detail={"error": {"code": "TEMPLATE_ERROR", "message": mapping.error_message}})
            content_for_gen = mapping.output
        else:
            content_for_gen = None  # generator uses its own default

        # Step 4: n8n or direct generation
        if request.use_n8n:
            n8n = get_gen_service("n8n_client")
            n8n_result = await n8n.trigger_document_generation(data, final_template, request.output_format)
            return {
                "status": "triggered",
                "n8n_success": n8n_result.success,
                "execution_id": n8n_result.execution_id,
                "message": n8n_result.error_message or "Workflow triggered successfully",
                "structured_data": data
            }

        # Direct generation
        doc_gen = get_gen_service("doc_generator")
        result = doc_gen.generate(data, request.output_format, content_for_gen)

        if not result.success:
            raise HTTPException(status_code=500, detail={"error": {"code": "GENERATION_FAILED", "message": result.error_message}})

        elapsed = int((time.time() - start) * 1000)
        logger.info(f"Document generated in {elapsed}ms: format={request.output_format}, size={len(result.content)} bytes")

        return StreamingResponse(
            io.BytesIO(result.content),
            media_type=result.mime_type,
            headers={"Content-Disposition": f"attachment; filename={result.filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"generate_from_query failed: {e}")
        raise HTTPException(status_code=500, detail={"error": {"code": "PIPELINE_ERROR", "message": str(e)}})


@app.post("/generate/from-data", tags=["Document Generation"])
async def generate_from_data(
    request: GenerateFromDataRequest,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Generate a document directly from pre-structured JSON data.

    Skips the RAG step — useful when you already have structured content.
    """
    try:
        template_engine = get_gen_service("template_engine")
        final_template = request.template

        if final_template:
            mapping = template_engine.map_data_to_template(final_template, request.data, request.output_format)
            if not mapping.success:
                raise HTTPException(status_code=400, detail={"error": {"code": "TEMPLATE_ERROR", "message": mapping.error_message}})
            content_for_gen = mapping.output
        else:
            content_for_gen = None

        if request.use_n8n:
            n8n = get_gen_service("n8n_client")
            n8n_result = await n8n.trigger_document_generation(request.data, final_template, request.output_format)
            return {
                "status": "triggered",
                "n8n_success": n8n_result.success,
                "execution_id": n8n_result.execution_id,
                "message": n8n_result.error_message or "Workflow triggered successfully"
            }

        doc_gen = get_gen_service("doc_generator")
        result = doc_gen.generate(request.data, request.output_format, content_for_gen)

        if not result.success:
            raise HTTPException(status_code=500, detail={"error": {"code": "GENERATION_FAILED", "message": result.error_message}})

        return StreamingResponse(
            io.BytesIO(result.content),
            media_type=result.mime_type,
            headers={"Content-Disposition": f"attachment; filename={result.filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"generate_from_data failed: {e}")
        raise HTTPException(status_code=500, detail={"error": {"code": "GENERATION_FAILED", "message": str(e)}})


@app.post("/generate/upload-and-generate", tags=["Document Generation"])
async def upload_and_generate(
    file: UploadFile = File(...),
    output_format: str = Form(default="pdf"),
    template_file: Optional[UploadFile] = File(default=None),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Upload a PDF → Extract text via RAG → Structure → Generate output document.

    All-in-one endpoint: upload source PDF + optional template, get back PDF/PPT/Excel.
    """
    try:
        # Validate input file
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_FILE", "message": "Only PDF files supported"}})

        content = await file.read()

        # Process document
        doc_processor = get_service("document_processor")
        doc_id = str(uuid.uuid4())
        proc_result = doc_processor.process_document(content, doc_id)

        if not proc_result.success:
            raise HTTPException(status_code=422, detail={"error": {"code": "PROCESSING_FAILED", "message": proc_result.error_message}})

        # Structure the extracted text
        structurer = get_gen_service("structurer")
        structured = structurer.structure_rag_output(proc_result.text, file.filename)
        data = structured.to_dict()

        # Load custom template if provided
        custom_template = None
        if template_file:
            template_bytes = await template_file.read()
            custom_template = template_bytes.decode("utf-8")

        # Apply template mapping
        template_engine = get_gen_service("template_engine")
        content_for_gen = None
        if custom_template:
            mapping = template_engine.map_data_to_template(custom_template, data, output_format)
            if mapping.success:
                content_for_gen = mapping.output

        # Generate document
        doc_gen = get_gen_service("doc_generator")
        result = doc_gen.generate(data, output_format, content_for_gen, file.filename.replace(".pdf", ""))

        if not result.success:
            raise HTTPException(status_code=500, detail={"error": {"code": "GENERATION_FAILED", "message": result.error_message}})

        return StreamingResponse(
            io.BytesIO(result.content),
            media_type=result.mime_type,
            headers={"Content-Disposition": f"attachment; filename={result.filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"upload_and_generate failed: {e}")
        raise HTTPException(status_code=500, detail={"error": {"code": "PIPELINE_ERROR", "message": str(e)}})


@app.post("/structure/text", tags=["Document Generation"])
async def structure_text(request: StructureRequest):
    """
    Structure raw text into JSON sections (title, abstract, methodology, results, etc.).

    Useful for previewing what the structuring module will produce before generation.
    """
    try:
        structurer = get_gen_service("structurer")
        structured = structurer.structure_rag_output(request.text, request.query or "")
        return {"structured_data": structured.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"code": "STRUCTURING_FAILED", "message": str(e)}})


@app.post("/template/validate", tags=["Document Generation"])
async def validate_template(request: TemplateValidateRequest):
    """
    Validate a template against provided data.

    Returns which placeholders are missing or extra.
    """
    try:
        engine = get_gen_service("template_engine")
        result = engine.validate_template(request.template, request.data)
        return {
            "valid": result.valid,
            "missing_fields": result.missing_fields,
            "extra_fields": result.extra_fields,
            "message": result.message
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": {"code": "VALIDATION_FAILED", "message": str(e)}})


@app.get("/template/default/{format_type}", tags=["Document Generation"])
async def get_default_template(format_type: str):
    """
    Get the default template for a given output format (pdf, ppt, excel).
    """
    if format_type not in ("pdf", "ppt", "excel"):
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_FORMAT", "message": f"Unsupported format: {format_type}"}})
    engine = get_gen_service("template_engine")
    template = engine.get_default_template(format_type)
    return {"format": format_type, "template": template}


@app.get("/n8n/workflow-definition", tags=["Automation"])
async def get_n8n_workflow():
    """
    Get the n8n workflow JSON definition.

    Import this into your n8n instance to set up the automation workflow.
    """
    n8n = get_gen_service("n8n_client")
    return n8n.get_n8n_workflow_json()


@app.post("/webhook/generate", tags=["Automation"])
async def n8n_webhook_generate(request: GenerateFromDataRequest):
    """
    n8n-compatible webhook endpoint for document generation.

    n8n calls this endpoint as part of its workflow to generate documents.
    POST /webhook/generate  { "data": {...}, "template": "...", "format": "pdf" }
    """
    return await generate_from_data(request)
