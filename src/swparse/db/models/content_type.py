from __future__ import annotations

from enum import Enum


class ContentType(str, Enum):
    """Valid Content-type for Document extraction."""

    # Text-based types
    MARKDOWN = "markdown"
    TEXT = "plain"
    CSV = "csv"
    HTML = "html"
    JSON = "json"
    XML = "xml"
    PDF = "pdf"



