"""Embedding service for converting text to vectors."""

import asyncio
import logging
import time
import hashlib
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from functools import lru_cache
from openai import AzureOpenAI
from openai.types import CreateEmbeddingResponse
from src.processing.document_processor import DocumentChunk
from src.config.settings import get_settings


@dataclass
class VectorEmbedding:
    """Represents a vector embedding with metadata."""
    vector: List[float]
    text: str
    metadata: dict
    chunk_id: Optional[str] = None


class EmbeddingService:
    """Converts text chunks into vector embeddings using Azure OpenAI."""
    
    def __init__(self, model_name: str = "text-embedding-ada-002"):
        self.model_name = model_name
        self.settings = get_settings()
        self.client = None
        self._initialize_client()
        
        # Retry configuration
        self.max_retries = 3
        self.base_delay = 1.0  # Base delay in seconds
        self.max_delay = 60.0  # Maximum delay in seconds
        
        # Batch configuration
        self.batch_size = 100  # Process embeddings in batches
        
        # Embedding cache for frequently accessed queries
        self._embedding_cache: Dict[str, VectorEmbedding] = {}
        self._cache_max_size = 1000
        
        logging.info("Initialized EmbeddingService with caching enabled")
        
    def _initialize_client(self):
        """Initialize Azure OpenAI client with configuration."""
        try:
            if not all([
                self.settings.azure_openai_endpoint,
                self.settings.azure_openai_api_key,
                self.settings.azure_openai_embedding_deployment
            ]):
                raise ValueError(
                    "Missing required Azure OpenAI configuration. "
                    "Please set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, "
                    "and AZURE_OPENAI_EMBEDDING_DEPLOYMENT environment variables."
                )
            
            self.client = AzureOpenAI(
                azure_endpoint=self.settings.azure_openai_endpoint,
                api_key=self.settings.azure_openai_api_key,
                api_version=self.settings.azure_openai_api_version
            )
            
            logging.info(f"Initialized Azure OpenAI embedding client with model: {self.model_name}")
            
        except Exception as e:
            logging.error(f"Failed to initialize Azure OpenAI client: {str(e)}")
            raise
    
    def generate_embeddings(self, chunks: List[DocumentChunk]) -> List[VectorEmbedding]:
        """Generate embeddings for document chunks with batch processing and retry logic."""
        if not chunks:
            return []
        
        embeddings = []
        
        # Process chunks in batches
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]
            batch_embeddings = self._process_batch(batch)
            embeddings.extend(batch_embeddings)
            
            # Small delay between batches to avoid rate limiting
            if i + self.batch_size < len(chunks):
                time.sleep(0.1)
        
        logging.info(f"Generated {len(embeddings)} embeddings for {len(chunks)} chunks")
        return embeddings
    
    def _process_batch(self, chunks: List[DocumentChunk]) -> List[VectorEmbedding]:
        """Process a batch of chunks with retry logic."""
        texts = [chunk.text for chunk in chunks]
        
        for attempt in range(self.max_retries):
            try:
                # Call Azure OpenAI embeddings API
                response: CreateEmbeddingResponse = self.client.embeddings.create(
                    model=self.settings.azure_openai_embedding_deployment,
                    input=texts
                )
                
                # Convert response to VectorEmbedding objects
                embeddings = []
                for i, embedding_data in enumerate(response.data):
                    chunk = chunks[i]
                    
                    # Create metadata combining chunk metadata with embedding info
                    metadata = {
                        **(chunk.metadata or {}),
                        "document_id": chunk.document_id,
                        "page_number": chunk.page_number,
                        "coordinates": {
                            "x0": chunk.coordinates.x0,
                            "y0": chunk.coordinates.y0,
                            "x1": chunk.coordinates.x1,
                            "y1": chunk.coordinates.y1
                        },
                        "embedding_model": self.model_name,
                        "embedding_dimensions": len(embedding_data.embedding)
                    }
                    
                    vector_embedding = VectorEmbedding(
                        vector=embedding_data.embedding,
                        text=chunk.text,
                        metadata=metadata,
                        chunk_id=chunk.id
                    )
                    embeddings.append(vector_embedding)
                
                return embeddings
                
            except Exception as e:
                logging.warning(f"Embedding generation attempt {attempt + 1} failed: {str(e)}")
                
                if attempt == self.max_retries - 1:
                    # Last attempt failed, raise the exception
                    logging.error(f"Failed to generate embeddings after {self.max_retries} attempts: {str(e)}")
                    raise
                
                # Calculate exponential backoff delay
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                logging.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
        
        return []  # Should never reach here
    
    def embed_query(self, query: str) -> VectorEmbedding:
        """Generate embedding for a query string with retry logic and caching."""
        if not query.strip():
            raise ValueError("Query cannot be empty")
        
        # Generate cache key
        cache_key = hashlib.md5(query.encode()).hexdigest()
        
        # Check cache first
        if cache_key in self._embedding_cache:
            logging.debug(f"Cache hit for query embedding: {query[:50]}...")
            return self._embedding_cache[cache_key]
        
        for attempt in range(self.max_retries):
            try:
                response: CreateEmbeddingResponse = self.client.embeddings.create(
                    model=self.settings.azure_openai_embedding_deployment,
                    input=[query]
                )
                
                embedding_data = response.data[0]
                
                metadata = {
                    "type": "query",
                    "embedding_model": self.model_name,
                    "embedding_dimensions": len(embedding_data.embedding),
                    "query_length": len(query)
                }
                
                embedding = VectorEmbedding(
                    vector=embedding_data.embedding,
                    text=query,
                    metadata=metadata
                )
                
                # Cache the embedding
                self._cache_embedding(cache_key, embedding)
                
                return embedding
                
            except Exception as e:
                logging.warning(f"Query embedding attempt {attempt + 1} failed: {str(e)}")
                
                if attempt == self.max_retries - 1:
                    logging.error(f"Failed to generate query embedding after {self.max_retries} attempts: {str(e)}")
                    raise
                
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                logging.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
        
        # Should never reach here
        raise RuntimeError("Unexpected error in embed_query")
    
    def _cache_embedding(self, cache_key: str, embedding: VectorEmbedding):
        """Cache an embedding with LRU eviction."""
        # Simple LRU: if cache is full, remove oldest entry
        if len(self._embedding_cache) >= self._cache_max_size:
            # Remove first (oldest) entry
            oldest_key = next(iter(self._embedding_cache))
            del self._embedding_cache[oldest_key]
        
        self._embedding_cache[cache_key] = embedding
    
    def clear_cache(self):
        """Clear the embedding cache."""
        self._embedding_cache.clear()
        logging.info("Embedding cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get embedding cache statistics."""
        return {
            "cache_size": len(self._embedding_cache),
            "cache_max_size": self._cache_max_size,
            "utilization_percentage": (len(self._embedding_cache) / self._cache_max_size) * 100
        }
    
    def validate_embeddings(self, embeddings: List[VectorEmbedding]) -> Dict[str, Any]:
        """Validate a list of embeddings and return statistics."""
        if not embeddings:
            return {
                "valid": True,
                "count": 0,
                "dimensions": 0,
                "errors": []
            }
        
        errors = []
        dimensions = None
        
        for i, embedding in enumerate(embeddings):
            # Check if vector is not empty
            if not embedding.vector:
                errors.append(f"Embedding {i} has empty vector")
                continue
            
            # Check dimensions consistency
            if dimensions is None:
                dimensions = len(embedding.vector)
            elif len(embedding.vector) != dimensions:
                errors.append(f"Embedding {i} has inconsistent dimensions: {len(embedding.vector)} vs {dimensions}")
            
            # Check for valid float values
            try:
                for j, value in enumerate(embedding.vector):
                    if not isinstance(value, (int, float)) or not (-1 <= value <= 1):
                        errors.append(f"Embedding {i} has invalid value at position {j}: {value}")
                        break
            except Exception as e:
                errors.append(f"Embedding {i} has invalid vector format: {str(e)}")
        
        return {
            "valid": len(errors) == 0,
            "count": len(embeddings),
            "dimensions": dimensions or 0,
            "errors": errors
        }