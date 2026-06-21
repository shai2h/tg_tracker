from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select

from app.expenses.models import ExpenseOrm, UserOrm
from app.expenses.repository import ExpenseRepository
from app.expenses.schemas import ExpenseCreate
from app.expenses.service import ExpenseService


async def create_expense(
    db_session_factory,
    *,
    telegram_id: int = 1,
    username: str | None = "user",
    title: str = "coffee",
    amount_rubles: str = "150.50",
) -> ExpenseOrm:
    async with db_session_factory() as session:
        service = ExpenseService(ExpenseRepository(session))
        expense = await service.create(
            telegram_id=telegram_id,
            username=username,
            data=ExpenseCreate(title=title, amount_rubles=Decimal(amount_rubles)),
        )
        await session.commit()
        await session.refresh(expense)
        return expense


async def test_create_and_read_expense(client, db_session_factory):
    expense = await create_expense(db_session_factory)

    response = await client.get(f"/expenses/user/{expense.user_id}")
    assert response.status_code == 200
    expenses = response.json()
    assert len(expenses) == 1
    assert expenses[0]["id"] == str(expense.id)
    assert expenses[0]["title"] == "coffee"
    assert Decimal(str(expenses[0]["amount_rubles"])) == Decimal("150.50")
    assert expenses[0]["category"] is None


async def test_create_expense_amount_stored_correctly(db_session_factory):
    expense = await create_expense(db_session_factory, amount_rubles="150.50")
    assert expense.amount_kopeiki == 15050


async def test_update_expense(client, db_session_factory):
    expense = await create_expense(db_session_factory)

    response = await client.put(
        f"/expenses/{expense.id}",
        json={"title": "taxi", "amount_rubles": "300.00"},
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["title"] == "taxi"
    assert Decimal(str(updated["amount_rubles"])) == Decimal("300.00")

    list_response = await client.get(f"/expenses/user/{expense.user_id}")
    assert list_response.json()[0]["title"] == "taxi"


async def test_delete_expense(client, db_session_factory):
    expense = await create_expense(db_session_factory)

    response = await client.delete(f"/expenses/{expense.id}")
    assert response.status_code == 204

    list_response = await client.get(f"/expenses/user/{expense.user_id}")
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
    first = await create_expense(db_session_factory, telegram_id=4, title="coffee")

    for title in ("taxi", "lunch", "dinner"):
        expense = await create_expense(db_session_factory, telegram_id=4, title=title)
        assert expense.user_id == first.user_id

    response = await client.get(f"/expenses/user/{first.user_id}")
    assert len(response.json()) == 4


async def test_same_telegram_id_same_user_id(db_session_factory):
    e1 = await create_expense(db_session_factory, telegram_id=42, title="a")
    e2 = await create_expense(db_session_factory, telegram_id=42, title="b")
    assert e1.user_id == e2.user_id


async def test_different_telegram_id_different_user_id(db_session_factory):
    e1 = await create_expense(db_session_factory, telegram_id=1, title="a")
    e2 = await create_expense(db_session_factory, telegram_id=2, title="b")
    assert e1.user_id != e2.user_id


async def test_creates_user_and_expense_in_db(db_session_factory):
    expense = await create_expense(db_session_factory, telegram_id=42, username="alice")

    async with db_session_factory() as session:
        user = await session.scalar(select(UserOrm).where(UserOrm.telegram_id == 42))
        db_expense = await session.scalar(select(ExpenseOrm).where(ExpenseOrm.id == expense.id))

    assert user is not None
    assert user.username == "alice"
    assert db_expense is not None
    assert db_expense.user_id == user.id


async def test_reuses_existing_user_for_same_telegram_id(db_session_factory):
    await create_expense(db_session_factory, telegram_id=77, username="alice", title="coffee")
    await create_expense(db_session_factory, telegram_id=77, username="alice_new", title="taxi")

    async with db_session_factory() as session:
        users_count = await session.scalar(
            select(func.count()).select_from(UserOrm).where(UserOrm.telegram_id == 77)
        )
        user = await session.scalar(select(UserOrm).where(UserOrm.telegram_id == 77))
        expenses_count = await session.scalar(
            select(func.count()).select_from(ExpenseOrm).where(ExpenseOrm.user_id == user.id)
        )

    assert users_count == 1
    assert expenses_count == 2
    assert user.username == "alice_new"


async def test_expenses_isolated_between_users(client, db_session_factory):
    e1 = await create_expense(db_session_factory, telegram_id=10, title="coffee")
    await create_expense(db_session_factory, telegram_id=20, title="taxi")

    response = await client.get(f"/expenses/user/{e1.user_id}")
    expenses = response.json()
    assert len(expenses) == 1
    assert expenses[0]["title"] == "coffee"
