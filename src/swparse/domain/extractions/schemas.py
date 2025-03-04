from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID
from swparse.lib.schema import CamelizedBaseStruct
from swparse.db.models.extraction import ExtractionStatus

__all__ = ["Extraction"]


class Extraction(CamelizedBaseStruct):
    id: UUID
    user_id: UUID
    file_name: str
    file_size: int
    job_id: str
    file_path: str
    status: ExtractionStatus
    document_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
