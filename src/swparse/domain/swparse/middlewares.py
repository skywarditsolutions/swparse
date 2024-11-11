"""User Account Controllers."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import structlog
from litestar import Request
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.middleware import AbstractMiddleware
from litestar.types import Receive, Scope, Send

from swparse.config.app import alchemy
from swparse.domain.accounts.dependencies import provide_api_key_service
from swparse.domain.accounts.urls import API_KEY_GENERATE

if TYPE_CHECKING:
    from litestar.types import Receive, Scope, Send

logger = structlog.get_logger()

api_key_header = os.environ.get("PARSER_API_HEADER")


class ApiKeyAuthMiddleware(AbstractMiddleware):
    exclude = [API_KEY_GENERATE, "/api/parsing/query_syntax"]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if api_key_header is None:
            raise NotAuthorizedException(detail="api key header missing", status_code=500)
        request = Request(scope)
        headers = request.headers

        api_key = headers.get(api_key_header)
        if not api_key:
            raise NotAuthorizedException(status_code=403, detail="Forbidden missing API key")

        connection: ASGIConnection = ASGIConnection(scope=scope, receive=receive, send=send)
        api_key_service = await anext(
            provide_api_key_service(alchemy.provide_session(connection.app.state, connection.scope))
        )
        is_authorized = bool(await api_key_service.authenticate(api_key))
        logger.error("API key authentication")
        logger.error(is_authorized)

        if not is_authorized:
            raise NotAuthorizedException(status_code=403, detail="Forbidden: Invalid API key")
        await self.app(scope, receive, send)
