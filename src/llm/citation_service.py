"""Citation service for formatting and validating source citations."""

import logging
import re
import base64
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple
from src.llm.context_manager import SourceAttribution


@dataclass
class Citation:
    """Formatted citation with document source information."""
    citation_id: str
    document_name: str
    page_number: int
    text_excerpt: str
    coordinates: Dict[str, float]
    formatted_citation: str
    relevance_score: float
    chunk_id: str
    highlighted_image_url: Optional[str] = None  # URL or base64 encoded image
    highlighted_image_data: Optional[bytes] = None  # Raw image bytes


@dataclass
class CitationValidationResult:
    """Result of citation validation."""
    valid: bool
    total_citations: int
    valid_citations: int
    missing_fields: List[str]
    issues: List[str]


class CitationService:
    """Service for creating, formatting, and validating source citations."""
    
    def __init__(self):
        """Initialize citation service."""
        self.citation_formats = {
            "standard": "{document_name}, Page {page_number}",
            "detailed": "{document_name}, Page {page_number}, Section: {text_excerpt}",
            "academic": "{document_name} (p. {page_number})",
            "inline": "[{document_name}, p.{page_number}]"
        }
        
        self.default_format = "standard"
        self.max_excerpt_length = 150
        
        logging.info("Initialized CitationService")
    
    def create_citation(self, source: SourceAttribution, 
                       citation_format: str = "standard") -> Citation:
        """Create a formatted citation from a source attribution."""
        # Truncate text excerpt if too long
        text_excerpt = source.text_excerpt
        if len(text_excerpt) > self.max_excerpt_length:
            text_excerpt = text_excerpt[:self.max_excerpt_length] + "..."
        
        # Generate citation ID
        citation_id = f"cite_{source.chunk_id}_{source.page_number}"
        
        # Format citation based on specified format
        format_template = self.citation_formats.get(
            citation_format, 
            self.citation_formats[self.default_format]
        )
        
        formatted_citation = format_template.format(
            document_name=source.document_name,
            page_number=source.page_number,
            text_excerpt=text_excerpt
        )
        
        citation = Citation(
            citation_id=citation_id,
            document_name=source.document_name,
            page_number=source.page_number,
            text_excerpt=text_excerpt,
            coordinates=source.coordinates,
            formatted_citation=formatted_citation,
            relevance_score=source.relevance_score,
            chunk_id=source.chunk_id
        )
        
        logging.debug(f"Created citation: {formatted_citation}")
        return citation
    
    def create_citations_from_sources(self, sources: List[SourceAttribution],
                                     citation_format: str = "standard") -> List[Citation]:
        """Create citations for all sources."""
        citations = []
        
        for source in sources:
            try:
                citation = self.create_citation(source, citation_format)
                citations.append(citation)
            except Exception as e:
                logging.error(f"Failed to create citation for source {source.chunk_id}: {str(e)}")
        
        logging.info(f"Created {len(citations)} citations from {len(sources)} sources")
        return citations
    
    def format_citations_for_response(self, citations: List[Citation],
                                     style: str = "numbered") -> str:
        """Format citations for inclusion in response text."""
        if not citations:
            return ""
        
        if style == "numbered":
            formatted = "\n\nSources:\n"
            for i, citation in enumerate(citations, 1):
                formatted += f"{i}. {citation.formatted_citation}\n"
            return formatted
            
        elif style == "inline":
            # Create inline citation references
            citation_refs = [f"[{i}]" for i in range(1, len(citations) + 1)]
            return " " + ", ".join(citation_refs)
            
        elif style == "footnote":
            formatted = "\n\nReferences:\n"
            for i, citation in enumerate(citations, 1):
                formatted += f"[{i}] {citation.formatted_citation}\n"
            return formatted
            
        else:
            # Default to numbered
            return self.format_citations_for_response(citations, "numbered")
    
    def validate_citation(self, citation: Citation) -> CitationValidationResult:
        """Validate that a citation has all required fields."""
        issues = []
        missing_fields = []
        
        # Check required fields
        if not citation.document_name or citation.document_name.strip() == "":
            missing_fields.append("document_name")
            issues.append("Document name is missing or empty")
        
        if citation.page_number is None or citation.page_number < 1:
            missing_fields.append("page_number")
            issues.append("Page number is invalid or missing")
        
        if not citation.text_excerpt or citation.text_excerpt.strip() == "":
            missing_fields.append("text_excerpt")
            issues.append("Text excerpt is missing or empty")
        
        if not citation.coordinates or len(citation.coordinates) == 0:
            missing_fields.append("coordinates")
            issues.append("Coordinates are missing")
        
        if not citation.chunk_id or citation.chunk_id.strip() == "":
            missing_fields.append("chunk_id")
            issues.append("Chunk ID is missing")
        
        # Validate coordinate structure
        if citation.coordinates:
            required_coords = ["x0", "y0", "x1", "y1"]
            for coord in required_coords:
                if coord not in citation.coordinates:
                    issues.append(f"Missing coordinate: {coord}")
        
        valid = len(issues) == 0
        
        return CitationValidationResult(
            valid=valid,
            total_citations=1,
            valid_citations=1 if valid else 0,
            missing_fields=missing_fields,
            issues=issues
        )
    
    def validate_citations(self, citations: List[Citation]) -> CitationValidationResult:
        """Validate a list of citations."""
        all_issues = []
        all_missing_fields = []
        valid_count = 0
        
        for i, citation in enumerate(citations):
            result = self.validate_citation(citation)
            if result.valid:
                valid_count += 1
            else:
                all_issues.extend([f"Citation {i+1}: {issue}" for issue in result.issues])
                all_missing_fields.extend(result.missing_fields)
        
        overall_valid = valid_count == len(citations)
        
        validation_result = CitationValidationResult(
            valid=overall_valid,
            total_citations=len(citations),
            valid_citations=valid_count,
            missing_fields=list(set(all_missing_fields)),
            issues=all_issues
        )
        
        logging.info(f"Validated {len(citations)} citations: "
                    f"{valid_count} valid, {len(citations) - valid_count} invalid")
        
        return validation_result
    
    def link_citations_to_response(self, response_text: str, 
                                  citations: List[Citation]) -> Dict[str, Any]:
        """Link citations to specific parts of the response text."""
        # Extract potential citation references from response
        # Look for patterns like [1], (Source 1), etc.
        citation_pattern = r'\[(\d+)\]|\(Source (\d+)\)|Source (\d+)'
        matches = re.finditer(citation_pattern, response_text)
        
        linked_citations = []
        unlinked_citations = list(citations)
        
        for match in matches:
            # Extract citation number
            citation_num = None
            for group in match.groups():
                if group:
                    citation_num = int(group)
                    break
            
            if citation_num and 1 <= citation_num <= len(citations):
                citation = citations[citation_num - 1]
                linked_citations.append({
                    "citation": citation,
                    "position": match.start(),
                    "reference_text": match.group(0)
                })
                
                if citation in unlinked_citations:
                    unlinked_citations.remove(citation)
        
        return {
            "response_text": response_text,
            "total_citations": len(citations),
            "linked_citations": len(linked_citations),
            "unlinked_citations": len(unlinked_citations),
            "citation_links": linked_citations,
            "unused_citations": unlinked_citations
        }
    
    def extract_citation_context(self, citation: Citation, 
                                context_chars: int = 200) -> str:
        """Extract surrounding context for a citation."""
        # This would typically fetch more context from the original document
        # For now, return the text excerpt with indication of truncation
        excerpt = citation.text_excerpt
        
        if len(excerpt) < context_chars:
            return excerpt
        
        # Return centered context around the excerpt
        return f"...{excerpt}..."
    
    def generate_citation_metadata(self, citation: Citation) -> Dict[str, Any]:
        """Generate metadata for a citation for API responses."""
        return {
            "citation_id": citation.citation_id,
            "document_name": citation.document_name,
            "page_number": citation.page_number,
            "coordinates": citation.coordinates,
            "relevance_score": citation.relevance_score,
            "formatted_citation": citation.formatted_citation,
            "chunk_id": citation.chunk_id
        }
    
    def check_citation_completeness(self, response_text: str, 
                                   citations: List[Citation]) -> Dict[str, Any]:
        """Check if response has complete citation coverage."""
        # Validate all citations
        validation = self.validate_citations(citations)
        
        # Link citations to response
        linking = self.link_citations_to_response(response_text, citations)
        
        # Calculate completeness score
        if not citations:
            completeness_score = 0.0
        else:
            completeness_score = (
                (validation.valid_citations / validation.total_citations) * 0.5 +
                (linking["linked_citations"] / linking["total_citations"]) * 0.5
            )
        
        return {
            "complete": validation.valid and linking["unlinked_citations"] == 0,
            "completeness_score": completeness_score,
            "validation": asdict(validation),
            "linking": {
                "total_citations": linking["total_citations"],
                "linked_citations": linking["linked_citations"],
                "unlinked_citations": linking["unlinked_citations"]
            },
            "issues": validation.issues
        }
    
    def format_citation_for_api(self, citation: Citation) -> Dict[str, Any]:
        """Format citation for API response."""
        result = {
            "id": citation.citation_id,
            "document": citation.document_name,
            "page": citation.page_number,
            "excerpt": citation.text_excerpt,
            "coordinates": citation.coordinates,
            "formatted": citation.formatted_citation,
            "relevance": citation.relevance_score
        }
        
        # Include highlighted image if available
        if citation.highlighted_image_url:
            result["highlighted_image_url"] = citation.highlighted_image_url
        
        return result
    
    def get_available_formats(self) -> List[str]:
        """Get list of available citation formats."""
        return list(self.citation_formats.keys())
    
    def generate_highlighted_citation(self, citation: Citation, pdf_file: bytes,
                                     color: str = "#FFFF00", opacity: float = 0.3,
                                     dpi: int = 150) -> Citation:
        """Generate a highlighted page image for a citation.
        
        Args:
            citation: Citation to generate highlight for
            pdf_file: PDF file as bytes
            color: Highlight color in hex format
            opacity: Highlight opacity (0.0-1.0)
            dpi: Resolution for rendering
            
        Returns:
            Updated citation with highlighted image data
        """
        try:
            from src.highlighting.text_highlighter import TextHighlighter
            from src.processing.document_processor import BoundingBox
            
            highlighter = TextHighlighter(default_color=color, default_opacity=opacity)
            
            # Create bounding box from coordinates
            bbox = BoundingBox(
                x0=citation.coordinates.get("x0", 0),
                y0=citation.coordinates.get("y0", 0),
                x1=citation.coordinates.get("x1", 0),
                y1=citation.coordinates.get("y1", 0)
            )
            
            # Create highlight overlay
            overlays = highlighter.create_highlight_overlay_from_bbox(
                [bbox],
                text_content=citation.text_excerpt,
                color=color,
                opacity=opacity
            )
            
            # Render highlighted page
            highlighted_image = highlighter.render_highlighted_page(
                pdf_file,
                citation.page_number,
                overlays,
                dpi=dpi
            )
            
            # Update citation with image data
            citation.highlighted_image_data = highlighted_image
            
            # Optionally convert to base64 for embedding in responses
            image_base64 = base64.b64encode(highlighted_image).decode('utf-8')
            citation.highlighted_image_url = f"data:image/png;base64,{image_base64}"
            
            logging.debug(f"Generated highlighted image for citation {citation.citation_id}")
            return citation
            
        except Exception as e:
            logging.error(f"Failed to generate highlighted image for citation: {str(e)}")
            # Return citation without highlight on error
            return citation
    
    def generate_highlighted_citations(self, citations: List[Citation], 
                                      pdf_files: Dict[str, bytes],
                                      color: str = "#FFFF00", 
                                      opacity: float = 0.3,
                                      dpi: int = 150) -> List[Citation]:
        """Generate highlighted images for multiple citations.
        
        Args:
            citations: List of citations to generate highlights for
            pdf_files: Dictionary mapping document names to PDF file bytes
            color: Highlight color in hex format
            opacity: Highlight opacity (0.0-1.0)
            dpi: Resolution for rendering
            
        Returns:
            List of citations with highlighted image data
        """
        highlighted_citations = []
        
        for citation in citations:
            try:
                # Get PDF file for this citation
                pdf_file = pdf_files.get(citation.document_name)
                
                if pdf_file:
                    highlighted_citation = self.generate_highlighted_citation(
                        citation, pdf_file, color, opacity, dpi
                    )
                    highlighted_citations.append(highlighted_citation)
                else:
                    logging.warning(f"PDF file not found for document: {citation.document_name}")
                    highlighted_citations.append(citation)
                    
            except Exception as e:
                logging.error(f"Failed to generate highlight for citation {citation.citation_id}: {str(e)}")
                highlighted_citations.append(citation)
        
        logging.info(f"Generated highlighted images for {len(highlighted_citations)} citations")
        return highlighted_citations
