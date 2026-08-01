import pytest

from app.llm.classifier import ExpenseCategoryClassifier
from app.llm.exceptions import RetryableLLMError
from app.llm.json_models import CLASSIFICATION_RESPONSE_FORMAT


class FakeProvider:
    def __init__(self, response: str):
        self.response = response
        self.last_response_format: dict[str, object] | None = None

    async def complete(
        self,
        prompt: str,
        response_format: dict[str, object] | None = None,
    ) -> str:
        self.last_response_format = response_format
        return self.response


class RetryableProvider:
    async def complete(
        self,
        prompt: str,
        response_format: dict[str, object] | None = None,
    ) -> str:
        raise RetryableLLMError("upstream retryable")


class RuntimeErrorProvider:
    async def complete(
        self,
        prompt: str,
        response_format: dict[str, object] | None = None,
    ) -> str:
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


@pytest.mark.asyncio
async def test_classify_passes_json_schema_response_format():
    provider = FakeProvider('{"category": "транспорт", "confidence": 0.95}')
    classifier = ExpenseCategoryClassifier(provider)

    await classifier.classify("такси")

    response_format = provider.last_response_format
    assert response_format is CLASSIFICATION_RESPONSE_FORMAT
    assert response_format["type"] == "json_schema"
    assert response_format["strict"] is True

    schema = response_format["schema"]
    assert schema["properties"]["category"]["type"] == "string"
    assert schema["properties"]["confidence"]["type"] == "number"
    assert schema["properties"]["confidence"]["minimum"] == 0.0
    assert schema["properties"]["confidence"]["maximum"] == 1.0
    assert schema["required"] == ["category", "confidence"]
    assert schema["additionalProperties"] is False
