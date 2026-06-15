import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(base_url="http://127.0.0.1:8001") as ac:
        yield ac