import pytest

from app.llm.classifier import ExpenseCategoryClassifier


class FakeProvider:
    def __init__(self, response: str):
        self.response = response

    async def complete(self, prompt: str) -> str:
        return self.response


@pytest.mark.asyncio
async def test_classify_valid_json():
    classifier = ExpenseCategoryClassifier(
        FakeProvider('{"category": "транспорт", "confidence": 0.95}')
    )

    assert await classifier.classify("такси") == ("транспорт", 0.95)


@pytest.mark.asyncio
async def test_classify_invalid_json():
    classifier = ExpenseCategoryClassifier(FakeProvider("непонятно"))

    assert await classifier.classify("что-то") == ("другое", 0.0)


@pytest.mark.asyncio
async def test_classify_unknown_category():
    classifier = ExpenseCategoryClassifier(
        FakeProvider('{"category": "непонятно", "confidence": 0.8}')
    )

    assert await classifier.classify("что-то") == ("другое", 0.8)


@pytest.mark.asyncio
async def test_classify_empty_response():
    classifier = ExpenseCategoryClassifier(FakeProvider(""))

    assert await classifier.classify("что-то") == ("другое", 0.0)


@pytest.mark.asyncio
async def test_classify_whitespace_only_category():
    classifier = ExpenseCategoryClassifier(
        FakeProvider('{"category": "   ", "confidence": 0.8}')
    )

    assert await classifier.classify("что-то") == ("другое", 0.0)
