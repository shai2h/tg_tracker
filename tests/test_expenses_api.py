from decimal import Decimal


async def test_create_expense(client):
    payload = {
        "telegram_id": 123,
        "username": "test_user",
        "title": "coffee",
        "amount_rubles": "150.50",
    }

    response = await client.post("/expenses", json=payload)

    assert response.status_code == 201

    data = response.json()

    assert data["title"] == "coffee"
    assert Decimal(str(data["amount_rubles"])) == Decimal("150.50")
    assert data["category"] is None


async def test_update_expense(client):
    create_response = await client.post(
        "/expenses",
        json={
            "telegram_id": 124,
            "username": "test_user",
            "title": "coffee",
            "amount_rubles": "150.50",
        },
    )

    expense = create_response.json()

    update_response = await client.put(
        f"/expenses/{expense['id']}",
        json={
            "title": "taxi",
            "amount_rubles": "300.00",
        },
    )

    assert update_response.status_code == 200

    data = update_response.json()

    assert data["title"] == "taxi"
    assert Decimal(str(data["amount_rubles"])) == Decimal("300.00")


async def test_delete_expense(client):
    create_response = await client.post(
        "/expenses",
        json={
            "telegram_id": 125,
            "username": "test_user",
            "title": "coffee",
            "amount_rubles": "150.50",
        },
    )

    assert create_response.status_code == 201

    expense = create_response.json()
    print("CREATED:", expense)

    delete_response = await client.delete(f"/expenses/{expense['id']}")
    print("DELETE STATUS:", delete_response.status_code)
    print("DELETE BODY:", delete_response.text)

    assert delete_response.status_code == 204