from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from redis.asyncio import Redis
from swparse.config import base
from httpx import AsyncClient

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pytest import MonkeyPatch


pytestmark = pytest.mark.anyio
pytest_plugins = [
    "tests.data_fixtures",
    "pytest_databases.docker",
    "pytest_databases.docker.postgres",
    "pytest_databases.docker.valkey",
]


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch: MonkeyPatch) -> None:
    """Path the settings."""

    settings = base.Settings.from_env(".env.testing")

    def get_settings(dotenv_filename: str = ".env.testing") -> base.Settings:
        return settings

    monkeypatch.setattr(base, "get_settings", get_settings)


@pytest.fixture(name="valkey_port", autouse=True, scope="session")
async def fx_valkey_port() -> int:
    """Set port for valkey testing"""

    return int(os.environ.get("VALKEY_PORT", 6308))


@pytest.fixture(name="redis", autouse=True)
async def fx_redis(valkey_docker_ip: str, valkey_service: None, valkey_port: int) -> AsyncGenerator[Redis, None]:
    """Redis instance for testing.

    Returns:
        Redis client instance, function scoped.
    """
    yield Redis(host=valkey_docker_ip, port=valkey_port)

@pytest.fixture(name="client")
async def fx_client(swparse: Litestar) -> AsyncIterator[AsyncClient]:
    config = swparse.get_config()
    async with AsyncClient(base_url="http://localhost", headers=config.headers) as client:
        yield client
