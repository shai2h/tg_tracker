from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import create_tables, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/expenses", response_model=schemas.ExpenseRead)
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


@app.get("/expenses/{user_id}", response_model=list[schemas.ExpenseRead])
def get_expenses(
    user_id: int,
    db: Session = Depends(get_db),
):
    return crud.get_user_expenses(db=db, user_id=user_id)

# описывать пути в мейн файле годится только для небольшого проекта, обычно пути описывают в отдельных файлах по модулям.
#
@app.delete("/expenses/{expense_id}")
def delete_expense(
    expense_id: int,
    user_id: int,
    db: Session = Depends(get_db),
):
    # а если я пошлю чужой user_id??? что будет?
    deleted = crud.delete_expense(
        db=db,
        expense_id=expense_id,
        user_id=user_id,
    )
    # во первых 204 тут лучше подходит, во вторых "не найдено" только одна из ошибок.

    if not deleted:
        raise HTTPException(status_code=404, detail="Expense not found")

    return {"status": "deleted"}