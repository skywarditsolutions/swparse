"""Application Modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from litestar.static_files import create_static_files_router

from swparse.domain.accounts.controllers import AccessController, UserController, UserRoleController, APIKeyController
from swparse.domain.documents.controller import DocumentController
from swparse.domain.swparse.controllers import ParserController
from swparse.domain.tags.controllers import TagController
from swparse.domain.teams.controllers import TeamController, TeamMemberController
from swparse.domain.extractions.controller import ExtractionController

if TYPE_CHECKING:
    from litestar.types import ControllerRouterHandler

statics = create_static_files_router(
    path="/vendor/",
    directories=["deploy/frontend/vendor/"],
    html_mode=True,
)

route_handlers: list[ControllerRouterHandler] = [
    ParserController,
    AccessController,
    DocumentController,
    ExtractionController,
    UserController,
    APIKeyController,
    TeamController,
    UserRoleController,
    TeamMemberController,
    TagController,
    statics,
]
