from __future__ import annotations

from uuid import UUID

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class Document(UUIDAuditBase):
    __tablename__ = "documents"

    file_name: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    file_size: Mapped[int | None] = mapped_column(nullable=True, default=None)
    file_path: Mapped[str] = mapped_column(String(length=255), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user_account.id", ondelete="cascade"), nullable=False)
    job_id: Mapped[str] = mapped_column(String(length=150), nullable=False)
