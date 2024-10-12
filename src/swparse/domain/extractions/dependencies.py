"""Document Controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from swparse.domain.extractions.services import ExtractionService

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession


async def provide_extraction_service(db_session: AsyncSession) -> AsyncGenerator[ExtractionService, None]:
    """Construct repository and service objects for the request."""
    async with ExtractionService.new(
        session=db_session,
        error_messages={"integrity": "Extraction operation failed."},
    ) as service:
        yield service
