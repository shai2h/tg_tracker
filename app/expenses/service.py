from uuid import UUID

from app.expenses.exceptions import ExpenseNotFoundError
from app.expenses.repository import ExpenseRepository
from app.expenses.schemas import ExpenseCreate, ExpenseUpdate


class ExpenseService:
    def __init__(self, repository: ExpenseRepository):
        self.repository = repository

    async def create(self, data: ExpenseCreate):
        user = await self.repository.get_or_create_user(
            telegram_id=data.telegram_id,
            username=data.username,
        )

        return await self.repository.create(
            user_id=user.id,
            title=data.title,
            amount_kopeiki=int(data.amount_rubles * 100),
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
            amount_kopeiki=int(data.amount_rubles * 100),
        )

        if expense is None:
            raise ExpenseNotFoundError

        return expense

    async def delete(self, expense_id: UUID):
        deleted_id = await self.repository.delete(expense_id)

        if deleted_id is None:
            raise ExpenseNotFoundError

        return deleted_id