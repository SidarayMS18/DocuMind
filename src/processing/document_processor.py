"""Document processor for PDF text extraction and chunking."""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import fitz  # PyMuPDF
import logging
import uuid
from datetime import datetime
import re


@dataclass
class BoundingBox:
    """Represents text coordinates on a page."""
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class TextBlock:
    """Represents a block of text with position information."""
    text: str
    page_number: int
    coordinates: BoundingBox
    font_size: float
    font_name: str


@dataclass
class DocumentChunk:
    """Represents a processed document chunk with metadata."""
    id: str
    document_id: str
    text: str
    page_number: int
    coordinates: BoundingBox
    embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None
    document_name: str = ""   # ← local mode: store filename here


@dataclass
class ProcessingResult:
    """Result of document processing operation."""
    document_id: str
    text: str
    metadata: Dict[str, Any]
    coordinates: List[BoundingBox]
    chunks: List[DocumentChunk]
    success: bool
    error_message: Optional[str] = None


class DocumentProcessor:
    """Handles PDF ingestion, text extraction, and chunking."""
    
    def __init__(self, chunk_size_min: int = 500, chunk_size_max: int = 1000):
        self.chunk_size_min = chunk_size_min
        self.chunk_size_max = chunk_size_max
    
    def process_document(self, pdf_file: bytes, document_id: str) -> ProcessingResult:
        """Process a PDF document and return structured result."""
        try:
            # Extract text blocks with coordinates
            text_blocks = self.extract_text_with_coordinates(pdf_file)
            
            if not text_blocks:
                return ProcessingResult(
                    document_id=document_id,
                    text="",
                    metadata={},
                    coordinates=[],
                    chunks=[],
                    success=False,
                    error_message="No text could be extracted from PDF"
                )
            
            # Extract metadata
            metadata = self.extract_metadata(pdf_file)
            
            # Combine all text
            full_text = " ".join([block.text for block in text_blocks])
            
            # Get all coordinates
            coordinates = [block.coordinates for block in text_blocks]
            
            # Create chunks (will be implemented in task 2.3)
            chunks = self.chunk_document(text_blocks, document_id)
            
            return ProcessingResult(
                document_id=document_id,
                text=full_text,
                metadata=metadata,
                coordinates=coordinates,
                chunks=chunks,
                success=True,
                error_message=None
            )
            
        except Exception as e:
            error_msg = f"Error processing document: {str(e)}"
            logging.error(error_msg)
            return ProcessingResult(
                document_id=document_id,
                text="",
                metadata={},
                coordinates=[],
                chunks=[],
                success=False,
                error_message=error_msg
            )
    
    def extract_text_with_coordinates(self, pdf_file: bytes) -> List[TextBlock]:
        """Extract text blocks with positional information."""
        text_blocks = []
        
        try:
            # Open PDF from bytes
            doc = fitz.open(stream=pdf_file, filetype="pdf")
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # Get text blocks with coordinates
                blocks = page.get_text("dict")
                
                for block in blocks["blocks"]:
                    if "lines" in block:  # Text block (not image)
                        for line in block["lines"]:
                            for span in line["spans"]:
                                if span["text"].strip():  # Skip empty text
                                    bbox = span["bbox"]
                                    text_block = TextBlock(
                                        text=span["text"],
                                        page_number=page_num + 1,  # 1-indexed
                                        coordinates=BoundingBox(
                                            x0=bbox[0],
                                            y0=bbox[1], 
                                            x1=bbox[2],
                                            y1=bbox[3]
                                        ),
                                        font_size=span["size"],
                                        font_name=span["font"]
                                    )
                                    text_blocks.append(text_block)
            
            doc.close()
            return text_blocks
            
        except Exception as e:
            logging.error(f"Error extracting text from PDF: {str(e)}")
            return []
    
    def extract_metadata(self, pdf_file: bytes) -> Dict[str, Any]:
        """Extract metadata from PDF document."""
        try:
            doc = fitz.open(stream=pdf_file, filetype="pdf")
            metadata = doc.metadata
            
            # Extract standard metadata fields
            extracted_metadata = {
                "title": metadata.get("title", ""),
                "author": metadata.get("author", ""),
                "subject": metadata.get("subject", ""),
                "creator": metadata.get("creator", ""),
                "producer": metadata.get("producer", ""),
                "creation_date": metadata.get("creationDate", ""),
                "modification_date": metadata.get("modDate", ""),
                "page_count": len(doc),
                "format": metadata.get("format", "PDF"),
                "encryption": metadata.get("encryption", None),
                "extracted_at": datetime.now().isoformat()
            }
            
            doc.close()
            return extracted_metadata
            
        except Exception as e:
            logging.error(f"Error extracting metadata from PDF: {str(e)}")
            return {
                "title": "",
                "author": "",
                "page_count": 0,
                "extracted_at": datetime.now().isoformat(),
                "error": str(e)
            }

    def chunk_document(self, text_blocks: List[TextBlock], document_id: str) -> List[DocumentChunk]:
        """Break document into meaningful chunks while preserving coordinates."""
        chunks = []
        current_chunk_text = ""
        current_chunk_blocks = []
        chunk_counter = 0
        
        for block in text_blocks:
            # Add block to current chunk
            current_chunk_blocks.append(block)
            current_chunk_text += " " + block.text.strip()
            
            # Estimate token count (rough approximation: 1 token ≈ 4 characters)
            estimated_tokens = len(current_chunk_text) // 4
            
            # Check if we should finalize this chunk
            should_finalize = False
            
            # If we're at max size, finalize
            if estimated_tokens >= self.chunk_size_max:
                should_finalize = True
            
            # If we're above min size and at a sentence boundary, finalize
            elif estimated_tokens >= self.chunk_size_min:
                # Check for sentence endings
                if self._is_sentence_boundary(block.text):
                    should_finalize = True
                # Check for paragraph breaks (significant whitespace or formatting changes)
                elif self._is_paragraph_boundary(current_chunk_blocks):
                    should_finalize = True
            
            if should_finalize and current_chunk_blocks:
                chunk = self._create_chunk(
                    current_chunk_blocks, 
                    document_id, 
                    chunk_counter,
                    current_chunk_text.strip()
                )
                chunks.append(chunk)
                
                # Reset for next chunk
                current_chunk_text = ""
                current_chunk_blocks = []
                chunk_counter += 1
        
        # Handle remaining text
        if current_chunk_blocks:
            chunk = self._create_chunk(
                current_chunk_blocks, 
                document_id, 
                chunk_counter,
                current_chunk_text.strip()
            )
            chunks.append(chunk)
        
        return chunks
    
    def _is_sentence_boundary(self, text: str) -> bool:
        """Check if text ends with sentence boundary markers."""
        text = text.strip()
        return bool(re.search(r'[.!?]\s*$', text))
    
    def _is_paragraph_boundary(self, blocks: List[TextBlock]) -> bool:
        """Check if there's a significant formatting change indicating paragraph boundary."""
        if len(blocks) < 2:
            return False
        
        last_block = blocks[-1]
        prev_block = blocks[-2]
        
        # Check for significant vertical gap (potential paragraph break)
        vertical_gap = abs(last_block.coordinates.y0 - prev_block.coordinates.y1)
        
        # Check for font size changes (headers, etc.)
        font_size_change = abs(last_block.font_size - prev_block.font_size) > 1
        
        # Consider it a paragraph boundary if there's a significant gap or font change
        return vertical_gap > 10 or font_size_change
    
    def _create_chunk(self, blocks: List[TextBlock], document_id: str, chunk_id: int, text: str) -> DocumentChunk:
        """Create a DocumentChunk from a list of TextBlocks."""
        if not blocks:
            raise ValueError("Cannot create chunk from empty blocks list")
        
        # Calculate bounding box that encompasses all blocks
        min_x0 = min(block.coordinates.x0 for block in blocks)
        min_y0 = min(block.coordinates.y0 for block in blocks)
        max_x1 = max(block.coordinates.x1 for block in blocks)
        max_y1 = max(block.coordinates.y1 for block in blocks)
        
        # Use the page number of the first block (chunks shouldn't span pages in this implementation)
        page_number = blocks[0].page_number
        
        # Create metadata
        metadata = {
            "block_count": len(blocks),
            "font_sizes": list(set(block.font_size for block in blocks)),
            "font_names": list(set(block.font_name for block in blocks)),
            "token_estimate": len(text) // 4,
            "char_count": len(text)
        }
        
        return DocumentChunk(
            id=f"{document_id}_chunk_{chunk_id}",
            document_id=document_id,
            text=text,
            page_number=page_number,
            coordinates=BoundingBox(x0=min_x0, y0=min_y0, x1=max_x1, y1=max_y1),
            metadata=metadata
        )
        """Break document into meaningful chunks while preserving coordinates."""
        # Placeholder implementation - will be implemented in task 2
        return []