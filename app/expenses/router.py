from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.expenses.schemas import ExpenseCreate, ExpenseRead, ExpenseUpdate
from app.expenses.service import ExpenseService

router = APIRouter(prefix="/expenses", tags=["expenses"])


def to_read(expense) -> ExpenseRead:
    return ExpenseRead(
        id=expense.id,
        user_id=expense.user_id,
        title=expense.title,
        amount_rubles=expense.amount_kopeiki / 100,
        created_at=expense.created_at,
    )


@router.post("", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
async def create_expense(
    data: ExpenseCreate,
    session: AsyncSession = Depends(get_db),
):
    service = ExpenseService(session)
    expense = await service.create(data)
    return to_read(expense)


@router.get("/user/{user_id}", response_model=list[ExpenseRead])
async def get_user_expenses(
    user_id: int,
    session: AsyncSession = Depends(get_db),
):
    service = ExpenseService(session)
    expenses = await service.get_by_user_id(user_id)
    return [to_read(expense) for expense in expenses]


@router.patch("/{expense_id}")
async def update_expense(
    expense_id: UUID,
    data: ExpenseUpdate,
    session: AsyncSession = Depends(get_db),
):
    service = ExpenseService(session)
    expense = await service.update(expense_id, data)

    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")

    return to_read(expense)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    service = ExpenseService(session)
    deleted = await service.delete(expense_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Expense not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)