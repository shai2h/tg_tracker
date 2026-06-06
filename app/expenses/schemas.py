from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ExpenseCreate(BaseModel):
    user_id: int
    title: str = Field(min_length=1, max_length=255)
    amount_rubles: int = Field(gt=0)


class ExpenseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    amount_rubles: int | None = Field(default=None, gt=0)


class ExpenseRead(BaseModel):
    id: UUID
    user_id: int
    title: str
    amount_rubles: float
    created_at: datetime