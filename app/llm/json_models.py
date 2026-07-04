from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


class ExpenseClassificationResponse(BaseModel):
    category: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    confidence: float = Field(ge=0.0, le=1.0)
