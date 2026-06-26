import re
from decimal import Decimal

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from app.core.config import get_settings

settings = get_settings()

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()


ADD_EXPENSE_BUTTON = "➕ Добавить расход"
EXAMPLES_BUTTON = "💡 Примеры"
HELP_BUTTON = "ℹ️ Помощь"
MY_EXPENSES_BUTTON = "📋 Мои расходы"


main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=ADD_EXPENSE_BUTTON)],
        [KeyboardButton(text=MY_EXPENSES_BUTTON)],
        [
            KeyboardButton(text=EXAMPLES_BUTTON),
            KeyboardButton(text=HELP_BUTTON),
        ],
    ],
    resize_keyboard=True,
    input_field_placeholder="Например: кофе 150",
)


def parse_expense(text: str) -> tuple[str, Decimal] | None:
    stripped_text = text.strip()

    if not stripped_text:
        return None

    amount_pattern = r"(?P<amount>\d+(?:[.,]\d{1,2})?)\s*(?:руб|р|₽)?"
    patterns = (
        rf"(?P<title>.+?),\s+{amount_pattern}",
        rf"(?P<title>.+?)\s+{amount_pattern}",
    )

    match = None

    for pattern in patterns:
        match = re.fullmatch(pattern, stripped_text, re.I)

        if match:
            break

    if not match:
        return None

    title = " ".join(match.group("title").split())

    if not title or len(title) > 100:
        return None

    amount = Decimal(match.group("amount").replace(",", "."))

    if amount <= 0 or amount > Decimal("1000000"):
        return None

    return title, amount


def format_amount(value: str | int | Decimal) -> str:
    amount = Decimal(str(value))

    if amount == amount.to_integral():
        return str(amount.quantize(Decimal("1")))

    return str(amount.quantize(Decimal("0.01")))


@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "Привет. Я помогу вести расходы.\n\n"
        "Отправь расход текстом:\n"
        "кофе 150\n"
        "такси, 250.50\n"
        "продукты 2500",
        reply_markup=main_keyboard,
    )


@dp.message(F.text == ADD_EXPENSE_BUTTON)
async def add_expense_button(message: Message):
    await message.answer(
        "Отправь расход одним сообщением:\n\n"
        "кофе 150\n"
        "такси, 250.50\n"
        "продукты 2500"
    )


@dp.message(F.text == EXAMPLES_BUTTON)
async def examples_button(message: Message):
    await message.answer(
        "Примеры:\n\n"
        "кофе 150\n"
        "такси, 250.50\n"
        "обед 420\n"
        "продукты 2500\n"
        "аптека 730.90"
    )


@dp.message(F.text == HELP_BUTTON)
async def help_button(message: Message):
    await message.answer(
        "Как пользоваться:\n\n"
        "1. Напиши название расхода.\n"
        "2. Через пробел или запятую укажи сумму.\n\n"
        "Пример:\n"
        "кофе 150\n\n"
        "Я сохраню расход и привяжу его к твоему Telegram ID."
    )


@dp.message(F.text == MY_EXPENSES_BUTTON)
async def my_expenses_button(message: Message):
    if message.from_user is None:
        return

    try:
        async with httpx.AsyncClient(
            base_url=settings.API_BASE_URL,
            timeout=10.0,
        ) as client:
            response = await client.get(
                "/bot/expenses",
                params={
                    "telegram_id": message.from_user.id,
                    "limit": 10,
                    "offset": 0,
                },
                headers={"Authorization": f"Bearer {settings.BOT_API_TOKEN}"},
            )
    except httpx.HTTPError:
        await message.answer("Не смог получить расходы. Попробуй позже.")
        return

    if response.status_code != 200:
        await message.answer("Не смог получить расходы. Попробуй позже.")
        return

    expenses = response.json()

    if not expenses:
        await message.answer("Расходов пока нет. Добавь первый: кофе 150")
        return

    lines = ["Последние расходы:"]

    for index, expense in enumerate(expenses, start=1):
        amount = format_amount(expense["amount_rubles"])
        line = f'{index}. {expense["title"]} — {amount} ₽'

        if expense.get("category") is not None:
            line = f'{line} ({expense["category"]})'

        lines.append(line)

    await message.answer("\n\n".join([lines[0], "\n".join(lines[1:])]))


@dp.message(F.text)
async def add_expense(message: Message):
    if message.from_user is None or message.text is None:
        return

    parsed = parse_expense(message.text)

    if parsed is None:
        await message.answer(
            "Не понял расход.\n\n"
            "Напиши так:\n"
            "кофе 150\n"
            "такси, 250.50\n\n"
            "Сумма должна быть больше 0 и максимум с двумя знаками после точки или запятой."
        )
        return

    title, amount = parsed

    payload = {
        "telegram_id": message.from_user.id,
        "username": message.from_user.username,
        "title": title,
        "amount_rubles": str(amount),
    }

    try:
        async with httpx.AsyncClient(
            base_url=settings.API_BASE_URL,
            timeout=10.0,
        ) as client:
            response = await client.post(
                "/bot/expenses",
                json=payload,
                headers={"Authorization": f"Bearer {settings.BOT_API_TOKEN}"},
            )
    except httpx.HTTPError:
        await message.answer("Не смог подключиться к API. Попробуй позже.")
        return

    if response.status_code != 201:
        await message.answer("Не смог сохранить расход. Попробуй позже.")
        return

    await message.answer(
        f"Сохранил расход:\n{title} — {amount} ₽",
        reply_markup=main_keyboard,
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
