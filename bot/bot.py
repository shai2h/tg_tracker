import asyncio
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv

from app import crud
from app.database.database import SessionLocal, create_tables


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "Привет! Я бот для учета расходов.\n\n"
        "Команды:\n"
        "/add coffee 300 - добавить расход\n"
        "/list - показать мои расходы"
    )


@dp.message(Command("add"))
async def add_expense(message: Message):
    if message.from_user is None:
        await message.answer("Не получилось определить пользователя")
        return

    user_id = message.from_user.id
    text = message.text or ""

    try:
        payload = text.split(maxsplit=1)[1]
        title, amount_text = payload.rsplit(maxsplit=1)
        amount = int(amount_text)
    except (IndexError, ValueError):
        await message.answer("Используй формат: /add coffee 300")
        return

    if amount <= 0:
        await message.answer("Сумма должна быть больше 0")
        return

    with SessionLocal() as db:
        expense = crud.create_expense(
            db=db,
            user_id=user_id,
            title=title,
            amount=amount,
        )

    await message.answer(f"Расход добавлен: {expense.title} - {expense.amount}")


@dp.message(Command("list"))
async def list_expenses(message: Message):
    if message.from_user is None:
        await message.answer("Не получилось определить пользователя")
        return

    user_id = message.from_user.id

    with SessionLocal() as db:
        expenses = crud.get_user_expenses(db=db, user_id=user_id)

    if not expenses:
        await message.answer("У тебя пока нет расходов")
        return

    lines = [
        f"{index}. {expense.title} - {expense.amount}"
        for index, expense in enumerate(expenses, start=1)
    ]

    await message.answer("\n".join(lines))


async def main():
    create_tables()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
