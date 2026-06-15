from datetime import datetime
from uuid import UUID

from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


class ExpenseCreate(BaseModel):
    telegram_id: int
    username: str | None = None
    title: str = Field(min_length=1, max_length=255)
    amount_rubles: Decimal = Field(gt=0, decimal_places=2)


class ExpenseUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    amount_rubles: Decimal = Field(gt=0, decimal_places=2)


class ExpenseRead(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    amount_rubles: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)