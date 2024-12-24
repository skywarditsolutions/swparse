from __future__ import annotations

from enum import Enum
from uuid import UUID

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class ApiKeyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class ApiKeys(UUIDAuditBase):
    __tablename__ = "api_keys"
    api_key: Mapped[str] = mapped_column(index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user_account.id", ondelete="cascade"), nullable=False)
    status: Mapped[ApiKeyStatus] = mapped_column(default=ApiKeyStatus.ACTIVE, nullable=True)
