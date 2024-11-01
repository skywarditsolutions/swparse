from __future__ import annotations

from enum import Enum


class ContentType(str, Enum):
    """Valid Content-type for Document extraction."""

    # Text-based types
    MARKDOWN = "markdown"
    TEXT = "text"
    CSV = "csv"
    HTML = "html"
    JSON = "json"
    XML = "xml"
    PDF = "pdf"
    TABLE = "table"
    MARKDOWN_TABLE = "table_md"
    IMAGES = "images"
