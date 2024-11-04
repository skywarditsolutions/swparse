from __future__ import annotations

from typing import TYPE_CHECKING

from .services import ExtractionService

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from sqlalchemy.ext.asyncio import AsyncSession


async def provide_extraction_serivice(db_session: AsyncSession) -> AsyncGenerator[ExtractionService, None]:
    async with ExtractionService.new(
        session=db_session,
    ) as service:
        yield service
