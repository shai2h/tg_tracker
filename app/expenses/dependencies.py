from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.expenses.repository import ExpenseRepository
from app.expenses.service import ExpenseService


def get_expense_repository(
    session: AsyncSession = Depends(get_db),
) -> ExpenseRepository:
    return ExpenseRepository(session)


def get_expense_service(
    repository: ExpenseRepository = Depends(get_expense_repository),
) -> ExpenseService:
    return ExpenseService(repository)