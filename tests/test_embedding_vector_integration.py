"""Integration tests for embedding service and vector database."""

import pytest
from unittest.mock import Mock, patch
from src.search.embedding_service import EmbeddingService, VectorEmbedding
from src.search.vector_database import VectorDatabase, SearchResult, IndexResult
from src.processing.document_processor import DocumentChunk, BoundingBox


@pytest.fixture
def mock_document_chunk():
    """Create a mock document chunk for testing."""
    return DocumentChunk(
        id="test_chunk_1",
        document_id="test_doc_1",
        text="This is a test document chunk with some sample text content.",
        page_number=1,
        coordinates=BoundingBox(x0=10.0, y0=20.0, x1=100.0, y1=40.0),
        metadata={
            "token_estimate": 15,
            "char_count": 65,
            "font_sizes": [12.0],
            "font_names": ["Arial"]
        }
    )


@pytest.fixture
def mock_vector_embedding():
    """Create a mock vector embedding for testing."""
    return VectorEmbedding(
        vector=[0.1] * 1536,  # Mock 1536-dimensional vector
        text="This is a test document chunk with some sample text content.",
        metadata={
            "document_id": "test_doc_1",
            "page_number": 1,
            "coordinates": {
                "x0": 10.0,
                "y0": 20.0,
                "x1": 100.0,
                "y1": 40.0
            },
            "embedding_model": "text-embedding-ada-002",
            "embedding_dimensions": 1536,
            "token_estimate": 15,
            "char_count": 65
        },
        chunk_id="test_chunk_1"
    )


def test_embedding_service_initialization(test_settings):
    """Test that EmbeddingService can be initialized with proper configuration."""
    # Update test settings to include embedding deployment
    test_settings.azure_openai_embedding_deployment = "text-embedding-ada-002"
    
    with patch('src.search.embedding_service.get_settings', return_value=test_settings):
        with patch('src.search.embedding_service.AzureOpenAI') as mock_client:
            # Mock the Azure OpenAI client
            mock_client.return_value = Mock()
            
            service = EmbeddingService()
            
            assert service.model_name == "text-embedding-ada-002"
            assert service.max_retries == 3
            assert service.batch_size == 100
            mock_client.assert_called_once()


def test_vector_database_initialization(test_settings):
    """Test that VectorDatabase can be initialized with proper configuration."""
    with patch('src.search.vector_database.get_settings', return_value=test_settings):
        with patch('src.search.vector_database.SearchIndexClient') as mock_index_client:
            with patch('src.search.vector_database.SearchClient') as mock_search_client:
                with patch.object(VectorDatabase, '_ensure_index_exists'):
                    # Mock the Azure clients
                    mock_index_client.return_value = Mock()
                    mock_search_client.return_value = Mock()
                    
                    db = VectorDatabase()
                    
                    assert db.index_name == test_settings.azure_search_index_name
                    assert db.max_retries == 3
                    assert db.batch_size == 100
                    mock_index_client.assert_called_once()
                    mock_search_client.assert_called_once()


def test_embedding_validation():
    """Test embedding validation functionality."""
    # Create a mock service without initializing the client
    with patch('src.search.embedding_service.EmbeddingService._initialize_client'):
        service = EmbeddingService()
        
        # Test valid embeddings
        valid_embeddings = [
            VectorEmbedding(
                vector=[0.1, 0.2, 0.3],
                text="test",
                metadata={"test": True}
            ),
            VectorEmbedding(
                vector=[0.4, 0.5, 0.6],
                text="test2",
                metadata={"test": True}
            )
        ]
        
        result = service.validate_embeddings(valid_embeddings)
        assert result["valid"] is True
        assert result["count"] == 2
        assert result["dimensions"] == 3
        assert len(result["errors"]) == 0
        
        # Test invalid embeddings
        invalid_embeddings = [
            VectorEmbedding(
                vector=[],  # Empty vector
                text="test",
                metadata={}
            ),
            VectorEmbedding(
                vector=[0.1, 0.2],  # Different dimensions
                text="test2",
                metadata={}
            )
        ]
        
        result = service.validate_embeddings(invalid_embeddings)
        assert result["valid"] is False
        assert result["count"] == 2
        assert len(result["errors"]) > 0


def test_search_result_creation():
    """Test SearchResult dataclass creation."""
    result = SearchResult(
        chunk_id="test_chunk_1",
        text="Test text content",
        metadata={"document_id": "test_doc_1"},
        score=0.85,
        coordinates={"x0": 10.0, "y0": 20.0, "x1": 100.0, "y1": 40.0}
    )
    
    assert result.chunk_id == "test_chunk_1"
    assert result.text == "Test text content"
    assert result.score == 0.85
    assert result.coordinates["x0"] == 10.0


def test_index_result_creation():
    """Test IndexResult dataclass creation."""
    # Test successful result
    success_result = IndexResult(success=True, indexed_count=5)
    assert success_result.success is True
    assert success_result.indexed_count == 5
    assert success_result.error_message is None
    
    # Test error result
    error_result = IndexResult(
        success=False,
        indexed_count=0,
        error_message="Test error"
    )
    assert error_result.success is False
    assert error_result.indexed_count == 0
    assert error_result.error_message == "Test error"


def test_empty_embeddings_handling():
    """Test handling of empty embedding lists."""
    # Create a mock service without initializing the client
    with patch('src.search.embedding_service.EmbeddingService._initialize_client'):
        service = EmbeddingService()
        
        # Test empty list validation
        result = service.validate_embeddings([])
        assert result["valid"] is True
        assert result["count"] == 0
        assert result["dimensions"] == 0
        assert len(result["errors"]) == 0


def test_vector_embedding_metadata_structure(mock_document_chunk):
    """Test that VectorEmbedding properly structures metadata from DocumentChunk."""
    # Simulate what the embedding service would create
    embedding = VectorEmbedding(
        vector=[0.1] * 1536,
        text=mock_document_chunk.text,
        metadata={
            **(mock_document_chunk.metadata or {}),
            "document_id": mock_document_chunk.document_id,
            "page_number": mock_document_chunk.page_number,
            "coordinates": {
                "x0": mock_document_chunk.coordinates.x0,
                "y0": mock_document_chunk.coordinates.y0,
                "x1": mock_document_chunk.coordinates.x1,
                "y1": mock_document_chunk.coordinates.y1
            },
            "embedding_model": "text-embedding-ada-002",
            "embedding_dimensions": 1536
        },
        chunk_id=mock_document_chunk.id
    )
    
    assert embedding.chunk_id == "test_chunk_1"
    assert embedding.metadata["document_id"] == "test_doc_1"
    assert embedding.metadata["page_number"] == 1
    assert embedding.metadata["coordinates"]["x0"] == 10.0
    assert embedding.metadata["token_estimate"] == 15
    assert embedding.metadata["embedding_dimensions"] == 1536