from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from litestar.events import listener

from swparse.config.app import alchemy

from .dependencies import provide_teams_service

if TYPE_CHECKING:
    from uuid import UUID

logger = structlog.get_logger()


@listener("team_created")
async def team_created_event_handler(
    team_id: UUID,
) -> None:
    """Executes when a new user is created.

    Args:
        team_id: The primary key of the team that was created.
    """
    await logger.ainfo("Running post signup flow.")
    async with alchemy.get_session() as db_session:
        service = await anext(provide_teams_service(db_session))
        obj = await service.get_one_or_none(id=team_id)
        if obj is None:
            await logger.aerror("Could not locate the specified team", id=team_id)
        else:
            await logger.ainfo("Found team", **obj.to_dict())
