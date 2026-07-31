from decimal import Decimal

import pytest

from app.bot.handlers import parse_expense


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
    ],
)
def test_parse_expense_valid_cases(text, expected):
    assert parse_expense(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "кофе",
        "150",
        "кофе -100",
        "кофе 150.999",
        "",
    ],
)
def test_parse_expense_invalid_cases(text):
    assert parse_expense(text) is None
