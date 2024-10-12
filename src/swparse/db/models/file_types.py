from __future__ import annotations

from enum import Enum


class FileTypes(str, Enum):
    """Valid Values for Extraction."""

    MARKDOWN = "MARKDOWN"
    TEXT = "TEXT"
    CSV = "CSV"
