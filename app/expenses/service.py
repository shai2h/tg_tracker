from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.expenses.repository import ExpenseRepository
from app.expenses.schemas import ExpenseCreate, ExpenseUpdate


class ExpenseService:
    def __init__(self, session: AsyncSession):
        self.repository = ExpenseRepository(session)

    async def create(self, data: ExpenseCreate):
        return await self.repository.create(
            user_id=data.user_id,
            title=data.title,
            amount_kopeiki=data.amount_rubles * 100,
        )

    async def get_by_user_id(self, user_id: int):
        return await self.repository.get_by_user_id(user_id)

    async def update(self, expense_id: UUID, data: ExpenseUpdate):
        amount_kopeiki = None

        if data.amount_rubles is not None:
            amount_kopeiki = data.amount_rubles * 100

        return await self.repository.update(
            expense_id=expense_id,
            title=data.title,
            amount_kopeiki=amount_kopeiki,
        )

    async def delete(self, expense_id: UUID):
        return await self.repository.delete(expense_id)