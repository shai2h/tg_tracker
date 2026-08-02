from collections.abc import Awaitable, Callable
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.expenses.exceptions import ExpenseNotFoundError
from app.expenses.repository import ExpenseRepository
from app.expenses.schemas import ExpenseCreate, ExpenseUpdate
from app.llm.queue import ClassificationQueue

_LOW_CONFIDENCE_THRESHOLD = 0.6
_LOW_CONFIDENCE_CATEGORY = "другое"


class ExpenseService:
    def __init__(
        self,
        repository: ExpenseRepository,
        queue: ClassificationQueue,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        self.repository = repository
        self.queue = queue
        self._session_factory = session_factory

    def _rubles_to_kopeiki(self, amount_rubles: Decimal) -> int:
        return int(amount_rubles * 100)

    async def create(
        self,
        telegram_id: int,
        username: str | None,
        data: ExpenseCreate,
        notify: Callable[[str, float], Awaitable[None]] | None = None,
        notify_error: Callable[[Exception], Awaitable[None]] | None = None,
    ):
        user = await self.repository.get_or_create_user(
            telegram_id=telegram_id,
            username=username,
        )

        expense = await self.repository.create(
            user_id=user.id,
            title=data.title,
            amount_kopeiki=self._rubles_to_kopeiki(data.amount_rubles),
            category=None,
        )

        await self.repository.session.commit()

        expense_id = expense.id

        async def on_done(category: str, confidence: float) -> None:
            stored = category if confidence >= _LOW_CONFIDENCE_THRESHOLD else _LOW_CONFIDENCE_CATEGORY
            async with self._session_factory() as session:
                repo = ExpenseRepository(session)
                await repo.update_category(expense_id, stored)
                await session.commit()
            if notify is not None:
                await notify(stored, confidence)

        async def on_error(exc: Exception) -> None:
            if notify_error is not None:
                await notify_error(exc)

        await self.queue.enqueue(expense_id, data.title, on_done, on_error)
        return expense

    async def get_by_telegram_id(
        self,
        telegram_id: int,
        username: str | None,
        limit: int,
        offset: int,
    ):
        user = await self.repository.get_or_create_user(
            telegram_id=telegram_id,
            username=username,
        )
        return await self.repository.get_by_user_id(
            user_id=user.id,
            limit=limit,
            offset=offset,
        )

    async def get_by_user_id(
        self,
        user_id: UUID,
        limit: int,
        offset: int,
    ):
        return await self.repository.get_by_user_id(
            user_id=user_id,
            limit=limit,
            offset=offset,
        )

    async def update(self, expense_id: UUID, data: ExpenseUpdate):
        expense = await self.repository.update(
            expense_id=expense_id,
            title=data.title,
            amount_kopeiki=self._rubles_to_kopeiki(data.amount_rubles),
        )

        if expense is None:
            raise ExpenseNotFoundError

        return expense

    async def delete(self, expense_id: UUID):
        deleted_id = await self.repository.delete(expense_id)

        if deleted_id is None:
            raise ExpenseNotFoundError

        return deleted_id
