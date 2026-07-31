import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.expenses.repository import ExpenseRepository
from app.expenses.service import ExpenseService
from app.llm.queue import ClassificationQueue

logger = logging.getLogger(__name__)

_CATEGORY_WAIT_TIMEOUT_SECONDS = 3.0


class ServiceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session_factory: async_sessionmaker = data["session_factory"]
        queue: ClassificationQueue = data["classification_queue"]

        async with session_factory() as session:
            service = ExpenseService(
                ExpenseRepository(session),
                queue,
                session_factory,
            )
            data["service"] = service

            try:
                result = await handler(event, data)
                await session.commit()
            except Exception:
                await session.rollback()
                service.pending_enqueue = None
                service.pending_category_future = None
                logger.exception("Unhandled error in handler")
                if isinstance(event, Message):
                    await event.answer("Что-то пошло не так. Попробуй позже.")
                return

            pending_enqueue = service.pending_enqueue
            service.pending_enqueue = None

            if pending_enqueue is not None:
                try:
                    await pending_enqueue()
                except Exception:
                    logger.exception("Failed to enqueue classification task")
                    service.pending_category_future = None
                    if isinstance(event, Message):
                        await event.answer(
                            "Расход сохранён, но категорию определить не удалось."
                        )
                    return result

            category_future = service.pending_category_future
            service.pending_category_future = None

            if category_future is not None and isinstance(event, Message):
                try:
                    category = await asyncio.wait_for(
                        asyncio.shield(category_future),
                        timeout=_CATEGORY_WAIT_TIMEOUT_SECONDS,
                    )
                    await event.answer(f"Категория: {category} ✓")
                except asyncio.TimeoutError:
                    pass
                except Exception:
                    logger.exception("Failed to notify user about category")

            return result
