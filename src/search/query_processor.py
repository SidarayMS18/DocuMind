"""Query processing service for handling user queries and search operations."""

import logging
import time
import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from src.search.embedding_service import EmbeddingService, VectorEmbedding
from src.search.vector_database import VectorDatabase, SearchResult
from src.config.settings import get_settings


@dataclass
class QueryResult:
    """Result of query processing with search results and metadata."""
    query: str
    processed_query: str
    results: List[SearchResult]
    total_results: int
    processing_time_ms: int
    search_type: str  # "vector" or "hybrid"


class QueryProcessor:
    """Handles query preprocessing, vectorization, and search operations."""
    
    def __init__(self, embedding_service: Optional[EmbeddingService] = None, 
                 vector_db: Optional[VectorDatabase] = None):
        """Initialize query processor with embedding service and vector database."""
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_db = vector_db or VectorDatabase()
        self.settings = get_settings()
        
        # Query preprocessing configuration
        self.min_query_length = 3
        self.max_query_length = 1000
        
        # Search configuration
        self.default_k = 5
        self.max_k = 20
        
        logging.info("Initialized QueryProcessor")
    
    def preprocess_query(self, query: str) -> str:
        """Preprocess and optimize user query for better search results."""
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        # Remove extra whitespace and normalize
        processed = re.sub(r'\s+', ' ', query.strip())
        
        # Check length constraints
        if len(processed) < self.min_query_length:
            raise ValueError(f"Query too short. Minimum length: {self.min_query_length}")
        
        if len(processed) > self.max_query_length:
            # Truncate long queries
            processed = processed[:self.max_query_length]
            logging.warning(f"Query truncated to {self.max_query_length} characters")
        
        # Remove special characters that might interfere with search
        # Keep alphanumeric, spaces, and common punctuation
        processed = re.sub(r'[^\w\s\-\.\,\?\!\:\;\"\'()]', ' ', processed)
        processed = re.sub(r'\s+', ' ', processed).strip()
        
        # Expand common abbreviations or synonyms if needed
        # This could be enhanced with a more sophisticated query expansion
        processed = self._expand_query_terms(processed)
        
        logging.debug(f"Preprocessed query: '{query}' -> '{processed}'")
        return processed
    
    def _expand_query_terms(self, query: str) -> str:
        """Expand query terms with synonyms or common variations."""
        # Simple term expansion - could be enhanced with a proper thesaurus
        expansions = {
            r'\bAPI\b': 'API application programming interface',
            r'\bUI\b': 'UI user interface',
            r'\bDB\b': 'DB database',
            r'\bAI\b': 'AI artificial intelligence',
            r'\bML\b': 'ML machine learning',
        }
        
        expanded = query
        for pattern, replacement in expansions.items():
            expanded = re.sub(pattern, replacement, expanded, flags=re.IGNORECASE)
        
        return expanded
    
    def process_query(self, query: str, k: Optional[int] = None, 
                     search_type: str = "hybrid") -> QueryResult:
        """Process a user query and return search results."""
        start_time = time.time()
        
        try:
            # Validate and preprocess query
            processed_query = self.preprocess_query(query)
            
            # Validate k parameter
            k = k or self.default_k
            if k > self.max_k:
                k = self.max_k
                logging.warning(f"Requested k={k} exceeds maximum, using {self.max_k}")
            
            # Generate query embedding
            query_embedding = self.embedding_service.embed_query(processed_query)
            
            # Perform search based on type
            if search_type == "vector":
                results = self.vector_db.search_similar(query_embedding, k)
            elif search_type == "hybrid":
                results = self.vector_db.hybrid_search(processed_query, query_embedding, k)
            else:
                raise ValueError(f"Invalid search_type: {search_type}. Use 'vector' or 'hybrid'")
            
            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Create result object
            query_result = QueryResult(
                query=query,
                processed_query=processed_query,
                results=results,
                total_results=len(results),
                processing_time_ms=processing_time_ms,
                search_type=search_type
            )
            
            logging.info(f"Processed query '{query}' in {processing_time_ms}ms, "
                        f"found {len(results)} results using {search_type} search")
            
            return query_result
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logging.error(f"Query processing failed after {processing_time_ms}ms: {str(e)}")
            
            # Return empty result with error information
            return QueryResult(
                query=query,
                processed_query=query,
                results=[],
                total_results=0,
                processing_time_ms=processing_time_ms,
                search_type=search_type
            )
    
    def get_top_k_results(self, query: str, k: int = 5) -> List[SearchResult]:
        """Simplified interface to get top-k search results."""
        result = self.process_query(query, k=k, search_type="hybrid")
        return result.results
    
    def search_by_document(self, query: str, document_id: str, k: int = 5) -> List[SearchResult]:
        """Search within a specific document."""
        try:
            # Process query normally first
            processed_query = self.preprocess_query(query)
            query_embedding = self.embedding_service.embed_query(processed_query)
            
            # Get all results first, then filter by document
            all_results = self.vector_db.hybrid_search(processed_query, query_embedding, k * 3)
            
            # Filter results by document_id
            document_results = [
                result for result in all_results 
                if result.metadata.get("document_id") == document_id
            ]
            
            # Return top k results from the document
            return document_results[:k]
            
        except Exception as e:
            logging.error(f"Document-specific search failed: {str(e)}")
            return []
    
    def search_by_page_range(self, query: str, document_id: str, 
                           start_page: int, end_page: int, k: int = 5) -> List[SearchResult]:
        """Search within a specific page range of a document."""
        try:
            # Get document results first
            document_results = self.search_by_document(query, document_id, k * 2)
            
            # Filter by page range
            page_results = [
                result for result in document_results
                if start_page <= result.metadata.get("page_number", 0) <= end_page
            ]
            
            return page_results[:k]
            
        except Exception as e:
            logging.error(f"Page range search failed: {str(e)}")
            return []
    
    def validate_query_embedding(self, query: str) -> Dict[str, Any]:
        """Validate that a query can be properly embedded."""
        try:
            processed_query = self.preprocess_query(query)
            embedding = self.embedding_service.embed_query(processed_query)
            
            return {
                "valid": True,
                "original_query": query,
                "processed_query": processed_query,
                "embedding_dimensions": len(embedding.vector),
                "embedding_model": embedding.metadata.get("embedding_model", "unknown")
            }
            
        except Exception as e:
            return {
                "valid": False,
                "original_query": query,
                "processed_query": None,
                "error": str(e)
            }
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """Get statistics about the search index."""
        try:
            stats = self.vector_db.get_index_stats()
            return {
                "index_stats": stats,
                "query_processor_config": {
                    "min_query_length": self.min_query_length,
                    "max_query_length": self.max_query_length,
                    "default_k": self.default_k,
                    "max_k": self.max_k
                }
            }
        except Exception as e:
            logging.error(f"Failed to get search statistics: {str(e)}")
            return {"error": str(e)}