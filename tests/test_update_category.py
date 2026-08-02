import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.expenses.exceptions import ExpenseNotFoundError
from app.expenses.models import ExpenseOrm
from app.expenses.repository import ExpenseRepository
from app.expenses.schemas import ExpenseCreate
from app.expenses.service import ExpenseService


class CaptureQueue:
    def __init__(self) -> None:
        self.on_done = None
        self.expense_id = None
        self.title = None

    async def enqueue(self, expense_id, title, on_done, on_error) -> None:
        self.expense_id = expense_id
        self.title = title
        self.on_done = on_done


@pytest.mark.asyncio
async def test_update_category_updates_existing_expense(db_session_factory):
    async with db_session_factory() as session:
        repository = ExpenseRepository(session)
        user = await repository.get_or_create_user(telegram_id=1, username="user")
        expense = await repository.create(
            user_id=user.id,
            title="кофе",
            amount_kopeiki=15000,
            category=None,
        )
        expense_id = expense.id

        await repository.update_category(expense_id, "кафе")
        await session.commit()

    async with db_session_factory() as session:
        stored = await session.scalar(
            select(ExpenseOrm).where(ExpenseOrm.id == expense_id)
        )

    assert stored is not None
    assert stored.category == "кафе"


@pytest.mark.asyncio
async def test_update_category_raises_when_expense_missing(db_session_factory):
    missing_id = uuid4()

    async with db_session_factory() as session:
        repository = ExpenseRepository(session)
        before = await session.scalar(select(func.count()).select_from(ExpenseOrm))

        with pytest.raises(ExpenseNotFoundError):
            await repository.update_category(missing_id, "кафе")

        after = await session.scalar(select(func.count()).select_from(ExpenseOrm))
        await session.rollback()

    assert before == 0
    assert after == 0


@pytest.mark.asyncio
async def test_on_done_does_not_succeed_when_expense_missing(db_session_factory):
    queue = CaptureQueue()

    async with db_session_factory() as session:
        service = ExpenseService(
            ExpenseRepository(session),
            queue,
            db_session_factory,
        )
        expense = await service.create(
            telegram_id=2,
            username="alice",
            data=ExpenseCreate(title="такси", amount_rubles=Decimal("250")),
        )
        expense_id = expense.id

    assert queue.on_done is not None

    async with db_session_factory() as session:
        deleted = await ExpenseRepository(session).delete(expense_id)
        await session.commit()

    assert deleted == expense_id

    with pytest.raises(ExpenseNotFoundError):
        await queue.on_done("транспорт", 0.95)
