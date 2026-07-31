import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message
from sqlalchemy import select

from app.bot import middleware as bot_middleware
from app.bot.middleware import ServiceMiddleware
from app.expenses.models import ExpenseOrm
from app.expenses.repository import ExpenseRepository
from app.expenses.schemas import ExpenseCreate
from app.expenses.service import ExpenseService
from app.llm.queue import ClassificationQueue


class RecordingQueue:
    def __init__(self, events: list[str]):
        self.events = events
        self.calls: list[tuple] = []

    async def enqueue(self, expense_id, title, on_done) -> None:
        self.events.append("enqueue")
        self.calls.append((expense_id, title, on_done))


class FailingEnqueueQueue:
    def __init__(self, events: list[str]):
        self.events = events
        self.calls: list[tuple] = []

    async def enqueue(self, expense_id, title, on_done) -> None:
        self.events.append("enqueue")
        self.calls.append((expense_id, title, on_done))
        raise RuntimeError("enqueue failed")


class TrackingSessionFactory:
    def __init__(
        self,
        session_factory,
        events: list[str],
        *,
        commit_error: Exception | None = None,
    ):
        self._session_factory = session_factory
        self._events = events
        self._commit_error = commit_error
        self._cm = None

    def __call__(self):
        return self

    async def __aenter__(self):
        self._cm = self._session_factory()
        session = await self._cm.__aenter__()
        original_commit = session.commit
        original_rollback = session.rollback

        async def commit():
            self._events.append("commit")
            if self._commit_error is not None:
                raise self._commit_error
            return await original_commit()

        async def rollback():
            self._events.append("rollback")
            return await original_rollback()

        session.commit = commit
        session.rollback = rollback
        return session

    async def __aexit__(self, exc_type, exc, tb):
        return await self._cm.__aexit__(exc_type, exc, tb)


def _message() -> Message:
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_service_create_does_not_enqueue_immediately(db_session_factory):
    events: list[str] = []
    queue = RecordingQueue(events)

    async with db_session_factory() as session:
        service = ExpenseService(
            ExpenseRepository(session),
            queue,
            db_session_factory,
        )
        await service.create(
            telegram_id=1,
            username="user",
            data=ExpenseCreate(title="кофе", amount_rubles=Decimal("150")),
        )
        assert events == []
        assert service.pending_enqueue is not None
        await session.commit()

    await service.pending_enqueue()
    assert events == ["enqueue"]


@pytest.mark.asyncio
async def test_middleware_enqueues_after_commit(db_session_factory):
    events: list[str] = []
    queue = RecordingQueue(events)
    middleware = ServiceMiddleware()

    async def handler(event, data):
        service: ExpenseService = data["service"]
        await service.create(
            telegram_id=10,
            username="alice",
            data=ExpenseCreate(title="такси", amount_rubles=Decimal("250")),
        )

    await middleware(
        handler,
        _message(),
        {
            "session_factory": TrackingSessionFactory(db_session_factory, events),
            "classification_queue": queue,
        },
    )

    assert events == ["commit", "enqueue"]


@pytest.mark.asyncio
async def test_middleware_skips_enqueue_on_handler_error(db_session_factory):
    events: list[str] = []
    queue = RecordingQueue(events)
    middleware = ServiceMiddleware()
    message = _message()

    async def handler(event, data):
        service: ExpenseService = data["service"]
        await service.create(
            telegram_id=11,
            username="bob",
            data=ExpenseCreate(title="обед", amount_rubles=Decimal("400")),
            category_future=asyncio.get_running_loop().create_future(),
        )
        raise RuntimeError("handler failed")

    await middleware(
        handler,
        message,
        {
            "session_factory": TrackingSessionFactory(db_session_factory, events),
            "classification_queue": queue,
        },
    )

    assert "enqueue" not in events
    assert "rollback" in events
    assert queue.calls == []
    message.answer.assert_awaited_with("Что-то пошло не так. Попробуй позже.")


