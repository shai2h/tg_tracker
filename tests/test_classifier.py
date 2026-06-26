import pytest

from app.llm.classifier import ExpenseCategoryClassifier


class FakeProvider:
    def __init__(self, response: str):
        self.response = response

    async def complete(self, prompt: str) -> str:
        return self.response


@pytest.mark.asyncio
async def test_classify_returns_valid_category():
    classifier = ExpenseCategoryClassifier(FakeProvider("транспорт"))

    assert await classifier.classify("такси") == "транспорт"


@pytest.mark.asyncio
async def test_classify_returns_other_for_unknown_category():
    classifier = ExpenseCategoryClassifier(FakeProvider("непонятно"))

    assert await classifier.classify("что-то") == "другое"


@pytest.mark.asyncio
async def test_classify_returns_other_for_empty_response():
    classifier = ExpenseCategoryClassifier(FakeProvider(""))

    assert await classifier.classify("что-то") == "другое"
