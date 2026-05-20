import pytest
from httpx import AsyncClient

BASE = "/api/v1"


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    res = await client.post(f"{BASE}/auth/register", json={
        "name": "Mandeep",
        "email": "mandeep@example.com",
        "password": "StrongPass123",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "mandeep@example.com"
    assert "id" in data
    assert "password_hash" not in data  # never leak hash


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {"name": "A", "email": "dup@example.com", "password": "Pass1234!"}
    await client.post(f"{BASE}/auth/register", json=payload)
    res = await client.post(f"{BASE}/auth/register", json=payload)
    assert res.status_code == 409
    assert res.json()["error"] == "USER_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post(f"{BASE}/auth/register", json={
        "name": "Login User",
        "email": "loginuser@example.com",
        "password": "MyPassword99",
    })
    res = await client.post(f"{BASE}/auth/login", json={
        "email": "loginuser@example.com",
        "password": "MyPassword99",
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(f"{BASE}/auth/register", json={
        "name": "User", "email": "fail@example.com", "password": "CorrectPass1",
    })
    res = await client.post(f"{BASE}/auth/login", json={
        "email": "fail@example.com", "password": "WrongPass",
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient):
    await client.post(f"{BASE}/auth/register", json={
        "name": "Me User", "email": "me@example.com", "password": "Pass12345",
    })
    login = await client.post(f"{BASE}/auth/login", json={
        "email": "me@example.com", "password": "Pass12345",
    })
    token = login.json()["access_token"]

    res = await client.get(f"{BASE}/users/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_get_me_no_token(client: AsyncClient):
    res = await client.get(f"{BASE}/users/me")
    assert res.status_code in (401, 403)  # HTTPBearer raises 403; custom handler may remap to 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    await client.post(f"{BASE}/auth/register", json={
        "name": "Refresh", "email": "refresh@example.com", "password": "Pass12345",
    })
    login = await client.post(f"{BASE}/auth/login", json={
        "email": "refresh@example.com", "password": "Pass12345",
    })
    refresh_token = login.json()["refresh_token"]

    res = await client.post(f"{BASE}/auth/refresh", json={"refresh_token": refresh_token})
    assert res.status_code == 200
    assert "access_token" in res.json()
