"""Text highlighting service for PDF pages."""

from dataclasses import dataclass
from typing import List, Optional
import fitz  # PyMuPDF
import logging
from src.processing.document_processor import BoundingBox


@dataclass
class TextCoordinate:
    """Represents text coordinate information."""
    text: str
    page_number: int
    coordinates: BoundingBox


@dataclass
class HighlightOverlay:
    """Represents a highlight overlay for text."""
    coordinates: BoundingBox
    color: str
    opacity: float
    text_content: str


class TextHighlighter:
    """Service for identifying and highlighting text on PDF pages."""
    
    def __init__(self, default_color: str = "#FFFF00", default_opacity: float = 0.3):
        self.default_color = default_color
        self.default_opacity = default_opacity
    
    def find_text_coordinates(self, pdf_file: bytes, text: str, page_num: int) -> List[TextCoordinate]:
        """Find coordinates of specific text on a PDF page.
        
        Args:
            pdf_file: PDF file as bytes
            text: Text to search for
            page_num: Page number (1-indexed)
            
        Returns:
            List of TextCoordinate objects for all occurrences
        """
        coordinates = []
        
        try:
            # Open PDF from bytes
            doc = fitz.open(stream=pdf_file, filetype="pdf")
            
            # Validate page number
            if page_num < 1 or page_num > len(doc):
                logging.warning(f"Invalid page number {page_num}. Document has {len(doc)} pages.")
                doc.close()
                return coordinates
            
            # Load page (convert to 0-indexed)
            page = doc.load_page(page_num - 1)
            
            # Search for text on the page
            # PyMuPDF's search_for returns list of Rect objects
            text_instances = page.search_for(text)
            
            for rect in text_instances:
                coord = TextCoordinate(
                    text=text,
                    page_number=page_num,
                    coordinates=BoundingBox(
                        x0=rect.x0,
                        y0=rect.y0,
                        x1=rect.x1,
                        y1=rect.y1
                    )
                )
                coordinates.append(coord)
            
            doc.close()
            return coordinates
            
        except Exception as e:
            logging.error(f"Error finding text coordinates: {str(e)}")
            return coordinates
    
    def find_text_coordinates_fuzzy(self, pdf_file: bytes, text: str, page_num: int, 
                                   tolerance: float = 0.9) -> List[TextCoordinate]:
        """Find coordinates of text with fuzzy matching for partial matches.
        
        Args:
            pdf_file: PDF file as bytes
            text: Text to search for
            page_num: Page number (1-indexed)
            tolerance: Similarity threshold (0.0-1.0)
            
        Returns:
            List of TextCoordinate objects for all matches
        """
        coordinates = []
        
        try:
            # Open PDF from bytes
            doc = fitz.open(stream=pdf_file, filetype="pdf")
            
            # Validate page number
            if page_num < 1 or page_num > len(doc):
                logging.warning(f"Invalid page number {page_num}. Document has {len(doc)} pages.")
                doc.close()
                return coordinates
            
            # Load page (convert to 0-indexed)
            page = doc.load_page(page_num - 1)
            
            # Get all text blocks with coordinates
            blocks = page.get_text("dict")
            
            # Normalize search text for comparison
            search_text_normalized = text.lower().strip()
            
            for block in blocks["blocks"]:
                if "lines" in block:  # Text block (not image)
                    for line in block["lines"]:
                        # Combine spans in line to get full line text
                        line_text = " ".join([span["text"] for span in line["spans"]])
                        line_text_normalized = line_text.lower().strip()
                        
                        # Check if search text is in this line
                        if search_text_normalized in line_text_normalized:
                            # Get bounding box for the entire line
                            # Calculate from all spans in the line
                            if line["spans"]:
                                min_x0 = min(span["bbox"][0] for span in line["spans"])
                                min_y0 = min(span["bbox"][1] for span in line["spans"])
                                max_x1 = max(span["bbox"][2] for span in line["spans"])
                                max_y1 = max(span["bbox"][3] for span in line["spans"])
                                
                                coord = TextCoordinate(
                                    text=line_text,
                                    page_number=page_num,
                                    coordinates=BoundingBox(
                                        x0=min_x0,
                                        y0=min_y0,
                                        x1=max_x1,
                                        y1=max_y1
                                    )
                                )
                                coordinates.append(coord)
            
            doc.close()
            return coordinates
            
        except Exception as e:
            logging.error(f"Error finding text coordinates with fuzzy matching: {str(e)}")
            return coordinates
    
    def create_highlight_overlay(self, coordinates: List[TextCoordinate], 
                                color: str = None, opacity: float = None) -> List[HighlightOverlay]:
        """Create highlight overlays for text coordinates.
        
        Args:
            coordinates: List of text coordinates to highlight
            color: Highlight color in hex format (e.g., "#FFFF00")
            opacity: Highlight opacity (0.0-1.0)
            
        Returns:
            List of HighlightOverlay objects
        """
        if color is None:
            color = self.default_color
        if opacity is None:
            opacity = self.default_opacity
            
        overlays = []
        
        for coord in coordinates:
            overlay = HighlightOverlay(
                coordinates=coord.coordinates,
                color=color,
                opacity=opacity,
                text_content=coord.text
            )
            overlays.append(overlay)
        
        return overlays
    
    def create_highlight_overlay_from_bbox(self, bounding_boxes: List[BoundingBox],
                                          text_content: str = "",
                                          color: str = None, 
                                          opacity: float = None) -> List[HighlightOverlay]:
        """Create highlight overlays directly from bounding boxes.
        
        Useful when coordinates are already known (e.g., from document chunks).
        
        Args:
            bounding_boxes: List of bounding boxes to highlight
            text_content: Associated text content
            color: Highlight color in hex format
            opacity: Highlight opacity (0.0-1.0)
            
        Returns:
            List of HighlightOverlay objects
        """
        if color is None:
            color = self.default_color
        if opacity is None:
            opacity = self.default_opacity
            
        overlays = []
        
        for bbox in bounding_boxes:
            overlay = HighlightOverlay(
                coordinates=bbox,
                color=color,
                opacity=opacity,
                text_content=text_content
            )
            overlays.append(overlay)
        
        return overlays
    
    def render_highlighted_page(self, pdf_file: bytes, page_num: int, 
                               overlays: List[HighlightOverlay], dpi: int = 150) -> bytes:
        """Render a PDF page with highlight overlays.
        
        This is a convenience method that combines page rendering and highlight application.
        
        Args:
            pdf_file: PDF file as bytes
            page_num: Page number (1-indexed)
            overlays: List of highlight overlays to apply
            dpi: Resolution for rendering
            
        Returns:
            PNG image with highlights as bytes
        """
        try:
            # Import here to avoid circular dependency
            from src.highlighting.page_renderer import PageRenderer
            
            renderer = PageRenderer(default_dpi=dpi)
            
            # Convert page to image
            image_bytes = renderer.pdf_page_to_image(pdf_file, page_num, dpi)
            
            # Apply highlights
            highlighted_image = renderer.apply_highlights(image_bytes, overlays)
            
            return highlighted_image
            
        except Exception as e:
            logging.error(f"Error rendering highlighted page: {str(e)}")
            raise