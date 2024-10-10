import pytest
from httpx import AsyncClient
from swparse.__about__ import __version__

pytestmark = pytest.mark.anyio


async def test_health(client: AsyncClient, valkey_service: None) -> None:
    response = await client.get("/health")
    assert response.status_code == 500

    expected = {
        "database_status": "online",
        "cache_status": "offline",
        "swparse": "swparse",
        "version": __version__,
    }

    assert response.json() == expected
