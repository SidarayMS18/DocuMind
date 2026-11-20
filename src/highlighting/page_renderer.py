"""Page rendering service for converting PDFs to images."""

from typing import List
import fitz  # PyMuPDF
from PIL import Image
import io
import logging
from src.highlighting.text_highlighter import HighlightOverlay


class PageRenderer:
    """Service for converting PDF pages to images with highlights."""
    
    def __init__(self, default_dpi: int = 150):
        self.default_dpi = default_dpi
    
    def pdf_page_to_image(self, pdf_file: bytes, page_num: int, dpi: int = None) -> bytes:
        """Convert a PDF page to an image.
        
        Args:
            pdf_file: PDF file as bytes
            page_num: Page number (1-indexed)
            dpi: Resolution for rendering (defaults to self.default_dpi)
            
        Returns:
            PNG image as bytes
        """
        if dpi is None:
            dpi = self.default_dpi
            
        try:
            # Open PDF from bytes
            doc = fitz.open(stream=pdf_file, filetype="pdf")
            
            # Validate page number
            if page_num < 1 or page_num > len(doc):
                raise ValueError(f"Invalid page number {page_num}. Document has {len(doc)} pages.")
            
            # Load page (convert to 0-indexed)
            page = doc.load_page(page_num - 1)
            
            # Calculate zoom factor from DPI
            # PyMuPDF default is 72 DPI
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            
            # Render page to pixmap
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Convert to PNG bytes
            img_bytes = pix.tobytes("png")
            
            doc.close()
            return img_bytes
            
        except Exception as e:
            logging.error(f"Error converting PDF page to image: {str(e)}")
            raise
    
    def apply_highlights(self, image: bytes, overlays: List[HighlightOverlay]) -> bytes:
        """Apply highlight overlays to an image.
        
        Args:
            image: PNG image as bytes
            overlays: List of highlight overlays to apply
            
        Returns:
            PNG image with highlights as bytes
        """
        try:
            # Load image from bytes
            img = Image.open(io.BytesIO(image))
            
            # Convert to RGBA if not already (needed for transparency)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Create a transparent overlay layer
            overlay_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
            
            # Draw each highlight on the overlay
            from PIL import ImageDraw
            draw = ImageDraw.Draw(overlay_layer)
            
            for overlay in overlays:
                # Parse color (hex format like "#FFFF00")
                color = self._parse_color(overlay.color)
                
                # Calculate alpha from opacity (0.0-1.0 to 0-255)
                alpha = int(overlay.opacity * 255)
                
                # Create RGBA color tuple
                rgba_color = (*color, alpha)
                
                # Draw rectangle for highlight
                coords = overlay.coordinates
                draw.rectangle(
                    [(coords.x0, coords.y0), (coords.x1, coords.y1)],
                    fill=rgba_color
                )
            
            # Composite the overlay onto the original image
            result = Image.alpha_composite(img, overlay_layer)
            
            # Convert back to RGB for PNG output (smaller file size)
            result = result.convert('RGB')
            
            # Save to bytes
            output = io.BytesIO()
            result.save(output, format='PNG', optimize=True)
            return output.getvalue()
            
        except Exception as e:
            logging.error(f"Error applying highlights to image: {str(e)}")
            raise
    
    def _parse_color(self, color_hex: str) -> tuple:
        """Parse hex color string to RGB tuple.
        
        Args:
            color_hex: Color in hex format (e.g., "#FFFF00" or "FFFF00")
            
        Returns:
            RGB tuple (r, g, b)
        """
        # Remove '#' if present
        color_hex = color_hex.lstrip('#')
        
        # Convert to RGB
        r = int(color_hex[0:2], 16)
        g = int(color_hex[2:4], 16)
        b = int(color_hex[4:6], 16)
        
        return (r, g, b)