import asyncio
from uuid import uuid4

import pytest

from app.llm.exceptions import RetryableLLMError
from app.llm.queue import ClassificationQueue, _MAX_ATTEMPTS


class SuccessClassifier:
    async def classify(self, title: str) -> tuple[str, float]:
        return ("кафе", 0.95)


class FailingClassifier:
    def __init__(self) -> None:
        self.calls = 0

    async def classify(self, title: str) -> tuple[str, float]:
        self.calls += 1
        raise RetryableLLMError("classification failed")


class FlakyClassifier:
    def __init__(self) -> None:
        self.calls = 0

    async def classify(self, title: str) -> tuple[str, float]:
        self.calls += 1
        if self.calls == 1:
            raise RetryableLLMError("temporary failure")
        return ("кафе", 0.95)


class CountingClassifier:
    def __init__(self) -> None:
        self.calls = 0

    async def classify(self, title: str) -> tuple[str, float]:
        self.calls += 1
        return ("кафе", 0.95)


class NonRetryableValueErrorClassifier:
    def __init__(self) -> None:
        self.calls = 0

    async def classify(self, title: str) -> tuple[str, float]:
        self.calls += 1
        raise ValueError("business logic error")


class NonRetryableRuntimeErrorClassifier:
    def __init__(self) -> None:
        self.calls = 0

    async def classify(self, title: str) -> tuple[str, float]:
        self.calls += 1
        raise RuntimeError("programmer error")


@pytest.mark.asyncio
async def test_queue_classifies_and_calls_callback_with_category():
    queue = ClassificationQueue(SuccessClassifier())
    await queue.start()

    done = asyncio.Event()
    result: str | None = None

    async def on_done(category: str) -> None:
        nonlocal result
        result = category
        done.set()

    await queue.enqueue(uuid4(), "кофе", on_done)
    await done.wait()

    assert result == "кафе"
    await queue.stop()


@pytest.mark.asyncio
async def test_queue_retries_then_succeeds():
    classifier = FlakyClassifier()
    queue = ClassificationQueue(classifier)
    await queue.start()

    done = asyncio.Event()
    result: str | None = None

    async def on_done(category: str) -> None:
        nonlocal result
        result = category
        done.set()

    await queue.enqueue(uuid4(), "кофе", on_done)
    await done.wait()

    assert result == "кафе"
    assert classifier.calls == 2
    await queue.stop()


@pytest.mark.asyncio
async def test_queue_uses_unknown_after_all_attempts_failed():
    classifier = FailingClassifier()
    queue = ClassificationQueue(classifier)
    await queue.start()

    done = asyncio.Event()
    result: str | None = None

    async def on_done(category: str) -> None:
        nonlocal result
        result = category
        done.set()

    await queue.enqueue(uuid4(), "кофе", on_done)
    await done.wait()

    assert result == "неизвестно"
    assert classifier.calls == _MAX_ATTEMPTS
    await queue.stop()


@pytest.mark.asyncio
async def test_queue_does_not_retry_on_success():
    classifier = CountingClassifier()
    queue = ClassificationQueue(classifier)
    await queue.start()

    done = asyncio.Event()
    callback_calls = 0

    async def on_done(category: str) -> None:
        nonlocal callback_calls
        callback_calls += 1
        done.set()

    await queue.enqueue(uuid4(), "кофе", on_done)
    await done.wait()

    assert callback_calls == 1
    assert classifier.calls == 1
    await queue.stop()


@pytest.mark.asyncio
async def test_queue_attempt_count_matches_max_attempts():
    classifier = FailingClassifier()
    queue = ClassificationQueue(classifier)
    await queue.start()

    done = asyncio.Event()

    async def on_done(category: str) -> None:
        done.set()

    await queue.enqueue(uuid4(), "кофе", on_done)
    await done.wait()

    assert classifier.calls == _MAX_ATTEMPTS
    assert _MAX_ATTEMPTS == 3
    await queue.stop()


@pytest.mark.asyncio
async def test_queue_does_not_retry_value_error():
    classifier = NonRetryableValueErrorClassifier()
    queue = ClassificationQueue(classifier)
    await queue.start()

    done = asyncio.Event()
    result: str | None = None

    async def on_done(category: str) -> None:
        nonlocal result
        result = category
        done.set()

    await queue.enqueue(uuid4(), "кофе", on_done)
    await done.wait()

    assert result == "неизвестно"
    assert classifier.calls == 1
    await queue.stop()


@pytest.mark.asyncio
async def test_queue_does_not_retry_runtime_error():
    classifier = NonRetryableRuntimeErrorClassifier()
    queue = ClassificationQueue(classifier)
    await queue.start()

    done = asyncio.Event()
    result: str | None = None

    async def on_done(category: str) -> None:
        nonlocal result
        result = category
        done.set()

    await queue.enqueue(uuid4(), "кофе", on_done)
    await done.wait()

    assert result == "неизвестно"
    assert classifier.calls == 1
    await queue.stop()
