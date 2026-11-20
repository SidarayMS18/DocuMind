"""Context preparation and prompt formatting for RAG responses."""

import logging
import json
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Tuple
from src.search.vector_database import SearchResult
from src.config.settings import get_settings


@dataclass
class SourceAttribution:
    """Source attribution information for tracking document sources."""
    document_id: str
    document_name: str
    page_number: int
    text_excerpt: str
    coordinates: Dict[str, float]
    relevance_score: float
    chunk_id: str
    highlighted_image_url: Optional[str] = None


@dataclass
class ContextWindow:
    """Represents a context window with sources and attribution tracking."""
    context_text: str
    sources: List[SourceAttribution]
    total_tokens: int
    truncated: bool
    context_id: str


@dataclass
class RAGPrompt:
    """Complete RAG prompt with system message, context, and user query."""
    system_message: str
    context_section: str
    user_query: str
    full_prompt: str
    context_window: ContextWindow
    prompt_tokens: int


class ContextManager:
    """Manages context preparation and prompt formatting for RAG responses."""
    
    def __init__(self):
        """Initialize context manager with configuration."""
        self.settings = get_settings()
        
        # Context window configuration
        self.max_context_tokens = 8000  # Conservative limit for GPT-4
        self.max_sources = 10  # Maximum number of sources to include
        self.min_source_relevance = 0.0  # Minimum relevance score to include
        
        # Token estimation (rough approximation: 1 token ≈ 4 characters)
        self.chars_per_token = 4
        
        # Prompt templates
        self.system_template = self._load_system_template()
        self.context_template = self._load_context_template()
        
        logging.info("Initialized ContextManager")
    
    def _load_system_template(self) -> str:
        """Load the system message template for RAG responses."""
        return """You are an Enterprise Document Assistant that helps employees find information from company documents. 

CRITICAL INSTRUCTIONS:
1. Answer questions ONLY using the provided document context below
2. If the context doesn't contain relevant information, clearly state that you cannot find the answer in the provided documents
3. Always cite your sources by referencing the document name and page number
4. Be precise and factual - do not add information not present in the context
5. If multiple documents contain relevant information, synthesize the information while maintaining source attribution
6. Format your response clearly with proper citations

Your role is to be helpful, accurate, and transparent about the limitations of the available information."""
    
    def _load_context_template(self) -> str:
        """Load the context section template."""
        return """DOCUMENT CONTEXT:
The following excerpts are from company documents that may contain relevant information:

{context_sources}

Based on this context, please answer the user's question."""
    
    def prepare_context(self, search_results: List[SearchResult], 
                       query: str) -> ContextWindow:
        """Prepare context window from search results with token management."""
        if not search_results:
            return ContextWindow(
                context_text="",
                sources=[],
                total_tokens=0,
                truncated=False,
                context_id=f"empty_{hash(query) % 10000}"
            )
        
        # Filter and sort results by relevance
        filtered_results = [
            result for result in search_results 
            if result.score >= self.min_source_relevance
        ]
        
        # Sort by relevance score (descending)
        filtered_results.sort(key=lambda x: x.score, reverse=True)
        
        # Limit number of sources
        if len(filtered_results) > self.max_sources:
            filtered_results = filtered_results[:self.max_sources]
            logging.info(f"Limited sources to {self.max_sources} (from {len(search_results)})")
        
        # Build context with token tracking
        sources = []
        context_parts = []
        total_tokens = 0
        truncated = False
        
        for i, result in enumerate(filtered_results):
            # Create source attribution
            source = SourceAttribution(
                document_id=result.metadata.get("document_id", "unknown"),
                document_name=self._extract_document_name(result.metadata.get("document_id", "unknown")),
                page_number=result.metadata.get("page_number", 1),
                text_excerpt=result.text,
                coordinates=result.coordinates or {},
                relevance_score=result.score,
                chunk_id=result.chunk_id
            )
            
            # Format source for context
            source_text = self._format_source_for_context(source, i + 1)
            source_tokens = self._estimate_tokens(source_text)
            
            # Check if adding this source would exceed token limit
            if total_tokens + source_tokens > self.max_context_tokens:
                truncated = True
                logging.warning(f"Context truncated at {len(sources)} sources due to token limit")
                break
            
            sources.append(source)
            context_parts.append(source_text)
            total_tokens += source_tokens
        
        # Combine all context parts
        context_text = "\n\n".join(context_parts)
        
        context_window = ContextWindow(
            context_text=context_text,
            sources=sources,
            total_tokens=total_tokens,
            truncated=truncated,
            context_id=f"ctx_{hash(query + str(len(sources))) % 10000}"
        )
        
        logging.info(f"Prepared context with {len(sources)} sources, "
                    f"{total_tokens} tokens, truncated: {truncated}")
        
        return context_window
    
    def _extract_document_name(self, document_id: str) -> str:
        """Extract a readable document name from document ID."""
        # Simple extraction - could be enhanced with document metadata lookup
        if "/" in document_id:
            return document_id.split("/")[-1]
        return document_id.replace("_", " ").replace("-", " ").title()
    
    def _format_source_for_context(self, source: SourceAttribution, source_number: int) -> str:
        """Format a source for inclusion in the context section."""
        return f"""Source {source_number} - {source.document_name} (Page {source.page_number}):
{source.text_excerpt}"""
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation)."""
        return max(1, len(text) // self.chars_per_token)
    
    def create_rag_prompt(self, context_window: ContextWindow, query: str) -> RAGPrompt:
        """Create a complete RAG prompt from context window and query."""
        # Format context section
        context_section = self.context_template.format(
            context_sources=context_window.context_text
        )
        
        # Combine all parts
        full_prompt = f"{self.system_template}\n\n{context_section}\n\nUser Question: {query}"
        
        # Estimate total prompt tokens
        prompt_tokens = (
            self._estimate_tokens(self.system_template) +
            self._estimate_tokens(context_section) +
            self._estimate_tokens(f"User Question: {query}")
        )
        
        rag_prompt = RAGPrompt(
            system_message=self.system_template,
            context_section=context_section,
            user_query=query,
            full_prompt=full_prompt,
            context_window=context_window,
            prompt_tokens=prompt_tokens
        )
        
        logging.debug(f"Created RAG prompt with {prompt_tokens} tokens")
        return rag_prompt
    
    def optimize_context_for_token_limit(self, search_results: List[SearchResult], 
                                       query: str, max_tokens: int) -> ContextWindow:
        """Optimize context to fit within a specific token limit."""
        # Temporarily adjust max context tokens
        original_max = self.max_context_tokens
        self.max_context_tokens = max_tokens
        
        try:
            context_window = self.prepare_context(search_results, query)
            return context_window
        finally:
            # Restore original limit
            self.max_context_tokens = original_max
    
    def extract_citations_from_response(self, response: str, 
                                      context_window: ContextWindow) -> List[SourceAttribution]:
        """Extract and validate citations from LLM response."""
        citations = []
        
        # Look for document names and page numbers in the response
        for source in context_window.sources:
            doc_name = source.document_name.lower()
            page_num = str(source.page_number)
            
            # Check if this source is referenced in the response
            response_lower = response.lower()
            if (doc_name in response_lower or 
                f"page {page_num}" in response_lower or
                f"p. {page_num}" in response_lower or
                f"pg {page_num}" in response_lower):
                citations.append(source)
        
        logging.info(f"Extracted {len(citations)} citations from response")
        return citations
    
    def validate_response_grounding(self, response: str, 
                                  context_window: ContextWindow) -> Dict[str, Any]:
        """Validate that response is properly grounded in provided context."""
        if not context_window.sources:
            return {
                "grounded": False,
                "reason": "No context sources available",
                "confidence": 0.0
            }
        
        # Extract key phrases from response (simple approach)
        response_words = set(response.lower().split())
        
        # Check overlap with context
        context_words = set()
        for source in context_window.sources:
            context_words.update(source.text_excerpt.lower().split())
        
        # Calculate overlap ratio
        if not response_words:
            overlap_ratio = 0.0
        else:
            overlap = len(response_words.intersection(context_words))
            overlap_ratio = overlap / len(response_words)
        
        # Simple grounding check
        grounded = overlap_ratio > 0.1  # At least 10% word overlap
        
        return {
            "grounded": grounded,
            "overlap_ratio": overlap_ratio,
            "response_words": len(response_words),
            "context_words": len(context_words),
            "confidence": min(overlap_ratio * 2, 1.0)  # Scale to 0-1
        }
    
    def get_context_summary(self, context_window: ContextWindow) -> Dict[str, Any]:
        """Get a summary of the context window for debugging/monitoring."""
        return {
            "context_id": context_window.context_id,
            "total_sources": len(context_window.sources),
            "total_tokens": context_window.total_tokens,
            "truncated": context_window.truncated,
            "documents": list(set(source.document_name for source in context_window.sources)),
            "page_range": {
                "min": min((source.page_number for source in context_window.sources), default=0),
                "max": max((source.page_number for source in context_window.sources), default=0)
            },
            "relevance_scores": {
                "min": min((source.relevance_score for source in context_window.sources), default=0.0),
                "max": max((source.relevance_score for source in context_window.sources), default=0.0),
                "avg": sum(source.relevance_score for source in context_window.sources) / len(context_window.sources) if context_window.sources else 0.0
            }
        }