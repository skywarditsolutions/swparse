from __future__ import annotations

from enum import Enum
from typing import Optional
from uuid import UUID

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class ExtractionStatus(Enum):
    COMPLETE = "COMPLETE"
    PENDING = "PENDING"
    FAILED = "FAILED"


class Extraction(UUIDAuditBase):
    __tablename__ = "extraction"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("user_account.id", ondelete="cascade"), nullable=False)
    file_name: Mapped[str] = mapped_column(nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)
    job_id: Mapped[str] = mapped_column(nullable=False)
    file_path: Mapped[str] = mapped_column(String(length=255), nullable=False)
    status: Mapped[ExtractionStatus] = mapped_column(default=ExtractionStatus.PENDING, nullable=False)
    document_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("documents.id", ondelete="cascade"), nullable=True)
