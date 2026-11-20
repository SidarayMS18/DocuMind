"""Tests for query processing and context management functionality."""

import pytest
from unittest.mock import Mock, patch
from src.search.query_processor import QueryProcessor, QueryResult
from src.search.vector_database import SearchResult
from src.llm.context_manager import ContextManager, ContextWindow, SourceAttribution
from src.search.embedding_service import VectorEmbedding


@pytest.fixture
def mock_search_results():
    """Create mock search results for testing."""
    return [
        SearchResult(
            chunk_id="chunk_1",
            text="This is the first relevant document chunk about API development.",
            metadata={
                "document_id": "api_guide.pdf",
                "page_number": 1,
                "token_estimate": 12
            },
            score=0.95,
            coordinates={"x0": 10.0, "y0": 20.0, "x1": 100.0, "y1": 40.0}
        ),
        SearchResult(
            chunk_id="chunk_2", 
            text="This is the second relevant document chunk about API authentication.",
            metadata={
                "document_id": "security_guide.pdf",
                "page_number": 3,
                "token_estimate": 14
            },
            score=0.87,
            coordinates={"x0": 15.0, "y0": 25.0, "x1": 105.0, "y1": 45.0}
        )
    ]


def test_query_preprocessing():
    """Test query preprocessing functionality."""
    with patch('src.search.query_processor.EmbeddingService'):
        with patch('src.search.query_processor.VectorDatabase'):
            processor = QueryProcessor()
            
            # Test normal query
            result = processor.preprocess_query("  How do I use the API?  ")
            assert "How do I use the" in result
            assert "API" in result
            
            # Test query with special characters
            result = processor.preprocess_query("What's the @#$% API endpoint???")
            assert "endpoint" in result
            assert "@#$%" not in result
            
            # Test empty query
            with pytest.raises(ValueError, match="Query cannot be empty"):
                processor.preprocess_query("")
            
            # Test short query
            with pytest.raises(ValueError, match="Query too short"):
                processor.preprocess_query("hi")


def test_context_manager_initialization():
    """Test ContextManager initialization."""
    manager = ContextManager()
    
    assert manager.max_context_tokens == 8000
    assert manager.max_sources == 10
    assert manager.min_source_relevance == 0.1
    assert "Enterprise Document Assistant" in manager.system_template


def test_context_preparation(mock_search_results):
    """Test context preparation from search results."""
    manager = ContextManager()
    
    context_window = manager.prepare_context(mock_search_results, "test query")
    
    assert len(context_window.sources) == 2
    assert context_window.total_tokens > 0
    assert not context_window.truncated
    assert "Api Guide" in context_window.context_text
    assert "Security Guide" in context_window.context_text


def test_context_preparation_empty_results():
    """Test context preparation with empty search results."""
    manager = ContextManager()
    
    context_window = manager.prepare_context([], "test query")
    
    assert len(context_window.sources) == 0
    assert context_window.total_tokens == 0
    assert not context_window.truncated
    assert context_window.context_text == ""


def test_rag_prompt_creation(mock_search_results):
    """Test RAG prompt creation."""
    manager = ContextManager()
    
    context_window = manager.prepare_context(mock_search_results, "test query")
    rag_prompt = manager.create_rag_prompt(context_window, "How do I use the API?")
    
    assert "Enterprise Document Assistant" in rag_prompt.system_message
    assert "How do I use the API?" in rag_prompt.user_query
    assert "Api Guide" in rag_prompt.context_section
    assert rag_prompt.prompt_tokens > 0


def test_source_attribution_creation():
    """Test SourceAttribution dataclass creation."""
    source = SourceAttribution(
        document_id="test_doc.pdf",
        document_name="Test Document",
        page_number=1,
        text_excerpt="Test content",
        coordinates={"x0": 10.0, "y0": 20.0, "x1": 100.0, "y1": 40.0},
        relevance_score=0.95,
        chunk_id="chunk_1"
    )
    
    assert source.document_id == "test_doc.pdf"
    assert source.document_name == "Test Document"
    assert source.page_number == 1
    assert source.relevance_score == 0.95


def test_response_grounding_validation(mock_search_results):
    """Test response grounding validation."""
    manager = ContextManager()
    
    context_window = manager.prepare_context(mock_search_results, "test query")
    
    # Test well-grounded response
    grounded_response = "The API development guide explains how to use authentication."
    result = manager.validate_response_grounding(grounded_response, context_window)
    
    assert result["grounded"] is True
    assert result["overlap_ratio"] > 0.1
    
    # Test poorly grounded response - use completely unrelated words
    ungrounded_response = "Elephants enjoy swimming in purple oceans with magical unicorns."
    result = manager.validate_response_grounding(ungrounded_response, context_window)
    
    assert result["grounded"] is False
    assert result["overlap_ratio"] < 0.1


def test_context_token_optimization(mock_search_results):
    """Test context optimization for token limits."""
    manager = ContextManager()
    
    # Test with very low token limit
    context_window = manager.optimize_context_for_token_limit(
        mock_search_results, "test query", max_tokens=50
    )
    
    assert context_window.total_tokens <= 50
    assert len(context_window.sources) <= len(mock_search_results)


def test_context_summary(mock_search_results):
    """Test context summary generation."""
    manager = ContextManager()
    
    context_window = manager.prepare_context(mock_search_results, "test query")
    summary = manager.get_context_summary(context_window)
    
    assert summary["total_sources"] == 2
    assert summary["total_tokens"] > 0
    assert not summary["truncated"]
    assert len(summary["documents"]) == 2
    assert summary["page_range"]["min"] == 1
    assert summary["page_range"]["max"] == 3


def test_query_result_dataclass():
    """Test QueryResult dataclass creation."""
    result = QueryResult(
        query="test query",
        processed_query="test query",
        results=[],
        total_results=0,
        processing_time_ms=100,
        search_type="hybrid"
    )
    
    assert result.query == "test query"
    assert result.total_results == 0
    assert result.processing_time_ms == 100
    assert result.search_type == "hybrid"