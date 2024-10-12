from __future__ import annotations

from datetime import datetime
from uuid import UUID

from swparse.db.models.file_types import FileTypes
from swparse.domain.swparse.schemas import Status
from swparse.lib.schema import CamelizedBaseStruct

__all__ = ("Extraction",)


class Extraction(CamelizedBaseStruct):
    """User properties to use for a response."""

    id: UUID
    extracted_file_url: str
    user_id: UUID
    document_id: UUID
    created_at: datetime
    updated_at: datetime
    file_type: FileTypes = FileTypes.MARKDOWN
    status: Status = Status.queued
