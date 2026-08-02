import asyncio
import re
from decimal import Decimal
from time import time

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.middleware import LoggingMiddleware
from app.expenses.repository import ExpenseRepository
from app.expenses.schemas import ExpenseCreate
from app.expenses.service import ExpenseService
from app.llm.queue import ClassificationQueue

dp = Dispatcher(storage=MemoryStorage())
dp.message.middleware(LoggingMiddleware())

_CATEGORY_STILL_PENDING_NOTIFICATION_TIMEOUT = 3.0
_CATEGORY_HARD_TIMEOUT = 10.0


def parse_expense(text: str) -> tuple[str, Decimal] | None:
    match = re.search(r"(.+?)[,\s]+(\d+(?:[.,]\d{1,2})?)\s*р?$", text.strip(), re.I)

    if not match:
        return None

    title = match.group(1).strip()
    amount = Decimal(match.group(2).replace(",", "."))

    return title, amount


@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "Привет. Отправь расход текстом: кофе 150 или такси, 250.50"
    )


@dp.message(Command("list"))
async def list_expenses(
    message: Message,
    session_factory: async_sessionmaker,
    classification_queue: ClassificationQueue,
):
    if message.from_user is None:
        return

    async with session_factory() as session:
        service = ExpenseService(ExpenseRepository(session), classification_queue, session_factory)
        expenses = await service.get_by_telegram_id(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            limit=20,
            offset=0,
        )

    if not expenses:
        await message.answer("У тебя пока нет расходов.")
        return

    lines = [f"• {e.title} — {e.amount_kopeiki // 100} ₽" for e in expenses]
    await message.answer("\n".join(lines))


@dp.message(F.text)
async def add_expense(
    message: Message,
    session_factory: async_sessionmaker,
    classification_queue: ClassificationQueue,
):
    if message.from_user is None or message.text is None:
        return

    parsed = parse_expense(message.text)

    if parsed is None:
        await message.answer("Не понял расход. Пример: кофе 150 или такси, 250.50")
        return

    title, amount = parsed

    future: asyncio.Future[tuple[str, float]] = asyncio.get_running_loop().create_future()

    async def notify(category: str, confidence: float) -> None:
        future.set_result((category, confidence))

    async def notify_error(exc: Exception) -> None:
        future.set_exception(exc)

    async with session_factory() as session:
        service = ExpenseService(ExpenseRepository(session), classification_queue, session_factory)
        await service.create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            data=ExpenseCreate(title=title, amount_rubles=amount),
            notify=notify,
            notify_error=notify_error,
        )

    await message.answer(
        f"Сохранил: {title} — {amount} ₽\n"
        "Определяю категорию..."
    )

    done, pending = await asyncio.wait({future}, timeout=_CATEGORY_STILL_PENDING_NOTIFICATION_TIMEOUT)

    if pending:
        await message.answer("Всё ещё определяю категорию, нужно чуть больше времени...")
        done, pending = await asyncio.wait(pending, timeout=_CATEGORY_HARD_TIMEOUT)
        if pending:
            future.cancel()
            return

    try:
        category, confidence = future.result()
        if confidence < 0.6:
            # todo: ask user to confirm
            await message.answer("Не удалось узнать категорию")
        else:
            await message.answer(f"Категория: {category} ✓")
    except Exception:
        await message.answer("Не удалось определить категорию")
