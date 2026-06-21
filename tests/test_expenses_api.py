from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.expenses.models import ExpenseOrm, UserOrm


BOT_API_TOKEN = "test-bot-api-token"


def bot_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {BOT_API_TOKEN}"}


def expense_payload(
    *,
    title: str = "coffee",
    amount_rubles: str = "150.50",
) -> dict[str, str]:
    return {
        "title": title,
        "amount_rubles": amount_rubles,
    }


def bot_expense_payload(
    *,
    telegram_id: int = 1,
    username: str | None = "user",
    title: str = "coffee",
    amount_rubles: str = "150.50",
) -> dict[str, str | int | None]:
    return {
        "telegram_id": telegram_id,
        "username": username,
        **expense_payload(title=title, amount_rubles=amount_rubles),
    }


async def create_user(
    db_session_factory,
    *,
    telegram_id: int = 1,
    username: str | None = "user",
):
    async with db_session_factory() as session:
        user = UserOrm(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.commit()
        await session.refresh(user)

        return user


async def create_expense_for_user(client, db_session_factory, *, title: str = "coffee"):
    user = await create_user(db_session_factory)

    response = await client.post(
        "/expenses",
        params={"user_id": str(user.id)},
        json=expense_payload(title=title),
    )

    return response, user


async def test_create_and_read_expense(client, db_session_factory):
    response, user = await create_expense_for_user(client, db_session_factory)

    assert response.status_code == 201
    created = response.json()
    assert created["user_id"] == str(user.id)
    assert created["title"] == "coffee"
    assert Decimal(str(created["amount_rubles"])) == Decimal("150.50")
    assert created["category"] is None

    list_response = await client.get(f"/expenses/user/{created['user_id']}")
    assert list_response.status_code == 200
    expenses = list_response.json()
    assert len(expenses) == 1
    assert expenses[0]["id"] == created["id"]
    assert expenses[0]["title"] == "coffee"


async def test_update_expense(client, db_session_factory):
    create_response, user = await create_expense_for_user(client, db_session_factory)
    assert create_response.status_code == 201
    expense = create_response.json()

    update_response = await client.put(
        f"/expenses/{expense['id']}",
        json={"title": "taxi", "amount_rubles": "300.00"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["title"] == "taxi"
    assert Decimal(str(updated["amount_rubles"])) == Decimal("300.00")

    list_response = await client.get(f"/expenses/user/{user.id}")
    expenses = list_response.json()
    assert expenses[0]["title"] == "taxi"


async def test_delete_expense(client, db_session_factory):
    create_response, user = await create_expense_for_user(client, db_session_factory)
    assert create_response.status_code == 201
    expense = create_response.json()

    delete_response = await client.delete(f"/expenses/{expense['id']}")
    assert delete_response.status_code == 204

    list_response = await client.get(f"/expenses/user/{user.id}")
    assert list_response.json() == []


async def test_update_nonexistent_expense(client):
    response = await client.put(
        "/expenses/00000000-0000-0000-0000-000000000000",
        json={"title": "ghost", "amount_rubles": "100.00"},
    )
    assert response.status_code == 404


async def test_delete_nonexistent_expense(client):
    response = await client.delete("/expenses/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_same_user_multiple_expenses(client, db_session_factory):
    user = await create_user(db_session_factory, telegram_id=4)

    for title in ("coffee", "taxi", "lunch", "dinner"):
        response = await client.post(
            "/expenses",
            params={"user_id": str(user.id)},
            json=expense_payload(title=title, amount_rubles="100.00"),
        )
        assert response.status_code == 201

    list_response = await client.get(f"/expenses/user/{user.id}")
    assert len(list_response.json()) == 4


async def test_bot_create_expense_without_authorization_returns_401(client):
    response = await client.post("/bot/expenses", json=bot_expense_payload())

    assert response.status_code == 401


async def test_bot_create_expense_with_invalid_authorization_returns_401(client):
    response = await client.post(
        "/bot/expenses",
        json=bot_expense_payload(),
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401


async def test_bot_create_expense_with_valid_authorization_creates_user_and_expense(
    client,
    db_session_factory,
):
    response = await client.post(
        "/bot/expenses",
        json=bot_expense_payload(telegram_id=42, username="alice"),
        headers=bot_headers(),
    )

    assert response.status_code == 201
    created = response.json()
    assert created["title"] == "coffee"
    assert created["amount_kopeiki"] == 15050
    assert Decimal(str(created["amount_rubles"])) == Decimal("150.5")

    async with db_session_factory() as session:
        user_result = await session.execute(
            select(UserOrm).where(UserOrm.telegram_id == 42)
        )
        user = user_result.scalar_one()

        expense_result = await session.execute(
            select(ExpenseOrm).where(ExpenseOrm.id == UUID(created["id"]))
        )
        expense = expense_result.scalar_one()

    assert user.username == "alice"
    assert str(user.id) == created["user_id"]
    assert expense.user_id == user.id
