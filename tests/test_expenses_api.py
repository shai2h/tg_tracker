from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select

from app.expenses.models import ExpenseOrm, UserOrm


BOT_API_TOKEN = "test-bot-api-token"


def bot_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {BOT_API_TOKEN}"}


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
        "title": title,
        "amount_rubles": amount_rubles,
    }


async def create_expense_from_bot(
    client,
    *,
    telegram_id: int = 1,
    username: str | None = "user",
    title: str = "coffee",
    amount_rubles: str = "150.50",
):
    response = await client.post(
        "/bot/expenses",
        json=bot_expense_payload(
            telegram_id=telegram_id,
            username=username,
            title=title,
            amount_rubles=amount_rubles,
        ),
        headers=bot_headers(),
    )

    assert response.status_code == 201
    return response


async def get_expenses_for_bot(
    client,
    *,
    telegram_id: int = 1,
    limit: int = 10,
    offset: int = 0,
    headers: dict[str, str] | None = None,
):
    return await client.get(
        "/bot/expenses",
        params={
            "telegram_id": telegram_id,
            "limit": limit,
            "offset": offset,
        },
        headers=headers,
    )


async def test_public_create_expense_endpoint_is_removed(client):
    response = await client.post(
        "/expenses",
        json={"title": "coffee", "amount_rubles": "150.50"},
    )

    assert response.status_code in {404, 405}


async def test_create_and_read_expense(client):
    response = await create_expense_from_bot(client)

    created = response.json()
    assert created["title"] == "coffee"
    assert Decimal(str(created["amount_rubles"])) == Decimal("150.50")
    # missing asserts:
    # telegram_id is returned
    assert created["category"] is None

    list_response = await client.get(f"/expenses/user/{created['user_id']}")
    assert list_response.status_code == 200
    expenses = list_response.json()
    assert len(expenses) == 1
    assert expenses[0]["id"] == created["id"]
    assert expenses[0]["title"] == "coffee"

# missing test: if we send "amount_rubles": 150,50 - it should throw (400)
# missing understanding: what is username???
# what is user_id ans how it corelates with telegram_id.

async def test_update_expense(client):
    create_response = await create_expense_from_bot(client)
    expense = create_response.json()

    update_response = await client.put(
        f"/expenses/{expense['id']}",
        json={"title": "taxi", "amount_rubles": "300.00"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["title"] == "taxi"
    assert Decimal(str(updated["amount_rubles"])) == Decimal("300.00")

    list_response = await client.get(f"/expenses/user/{expense['user_id']}")
    expenses = list_response.json()
    assert expenses[0]["title"] == "taxi"


async def test_delete_expense(client):
    create_response = await create_expense_from_bot(client)
    expense = create_response.json()

    delete_response = await client.delete(f"/expenses/{expense['id']}")
    assert delete_response.status_code == 204

    list_response = await client.get(f"/expenses/user/{expense['user_id']}")
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


async def test_same_user_multiple_expenses(client):
    first_response = await create_expense_from_bot(
        client,
        telegram_id=4,
        title="coffee",
        amount_rubles="100.00",
    )
    user_id = first_response.json()["user_id"]

    for title in ("taxi", "lunch", "dinner"):
        response = await create_expense_from_bot(
            client,
            telegram_id=4,
            title=title,
            amount_rubles="100.00",
        )
        assert response.json()["user_id"] == user_id

    list_response = await client.get(f"/expenses/user/{user_id}")
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


async def test_bot_get_expenses_without_authorization_returns_401(client):
    response = await get_expenses_for_bot(client)

    assert response.status_code == 401


async def test_bot_get_expenses_with_invalid_authorization_returns_401(client):
    response = await get_expenses_for_bot(
        client,
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401


async def test_bot_get_expenses_for_unknown_telegram_id_returns_empty_list(client):
    response = await get_expenses_for_bot(
        client,
        telegram_id=404,
        headers=bot_headers(),
    )

    assert response.status_code == 200
    assert response.json() == []


async def test_bot_get_expenses_returns_current_telegram_user_expenses_only(client):
    coffee_response = await create_expense_from_bot(
        client,
        telegram_id=100,
        title="coffee",
        amount_rubles="150.00",
    )
    taxi_response = await create_expense_from_bot(
        client,
        telegram_id=100,
        title="taxi",
        amount_rubles="250.50",
    )
    await create_expense_from_bot(
        client,
        telegram_id=200,
        title="lunch",
        amount_rubles="500.00",
    )

    response = await get_expenses_for_bot(
        client,
        telegram_id=100,
        headers=bot_headers(),
    )

    assert response.status_code == 200
    expenses = response.json()
    assert len(expenses) == 2
    assert {expense["id"] for expense in expenses} == {
        coffee_response.json()["id"],
        taxi_response.json()["id"],
    }
    assert {expense["title"] for expense in expenses} == {"coffee", "taxi"}


async def test_bot_get_expenses_supports_limit_and_offset(client):
    first_response = await create_expense_from_bot(
        client,
        telegram_id=300,
        title="coffee",
        amount_rubles="100.00",
    )
    second_response = await create_expense_from_bot(
        client,
        telegram_id=300,
        title="taxi",
        amount_rubles="200.00",
    )

    first_page_response = await get_expenses_for_bot(
        client,
        telegram_id=300,
        limit=1,
        offset=0,
        headers=bot_headers(),
    )
    second_page_response = await get_expenses_for_bot(
        client,
        telegram_id=300,
        limit=1,
        offset=1,
        headers=bot_headers(),
    )

    assert first_page_response.status_code == 200
    assert second_page_response.status_code == 200

    first_page = first_page_response.json()
    second_page = second_page_response.json()
    assert len(first_page) == 1
    assert len(second_page) == 1
    assert first_page[0]["id"] != second_page[0]["id"]
    assert {first_page[0]["id"], second_page[0]["id"]} == {
        first_response.json()["id"],
        second_response.json()["id"],
    }


async def test_bot_create_expense_with_valid_authorization_creates_user_and_expense(
    client,
    db_session_factory,
):
    response = await create_expense_from_bot(
        client,
        telegram_id=42,
        username="alice",
    )

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


async def test_bot_create_expense_reuses_existing_user_for_same_telegram_id(
    client,
    db_session_factory,
):
    first_response = await create_expense_from_bot(
        client,
        telegram_id=77,
        username="alice",
        title="coffee",
    )
    second_response = await create_expense_from_bot(
        client,
        telegram_id=77,
        username="alice_new",
        title="taxi",
    )

    first = first_response.json()
    second = second_response.json()
    assert second["user_id"] == first["user_id"]

    async with db_session_factory() as session:
        users_count = await session.scalar(
            select(func.count()).select_from(UserOrm).where(UserOrm.telegram_id == 77)
        )
        expenses_count = await session.scalar(
            select(func.count())
            .select_from(ExpenseOrm)
            .where(ExpenseOrm.user_id == UUID(first["user_id"]))
        )
        user = await session.scalar(select(UserOrm).where(UserOrm.telegram_id == 77))

    assert users_count == 1
    assert expenses_count == 2
    assert user is not None
    assert user.username == "alice_new"
