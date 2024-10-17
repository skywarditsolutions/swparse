from __future__ import annotations

from enum import Enum


class ContentType(str, Enum):
    """Valid Content-type for Document extraction."""

    # Text-based types
    MARKDOWN = "text/markdown"
    TEXT = "text/plain"
    CSV = "text/csv"
    HTML = "text/html"
    JSON = "application/json"
    XML = "application/xml"
    PDF = "application/pdf"



