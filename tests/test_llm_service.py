"""Tests for LLM service and citation system."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.llm.llm_service import LLMService, LLMResponse
from src.llm.citation_service import CitationService, Citation
from src.llm.context_manager import SourceAttribution
from src.search.vector_database import SearchResult


@pytest.fixture
def mock_search_results():
    """Create mock search results for testing."""
    return [
        SearchResult(
            chunk_id="chunk_1",
            text="This is a sample text from document 1 about enterprise systems.",
            score=0.95,
            metadata={
                "document_id": "doc_1.pdf",
                "page_number": 5
            },
            coordinates={"x0": 100.0, "y0": 200.0, "x1": 400.0, "y1": 250.0}
        ),
        SearchResult(
            chunk_id="chunk_2",
            text="Additional information about document management systems.",
            score=0.87,
            metadata={
                "document_id": "doc_2.pdf",
                "page_number": 12
            },
            coordinates={"x0": 150.0, "y0": 300.0, "x1": 450.0, "y1": 350.0}
        )
    ]


@pytest.fixture
def mock_source_attribution():
    """Create mock source attribution for testing."""
    return SourceAttribution(
        document_id="doc_1.pdf",
        document_name="Document 1",
        page_number=5,
        text_excerpt="This is a sample text from document 1 about enterprise systems.",
        coordinates={"x0": 100.0, "y0": 200.0, "x1": 400.0, "y1": 250.0},
        relevance_score=0.95,
        chunk_id="chunk_1"
    )


class TestCitationService:
    """Test citation service functionality."""
    
    def test_create_citation(self, mock_source_attribution):
        """Test creating a citation from source attribution."""
        citation_service = CitationService()
        citation = citation_service.create_citation(mock_source_attribution)
        
        assert citation.document_name == "Document 1"
        assert citation.page_number == 5
        assert citation.chunk_id == "chunk_1"
        assert "Document 1" in citation.formatted_citation
        assert "Page 5" in citation.formatted_citation
    
    def test_create_citation_with_different_formats(self, mock_source_attribution):
        """Test creating citations with different formats."""
        citation_service = CitationService()
        
        # Test standard format
        citation_std = citation_service.create_citation(mock_source_attribution, "standard")
        assert "Document 1, Page 5" in citation_std.formatted_citation
        
        # Test academic format
        citation_academic = citation_service.create_citation(mock_source_attribution, "academic")
        assert "Document 1 (p. 5)" in citation_academic.formatted_citation
        
        # Test inline format
        citation_inline = citation_service.create_citation(mock_source_attribution, "inline")
        assert "[Document 1, p.5]" in citation_inline.formatted_citation
    
    def test_validate_citation(self, mock_source_attribution):
        """Test citation validation."""
        citation_service = CitationService()
        citation = citation_service.create_citation(mock_source_attribution)
        
        validation = citation_service.validate_citation(citation)
        
        assert validation.valid is True
        assert validation.total_citations == 1
        assert validation.valid_citations == 1
        assert len(validation.issues) == 0
    
    def test_validate_invalid_citation(self):
        """Test validation of invalid citation."""
        citation_service = CitationService()
        
        # Create invalid citation with missing fields
        invalid_citation = Citation(
            citation_id="test",
            document_name="",
            page_number=0,
            text_excerpt="",
            coordinates={},
            formatted_citation="",
            relevance_score=0.0,
            chunk_id=""
        )
        
        validation = citation_service.validate_citation(invalid_citation)
        
        assert validation.valid is False
        assert len(validation.issues) > 0
        assert len(validation.missing_fields) > 0
    
    def test_format_citations_for_response(self, mock_source_attribution):
        """Test formatting citations for response."""
        citation_service = CitationService()
        citations = [citation_service.create_citation(mock_source_attribution)]
        
        formatted = citation_service.format_citations_for_response(citations, "numbered")
        
        assert "Sources:" in formatted
        assert "1." in formatted
        assert "Document 1" in formatted
    
    def test_check_citation_completeness(self, mock_source_attribution):
        """Test checking citation completeness."""
        citation_service = CitationService()
        citation = citation_service.create_citation(mock_source_attribution)
        
        response_text = "This is a response with citation [1]."
        
        completeness = citation_service.check_citation_completeness(response_text, [citation])
        
        assert "completeness_score" in completeness
        assert "validation" in completeness
        assert "linking" in completeness


class TestLLMService:
    """Test LLM service functionality."""
    
    @patch('src.llm.llm_service.AzureOpenAI')
    def test_llm_service_initialization(self, mock_azure_openai):
        """Test LLM service initialization."""
        llm_service = LLMService()
        
        assert llm_service.context_manager is not None
        assert llm_service.citation_service is not None
        assert llm_service.deployment_name is not None
    
    @patch('src.llm.llm_service.AzureOpenAI')
    def test_generate_response_with_mock(self, mock_azure_openai, mock_search_results):
        """Test response generation with mocked Azure OpenAI."""
        # Create mock completion response
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "This is a test response about enterprise systems."
        mock_completion.usage.prompt_tokens = 100
        mock_completion.usage.completion_tokens = 50
        mock_completion.usage.total_tokens = 150
        
        # Setup mock client
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_completion
        mock_azure_openai.return_value = mock_client
        
        # Create service and generate response
        llm_service = LLMService()
        llm_service.client = mock_client
        
        response = llm_service.generate_response("What is an enterprise system?", mock_search_results)
        
        assert isinstance(response, LLMResponse)
        assert response.text is not None
        assert len(response.text) > 0
        assert response.total_tokens == 150
        assert len(response.citations) > 0
    
    @patch('src.llm.llm_service.AzureOpenAI')
    def test_validate_response_grounding(self, mock_azure_openai, mock_search_results):
        """Test response grounding validation."""
        llm_service = LLMService()
        
        response_text = "Enterprise systems are important for business operations."
        grounding = llm_service.validate_response_grounding(response_text, mock_search_results)
        
        assert "grounded" in grounding
        assert "confidence" in grounding
    
    @patch('src.llm.llm_service.AzureOpenAI')
    def test_check_hallucination(self, mock_azure_openai, mock_search_results):
        """Test hallucination detection."""
        llm_service = LLMService()
        
        response_text = "This is completely unrelated text about cooking recipes."
        hallucination = llm_service.check_hallucination(response_text, mock_search_results)
        
        assert "hallucination_detected" in hallucination
        assert "confidence" in hallucination
    
    @patch('src.llm.llm_service.AzureOpenAI')
    def test_get_service_status(self, mock_azure_openai):
        """Test getting service status."""
        llm_service = LLMService()
        
        status = llm_service.get_service_status()
        
        assert "service" in status
        assert status["service"] == "LLMService"
        assert "deployment_name" in status
        assert "configuration" in status


class TestCitationIntegration:
    """Test integration between LLM service and citation system."""
    
    def test_citation_service_formats(self):
        """Test all available citation formats."""
        citation_service = CitationService()
        formats = citation_service.get_available_formats()
        
        assert len(formats) > 0
        assert "standard" in formats
        assert "academic" in formats
        assert "inline" in formats
    
    def test_citation_metadata_generation(self, mock_source_attribution):
        """Test citation metadata generation for API."""
        citation_service = CitationService()
        citation = citation_service.create_citation(mock_source_attribution)
        
        metadata = citation_service.generate_citation_metadata(citation)
        
        assert "citation_id" in metadata
        assert "document_name" in metadata
        assert "page_number" in metadata
        assert "coordinates" in metadata
        assert "relevance_score" in metadata
