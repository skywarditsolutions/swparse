from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from httpx import AsyncClient
from litestar import get

from swparse.config import app as config

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.stores.redis import RedisStore
    from redis.asyncio import Redis as AsyncRedis
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

pytestmark = pytest.mark.anyio


def test_cache_on_app(swparse: "Litestar", redis: "AsyncRedis") -> None:
    """Test that the swparse's cache is patched.

    Args:
        swparse: The test Litestar instance
        redis: The test Redis client instance.
    """
    assert cast("RedisStore", swparse.stores.get("response_cache"))._redis is redis


def test_engine_on_app(swparse: "Litestar", engine: "AsyncEngine") -> None:
    """Test that the swparse's engine is patched.

    Args:
        swparse: The test Litestar instance
        engine: The test SQLAlchemy engine instance.
    """
    assert swparse.state[config.alchemy.engine_app_state_key] is engine


@pytest.mark.anyio
async def test_db_session_dependency(swparse: "Litestar", engine: "AsyncEngine") -> None:
    """Test that handlers receive session attached to patched engine.

    Args:
        swparse: The test Litestar instance
        engine: The patched SQLAlchemy engine instance.
    """

    @get("/db-session-test", opt={"exclude_from_auth": True})
    async def db_session_dependency_patched(db_session: AsyncSession) -> dict[str, str]:
        return {"result": f"{db_session.bind is engine = }"}

    swparse.register(db_session_dependency_patched)
    # can't use test client as it always starts its own event loop
    async with AsyncClient(swparse=swparse, base_url="http://testserver") as client:
        response = await client.get("/db-session-test")
        assert response.json()["result"] == "db_session.bind is engine = True"
