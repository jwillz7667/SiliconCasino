import pytest


async def create_authenticated_agent(client, name: str) -> tuple[str, str]:
    """Helper to create and authenticate an agent."""
    reg_response = await client.post(
        "/api/auth/register",
        json={"display_name": name},
    )
    agent_id = reg_response.json()["agent_id"]
    api_key = reg_response.json()["api_key"]

    token_response = await client.post(
        "/api/auth/token",
        json={"api_key": api_key},
    )
    token = token_response.json()["access_token"]

    return agent_id, token


@pytest.mark.asyncio
async def test_create_table(client):
    _, token = await create_authenticated_agent(client, "Test Agent")

    response = await client.post(
        "/api/poker/tables",
        json={
            "name": "Test Table",
            "small_blind": 5,
            "big_blind": 10,
            "min_buy_in": 100,
            "max_buy_in": 1000,
            "max_players": 6,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Table"
    assert data["small_blind"] == 5
    assert data["big_blind"] == 10


@pytest.mark.asyncio
async def test_list_tables(client):
    _, token = await create_authenticated_agent(client, "Test Agent")

    await client.post(
        "/api/poker/tables",
        json={
            "name": "Table 1",
            "small_blind": 5,
            "big_blind": 10,
            "min_buy_in": 100,
            "max_buy_in": 1000,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        "/api/poker/tables",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["tables"]) >= 1


@pytest.mark.asyncio
async def test_join_table(client):
    _, token = await create_authenticated_agent(client, "Test Agent")

    table_response = await client.post(
        "/api/poker/tables",
        json={
            "name": "Test Table",
            "small_blind": 5,
            "big_blind": 10,
            "min_buy_in": 100,
            "max_buy_in": 1000,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    table_id = table_response.json()["id"]

    response = await client.post(
        f"/api/poker/tables/{table_id}/join",
        json={"seat_number": 0, "buy_in": 500},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["seat_number"] == 0
    assert data["stack"] == 500


@pytest.mark.asyncio
async def test_join_table_invalid_buy_in(client):
    _, token = await create_authenticated_agent(client, "Test Agent")

    table_response = await client.post(
        "/api/poker/tables",
        json={
            "name": "Test Table",
            "small_blind": 5,
            "big_blind": 10,
            "min_buy_in": 100,
            "max_buy_in": 1000,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    table_id = table_response.json()["id"]

    response = await client.post(
        f"/api/poker/tables/{table_id}/join",
        json={"seat_number": 0, "buy_in": 50},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_leave_table(client):
    _, token = await create_authenticated_agent(client, "Test Agent")

    table_response = await client.post(
        "/api/poker/tables",
        json={
            "name": "Test Table",
            "small_blind": 5,
            "big_blind": 10,
            "min_buy_in": 100,
            "max_buy_in": 1000,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    table_id = table_response.json()["id"]

    await client.post(
        f"/api/poker/tables/{table_id}/join",
        json={"seat_number": 0, "buy_in": 500},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.post(
        f"/api/poker/tables/{table_id}/leave",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["chips_returned"] == 500


@pytest.mark.asyncio
async def test_get_table_state(client):
    _, token = await create_authenticated_agent(client, "Test Agent")

    table_response = await client.post(
        "/api/poker/tables",
        json={
            "name": "Test Table",
            "small_blind": 5,
            "big_blind": 10,
            "min_buy_in": 100,
            "max_buy_in": 1000,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    table_id = table_response.json()["id"]

    response = await client.get(
        f"/api/poker/tables/{table_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "table" in data
    assert data["table"]["name"] == "Test Table"


@pytest.mark.asyncio
async def test_two_players_can_play(client):
    _, token1 = await create_authenticated_agent(client, "Agent 1")
    _, token2 = await create_authenticated_agent(client, "Agent 2")

    table_response = await client.post(
        "/api/poker/tables",
        json={
            "name": "Test Table",
            "small_blind": 5,
            "big_blind": 10,
            "min_buy_in": 100,
            "max_buy_in": 1000,
        },
        headers={"Authorization": f"Bearer {token1}"},
    )
    table_id = table_response.json()["id"]

    await client.post(
        f"/api/poker/tables/{table_id}/join",
        json={"seat_number": 0, "buy_in": 500},
        headers={"Authorization": f"Bearer {token1}"},
    )

    await client.post(
        f"/api/poker/tables/{table_id}/join",
        json={"seat_number": 1, "buy_in": 500},
        headers={"Authorization": f"Bearer {token2}"},
    )

    state_response = await client.get(
        f"/api/poker/tables/{table_id}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    state = state_response.json()

    assert state["hand"] is not None
    assert state["hand"]["phase"] == "PREFLOP"
