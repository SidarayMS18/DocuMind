"""Integration tests for the document ingestion pipeline."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.processing.document_processor import DocumentProcessor, ProcessingResult
from src.search.embedding_service import EmbeddingService
from src.search.vector_database import VectorDatabase
import io


@pytest.fixture
def sample_pdf_content():
    """Create a minimal PDF content for testing."""
    # This is a very basic PDF structure - in real tests you'd use a proper PDF
    # For now, we'll mock the PDF processing
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"


def test_document_processor_basic_functionality():
    """Test that DocumentProcessor can process a document without errors."""
    processor = DocumentProcessor()
    
    # Mock PyMuPDF to avoid needing real PDF files
    with patch('src.processing.document_processor.fitz') as mock_fitz:
        # Mock document
        mock_doc = Mock()
        mock_doc.__len__ = Mock(return_value=1)  # 1 page
        mock_doc.metadata = {
            'title': 'Test Document',
            'author': 'Test Author',
            'creationDate': '2024-01-01'
        }
        
        # Mock page
        mock_page = Mock()
        mock_page.get_text.return_value = {
            'blocks': [{
                'lines': [{
                    'spans': [{
                        'text': 'This is test content.',
                        'bbox': [10.0, 20.0, 100.0, 40.0],
                        'size': 12.0,
                        'font': 'Arial'
                    }]
                }]
            }]
        }
        
        mock_doc.load_page.return_value = mock_page
        mock_doc.close = Mock()
        
        mock_fitz.open.return_value = mock_doc
        
        # Test processing
        result = processor.process_document(b"fake pdf content", "test_doc_1")
        
        assert result.success is True
        assert result.document_id == "test_doc_1"
        assert len(result.text) > 0
        assert len(result.coordinates) > 0
        assert result.metadata is not None
        assert result.error_message is None


def test_embedding_service_mock_functionality():
    """Test that EmbeddingService can be initialized and validates embeddings."""
    # Test without actually calling Azure OpenAI
    with patch('src.search.embedding_service.EmbeddingService._initialize_client'):
        service = EmbeddingService()
        
        # Test validation with empty list
        result = service.validate_embeddings([])
        assert result["valid"] is True
        assert result["count"] == 0


def test_vector_database_mock_functionality():
    """Test that VectorDatabase can be initialized."""
    # Test without actually connecting to Azure Search
    with patch('src.search.vector_database.VectorDatabase._initialize_clients'):
        with patch('src.search.vector_database.VectorDatabase._ensure_index_exists'):
            db = VectorDatabase()
            
            # Test that it initializes without errors
            assert db.index_name is not None
            assert db.max_retries == 3


def test_document_ingestion_pipeline_integration():
    """Test the complete document ingestion pipeline with mocked services."""
    # Initialize components with mocked dependencies
    processor = DocumentProcessor()
    
    with patch('src.search.embedding_service.EmbeddingService._initialize_client'):
        embedding_service = EmbeddingService()
    
    with patch('src.search.vector_database.VectorDatabase._initialize_clients'):
        with patch('src.search.vector_database.VectorDatabase._ensure_index_exists'):
            vector_db = VectorDatabase()
    
    # Mock the document processing
    with patch('src.processing.document_processor.fitz') as mock_fitz:
        # Setup mock document
        mock_doc = Mock()
        mock_doc.__len__ = Mock(return_value=1)
        mock_doc.metadata = {'title': 'Test Document'}
        
        mock_page = Mock()
        mock_page.get_text.return_value = {
            'blocks': [{
                'lines': [{
                    'spans': [{
                        'text': 'This is a test document with enough content to create a meaningful chunk for testing purposes.',
                        'bbox': [10.0, 20.0, 200.0, 40.0],
                        'size': 12.0,
                        'font': 'Arial'
                    }]
                }]
            }]
        }
        
        mock_doc.load_page.return_value = mock_page
        mock_doc.close = Mock()
        mock_fitz.open.return_value = mock_doc
        
        # Process document
        result = processor.process_document(b"fake pdf content", "test_doc_1")
        
        # Verify processing succeeded
        assert result.success is True
        assert len(result.chunks) > 0
        
        # Test embedding validation (without actual API calls)
        validation_result = embedding_service.validate_embeddings([])
        assert validation_result["valid"] is True
        
        # Test that vector database can handle empty operations
        index_result = vector_db.index_documents([])
        assert index_result.success is True
        assert index_result.indexed_count == 0


def test_error_handling_in_pipeline():
    """Test error handling in the document processing pipeline."""
    processor = DocumentProcessor()
    
    # Test with invalid PDF content
    with patch('src.processing.document_processor.fitz') as mock_fitz:
        mock_fitz.open.side_effect = Exception("Invalid PDF format")
        
        result = processor.process_document(b"invalid content", "test_doc_error")
        
        assert result.success is False
        assert result.error_message is not None
        # The error could be either from extraction failure or no text extracted
        assert ("Error processing document" in result.error_message or 
                "No text could be extracted from PDF" in result.error_message)


def test_chunking_functionality():
    """Test that document chunking works correctly."""
    processor = DocumentProcessor(chunk_size_min=50, chunk_size_max=100)
    
    # Mock PyMuPDF with longer content that will require chunking
    with patch('src.processing.document_processor.fitz') as mock_fitz:
        mock_doc = Mock()
        mock_doc.__len__ = Mock(return_value=1)
        mock_doc.metadata = {'title': 'Test Document'}
        
        # Create multiple text spans that will be chunked
        mock_page = Mock()
        mock_page.get_text.return_value = {
            'blocks': [{
                'lines': [{
                    'spans': [
                        {
                            'text': 'This is the first sentence of a longer document. ',
                            'bbox': [10.0, 20.0, 200.0, 40.0],
                            'size': 12.0,
                            'font': 'Arial'
                        },
                        {
                            'text': 'This is the second sentence that continues the content. ',
                            'bbox': [10.0, 45.0, 200.0, 65.0],
                            'size': 12.0,
                            'font': 'Arial'
                        },
                        {
                            'text': 'This is the third sentence that should create multiple chunks. ',
                            'bbox': [10.0, 70.0, 200.0, 90.0],
                            'size': 12.0,
                            'font': 'Arial'
                        }
                    ]
                }]
            }]
        }
        
        mock_doc.load_page.return_value = mock_page
        mock_doc.close = Mock()
        mock_fitz.open.return_value = mock_doc
        
        # Process document
        result = processor.process_document(b"fake pdf content", "test_doc_chunks")
        
        # Verify chunking worked
        assert result.success is True
        assert len(result.chunks) > 0
        
        # Verify chunk properties
        for chunk in result.chunks:
            assert chunk.id is not None
            assert chunk.document_id == "test_doc_chunks"
            assert len(chunk.text) > 0
            assert chunk.coordinates is not None
            assert chunk.metadata is not None