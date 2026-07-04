import json
from typing import Protocol

from pydantic import ValidationError

from app.llm.json_models import ExpenseClassificationResponse

CATEGORIES = (
    "кафе",
    "транспорт",
    "жильё",
    "одежда",
    "продукты",
    "здоровье",
    "развлечения",
    "связь",
    "спорт",
    "другое",
)
ALLOWED_CATEGORIES = set(CATEGORIES)

_CATEGORIES_PROMPT = ", ".join(CATEGORIES)
_CLASSIFY_PROMPT = (
    "Классифицируй расход по одной категории.\n"
    f"Название расхода: {{title}}\n"
    f"Допустимые категории: {_CATEGORIES_PROMPT}\n"
    'Верни ТОЛЬКО JSON без markdown и пояснений: '
    '{{"category": "<категория>", "confidence": <число от 0.0 до 1.0>}}\n'
    "confidence — уверенность модели от 0.0 до 1.0."
)


class LLMProvider(Protocol):
    async def complete(self, prompt: str) -> str: ...


class ExpenseCategoryClassifier:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def classify(self, title: str) -> tuple[str, float]:
        prompt = _CLASSIFY_PROMPT.format(title=title)

        try:
            raw = await self.provider.complete(prompt)
        except Exception:
            return ("другое", 0.0)

        if not raw or not raw.strip():
            return ("другое", 0.0)

        try:
            payload = json.loads(raw.strip())
            parsed = ExpenseClassificationResponse.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
            return ("другое", 0.0)

        category = parsed.category.casefold().strip().replace("е\u0308", "ё")

        if category not in ALLOWED_CATEGORIES:
            return ("другое", parsed.confidence)

        return (category, parsed.confidence)
