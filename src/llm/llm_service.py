"""LLM service for generating responses based on retrieved context."""

import logging
import time
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from openai import AzureOpenAI, OpenAIError, APIError, APITimeoutError, RateLimitError
from src.llm.context_manager import ContextManager, RAGPrompt, SourceAttribution
from src.llm.citation_service import CitationService, Citation
from src.search.vector_database import SearchResult
from src.config.settings import get_settings


@dataclass
class LLMResponse:
    """Response from the language model."""
    text: str
    confidence_score: float
    grounded: bool
    sources: List[SourceAttribution]
    citations: List[Citation]
    processing_time_ms: int
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LLMService:
    """Service for generating responses using Azure OpenAI GPT-4."""
    
    def __init__(self, context_manager: Optional[ContextManager] = None):
        """Initialize LLM service with Azure OpenAI client."""
        self.settings = get_settings()
        self.context_manager = context_manager or ContextManager()
        self.citation_service = CitationService()
        
        # Initialize Azure OpenAI client
        if not self.settings.azure_openai_endpoint or not self.settings.azure_openai_api_key:
            logging.warning("Azure OpenAI credentials not configured")
            self.client = None
        else:
            self.client = AzureOpenAI(
                azure_endpoint=self.settings.azure_openai_endpoint,
                api_key=self.settings.azure_openai_api_key,
                api_version=self.settings.azure_openai_api_version
            )
        
        # Model configuration
        self.deployment_name = self.settings.azure_openai_deployment_name or "gpt-4"
        self.temperature = 0.3  # Lower temperature for more factual responses
        self.max_tokens = 1000  # Maximum response length
        self.top_p = 0.9
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delay_seconds = 2
        self.backoff_multiplier = 2
        
        logging.info(f"Initialized LLMService with deployment: {self.deployment_name}")
    
    def generate_response(self, query: str, search_results: List[SearchResult]) -> LLMResponse:
        """Generate a response based on query and retrieved search results."""
        start_time = time.time()
        
        try:
            # Prepare context from search results
            context_window = self.context_manager.prepare_context(search_results, query)
            
            # Create RAG prompt
            rag_prompt = self.context_manager.create_rag_prompt(context_window, query)
            
            # Generate response with retry logic
            completion = self._generate_with_retry(rag_prompt)
            
            # Extract response text
            response_text = completion.choices[0].message.content
            
            # Validate response grounding
            grounding_result = self.context_manager.validate_response_grounding(
                response_text, context_window
            )
            
            # Extract citations from response
            source_citations = self.context_manager.extract_citations_from_response(
                response_text, context_window
            )
            
            # Create formatted citations
            citations = self.citation_service.create_citations_from_sources(
                source_citations if source_citations else context_window.sources
            )
            
            # Validate citation completeness
            citation_check = self.citation_service.check_citation_completeness(
                response_text, citations
            )
            
            # Append formatted citations to response if not already present
            if citations and "[" not in response_text[-50:]:  # Simple check if citations already added
                citation_text = self.citation_service.format_citations_for_response(
                    citations, style="numbered"
                )
                response_text += citation_text
            
            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Create response object
            llm_response = LLMResponse(
                text=response_text,
                confidence_score=grounding_result.get("confidence", 0.0),
                grounded=grounding_result.get("grounded", False),
                sources=source_citations if source_citations else context_window.sources,
                citations=citations,
                processing_time_ms=processing_time_ms,
                model_name=self.deployment_name,
                prompt_tokens=completion.usage.prompt_tokens,
                completion_tokens=completion.usage.completion_tokens,
                total_tokens=completion.usage.total_tokens
            )
            
            logging.info(f"Generated response in {processing_time_ms}ms, "
                        f"grounded: {llm_response.grounded}, "
                        f"citations: {len(citations)}, "
                        f"tokens: {llm_response.total_tokens}")
            
            return llm_response
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logging.error(f"Response generation failed after {processing_time_ms}ms: {str(e)}")
            
            # Return error response
            return LLMResponse(
                text=f"I apologize, but I encountered an error while processing your query: {str(e)}",
                confidence_score=0.0,
                grounded=False,
                sources=[],
                citations=[],
                processing_time_ms=processing_time_ms,
                model_name=self.deployment_name,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0
            )
    
    def _generate_with_retry(self, rag_prompt: RAGPrompt) -> Any:
        """Generate response with retry logic for handling API failures."""
        if not self.client:
            raise ValueError("Azure OpenAI client not initialized. Check configuration.")
        
        last_error = None
        retry_delay = self.retry_delay_seconds
        
        for attempt in range(self.max_retries):
            try:
                # Call Azure OpenAI API
                completion = self.client.chat.completions.create(
                    model=self.deployment_name,
                    messages=[
                        {"role": "system", "content": rag_prompt.system_message},
                        {"role": "user", "content": f"{rag_prompt.context_section}\n\nUser Question: {rag_prompt.user_query}"}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=self.top_p,
                    timeout=self.settings.request_timeout_seconds
                )
                
                return completion
                
            except RateLimitError as e:
                last_error = e
                logging.warning(f"Rate limit hit on attempt {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= self.backoff_multiplier
                    
            except APITimeoutError as e:
                last_error = e
                logging.warning(f"API timeout on attempt {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= self.backoff_multiplier
                    
            except APIError as e:
                last_error = e
                logging.error(f"API error on attempt {attempt + 1}/{self.max_retries}: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= self.backoff_multiplier
                    
            except OpenAIError as e:
                # Non-retryable OpenAI errors
                logging.error(f"OpenAI error: {str(e)}")
                raise
                
            except Exception as e:
                # Unexpected errors
                logging.error(f"Unexpected error: {str(e)}")
                raise
        
        # All retries exhausted
        raise Exception(f"Failed to generate response after {self.max_retries} attempts: {str(last_error)}")
    
    def validate_response_grounding(self, response: str, search_results: List[SearchResult]) -> Dict[str, Any]:
        """Validate that response is grounded in the provided search results."""
        try:
            # Prepare context from search results
            context_window = self.context_manager.prepare_context(search_results, "")
            
            # Use context manager's validation
            grounding_result = self.context_manager.validate_response_grounding(
                response, context_window
            )
            
            return grounding_result
            
        except Exception as e:
            logging.error(f"Response grounding validation failed: {str(e)}")
            return {
                "grounded": False,
                "reason": f"Validation error: {str(e)}",
                "confidence": 0.0
            }
    
    def check_hallucination(self, response: str, search_results: List[SearchResult]) -> Dict[str, Any]:
        """Check if response contains hallucinated information not in context."""
        grounding_result = self.validate_response_grounding(response, search_results)
        
        # Simple hallucination detection based on grounding
        hallucination_detected = not grounding_result.get("grounded", False)
        
        return {
            "hallucination_detected": hallucination_detected,
            "confidence": 1.0 - grounding_result.get("confidence", 0.0),
            "grounding_score": grounding_result.get("overlap_ratio", 0.0),
            "details": grounding_result
        }
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get LLM service status and configuration."""
        return {
            "service": "LLMService",
            "client_initialized": self.client is not None,
            "deployment_name": self.deployment_name,
            "endpoint_configured": bool(self.settings.azure_openai_endpoint),
            "api_key_configured": bool(self.settings.azure_openai_api_key),
            "configuration": {
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "top_p": self.top_p,
                "max_retries": self.max_retries,
                "retry_delay_seconds": self.retry_delay_seconds
            }
        }