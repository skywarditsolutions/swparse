"""Application Modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from swparse.domain.accounts.controllers import AccessController, UserController, UserRoleController
from swparse.domain.swparse.controllers import ParserController
from swparse.domain.system.controllers import SystemController
from swparse.domain.tags.controllers import TagController
from swparse.domain.teams.controllers import TeamController, TeamMemberController

if TYPE_CHECKING:
    from litestar.types import ControllerRouterHandler


route_handlers: list[ControllerRouterHandler] = [
    AccessController,
    UserController,
    TeamController,
    UserRoleController,
    TeamMemberController,
    TagController,
    SystemController,
    ParserController,
]
