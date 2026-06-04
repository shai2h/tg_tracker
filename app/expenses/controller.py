from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.expenses import schemas
from app.expenses.repository import ExpenseRepository

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.post("", response_model=schemas.ExpenseRead)
def create_expense(
    expense: schemas.ExpenseCreate,
    db: Session = Depends(get_db),
):
    repository = ExpenseRepository(db)

    return repository.create(
        user_id=expense.user_id,
        title=expense.title,
        amount=expense.amount,
    )


@router.get("/{user_id}", response_model=list[schemas.ExpenseRead])
def get_expenses(
    user_id: int,
    db: Session = Depends(get_db),
):
    repository = ExpenseRepository(db)

    return repository.get_by_user_id(user_id=user_id)


@router.delete("/{expense_id}")
def delete_expense(
    expense_id: int,
    user_id: int,
    db: Session = Depends(get_db),
):
    repository = ExpenseRepository(db)

    deleted = repository.delete_by_id_and_user_id(
        expense_id=expense_id,
        user_id=user_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Expense not found",
        )

    return {"status": "deleted"}