from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


class ExpenseClassificationResponse(BaseModel):
    category: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    confidence: float = Field(ge=0.0, le=1.0)


CLASSIFICATION_RESPONSE_FORMAT: dict[str, object] = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
            },
        },
        "required": ["category", "confidence"],
        "additionalProperties": False,
    },
    "strict": True,
}
