from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.expenses.dependencies import get_expense_service
from app.expenses.exceptions import ExpenseNotFoundError
from app.expenses.schemas import ExpenseCreate, ExpenseRead, ExpenseUpdate
from app.expenses.service import ExpenseService


router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.post(
    "",
    response_model=ExpenseRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_expense(
    user_id: UUID,
    data: ExpenseCreate,
    service: ExpenseService = Depends(get_expense_service),
):
    return await service.create_for_user(
        user_id=user_id,
        data=data,
    )


@router.get("/user/{user_id}", response_model=list[ExpenseRead])
async def get_user_expenses(
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
    service: ExpenseService = Depends(get_expense_service),
):
    return await service.get_by_user_id(
        user_id=user_id,
        limit=limit,
        offset=offset,
    )


@router.put("/{expense_id}", response_model=ExpenseRead)
async def update_expense(
    expense_id: UUID,
    data: ExpenseUpdate,
    service: ExpenseService = Depends(get_expense_service),
):
    try:
        return await service.update(expense_id, data)
    except ExpenseNotFoundError:
        raise HTTPException(status_code=404, detail="Expense not found")


@router.delete(
    "/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_expense(
    expense_id: UUID,
    service: ExpenseService = Depends(get_expense_service),
):
    try:
        await service.delete(expense_id)
    except ExpenseNotFoundError:
        raise HTTPException(status_code=404, detail="Expense not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)