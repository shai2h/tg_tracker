import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from app.llm.classifier import ExpenseCategoryClassifier

logger = logging.getLogger(__name__)

_STOP = object()


@dataclass
class _ClassificationTask:
    expense_id: UUID
    title: str
    on_done: Callable[[str, float], Awaitable[None]]
    on_error: Callable[[Exception], Awaitable[None]]


class ClassificationQueue:
    def __init__(self, classifier: ExpenseCategoryClassifier):
        self._classifier = classifier
        self._queue: asyncio.Queue[_ClassificationTask | object] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._worker_task is not None and not self._worker_task.done():
            return
        self._worker_task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        if self._worker_task is None:
            return
        await self._queue.put(_STOP)
        await self._worker_task
        self._worker_task = None

    async def enqueue(
        self,
        expense_id: UUID,
        title: str,
        on_done: Callable[[str, float], Awaitable[None]],
        on_error: Callable[[Exception], Awaitable[None]],
    ) -> None:
        await self._queue.put(
            _ClassificationTask(
                expense_id=expense_id,
                title=title,
                on_done=on_done,
                on_error=on_error,
            )
        )

    async def _worker(self) -> None:
        while True:
            item = await self._queue.get()
            try:
                if item is _STOP:
                    break
                await self._process_task(item)
            finally:
                self._queue.task_done()

    async def _process_task(self, task: _ClassificationTask) -> None:
        try:
            category, confidence = await self._classifier.classify(task.title)
            await task.on_done(category, confidence)
        except Exception as exc:
            logger.exception("classification_failed expense_id=%s", task.expense_id)
            try:
                await task.on_error(exc)
            except Exception:
                logger.exception("on_error failed expense_id=%s", task.expense_id)
