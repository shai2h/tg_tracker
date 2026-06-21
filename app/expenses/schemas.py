from datetime import datetime
from uuid import UUID

from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict, computed_field


class ExpenseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    amount_rubles: Decimal = Field(gt=0, decimal_places=2)


class ExpenseUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    amount_rubles: Decimal = Field(gt=0, decimal_places=2)

# ExpenseRead теперь сам берёт поля из ORM и считает amount_rubles через @computed_field
class ExpenseRead(BaseModel):
    id: UUID
    user_id: UUID
    category: str | None = None
    title: str
    amount_kopeiki: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def amount_rubles(self) -> Decimal:
        return Decimal(self.amount_kopeiki) / Decimal(100)


class ExpenseBotCreate(ExpenseCreate):
    telegram_id: int = Field(gt=0)
    username: str | None = Field(default=None, max_length=255)