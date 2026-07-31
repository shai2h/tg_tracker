import asyncio
import re
from decimal import Decimal

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from app.bot.middleware import ServiceMiddleware
from app.expenses.schemas import ExpenseCreate
from app.expenses.service import ExpenseService

dp = Dispatcher(storage=MemoryStorage())
dp.message.middleware(ServiceMiddleware())


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
async def list_expenses(message: Message, service: ExpenseService):
    if message.from_user is None:
        return

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
async def add_expense(message: Message, service: ExpenseService):
    if message.from_user is None or message.text is None:
        return

    parsed = parse_expense(message.text)

    if parsed is None:
        await message.answer("Не понял расход. Пример: кофе 150 или такси, 250.50")
        return

    title, amount = parsed
    category_future: asyncio.Future[str] = asyncio.get_running_loop().create_future()

    await service.create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        data=ExpenseCreate(title=title, amount_rubles=amount),
        category_future=category_future,
    )

    await message.answer(
        f"Сохранил: {title} — {amount} ₽\n"
        "Определяю категорию..."
    )
