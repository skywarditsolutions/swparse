from __future__ import annotations

from uuid import UUID

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB


class Document(UUIDAuditBase):
    __tablename__ = "documents"
    extracted_file_paths: Mapped[dict[str, str]] = mapped_column(JSONB, default={}, nullable=False)
    file_name: Mapped[str] = mapped_column(index=True, nullable=False)
    file_size: Mapped[int | None] = mapped_column(nullable=True, default=None)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user_account.id", ondelete="cascade"), nullable=False)
    job_id: Mapped[str] = mapped_column(String(length=150), nullable=False)
    file_path: Mapped[str] = mapped_column(String(length=255), nullable=False)
