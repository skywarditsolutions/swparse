"""Document Controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from swparse.domain.documents.services import DocumentService

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession


async def provide_document_service(db_session: AsyncSession) -> AsyncGenerator[DocumentService, None]:
    """Construct repository and service objects for the request."""
    async with DocumentService.new(
        session=db_session,
        error_messages={"duplicate_key": "This document already exists.", "integrity": "Document operation failed."},
    ) as service:
        yield service
