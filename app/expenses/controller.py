from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud
from app.database.database import get_db
from app.expenses import schemas

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.post("", response_model=schemas.ExpenseRead)
def create_expense(
    expense: schemas.ExpenseCreate,
    db: Session = Depends(get_db),
):
    return crud.create_expense(
        db=db,
        user_id=expense.user_id,
        title=expense.title,
        amount=expense.amount,
    )


@router.get("/{user_id}", response_model=list[schemas.ExpenseRead])
def get_expenses(
    user_id: int,
    db: Session = Depends(get_db),
):
    return crud.get_user_expenses(db=db, user_id=user_id)


@router.delete("/{expense_id}")
def delete_expense(
    expense_id: int,
    user_id: int,
    db: Session = Depends(get_db),
):
    deleted = crud.delete_expense(
        db=db,
        expense_id=expense_id,
        user_id=user_id,
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Expense not found")

    return {"status": "deleted"}