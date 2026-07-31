import pytest

from app.llm.classifier import ExpenseCategoryClassifier
from app.llm.exceptions import RetryableLLMError


class FakeProvider:
    def __init__(self, response: str):
        self.response = response

    async def complete(self, prompt: str) -> str:
        return self.response


class RetryableProvider:
    async def complete(self, prompt: str) -> str:
        raise RetryableLLMError("upstream retryable")


class RuntimeErrorProvider:
    async def complete(self, prompt: str) -> str:
        raise RuntimeError("provider bug")


@pytest.mark.asyncio
async def test_classify_valid_json():
    classifier = ExpenseCategoryClassifier(
        FakeProvider('{"category": "транспорт", "confidence": 0.95}')
    )

    assert await classifier.classify("такси") == ("транспорт", 0.95)


@pytest.mark.asyncio
async def test_classify_invalid_json_raises():
    classifier = ExpenseCategoryClassifier(FakeProvider("непонятно"))

    with pytest.raises(RetryableLLMError):
        await classifier.classify("что-то")


@pytest.mark.asyncio
async def test_classify_unknown_category():
    classifier = ExpenseCategoryClassifier(
        FakeProvider('{"category": "непонятно", "confidence": 0.8}')
    )

    assert await classifier.classify("что-то") == ("другое", 0.8)


@pytest.mark.asyncio
async def test_classify_empty_response_raises():
    classifier = ExpenseCategoryClassifier(FakeProvider(""))

    with pytest.raises(RetryableLLMError):
        await classifier.classify("что-то")


@pytest.mark.asyncio
async def test_classify_whitespace_only_category_raises():
    classifier = ExpenseCategoryClassifier(
        FakeProvider('{"category": "   ", "confidence": 0.8}')
    )

    with pytest.raises(RetryableLLMError):
        await classifier.classify("что-то")


@pytest.mark.asyncio
async def test_classify_passes_through_retryable_from_provider():
    classifier = ExpenseCategoryClassifier(RetryableProvider())

    with pytest.raises(RetryableLLMError, match="upstream retryable"):
        await classifier.classify("что-то")


@pytest.mark.asyncio
async def test_classify_passes_through_runtime_error_from_provider():
    classifier = ExpenseCategoryClassifier(RuntimeErrorProvider())

    with pytest.raises(RuntimeError, match="provider bug"):
        await classifier.classify("что-то")
