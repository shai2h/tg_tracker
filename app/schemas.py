from datetime import datetime

from pydantic import BaseModel


class ExpenseCreate(BaseModel):
    user_id: int
    title: str
    amount: int


class ExpenseRead(BaseModel):
    id: int
    user_id: int
    title: str
    amount: int
    created_at: datetime

    model_config = {
        "from_attributes": True
    }