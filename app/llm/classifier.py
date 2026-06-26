from app.llm.gigachat import GigaChatProvider

ALLOWED_CATEGORIES = {
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
}

_CATEGORIES_PROMPT = ", ".join(sorted(ALLOWED_CATEGORIES))
_CLASSIFY_PROMPT = (
    "Классифицируй расход по одной категории.\n"
    f"Название расхода: {{title}}\n"
    f"Верни ровно одно слово из списка: {_CATEGORIES_PROMPT}.\n"
    "Без пояснений, только название категории."
)


class ExpenseCategoryClassifier:
    def __init__(self, provider: GigaChatProvider):
        self.provider = provider

    async def classify(self, title: str) -> str:
        prompt = _CLASSIFY_PROMPT.format(title=title)
        raw = await self.provider.complete(prompt)
        category = raw.lower().strip().replace("е\u0308", "ё")

        if not category or category not in ALLOWED_CATEGORIES:
            return "другое"

        return category
