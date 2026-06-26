from uuid import UUID
from decimal import Decimal

from app.expenses.exceptions import ExpenseNotFoundError
from app.expenses.repository import ExpenseRepository
from app.expenses.schemas import ExpenseCreate, ExpenseUpdate


class ExpenseService:
    def __init__(self, repository: ExpenseRepository):
        self.repository = repository

    def _rubles_to_kopeiki(self, amount_rubles: Decimal) -> int:
        return int(amount_rubles * 100)

    async def create(self, telegram_id: int, username: str | None, data: ExpenseCreate):
        user = await self.repository.get_or_create_user(
            telegram_id=telegram_id,
            username=username,
        )

        return await self.repository.create(
            user_id=user.id,
            title=data.title,
            amount_kopeiki=self._rubles_to_kopeiki(data.amount_rubles),
        )

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
