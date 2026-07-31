import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.expenses.dependencies import get_gigachat_provider
from app.expenses.repository import ExpenseRepository
from app.expenses.service import ExpenseService
from app.llm.classifier import ExpenseCategoryClassifier

logger = logging.getLogger(__name__)


class ServiceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session_factory: async_sessionmaker = data["session_factory"]

        async with session_factory() as session:
            classifier = ExpenseCategoryClassifier(get_gigachat_provider())
            data["service"] = ExpenseService(ExpenseRepository(session), classifier)
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                logger.exception("Unhandled error in handler")
                if isinstance(event, Message):
                    await event.answer("Что-то пошло не так. Попробуй позже.")
