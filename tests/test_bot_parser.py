import os
from decimal import Decimal

import pytest

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASS", "test")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("BOT_TOKEN", "123456:test-token")
os.environ.setdefault("BOT_API_TOKEN", "test-bot-api-token")

from bot.handlers import (  # noqa: E402
    ADD_EXPENSE_BUTTON,
    EXAMPLES_BUTTON,
    HELP_BUTTON,
    MY_EXPENSES_BUTTON,
    format_amount,
    parse_expense,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("чай 190", ("чай", Decimal("190"))),
        ("кофе 150.99", ("кофе", Decimal("150.99"))),
        ("кофе 150,99", ("кофе", Decimal("150.99"))),
        ("такси, 250", ("такси", Decimal("250"))),
        ("такси, 250.50", ("такси", Decimal("250.50"))),
        ("такси, 250,50", ("такси", Decimal("250.50"))),
        ("кофе   150 р", ("кофе", Decimal("150"))),
        ("кофе 150 руб", ("кофе", Decimal("150"))),
        ("кофе 150 ₽", ("кофе", Decimal("150"))),
    ],
)
def test_parse_expense_valid_cases(text, expected):
    assert parse_expense(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "печенья 199,21321321",
        "кофе",
        "150",
        "кофе -100",
        "кофе 0",
        "кофе 1000000000",
        "кофе 150.999",
        "кофе 150,999",
        "",
        ADD_EXPENSE_BUTTON,
        EXAMPLES_BUTTON,
        HELP_BUTTON,
        MY_EXPENSES_BUTTON,
    ],
)
def test_parse_expense_invalid_cases(text):
    assert parse_expense(text) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("190.00"), "190"),
        (Decimal("150.50"), "150.50"),
        (Decimal("150.99"), "150.99"),
        ("190.00", "190"),
        (150, "150"),
    ],
)
def test_format_amount(value, expected):
    assert format_amount(value) == expected
