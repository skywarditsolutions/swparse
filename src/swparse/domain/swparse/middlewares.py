"""User Account Controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import os
import structlog
from litestar import Request
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.middleware import AbstractMiddleware
from litestar.types import Receive, Scope, Send

from swparse.config.app import alchemy
from swparse.domain.accounts.dependencies import provide_api_key_service
from swparse.domain.accounts.urls import API_KEY_GENERATE
from dotenv import load_dotenv

if TYPE_CHECKING:
    from litestar.types import Receive, Scope, Send

logger = structlog.get_logger()

load_dotenv()
DEFAULT_API_KEY = os.environ["PARSER_API_KEY"]


class ApiKeyAuthMiddleware(AbstractMiddleware):
    exclude = [API_KEY_GENERATE, "/api/parsing/query_syntax"]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        #     request = Request(scope)
        #     headers = request.headers

        #     api_key = headers.get("authorization")
        #     if not api_key:
        #         raise NotAuthorizedException(status_code=403, detail="Forbidden missing API key")

        #     connection: ASGIConnection = ASGIConnection(scope=scope, receive=receive, send=send)
        #     api_key_service = await anext(
        #         provide_api_key_service(alchemy.provide_session(connection.app.state, connection.scope))
        #     )
        #     if api_key != DEFAULT_API_KEY:
        #         is_authorized = bool(await api_key_service.authenticate(api_key))
        #         logger.error("API key authentication")
        #         logger.error(is_authorized)

        #         if not is_authorized:
        #             raise NotAuthorizedException(status_code=403, detail="Forbidden: Invalid API key")
        await self.app(scope, receive, send)
