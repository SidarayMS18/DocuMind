"""Azure Blob Storage service for secure document storage."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from io import BytesIO

from azure.storage.blob import (
    BlobServiceClient,
    BlobClient,
    ContainerClient,
    generate_blob_sas,
    BlobSasPermissions,
    ContentSettings
)
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class BlobStorageService:
    """Service for managing document storage in Azure Blob Storage with encryption and access controls."""
    
    def __init__(self):
        """Initialize Azure Blob Storage client with configuration from settings."""
        settings = get_settings()
        storage_config = settings.get_azure_storage_config()
        
        self.account_name = storage_config["account_name"]
        self.account_key = storage_config["account_key"]
        self.container_name = storage_config["container_name"]
        
        if not self.account_name or not self.account_key:
            raise ValueError("Azure Storage credentials not configured")
        
        # Create connection string
        connection_string = (
            f"DefaultEndpointsProtocol=https;"
            f"AccountName={self.account_name};"
            f"AccountKey={self.account_key};"
            f"EndpointSuffix=core.windows.net"
        )
        
        # Initialize blob service client
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_client = self.blob_service_client.get_container_client(self.container_name)
        
        # Ensure container exists
        self._ensure_container_exists()
        
        logger.info(f"Initialized BlobStorageService for container: {self.container_name}")
    
    def _ensure_container_exists(self) -> None:
        """Create container if it doesn't exist with proper encryption settings."""
        try:
            self.container_client.create_container()
            logger.info(f"Created container: {self.container_name}")
        except ResourceExistsError:
            logger.debug(f"Container already exists: {self.container_name}")
        except Exception as e:
            logger.error(f"Error ensuring container exists: {e}")
            raise
    
    def upload_document(
        self,
        document_id: str,
        file_data: bytes,
        content_type: str = "application/pdf",
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Upload a document to blob storage with encryption and metadata.
        
        Args:
            document_id: Unique identifier for the document
            file_data: Binary content of the document
            content_type: MIME type of the document
            metadata: Optional metadata to store with the document
            
        Returns:
            Dictionary containing upload result with blob URL and metadata
        """
        try:
            blob_name = f"documents/{document_id}.pdf"
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Set content settings
            content_settings = ContentSettings(content_type=content_type)
            
            # Add upload timestamp to metadata
            upload_metadata = metadata or {}
            upload_metadata["upload_timestamp"] = datetime.now(timezone.utc).isoformat()
            upload_metadata["document_id"] = document_id
            
            # Upload with encryption (Azure Storage encrypts by default)
            blob_client.upload_blob(
                file_data,
                overwrite=True,
                content_settings=content_settings,
                metadata=upload_metadata
            )
            
            logger.info(f"Uploaded document: {document_id} to {blob_name}")
            
            return {
                "document_id": document_id,
                "blob_name": blob_name,
                "blob_url": blob_client.url,
                "size_bytes": len(file_data),
                "upload_timestamp": upload_metadata["upload_timestamp"],
                "metadata": upload_metadata
            }
            
        except Exception as e:
            logger.error(f"Error uploading document {document_id}: {e}")
            raise
    
    def download_document(self, document_id: str) -> bytes:
        """
        Download a document from blob storage.
        
        Args:
            document_id: Unique identifier for the document
            
        Returns:
            Binary content of the document
        """
        try:
            blob_name = f"documents/{document_id}.pdf"
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Download blob content
            download_stream = blob_client.download_blob()
            file_data = download_stream.readall()
            
            logger.info(f"Downloaded document: {document_id}")
            return file_data
            
        except ResourceNotFoundError:
            logger.error(f"Document not found: {document_id}")
            raise FileNotFoundError(f"Document {document_id} not found in storage")
        except Exception as e:
            logger.error(f"Error downloading document {document_id}: {e}")
            raise
    
    def get_document_metadata(self, document_id: str) -> Dict[str, Any]:
        """
        Retrieve metadata for a document.
        
        Args:
            document_id: Unique identifier for the document
            
        Returns:
            Dictionary containing document metadata
        """
        try:
            blob_name = f"documents/{document_id}.pdf"
            blob_client = self.container_client.get_blob_client(blob_name)
            
            properties = blob_client.get_blob_properties()
            
            return {
                "document_id": document_id,
                "blob_name": blob_name,
                "size_bytes": properties.size,
                "content_type": properties.content_settings.content_type,
                "created_on": properties.creation_time.isoformat() if properties.creation_time else None,
                "last_modified": properties.last_modified.isoformat() if properties.last_modified else None,
                "metadata": properties.metadata or {}
            }
            
        except ResourceNotFoundError:
            logger.error(f"Document not found: {document_id}")
            raise FileNotFoundError(f"Document {document_id} not found in storage")
        except Exception as e:
            logger.error(f"Error retrieving metadata for {document_id}: {e}")
            raise
    
    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from blob storage.
        
        Args:
            document_id: Unique identifier for the document
            
        Returns:
            True if deletion was successful
        """
        try:
            blob_name = f"documents/{document_id}.pdf"
            blob_client = self.container_client.get_blob_client(blob_name)
            
            blob_client.delete_blob()
            logger.info(f"Deleted document: {document_id}")
            return True
            
        except ResourceNotFoundError:
            logger.warning(f"Document not found for deletion: {document_id}")
            return False
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {e}")
            raise
    
    def list_documents(self, prefix: str = "documents/") -> List[Dict[str, Any]]:
        """
        List all documents in storage.
        
        Args:
            prefix: Blob name prefix to filter results
            
        Returns:
            List of document metadata dictionaries
        """
        try:
            blobs = self.container_client.list_blobs(name_starts_with=prefix)
            
            documents = []
            for blob in blobs:
                documents.append({
                    "blob_name": blob.name,
                    "document_id": blob.name.replace("documents/", "").replace(".pdf", ""),
                    "size_bytes": blob.size,
                    "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
                    "metadata": blob.metadata or {}
                })
            
            logger.info(f"Listed {len(documents)} documents")
            return documents
            
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            raise
    
    def generate_sas_url(
        self,
        document_id: str,
        expiry_hours: int = 1,
        permissions: str = "r"
    ) -> str:
        """
        Generate a time-limited SAS URL for secure document access.
        
        Args:
            document_id: Unique identifier for the document
            expiry_hours: Number of hours until the URL expires
            permissions: SAS permissions (r=read, w=write, d=delete)
            
        Returns:
            SAS URL for accessing the document
        """
        try:
            blob_name = f"documents/{document_id}.pdf"
            
            # Set SAS permissions
            sas_permissions = BlobSasPermissions(read="r" in permissions)
            
            # Generate SAS token
            sas_token = generate_blob_sas(
                account_name=self.account_name,
                container_name=self.container_name,
                blob_name=blob_name,
                account_key=self.account_key,
                permission=sas_permissions,
                expiry=datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
            )
            
            # Construct full URL
            blob_url = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}"
            sas_url = f"{blob_url}?{sas_token}"
            
            logger.info(f"Generated SAS URL for document: {document_id}")
            return sas_url
            
        except Exception as e:
            logger.error(f"Error generating SAS URL for {document_id}: {e}")
            raise
    
    def backup_document(self, document_id: str, backup_container: str = "backups") -> Dict[str, Any]:
        """
        Create a backup copy of a document in a separate container.
        
        Args:
            document_id: Unique identifier for the document
            backup_container: Name of the backup container
            
        Returns:
            Dictionary containing backup information
        """
        try:
            source_blob_name = f"documents/{document_id}.pdf"
            backup_blob_name = f"{document_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
            
            # Get source blob client
            source_blob_client = self.container_client.get_blob_client(source_blob_name)
            
            # Get or create backup container
            backup_container_client = self.blob_service_client.get_container_client(backup_container)
            try:
                backup_container_client.create_container()
            except ResourceExistsError:
                pass
            
            # Copy blob to backup container
            backup_blob_client = backup_container_client.get_blob_client(backup_blob_name)
            backup_blob_client.start_copy_from_url(source_blob_client.url)
            
            logger.info(f"Created backup for document: {document_id}")
            
            return {
                "document_id": document_id,
                "backup_blob_name": backup_blob_name,
                "backup_container": backup_container,
                "backup_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error backing up document {document_id}: {e}")
            raise
