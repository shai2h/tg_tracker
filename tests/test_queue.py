import asyncio
from uuid import uuid4

import pytest

from app.llm.queue import ClassificationQueue


class SuccessClassifier:
    async def classify(self, title: str) -> tuple[str, float]:
        return ("кафе", 0.95)


class FailingClassifier:
    async def classify(self, title: str) -> tuple[str, float]:
        raise RuntimeError("classification failed")


class CountingClassifier:
    def __init__(self) -> None:
        self.calls = 0

    async def classify(self, title: str) -> tuple[str, float]:
        self.calls += 1
        return ("кафе", 0.95)


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
async def test_queue_uses_unknown_after_three_failed_attempts():
    queue = ClassificationQueue(FailingClassifier())
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
    await queue.stop()


@pytest.mark.asyncio
async def test_queue_calls_callback_exactly_once():
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
