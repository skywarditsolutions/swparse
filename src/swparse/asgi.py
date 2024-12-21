# pylint: disable=[invalid-name,import-outside-toplevel]
# SPDX-FileCopyrightText: 2023-present Cody Fincher <cody.fincher@gmail.com>
#
# SPDX-License-Identifier: MIT
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID
import structlog

if TYPE_CHECKING:
    from litestar import Litestar

logger = structlog.get_logger()

def create_app() -> Litestar:
    """Create ASGI application."""

    from litestar import Litestar
    from litestar.di import Provide

    from swparse.config import app as config
    from swparse.config import constants
    from swparse.config.base import get_settings
    from swparse.domain.accounts import signals as account_signals
    from swparse.domain.accounts.dependencies import provide_user
    from swparse.domain.accounts.guards import auth
    from swparse.domain.teams import signals as team_signals
    from swparse.lib.dependencies import create_collection_dependencies
    from swparse.server import openapi, plugins, routers

    dependencies = {constants.USER_DEPENDENCY_KEY: Provide(provide_user)}
    dependencies.update(create_collection_dependencies())
    settings = get_settings()

    return Litestar(
        cors_config=config.cors,
        dependencies=dependencies,
        debug=settings.app.DEBUG,
        openapi_config=openapi.config,
        route_handlers=routers.route_handlers,
        signature_types=[UUID],
        plugins=[
            plugins.app_config,
            plugins.structlog,
            plugins.alchemy,
            plugins.saq,
            plugins.granian,
        ],
        request_max_body_size = 1_073_741_824  # 1 GB in bytes
        on_app_init=[auth.on_app_init],
        listeners=[account_signals.user_created_event_handler, team_signals.team_created_event_handler],
    )


swparse = create_app()
