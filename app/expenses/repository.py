from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.expenses.models import Expense


class ExpenseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: int,
        title: str,
        amount: int,
    ) -> Expense:
        expense = Expense(
            user_id=user_id,
            title=title,
            amount=amount,
        )

        self.db.add(expense)
        await self.db.commit()
        await self.db.refresh(expense)

        return expense

    async def get_by_user_id(self, user_id: int) -> list[Expense]:
        stmt = (
            select(Expense)
            .where(Expense.user_id == user_id)
            .order_by(Expense.created_at.desc())
        )

        result = await self.db.execute(stmt)

        return list(result.scalars().all())

    async def delete_by_id_and_user_id(
        self,
        expense_id: int,
        user_id: int,
    ) -> bool:
        stmt = delete(Expense).where(
            Expense.id == expense_id,
            Expense.user_id == user_id,
        )

        result = await self.db.execute(stmt)
        await self.db.commit()

        return result.rowcount > 0