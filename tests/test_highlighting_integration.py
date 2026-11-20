"""Integration tests for visual highlighting system."""

import pytest
from src.highlighting import TextHighlighter, PageRenderer, HighlightOverlay
from src.processing.document_processor import BoundingBox
from src.llm.citation_service import CitationService, Citation


class TestHighlightingIntegration:
    """Test integration of highlighting system with response generation."""
    
    def test_page_renderer_initialization(self):
        """Test PageRenderer can be initialized."""
        renderer = PageRenderer(default_dpi=150)
        assert renderer.default_dpi == 150
    
    def test_text_highlighter_initialization(self):
        """Test TextHighlighter can be initialized."""
        highlighter = TextHighlighter(default_color="#FFFF00", default_opacity=0.3)
        assert highlighter.default_color == "#FFFF00"
        assert highlighter.default_opacity == 0.3
    
    def test_create_highlight_overlay_from_bbox(self):
        """Test creating highlight overlays from bounding boxes."""
        highlighter = TextHighlighter()
        
        bbox = BoundingBox(x0=10.0, y0=20.0, x1=100.0, y1=40.0)
        overlays = highlighter.create_highlight_overlay_from_bbox(
            [bbox],
            text_content="Test text",
            color="#FFFF00",
            opacity=0.3
        )
        
        assert len(overlays) == 1
        assert overlays[0].coordinates == bbox
        assert overlays[0].color == "#FFFF00"
        assert overlays[0].opacity == 0.3
        assert overlays[0].text_content == "Test text"
    
    def test_citation_with_highlighting_fields(self):
        """Test Citation dataclass includes highlighting fields."""
        citation = Citation(
            citation_id="test_1",
            document_name="test.pdf",
            page_number=1,
            text_excerpt="Test excerpt",
            coordinates={"x0": 10, "y0": 20, "x1": 100, "y1": 40},
            formatted_citation="test.pdf, Page 1",
            relevance_score=0.95,
            chunk_id="chunk_1",
            highlighted_image_url=None,
            highlighted_image_data=None
        )
        
        assert citation.highlighted_image_url is None
        assert citation.highlighted_image_data is None
    
    def test_citation_service_format_with_highlight(self):
        """Test citation service formats citations with highlight URLs."""
        service = CitationService()
        
        citation = Citation(
            citation_id="test_1",
            document_name="test.pdf",
            page_number=1,
            text_excerpt="Test excerpt",
            coordinates={"x0": 10, "y0": 20, "x1": 100, "y1": 40},
            formatted_citation="test.pdf, Page 1",
            relevance_score=0.95,
            chunk_id="chunk_1",
            highlighted_image_url="http://example.com/image.png"
        )
        
        formatted = service.format_citation_for_api(citation)
        
        assert "highlighted_image_url" in formatted
        assert formatted["highlighted_image_url"] == "http://example.com/image.png"
    
    def test_multiple_overlays_creation(self):
        """Test creating multiple highlight overlays."""
        highlighter = TextHighlighter()
        
        bboxes = [
            BoundingBox(x0=10.0, y0=20.0, x1=100.0, y1=40.0),
            BoundingBox(x0=10.0, y0=50.0, x1=100.0, y1=70.0),
            BoundingBox(x0=10.0, y0=80.0, x1=100.0, y1=100.0)
        ]
        
        overlays = highlighter.create_highlight_overlay_from_bbox(
            bboxes,
            text_content="Multi-line text",
            color="#00FF00",
            opacity=0.4
        )
        
        assert len(overlays) == 3
        for i, overlay in enumerate(overlays):
            assert overlay.coordinates == bboxes[i]
            assert overlay.color == "#00FF00"
            assert overlay.opacity == 0.4
