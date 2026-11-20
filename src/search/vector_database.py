"""Vector database interface for storing and retrieving embeddings using Azure AI Search."""

import logging
import time
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import VectorizedQuery
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticSearch,
    SemanticPrioritizedFields,
    SemanticField
)
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from src.search.embedding_service import VectorEmbedding
from src.config.settings import get_settings


@dataclass
class SearchResult:
    """Represents a search result with relevance score."""
    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    score: float
    coordinates: Optional[Dict[str, float]] = None


@dataclass
class IndexResult:
    """Result of indexing operation."""
    success: bool
    indexed_count: int
    error_message: Optional[str] = None


class VectorDatabase:
    """Azure AI Search implementation for vector storage and retrieval operations."""
    
    def __init__(self, connection_string: Optional[str] = None):
        self.settings = get_settings()
        self.index_name = self.settings.azure_search_index_name
        
        # Initialize clients
        self._initialize_clients()
        
        # Retry configuration
        self.max_retries = 3
        self.base_delay = 1.0
        self.max_delay = 30.0
        
        # Batch configuration
        self.batch_size = 100
        
        # Ensure index exists
        self._ensure_index_exists()
    
    def _initialize_clients(self):
        """Initialize Azure AI Search clients."""
        try:
            if not all([
                self.settings.azure_search_endpoint,
                self.settings.azure_search_api_key
            ]):
                raise ValueError(
                    "Missing required Azure AI Search configuration. "
                    "Please set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY environment variables."
                )
            
            credential = AzureKeyCredential(self.settings.azure_search_api_key)
            
            self.index_client = SearchIndexClient(
                endpoint=self.settings.azure_search_endpoint,
                credential=credential
            )
            
            self.search_client = SearchClient(
                endpoint=self.settings.azure_search_endpoint,
                index_name=self.index_name,
                credential=credential
            )
            
            logging.info(f"Initialized Azure AI Search clients for index: {self.index_name}")
            
        except Exception as e:
            logging.error(f"Failed to initialize Azure AI Search clients: {str(e)}")
            raise
    
    def _ensure_index_exists(self):
        """Create the search index if it doesn't exist."""
        try:
            # Try to get existing index
            try:
                existing_index = self.index_client.get_index(self.index_name)
                logging.info(f"Using existing search index: {self.index_name}")
                return
            except ResourceNotFoundError:
                # Index doesn't exist, create it
                pass
            
            # Define the search index schema
            fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                SimpleField(name="chunk_id", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="document_id", type=SearchFieldDataType.String, filterable=True),
                SearchableField(name="text", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
                SimpleField(name="page_number", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
                
                # Coordinate fields
                SimpleField(name="x0", type=SearchFieldDataType.Double, filterable=True),
                SimpleField(name="y0", type=SearchFieldDataType.Double, filterable=True),
                SimpleField(name="x1", type=SearchFieldDataType.Double, filterable=True),
                SimpleField(name="y1", type=SearchFieldDataType.Double, filterable=True),
                
                # Metadata fields
                SimpleField(name="embedding_model", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="token_estimate", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
                SimpleField(name="char_count", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
                
                # Vector field for embeddings (1536 dimensions for text-embedding-ada-002)
                SearchField(
                    name="embedding_vector",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=1536,
                    vector_search_profile_name="default-vector-profile"
                )
            ]
            
            # Configure vector search
            vector_search = VectorSearch(
                algorithms=[
                    HnswAlgorithmConfiguration(
                        name="default-hnsw-algorithm",
                        parameters={
                            "m": 4,
                            "efConstruction": 400,
                            "efSearch": 500,
                            "metric": "cosine"
                        }
                    )
                ],
                profiles=[
                    VectorSearchProfile(
                        name="default-vector-profile",
                        algorithm_configuration_name="default-hnsw-algorithm"
                    )
                ]
            )
            
            # Configure semantic search for hybrid search capabilities
            semantic_config = SemanticConfiguration(
                name="default-semantic-config",
                prioritized_fields=SemanticPrioritizedFields(
                    content_fields=[SemanticField(field_name="text")]
                )
            )
            
            semantic_search = SemanticSearch(configurations=[semantic_config])
            
            # Create the index
            index = SearchIndex(
                name=self.index_name,
                fields=fields,
                vector_search=vector_search,
                semantic_search=semantic_search
            )
            
            self.index_client.create_index(index)
            logging.info(f"Created new search index: {self.index_name}")
            
        except ResourceExistsError:
            logging.info(f"Search index already exists: {self.index_name}")
        except Exception as e:
            logging.error(f"Failed to create search index: {str(e)}")
            raise
    
    def index_documents(self, embeddings: List[VectorEmbedding]) -> IndexResult:
        """Store document embeddings in the vector database with batch processing."""
        if not embeddings:
            return IndexResult(success=True, indexed_count=0)
        
        try:
            total_indexed = 0
            
            # Process embeddings in batches
            for i in range(0, len(embeddings), self.batch_size):
                batch = embeddings[i:i + self.batch_size]
                batch_result = self._index_batch(batch)
                
                if not batch_result.success:
                    return IndexResult(
                        success=False,
                        indexed_count=total_indexed,
                        error_message=batch_result.error_message
                    )
                
                total_indexed += batch_result.indexed_count
                
                # Small delay between batches
                if i + self.batch_size < len(embeddings):
                    time.sleep(0.1)
            
            logging.info(f"Successfully indexed {total_indexed} documents")
            return IndexResult(success=True, indexed_count=total_indexed)
            
        except Exception as e:
            error_msg = f"Failed to index documents: {str(e)}"
            logging.error(error_msg)
            return IndexResult(
                success=False,
                indexed_count=0,
                error_message=error_msg
            )
    
    def _index_batch(self, embeddings: List[VectorEmbedding]) -> IndexResult:
        """Index a batch of embeddings with retry logic."""
        documents = []
        
        for embedding in embeddings:
            # Extract coordinates from metadata
            coordinates = embedding.metadata.get("coordinates", {})
            
            document = {
                "id": embedding.chunk_id or f"doc_{len(documents)}",
                "chunk_id": embedding.chunk_id,
                "document_id": embedding.metadata.get("document_id", ""),
                "text": embedding.text,
                "page_number": embedding.metadata.get("page_number", 1),
                "x0": coordinates.get("x0", 0.0),
                "y0": coordinates.get("y0", 0.0),
                "x1": coordinates.get("x1", 0.0),
                "y1": coordinates.get("y1", 0.0),
                "embedding_model": embedding.metadata.get("embedding_model", ""),
                "token_estimate": embedding.metadata.get("token_estimate", 0),
                "char_count": embedding.metadata.get("char_count", len(embedding.text)),
                "embedding_vector": embedding.vector
            }
            documents.append(document)
        
        for attempt in range(self.max_retries):
            try:
                result = self.search_client.upload_documents(documents)
                
                # Check for any failures in the batch
                failed_count = sum(1 for r in result if not r.succeeded)
                if failed_count > 0:
                    logging.warning(f"{failed_count} documents failed to index in batch")
                
                success_count = len(result) - failed_count
                return IndexResult(success=True, indexed_count=success_count)
                
            except Exception as e:
                logging.warning(f"Batch indexing attempt {attempt + 1} failed: {str(e)}")
                
                if attempt == self.max_retries - 1:
                    error_msg = f"Failed to index batch after {self.max_retries} attempts: {str(e)}"
                    logging.error(error_msg)
                    return IndexResult(
                        success=False,
                        indexed_count=0,
                        error_message=error_msg
                    )
                
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                logging.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
        
        return IndexResult(success=False, indexed_count=0, error_message="Unexpected error")
    
    def search_similar(self, query_embedding: VectorEmbedding, k: int = 5) -> List[SearchResult]:
        """Search for similar documents using vector similarity with optimized query."""
        try:
            vector_query = VectorizedQuery(
                vector=query_embedding.vector,
                k_nearest_neighbors=k,
                fields="embedding_vector"
            )
            
            # Optimized search with select to reduce payload size
            results = self.search_client.search(
                search_text=None,
                vector_queries=[vector_query],
                top=k,
                select=["chunk_id", "text", "document_id", "page_number", 
                       "x0", "y0", "x1", "y1", "embedding_model", 
                       "token_estimate", "char_count"]
            )
            
            search_results = []
            for result in results:
                coordinates = {
                    "x0": result.get("x0", 0.0),
                    "y0": result.get("y0", 0.0),
                    "x1": result.get("x1", 0.0),
                    "y1": result.get("y1", 0.0)
                }
                
                metadata = {
                    "document_id": result.get("document_id", ""),
                    "page_number": result.get("page_number", 1),
                    "embedding_model": result.get("embedding_model", ""),
                    "token_estimate": result.get("token_estimate", 0),
                    "char_count": result.get("char_count", 0)
                }
                
                search_result = SearchResult(
                    chunk_id=result.get("chunk_id", ""),
                    text=result.get("text", ""),
                    metadata=metadata,
                    score=result.get("@search.score", 0.0),
                    coordinates=coordinates
                )
                search_results.append(search_result)
            
            logging.info(f"Vector search returned {len(search_results)} results")
            return search_results
            
        except Exception as e:
            logging.error(f"Vector search failed: {str(e)}")
            return []
    
    def hybrid_search(self, query: str, query_embedding: VectorEmbedding, k: int = 5) -> List[SearchResult]:
        """Perform hybrid search combining vector and text search with optimized query."""
        try:
            vector_query = VectorizedQuery(
                vector=query_embedding.vector,
                k_nearest_neighbors=k,
                fields="embedding_vector"
            )
            
            # Optimized search with select to reduce payload size
            results = self.search_client.search(
                search_text=query,
                vector_queries=[vector_query],
                top=k,
                query_type="semantic",
                semantic_configuration_name="default-semantic-config",
                select=["chunk_id", "text", "document_id", "page_number", 
                       "x0", "y0", "x1", "y1", "embedding_model", 
                       "token_estimate", "char_count"]
            )
            
            search_results = []
            for result in results:
                coordinates = {
                    "x0": result.get("x0", 0.0),
                    "y0": result.get("y0", 0.0),
                    "x1": result.get("x1", 0.0),
                    "y1": result.get("y1", 0.0)
                }
                
                metadata = {
                    "document_id": result.get("document_id", ""),
                    "page_number": result.get("page_number", 1),
                    "embedding_model": result.get("embedding_model", ""),
                    "token_estimate": result.get("token_estimate", 0),
                    "char_count": result.get("char_count", 0),
                    "semantic_score": result.get("@search.reranker_score")
                }
                
                search_result = SearchResult(
                    chunk_id=result.get("chunk_id", ""),
                    text=result.get("text", ""),
                    metadata=metadata,
                    score=result.get("@search.score", 0.0),
                    coordinates=coordinates
                )
                search_results.append(search_result)
            
            logging.info(f"Hybrid search returned {len(search_results)} results")
            return search_results
            
        except Exception as e:
            logging.error(f"Hybrid search failed: {str(e)}")
            # Fallback to vector search only
            logging.info("Falling back to vector search only")
            return self.search_similar(query_embedding, k)
    
    def delete_document(self, document_id: str) -> bool:
        """Delete all chunks for a specific document."""
        try:
            # Search for all chunks of the document
            results = self.search_client.search(
                search_text="*",
                filter=f"document_id eq '{document_id}'",
                select=["id"]
            )
            
            # Collect document IDs to delete
            docs_to_delete = [{"id": result["id"]} for result in results]
            
            if docs_to_delete:
                delete_result = self.search_client.delete_documents(docs_to_delete)
                success_count = sum(1 for r in delete_result if r.succeeded)
                logging.info(f"Deleted {success_count} chunks for document {document_id}")
                return success_count > 0
            else:
                logging.info(f"No chunks found for document {document_id}")
                return True
                
        except Exception as e:
            logging.error(f"Failed to delete document {document_id}: {str(e)}")
            return False
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the search index."""
        try:
            # Get document count
            results = self.search_client.search(
                search_text="*",
                include_total_count=True,
                top=0
            )
            
            document_count = results.get_count()
            
            # Get unique document count
            unique_docs_results = self.search_client.search(
                search_text="*",
                facets=["document_id"],
                top=0
            )
            
            unique_document_count = len(unique_docs_results.get_facets().get("document_id", []))
            
            return {
                "total_chunks": document_count,
                "unique_documents": unique_document_count,
                "index_name": self.index_name
            }
            
        except Exception as e:
            logging.error(f"Failed to get index stats: {str(e)}")
            return {
                "total_chunks": 0,
                "unique_documents": 0,
                "index_name": self.index_name,
                "error": str(e)
            }