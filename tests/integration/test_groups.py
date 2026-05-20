"""Integration tests for group and member management."""
import pytest
from httpx import AsyncClient

BASE = "/api/v1"


async def _register_and_login(client: AsyncClient, email: str, name: str = "User") -> str:
    await client.post(f"{BASE}/auth/register", json={
        "name": name, "email": email, "password": "Pass12345"
    })
    res = await client.post(f"{BASE}/auth/login", json={
        "email": email, "password": "Pass12345"
    })
    return res.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Create Group ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_group(client: AsyncClient):
    token = await _register_and_login(client, "creator@test.com", "Creator")
    res = await client.post(f"{BASE}/groups", json={
        "name": "Goa Trip", "default_currency": "INR"
    }, headers=_auth(token))
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Goa Trip"
    assert data["default_currency"] == "INR"
    assert data["status"] == "ACTIVE"
    assert data["members_count"] == 1
    assert len(data["members"]) == 1
    assert data["members"][0]["role"] == "ADMIN"


@pytest.mark.asyncio
async def test_create_group_unauthenticated(client: AsyncClient):
    res = await client.post(f"{BASE}/groups", json={"name": "X"})
    assert res.status_code in (401, 403)


# ── List Groups ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_groups_empty(client: AsyncClient):
    token = await _register_and_login(client, "nogroups@test.com")
    res = await client.get(f"{BASE}/groups", headers=_auth(token))
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_list_groups_returns_user_groups(client: AsyncClient):
    token = await _register_and_login(client, "lister@test.com")
    await client.post(f"{BASE}/groups", json={"name": "Trip 1"}, headers=_auth(token))
    await client.post(f"{BASE}/groups", json={"name": "Trip 2"}, headers=_auth(token))
    res = await client.get(f"{BASE}/groups", headers=_auth(token))
    assert res.status_code == 200
    assert len(res.json()) == 2


# ── Get Group Detail ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_group_detail(client: AsyncClient):
    token = await _register_and_login(client, "detail@test.com")
    grp = (await client.post(f"{BASE}/groups", json={"name": "Detail Group"},
                              headers=_auth(token))).json()
    res = await client.get(f"{BASE}/groups/{grp['id']}", headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["id"] == grp["id"]


@pytest.mark.asyncio
async def test_get_group_non_member_forbidden(client: AsyncClient):
    token_a = await _register_and_login(client, "owner_g@test.com")
    token_b = await _register_and_login(client, "stranger_g@test.com")
    grp = (await client.post(f"{BASE}/groups", json={"name": "Private"},
                              headers=_auth(token_a))).json()
    res = await client.get(f"{BASE}/groups/{grp['id']}", headers=_auth(token_b))
    assert res.status_code == 422  # UserNotInGroupError


# ── Archive Group ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_archive_group(client: AsyncClient):
    token = await _register_and_login(client, "archiver@test.com")
    grp = (await client.post(f"{BASE}/groups", json={"name": "Archive Me"},
                              headers=_auth(token))).json()
    res = await client.patch(f"{BASE}/groups/{grp['id']}/archive", headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["status"] == "ARCHIVED"


@pytest.mark.asyncio
async def test_non_admin_cannot_archive(client: AsyncClient):
    token_admin = await _register_and_login(client, "adm_arch@test.com", "Admin")
    token_member = await _register_and_login(client, "mem_arch@test.com", "Member")
    grp = (await client.post(f"{BASE}/groups", json={"name": "Group"},
                              headers=_auth(token_admin))).json()
    # Add member
    await client.post(f"{BASE}/groups/{grp['id']}/members",
                      json={"email": "mem_arch@test.com"}, headers=_auth(token_admin))
    res = await client.patch(f"{BASE}/groups/{grp['id']}/archive",
                             headers=_auth(token_member))
    assert res.status_code == 403


# ── Add Member ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_member(client: AsyncClient):
    token_admin = await _register_and_login(client, "adm_add@test.com", "Admin")
    await _register_and_login(client, "newmember@test.com", "New Member")
    grp = (await client.post(f"{BASE}/groups", json={"name": "Group"},
                              headers=_auth(token_admin))).json()
    res = await client.post(
        f"{BASE}/groups/{grp['id']}/members",
        json={"email": "newmember@test.com"},
        headers=_auth(token_admin),
    )
    assert res.status_code == 201
    assert res.json()["role"] == "MEMBER"


@pytest.mark.asyncio
async def test_add_nonexistent_user_returns_404(client: AsyncClient):
    token = await _register_and_login(client, "adm_404@test.com")
    grp = (await client.post(f"{BASE}/groups", json={"name": "G"},
                              headers=_auth(token))).json()
    res = await client.post(
        f"{BASE}/groups/{grp['id']}/members",
        json={"email": "ghost@nowhere.com"},
        headers=_auth(token),
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_add_duplicate_member_returns_409(client: AsyncClient):
    token_admin = await _register_and_login(client, "adm_dup@test.com", "Admin")
    await _register_and_login(client, "dup_mem@test.com", "Dup")
    grp = (await client.post(f"{BASE}/groups", json={"name": "G"},
                              headers=_auth(token_admin))).json()
    await client.post(f"{BASE}/groups/{grp['id']}/members",
                      json={"email": "dup_mem@test.com"}, headers=_auth(token_admin))
    res = await client.post(f"{BASE}/groups/{grp['id']}/members",
                            json={"email": "dup_mem@test.com"}, headers=_auth(token_admin))
    assert res.status_code == 409


# ── Remove Member ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_remove_member_with_no_balance(client: AsyncClient):
    token_admin = await _register_and_login(client, "adm_rem@test.com", "Admin")
    token_mem = await _register_and_login(client, "rem_mem@test.com", "ToRemove")
    grp = (await client.post(f"{BASE}/groups", json={"name": "G"},
                              headers=_auth(token_admin))).json()
    add_res = await client.post(
        f"{BASE}/groups/{grp['id']}/members",
        json={"email": "rem_mem@test.com"},
        headers=_auth(token_admin),
    )
    user_id = add_res.json()["user_id"]
    res = await client.delete(
        f"{BASE}/groups/{grp['id']}/members/{user_id}",
        headers=_auth(token_admin),
    )
    assert res.status_code == 204
