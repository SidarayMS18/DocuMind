"""Tests for Azure Blob Storage service."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from io import BytesIO

from src.storage.blob_storage import BlobStorageService


@pytest.fixture
def mock_blob_service():
    """Create a mock blob storage service for testing."""
    with patch("src.storage.blob_storage.BlobServiceClient") as mock_client:
        # Mock container client
        mock_container = MagicMock()
        mock_client.from_connection_string.return_value.get_container_client.return_value = mock_container
        
        # Mock settings
        with patch("src.storage.blob_storage.get_settings") as mock_settings:
            settings = Mock()
            settings.get_azure_storage_config.return_value = {
                "account_name": "test_account",
                "account_key": "test_key",
                "container_name": "test-container"
            }
            mock_settings.return_value = settings
            
            service = BlobStorageService()
            service.container_client = mock_container
            yield service, mock_container


def test_upload_document(mock_blob_service):
    """Test document upload with metadata."""
    service, mock_container = mock_blob_service
    
    # Mock blob client
    mock_blob_client = MagicMock()
    mock_container.get_blob_client.return_value = mock_blob_client
    mock_blob_client.url = "https://test.blob.core.windows.net/test-container/documents/doc123.pdf"
    
    # Test upload
    document_id = "doc123"
    file_data = b"test pdf content"
    metadata = {"author": "Test User"}
    
    result = service.upload_document(document_id, file_data, metadata=metadata)
    
    # Verify upload was called
    mock_blob_client.upload_blob.assert_called_once()
    
    # Verify result
    assert result["document_id"] == document_id
    assert result["blob_name"] == "documents/doc123.pdf"
    assert result["size_bytes"] == len(file_data)
    assert "upload_timestamp" in result
    assert result["metadata"]["author"] == "Test User"


def test_download_document(mock_blob_service):
    """Test document download."""
    service, mock_container = mock_blob_service
    
    # Mock blob client and download
    mock_blob_client = MagicMock()
    mock_container.get_blob_client.return_value = mock_blob_client
    
    mock_download = MagicMock()
    mock_download.readall.return_value = b"test pdf content"
    mock_blob_client.download_blob.return_value = mock_download
    
    # Test download
    document_id = "doc123"
    file_data = service.download_document(document_id)
    
    # Verify download was called
    mock_blob_client.download_blob.assert_called_once()
    assert file_data == b"test pdf content"


def test_download_document_not_found(mock_blob_service):
    """Test download of non-existent document."""
    service, mock_container = mock_blob_service
    
    # Mock blob client to raise ResourceNotFoundError
    from azure.core.exceptions import ResourceNotFoundError
    mock_blob_client = MagicMock()
    mock_container.get_blob_client.return_value = mock_blob_client
    mock_blob_client.download_blob.side_effect = ResourceNotFoundError("Not found")
    
    # Test download should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        service.download_document("nonexistent")


def test_get_document_metadata(mock_blob_service):
    """Test retrieving document metadata."""
    service, mock_container = mock_blob_service
    
    # Mock blob client and properties
    mock_blob_client = MagicMock()
    mock_container.get_blob_client.return_value = mock_blob_client
    
    mock_properties = MagicMock()
    mock_properties.size = 1024
    mock_properties.content_settings.content_type = "application/pdf"
    mock_properties.creation_time = datetime(2024, 1, 1, 12, 0, 0)
    mock_properties.last_modified = datetime(2024, 1, 2, 12, 0, 0)
    mock_properties.metadata = {"author": "Test User"}
    mock_blob_client.get_blob_properties.return_value = mock_properties
    
    # Test get metadata
    document_id = "doc123"
    metadata = service.get_document_metadata(document_id)
    
    # Verify metadata
    assert metadata["document_id"] == document_id
    assert metadata["size_bytes"] == 1024
    assert metadata["content_type"] == "application/pdf"
    assert metadata["metadata"]["author"] == "Test User"


def test_delete_document(mock_blob_service):
    """Test document deletion."""
    service, mock_container = mock_blob_service
    
    # Mock blob client
    mock_blob_client = MagicMock()
    mock_container.get_blob_client.return_value = mock_blob_client
    
    # Test delete
    document_id = "doc123"
    result = service.delete_document(document_id)
    
    # Verify delete was called
    mock_blob_client.delete_blob.assert_called_once()
    assert result is True


def test_list_documents(mock_blob_service):
    """Test listing documents."""
    service, mock_container = mock_blob_service
    
    # Mock blob list
    mock_blob1 = MagicMock()
    mock_blob1.name = "documents/doc1.pdf"
    mock_blob1.size = 1024
    mock_blob1.last_modified = datetime(2024, 1, 1, 12, 0, 0)
    mock_blob1.metadata = {}
    
    mock_blob2 = MagicMock()
    mock_blob2.name = "documents/doc2.pdf"
    mock_blob2.size = 2048
    mock_blob2.last_modified = datetime(2024, 1, 2, 12, 0, 0)
    mock_blob2.metadata = {"author": "Test"}
    
    mock_container.list_blobs.return_value = [mock_blob1, mock_blob2]
    
    # Test list
    documents = service.list_documents()
    
    # Verify results
    assert len(documents) == 2
    assert documents[0]["document_id"] == "doc1"
    assert documents[1]["document_id"] == "doc2"
    assert documents[1]["metadata"]["author"] == "Test"


def test_backup_document(mock_blob_service):
    """Test document backup."""
    service, mock_container = mock_blob_service
    
    # Mock source blob client
    mock_source_blob = MagicMock()
    mock_source_blob.url = "https://test.blob.core.windows.net/test-container/documents/doc123.pdf"
    mock_container.get_blob_client.return_value = mock_source_blob
    
    # Mock backup container
    mock_backup_container = MagicMock()
    service.blob_service_client.get_container_client.return_value = mock_backup_container
    
    mock_backup_blob = MagicMock()
    mock_backup_container.get_blob_client.return_value = mock_backup_blob
    
    # Test backup
    document_id = "doc123"
    result = service.backup_document(document_id)
    
    # Verify backup was created
    mock_backup_blob.start_copy_from_url.assert_called_once_with(mock_source_blob.url)
    assert result["document_id"] == document_id
    assert "backup_timestamp" in result
