"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
import io


def test_health_endpoint(test_client: TestClient):
    """Test the health check endpoint."""
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"
    assert "services" in data


def test_status_endpoint(test_client: TestClient):
    """Test the detailed status endpoint."""
    response = test_client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "configuration" in data


def test_query_endpoint_validation(test_client: TestClient):
    """Test query endpoint input validation."""
    # Test empty query
    response = test_client.post("/query", json={"query": ""})
    assert response.status_code == 422  # Validation error
    
    # Test query too long
    long_query = "a" * 1001
    response = test_client.post("/query", json={"query": long_query})
    assert response.status_code == 422


def test_query_endpoint_with_no_results(test_client: TestClient):
    """Test query endpoint when no results are found."""
    with patch("src.api.main.get_service") as mock_get_service:
        # Mock query processor to return no results
        mock_query_processor = Mock()
        mock_query_result = Mock()
        mock_query_result.results = []
        mock_query_result.processing_time_ms = 100
        mock_query_processor.process_query.return_value = mock_query_result
        
        mock_get_service.return_value = mock_query_processor
        
        response = test_client.post("/query", json={"query": "test query"})
        assert response.status_code == 200
        data = response.json()
        assert "couldn't find any relevant information" in data["answer"].lower()
        assert len(data["sources"]) == 0


def test_upload_endpoint_invalid_file_type(test_client: TestClient):
    """Test upload endpoint with non-PDF file."""
    response = test_client.post(
        "/documents/upload",
        files={"file": ("test.txt", b"test content", "text/plain")}
    )
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "error" in data["detail"]
    assert data["detail"]["error"]["code"] == "INVALID_FILE_TYPE"


def test_upload_endpoint_file_too_large(test_client: TestClient):
    """Test upload endpoint with file exceeding size limit."""
    # Create a large file (> 50MB)
    large_content = b"x" * (51 * 1024 * 1024)
    
    response = test_client.post(
        "/documents/upload",
        files={"file": ("large.pdf", large_content, "application/pdf")}
    )
    assert response.status_code == 413
    data = response.json()
    assert "detail" in data
    assert "error" in data["detail"]
    assert data["detail"]["error"]["code"] == "FILE_TOO_LARGE"


def test_upload_endpoint_success(test_client: TestClient):
    """Test successful document upload."""
    with patch("src.api.main.get_service") as mock_get_service:
        # Mock document processor
        mock_doc_processor = Mock()
        mock_processing_result = Mock()
        mock_processing_result.success = True
        mock_processing_result.chunks = [Mock(), Mock()]
        mock_processing_result.metadata = {"title": "Test Doc", "page_count": 5}
        mock_doc_processor.process_document.return_value = mock_processing_result
        
        # Mock embedding service
        mock_embedding_service = Mock()
        mock_embedding = Mock()
        mock_embedding.vector = [0.1] * 1536
        mock_embedding_service.generate_embeddings.return_value = [mock_embedding, mock_embedding]
        
        # Mock vector database
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
        
        # Create a small PDF-like file
        pdf_content = b"%PDF-1.4 test content"
        
        response = test_client.post(
            "/documents/upload",
            files={"file": ("test.pdf", pdf_content, "application/pdf")}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert data["filename"] == "test.pdf"
        assert data["chunks_created"] == 2
        assert "document_id" in data
        assert "processing_time_ms" in data


def test_upload_endpoint_processing_failure(test_client: TestClient):
    """Test upload endpoint when document processing fails."""
    with patch("src.api.main.get_service") as mock_get_service:
        # Mock document processor to return failure
        mock_doc_processor = Mock()
        mock_processing_result = Mock()
        mock_processing_result.success = False
        mock_processing_result.error_message = "Failed to extract text"
        mock_doc_processor.process_document.return_value = mock_processing_result
        
        mock_get_service.return_value = mock_doc_processor
        
        pdf_content = b"%PDF-1.4 test content"
        
        response = test_client.post(
            "/documents/upload",
            files={"file": ("test.pdf", pdf_content, "application/pdf")}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"]["code"] == "PROCESSING_FAILED"


def test_query_endpoint_success(test_client: TestClient):
    """Test successful query processing."""
    with patch("src.api.main.get_service") as mock_get_service:
        # Mock query processor
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
        mock_query_result.processing_time_ms = 100
        mock_query_processor.process_query.return_value = mock_query_result
        
        # Mock LLM service
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
        
        response = test_client.post("/query", json={"query": "test query"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "This is the answer"
        assert len(data["sources"]) == 1
        assert data["sources"][0]["document_name"] == "test.pdf"
        assert data["confidence_score"] == 0.85
        assert data["grounded"] is True
        assert data["model_name"] == "gpt-4"


def test_highlighted_page_endpoint_not_implemented(test_client: TestClient):
    """Test that highlighted page endpoint returns not implemented."""
    response = test_client.get("/documents/test-doc-id/page/1")
    assert response.status_code == 501
    data = response.json()
    assert "detail" in data
    assert "error" in data["detail"]
    assert data["detail"]["error"]["code"] == "NOT_IMPLEMENTED"


def test_query_request_validation(test_client: TestClient):
    """Test query request model validation."""
    # Test invalid search_type
    response = test_client.post("/query", json={
        "query": "test",
        "search_type": "invalid"
    })
    assert response.status_code == 422
    
    # Test max_results out of range
    response = test_client.post("/query", json={
        "query": "test",
        "max_results": 100  # Exceeds max of 20
    })
    assert response.status_code == 422
    
    # Test negative max_results
    response = test_client.post("/query", json={
        "query": "test",
        "max_results": -1
    })
    assert response.status_code == 422