import asyncio
from uuid import uuid4

import pytest

from app.llm.exceptions import RetryableLLMError
from app.llm.queue import ClassificationQueue


class SuccessClassifier:
    async def classify(self, title: str) -> tuple[str, float]:
        return ("кафе", 0.95)


class FailingClassifier:
    def __init__(self) -> None:
        self.calls = 0

    async def classify(self, title: str) -> tuple[str, float]:
        self.calls += 1
        raise RetryableLLMError("classification failed")


class CountingClassifier:
    def __init__(self) -> None:
        self.calls = 0

    async def classify(self, title: str) -> tuple[str, float]:
        self.calls += 1
        return ("кафе", 0.95)


class ValueErrorClassifier:
    def __init__(self) -> None:
        self.calls = 0

    async def classify(self, title: str) -> tuple[str, float]:
        self.calls += 1
        raise ValueError("business logic error")


async def _noop_on_error(exc: Exception) -> None:
    pass


@pytest.mark.asyncio
async def test_queue_classifies_and_calls_on_done():
    queue = ClassificationQueue(SuccessClassifier())
    await queue.start()

    done = asyncio.Event()
    result: tuple[str, float] | None = None

    async def on_done(category: str, confidence: float) -> None:
        nonlocal result
        result = (category, confidence)
        done.set()

    await queue.enqueue(uuid4(), "кофе", on_done, _noop_on_error)
    await done.wait()

    assert result == ("кафе", 0.95)
    await queue.stop()


@pytest.mark.asyncio
async def test_queue_calls_on_error_when_classifier_raises():
    queue = ClassificationQueue(FailingClassifier())
    await queue.start()

    done = asyncio.Event()
    error: Exception | None = None

    async def on_error(exc: Exception) -> None:
        nonlocal error
        error = exc
        done.set()

    async def on_done(category: str, confidence: float) -> None:
        pass

    await queue.enqueue(uuid4(), "кофе", on_done, on_error)
    await done.wait()

    assert isinstance(error, RetryableLLMError)
    await queue.stop()


@pytest.mark.asyncio
async def test_queue_on_done_called_exactly_once():
    classifier = CountingClassifier()
    queue = ClassificationQueue(classifier)
    await queue.start()

    done = asyncio.Event()
    callback_calls = 0

    async def on_done(category: str, confidence: float) -> None:
        nonlocal callback_calls
        callback_calls += 1
        done.set()

    await queue.enqueue(uuid4(), "кофе", on_done, _noop_on_error)
    await done.wait()

    assert callback_calls == 1
    assert classifier.calls == 1
    await queue.stop()


@pytest.mark.asyncio
async def test_queue_calls_on_error_for_value_error():
    classifier = ValueErrorClassifier()
    queue = ClassificationQueue(classifier)
    await queue.start()

    done = asyncio.Event()
    error: Exception | None = None

    async def on_error(exc: Exception) -> None:
        nonlocal error
        error = exc
        done.set()

    async def on_done(category: str, confidence: float) -> None:
        pass

    await queue.enqueue(uuid4(), "кофе", on_done, on_error)
    await done.wait()

    assert isinstance(error, ValueError)
    assert classifier.calls == 1
    await queue.stop()
