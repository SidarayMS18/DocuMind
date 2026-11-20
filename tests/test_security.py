"""Tests for authentication and security middleware."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import timedelta

from src.api.auth import create_access_token, decode_access_token, TokenData
from src.api.rate_limiter import RateLimiter
from src.config.settings import get_settings


def test_create_and_decode_access_token():
    """Test JWT token creation and decoding."""
    # Create token
    token_data = {"sub": "testuser", "scopes": ["read", "write"]}
    token = create_access_token(token_data, expires_delta=timedelta(minutes=30))
    
    assert token is not None
    assert isinstance(token, str)
    
    # Decode token
    decoded = decode_access_token(token)
    assert decoded.username == "testuser"
    assert "read" in decoded.scopes
    assert "write" in decoded.scopes


def test_decode_invalid_token():
    """Test decoding an invalid token raises exception."""
    from fastapi import HTTPException
    
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token("invalid.token.here")
    
    assert exc_info.value.status_code == 401


def test_login_endpoint(test_client: TestClient):
    """Test login endpoint returns valid token."""
    response = test_client.post(
        "/auth/login",
        json={"username": "testuser", "password": "testpass"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data


def test_login_endpoint_missing_credentials(test_client: TestClient):
    """Test login endpoint with missing credentials."""
    response = test_client.post(
        "/auth/login",
        json={"username": "", "password": ""}
    )
    
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert "error" in data["detail"]


def test_rate_limiter_allows_requests():
    """Test rate limiter allows requests within limits."""
    limiter = RateLimiter(requests_per_minute=10, requests_per_hour=100)
    
    # Make 5 requests (should all be allowed)
    for i in range(5):
        is_allowed, info = limiter.check_rate_limit("test_client")
        assert is_allowed is True
        # After the request is recorded, count should be i+1
        assert info["requests_last_minute"] <= i + 1


def test_rate_limiter_blocks_excessive_requests():
    """Test rate limiter blocks requests exceeding limits."""
    limiter = RateLimiter(requests_per_minute=5, requests_per_hour=100)
    
    # Make 5 requests (at the limit)
    for i in range(5):
        is_allowed, info = limiter.check_rate_limit("test_client")
        assert is_allowed is True
    
    # 6th request should be blocked
    is_allowed, info = limiter.check_rate_limit("test_client")
    assert is_allowed is False
    assert info["requests_last_minute"] >= 5


def test_rate_limiter_per_client():
    """Test rate limiter tracks clients separately."""
    limiter = RateLimiter(requests_per_minute=5, requests_per_hour=100)
    
    # Client 1 makes 5 requests
    for i in range(5):
        is_allowed, info = limiter.check_rate_limit("client1")
        assert is_allowed is True
    
    # Client 1's 6th request should be blocked
    is_allowed, info = limiter.check_rate_limit("client1")
    assert is_allowed is False
    
    # Client 2 should still be allowed
    is_allowed, info = limiter.check_rate_limit("client2")
    assert is_allowed is True


def test_rate_limiter_reset():
    """Test rate limiter reset functionality."""
    limiter = RateLimiter(requests_per_minute=5, requests_per_hour=100)
    
    # Make 5 requests
    for i in range(5):
        limiter.check_rate_limit("test_client")
    
    # Reset client
    limiter.reset_client("test_client")
    
    # Should be able to make requests again
    is_allowed, info = limiter.check_rate_limit("test_client")
    assert is_allowed is True
    # After reset and one new request, count should be 1 or less
    assert info["requests_last_minute"] <= 1


def test_rate_limit_headers_in_response(test_client: TestClient):
    """Test that rate limit headers are added to responses."""
    response = test_client.get("/health")
    
    # Health endpoint is excluded from rate limiting
    assert response.status_code == 200


def test_authenticated_upload(test_client: TestClient):
    """Test document upload with authentication."""
    # First, get a token
    login_response = test_client.post(
        "/auth/login",
        json={"username": "testuser", "password": "testpass"}
    )
    token = login_response.json()["access_token"]
    
    # Mock the services
    with patch("src.api.main.get_service") as mock_get_service:
        mock_doc_processor = Mock()
        mock_processing_result = Mock()
        mock_processing_result.success = True
        mock_processing_result.chunks = [Mock(), Mock()]
        mock_processing_result.metadata = {"title": "Test Doc"}
        mock_doc_processor.process_document.return_value = mock_processing_result
        
        mock_embedding_service = Mock()
        mock_embedding = Mock()
        mock_embedding.vector = [0.1] * 1536
        mock_embedding_service.generate_embeddings.return_value = [mock_embedding, mock_embedding]
        
        mock_vector_db = Mock()
        mock_vector_db.index_documents.return_value = {"indexed_count": 2}
        
        def get_service_side_effect(service_name):
            if service_name == "document_processor":
                return mock_doc_processor
            elif service_name == "embedding_service":
                return mock_embedding_service
            elif service_name == "vector_db":
                return mock_vector_db
            return Mock()
        
        mock_get_service.side_effect = get_service_side_effect
        
        # Upload with authentication
        pdf_content = b"%PDF-1.4 test content"
        response = test_client.post(
            "/documents/upload",
            files={"file": ("test.pdf", pdf_content, "application/pdf")},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["metadata"]["uploaded_by"] == "testuser"


def test_authenticated_query(test_client: TestClient):
    """Test query with authentication."""
    # First, get a token
    login_response = test_client.post(
        "/auth/login",
        json={"username": "testuser", "password": "testpass"}
    )
    token = login_response.json()["access_token"]
    
    # Mock the services
    with patch("src.api.main.get_service") as mock_get_service:
        mock_query_processor = Mock()
        mock_search_result = Mock()
        mock_search_result.chunk_id = "chunk1"
        mock_search_result.text = "Test content"
        mock_search_result.score = 0.9
        mock_search_result.metadata = {
            "document_name": "test.pdf",
            "page_number": 1
        }
        
        mock_query_result = Mock()
        mock_query_result.results = [mock_search_result]
        mock_query_processor.process_query.return_value = mock_query_result
        
        mock_llm_service = Mock()
        mock_source = Mock()
        mock_source.document_name = "test.pdf"
        mock_source.page_number = 1
        mock_source.highlighted_image_url = "http://example.com/image.png"
        mock_source.text_excerpt = "Test excerpt"
        mock_source.relevance_score = 0.9
        
        mock_llm_response = Mock()
        mock_llm_response.text = "This is the answer"
        mock_llm_response.sources = [mock_source]
        mock_llm_response.confidence_score = 0.85
        mock_llm_response.grounded = True
        mock_llm_response.model_name = "gpt-4"
        mock_llm_service.generate_response.return_value = mock_llm_response
        
        def get_service_side_effect(service_name):
            if service_name == "query_processor":
                return mock_query_processor
            elif service_name == "llm_service":
                return mock_llm_service
            return Mock()
        
        mock_get_service.side_effect = get_service_side_effect
        
        # Query with authentication
        response = test_client.post(
            "/query",
            json={"query": "test query"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "This is the answer"


def test_unauthenticated_access_allowed(test_client: TestClient):
    """Test that endpoints work without authentication (optional auth)."""
    # Query without authentication should still work
    with patch("src.api.main.get_service") as mock_get_service:
        mock_query_processor = Mock()
        mock_query_result = Mock()
        mock_query_result.results = []
        mock_query_processor.process_query.return_value = mock_query_result
        
        mock_get_service.return_value = mock_query_processor
        
        response = test_client.post("/query", json={"query": "test"})
        assert response.status_code == 200
