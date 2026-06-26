from fastapi import APIRouter, Depends, Query, status

from app.core.security import verify_bot_api_token
from app.expenses.dependencies import get_expense_service
from app.expenses.schemas import ExpenseBotCreate, ExpenseRead
from app.expenses.service import ExpenseService


router = APIRouter(
    prefix="/bot/expenses",
    tags=["bot-expenses"],
    dependencies=[Depends(verify_bot_api_token)],
)


@router.post(
    "",
    response_model=ExpenseRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_expense_from_bot(
    data: ExpenseBotCreate,
    service: ExpenseService = Depends(get_expense_service),
):
    return await service.create_from_bot(data)


@router.get("", response_model=list[ExpenseRead])
async def get_expenses_for_bot(
    telegram_id: int = Query(gt=0),
    limit: int = Query(default=10, ge=1, le=20),
    offset: int = Query(default=0, ge=0),
    service: ExpenseService = Depends(get_expense_service),
):
    return await service.get_by_telegram_id(
        telegram_id=telegram_id,
        limit=limit,
        offset=offset,
    )
