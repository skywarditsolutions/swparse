from __future__ import annotations

from datetime import datetime  # noqa: TCH003
from uuid import UUID  # noqa: TCH003

from swparse.lib.schema import CamelizedBaseStruct

__all__ = ("Document",)


class Document(CamelizedBaseStruct):
    """User properties to use for a response."""

    id: UUID
    user_id: UUID
    job_id: str
    email: str
    created_at: datetime
    updated_at: datetime
    file_name: str
    file_path: str
    file_size: int | None = None
