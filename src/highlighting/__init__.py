"""Text highlighting and page rendering module."""

from src.highlighting.text_highlighter import (
    TextHighlighter,
    TextCoordinate,
    HighlightOverlay
)
from src.highlighting.page_renderer import PageRenderer

__all__ = [
    'TextHighlighter',
    'TextCoordinate',
    'HighlightOverlay',
    'PageRenderer'
]