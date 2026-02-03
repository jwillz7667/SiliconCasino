import pytest


@pytest.mark.asyncio
async def test_register_agent(client):
    response = await client.post(
        "/api/auth/register",
        json={"display_name": "Test Agent"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "agent_id" in data
    assert "api_key" in data
    assert data["api_key"].startswith("sk_")
    assert data["display_name"] == "Test Agent"


@pytest.mark.asyncio
async def test_register_agent_with_moltbook_id(client):
    response = await client.post(
        "/api/auth/register",
        json={"display_name": "Test Agent", "moltbook_id": "test-moltbook-123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "agent_id" in data


@pytest.mark.asyncio
async def test_register_duplicate_moltbook_id(client):
    await client.post(
        "/api/auth/register",
        json={"display_name": "Agent 1", "moltbook_id": "duplicate-id"},
    )

    response = await client.post(
        "/api/auth/register",
        json={"display_name": "Agent 2", "moltbook_id": "duplicate-id"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_get_token(client):
    reg_response = await client.post(
        "/api/auth/register",
        json={"display_name": "Test Agent"},
    )
    api_key = reg_response.json()["api_key"]

    response = await client.post(
        "/api/auth/token",
        json={"api_key": api_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_get_token_invalid_key(client):
    response = await client.post(
        "/api/auth/token",
        json={"api_key": "sk_invalid_key_12345"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client):
    reg_response = await client.post(
        "/api/auth/register",
        json={"display_name": "Test Agent"},
    )
    api_key = reg_response.json()["api_key"]

    token_response = await client.post(
        "/api/auth/token",
        json={"api_key": api_key},
    )
    token = token_response.json()["access_token"]

    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Test Agent"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_get_me_no_token(client):
    response = await client.get("/api/auth/me")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_me_invalid_token(client):
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid_token"},
    )
    assert response.status_code == 401
