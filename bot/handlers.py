import re
from decimal import Decimal

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from app.core.config import get_settings

settings = get_settings()

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()


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


@dp.message(F.text)
async def add_expense(message: Message):
    if message.from_user is None or message.text is None:
        return

    parsed = parse_expense(message.text)

    if parsed is None:
        await message.answer("Не понял расход. Пример: кофе 150 или такси, 250.50")
        return

    title, amount = parsed

    payload = {
        "telegram_id": message.from_user.id,
        "username": message.from_user.username,
        "title": title,
        "amount_rubles": str(amount),
    }

    async with httpx.AsyncClient(base_url=settings.API_BASE_URL) as client:
        response = await client.post("/expenses", json=payload)

    if response.status_code != 201:
        await message.answer("Не смог сохранить расход. Попробуй позже.")
        return

    await message.answer(f"Сохранил: {title} — {amount} ₽")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())