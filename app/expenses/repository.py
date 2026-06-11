from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.expenses.models import ExpenseOrm


class ExpenseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, title: str, amount_kopeiki: int):
        expense = ExpenseOrm(
            user_id=user_id,
            title=title,
            amount_kopeiki=amount_kopeiki,
        )

        self.session.add(expense)
        await self.session.commit()
        await self.session.refresh(expense)

        return expense

    async def get_by_user_id(self, user_id: int):
        stmt = (
            select(ExpenseOrm)
            .where(ExpenseOrm.user_id == user_id)
            .order_by(ExpenseOrm.created_at.desc())
        )

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, expense_id: UUID):
        stmt = select(ExpenseOrm).where(ExpenseOrm.id == expense_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, expense_id: UUID, title: str | None, amount_kopeiki: int | None):
        expense = await self.get_by_id(expense_id)

        if expense is None:
            return None

        if title is not None:
            expense.title = title

        if amount_kopeiki is not None:
            expense.amount_kopeiki = amount_kopeiki

        await self.session.commit()
        await self.session.refresh(expense)

        return expense

    async def delete(self, expense_id: UUID):
        expense = await self.get_by_id(expense_id)

        if expense is None:
            return False

        await self.session.delete(expense)
        await self.session.commit()

        return True