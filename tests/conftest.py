from uuid import UUID

import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.expenses.dependencies import get_classification_queue, get_gigachat_provider
from app.main import app


class NoOpGigaChatProvider:
    async def complete(self, prompt: str) -> str:
        return '{"category": "другое", "confidence": 0.0}'


class NoOpClassificationQueue:
    async def enqueue(
        self,
        expense_id: UUID,
        title: str,
        on_done,
    ) -> None:
        pass


@pytest_asyncio.fixture
async def db_session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    yield session_factory

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session_factory):
    async def override_get_db():
        async with db_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    fake_provider = NoOpGigaChatProvider()

    def override_get_gigachat_provider(request: Request):
        return fake_provider

    app.dependency_overrides[get_gigachat_provider] = override_get_gigachat_provider
    fake_queue = NoOpClassificationQueue()

    def override_get_classification_queue(request: Request):
        return fake_queue

    app.dependency_overrides[get_classification_queue] = override_get_classification_queue

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