@pytest.mark.asyncio
async def test_middleware_skips_enqueue_on_commit_error(db_session_factory):
    events: list[str] = []
    queue = RecordingQueue(events)
    middleware = ServiceMiddleware()
    message = _message()

    async def handler(event, data):
        service: ExpenseService = data["service"]
        await service.create(
            telegram_id=13,
            username="dana",
            data=ExpenseCreate(title="метро", amount_rubles=Decimal("50")),
            category_future=asyncio.get_running_loop().create_future(),
        )

    await middleware(
        handler,
        message,
        {
            "session_factory": TrackingSessionFactory(
                db_session_factory,
                events,
                commit_error=RuntimeError("commit failed"),
            ),
            "classification_queue": queue,
        },
    )

    assert "enqueue" not in events
    assert "commit" in events
    assert "rollback" in events
    assert queue.calls == []
    message.answer.assert_awaited_with("Что-то пошло не так. Попробуй позже.")


@pytest.mark.asyncio
async def test_middleware_keeps_commit_when_enqueue_fails(db_session_factory):
    events: list[str] = []
    queue = FailingEnqueueQueue(events)
    middleware = ServiceMiddleware()
    message = _message()

    async def handler(event, data):
        service: ExpenseService = data["service"]
        await service.create(
            telegram_id=14,
            username="erin",
            data=ExpenseCreate(title="чай", amount_rubles=Decimal("120")),
            category_future=asyncio.get_running_loop().create_future(),
        )

    await middleware(
        handler,
        message,
        {
            "session_factory": TrackingSessionFactory(db_session_factory, events),
            "classification_queue": queue,
        },
    )

    assert events == ["commit", "enqueue"]
    assert "rollback" not in events
    message.answer.assert_awaited_with(
        "Расход сохранён, но категорию определить не удалось."
    )
    generic_error = "Что-то пошло не так. Попробуй позже."
    assert generic_error not in [
        call.args[0] for call in message.answer.await_args_list
    ]


@pytest.mark.asyncio
async def test_category_wait_timeout_does_not_cancel_future(
    db_session_factory,
    monkeypatch,
):
    events: list[str] = []
    monkeypatch.setattr(bot_middleware, "_CATEGORY_WAIT_TIMEOUT_SECONDS", 0.05)

    class NeverDoneQueue:
        async def enqueue(self, expense_id, title, on_done) -> None:
            events.append("enqueue")

    queue = NeverDoneQueue()
    middleware = ServiceMiddleware()
    category_future: asyncio.Future[str] = asyncio.get_running_loop().create_future()

    async def handler(event, data):
        service: ExpenseService = data["service"]
        await service.create(
            telegram_id=15,
            username="frank",
            data=ExpenseCreate(title="сок", amount_rubles=Decimal("90")),
            category_future=category_future,
        )

    await middleware(
        handler,
        _message(),
        {
            "session_factory": TrackingSessionFactory(db_session_factory, events),
            "classification_queue": queue,
        },
    )

    assert events == ["commit", "enqueue"]
    assert category_future.cancelled() is False
    assert category_future.done() is False


@pytest.mark.asyncio
async def test_callback_updates_category_after_commit(db_session_factory):
    events: list[str] = []

    class SuccessClassifier:
        async def classify(self, title: str) -> tuple[str, float]:
            return ("кафе", 0.95)

    class OrderRecordingQueue(ClassificationQueue):
        async def enqueue(self, expense_id, title, on_done) -> None:
            events.append("enqueue")
            await super().enqueue(expense_id, title, on_done)

    queue = OrderRecordingQueue(SuccessClassifier())
    await queue.start()
    middleware = ServiceMiddleware()
    category_future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
    expense_id_holder: dict[str, object] = {}

    async def handler(event, data):
        service: ExpenseService = data["service"]
        expense = await service.create(
            telegram_id=12,
            username="carol",
            data=ExpenseCreate(title="латте", amount_rubles=Decimal("180")),
            category_future=category_future,
        )
        expense_id_holder["id"] = expense.id

    message = _message()
    await middleware(
        handler,
        message,
        {
            "session_factory": TrackingSessionFactory(db_session_factory, events),
            "classification_queue": queue,
        },
    )

    assert events[:2] == ["commit", "enqueue"]
    assert await category_future == "кафе"
    message.answer.assert_any_call("Категория: кафе ✓")

    async with db_session_factory() as session:
        expense = await session.scalar(
            select(ExpenseOrm).where(ExpenseOrm.id == expense_id_holder["id"])
        )

    assert expense is not None
    assert expense.category == "кафе"
    await queue.stop()
