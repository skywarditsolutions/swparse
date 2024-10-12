from __future__ import annotations

from uuid import UUID

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from swparse.domain.swparse.schemas import Status

from .file_types import FileTypes


class Extraction(UUIDAuditBase):
    __tablename__ = "extraction"

    file_type: Mapped[FileTypes] = mapped_column(
        String(length=50),
        default=FileTypes.MARKDOWN,
        nullable=False,
        index=True,
    )

    status: Mapped[Status] = mapped_column(
        String(length=50),
        default=Status.queued,
        nullable=False,
        index=True,
    )

    extracted_file_url: Mapped[str] = mapped_column(String(length=255), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user_account.id", ondelete="cascade"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="cascade"), nullable=False)
