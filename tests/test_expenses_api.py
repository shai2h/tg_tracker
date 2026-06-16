from decimal import Decimal


async def test_create_and_read_expense(client):
    response = await client.post(
        "/expenses",
        json={
            "telegram_id": 1,
            "username": "user",
            "title": "coffee",
            "amount_rubles": "150.50",
        },
    )

    assert response.status_code == 201
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
    create_response = await client.post(
        "/expenses",
        json={
            "telegram_id": 1,
            "username": "user",
            "title": "coffee",
            "amount_rubles": "150.50",
        },
    )
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

    list_response = await client.get(f"/expenses/user/{expense['user_id']}")
    expenses = list_response.json()
    assert expenses[0]["title"] == "taxi"


async def test_delete_expense(client):
    create_response = await client.post(
        "/expenses",
        json={
            "telegram_id": 1,
            "username": "user",
            "title": "coffee",
            "amount_rubles": "150.50",
        },
    )
    assert create_response.status_code == 201
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
    for title in ("coffee", "taxi", "lunch"):
        await client.post(
            "/expenses",
            json={"telegram_id": 4, "username": "user", "title": title, "amount_rubles": "100.00"},
        )

    first_response = await client.post(
        "/expenses",
        json={"telegram_id": 4, "username": "user", "title": "dinner", "amount_rubles": "100.00"},
    )
    user_id = first_response.json()["user_id"]

    list_response = await client.get(f"/expenses/user/{user_id}")
    assert len(list_response.json()) == 4
