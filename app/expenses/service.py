from uuid import UUID
from decimal import Decimal
import asyncio
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.expenses.exceptions import ExpenseNotFoundError
from app.expenses.repository import ExpenseRepository
from app.expenses.schemas import ExpenseCreate, ExpenseUpdate
from app.llm.queue import ClassificationQueue


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
        self.pending_enqueue: Callable[[], Awaitable[None]] | None = None
        self.pending_category_future: asyncio.Future[str] | None = None

    def _rubles_to_kopeiki(self, amount_rubles: Decimal) -> int:
        return int(amount_rubles * 100)

    async def create(
        self,
        telegram_id: int,
        username: str | None,
        data: ExpenseCreate,
        category_future: asyncio.Future[str] | None = None,
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

        expense_id = expense.id
        title = data.title
        self.pending_category_future = category_future

        async def on_done(category: str) -> None:
            async with self._session_factory() as session:
                repository = ExpenseRepository(session)
                await repository.update_category(expense_id, category)
                await session.commit()

            if category_future is not None and not category_future.done():
                category_future.set_result(category)

        async def enqueue() -> None:
            await self.queue.enqueue(expense_id, title, on_done)

        self.pending_enqueue = enqueue
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
