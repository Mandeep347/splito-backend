"""Integration tests for expense creation and management."""
import pytest
from httpx import AsyncClient

BASE = "/api/v1"


async def _register_and_login(client: AsyncClient, email: str, name: str = "User") -> tuple[str, str]:
    """Returns (token, user_id)."""
    reg = await client.post(f"{BASE}/auth/register", json={
        "name": name, "email": email, "password": "Pass12345"
    })
    user_id = reg.json()["id"]
    res = await client.post(f"{BASE}/auth/login", json={
        "email": email, "password": "Pass12345"
    })
    return res.json()["access_token"], user_id


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _setup_group(client, admin_email, member_emails=None):
    """Create a group with admin + optional members. Returns (admin_token, group_id, user_ids)."""
    token_admin, admin_id = await _register_and_login(client, admin_email, "Admin")
    grp = (await client.post(f"{BASE}/groups", json={"name": "Test Group", "default_currency": "INR"},
                              headers=_auth(token_admin))).json()
    group_id = grp["id"]
    user_ids = {admin_email: admin_id}

    for email in (member_emails or []):
        token_m, uid = await _register_and_login(client, email, email.split("@")[0])
        user_ids[email] = uid
        await client.post(f"{BASE}/groups/{group_id}/members",
                          json={"email": email}, headers=_auth(token_admin))

    return token_admin, group_id, user_ids


# ── EQUAL split ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_expense_equal_split(client: AsyncClient):
    token, gid, uids = await _setup_group(
        client, "eq_admin@t.com", ["eq_u2@t.com", "eq_u3@t.com"]
    )
    res = await client.post(f"{BASE}/groups/{gid}/expenses", json={
        "title": "Dinner",
        "total_amount": "3000",
        "currency": "INR",
        "paid_by_user_id": uids["eq_admin@t.com"],
        "split_type": "EQUAL",
        "participants_equal": [
            {"user_id": uids["eq_admin@t.com"]},
            {"user_id": uids["eq_u2@t.com"]},
            {"user_id": uids["eq_u3@t.com"]},
        ],
    }, headers=_auth(token))
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Dinner"
    assert data["split_type"] == "EQUAL"
    assert len(data["participants"]) == 3
    amounts = sorted([p["owed_amount"] for p in data["participants"]])
    # 3000 / 3 = 1000 each
    assert all(float(a) == 1000.0 for a in amounts)


@pytest.mark.asyncio
async def test_create_expense_exact_split(client: AsyncClient):
    token, gid, uids = await _setup_group(
        client, "ex_admin@t.com", ["ex_u2@t.com", "ex_u3@t.com"]
    )
    res = await client.post(f"{BASE}/groups/{gid}/expenses", json={
        "title": "Hotel",
        "total_amount": "3000",
        "currency": "INR",
        "paid_by_user_id": uids["ex_admin@t.com"],
        "split_type": "EXACT",
        "participants_exact": [
            {"user_id": uids["ex_admin@t.com"], "owed_amount": "1000"},
            {"user_id": uids["ex_u2@t.com"], "owed_amount": "500"},
            {"user_id": uids["ex_u3@t.com"], "owed_amount": "1500"},
        ],
    }, headers=_auth(token))
    assert res.status_code == 201
    amounts = {p["user_id"]: float(p["owed_amount"]) for p in res.json()["participants"]}
    assert amounts[uids["ex_u3@t.com"]] == 1500.0


@pytest.mark.asyncio
async def test_create_expense_percentage_split(client: AsyncClient):
    token, gid, uids = await _setup_group(
        client, "pct_admin@t.com", ["pct_u2@t.com"]
    )
    res = await client.post(f"{BASE}/groups/{gid}/expenses", json={
        "title": "Cab",
        "total_amount": "1000",
        "currency": "INR",
        "paid_by_user_id": uids["pct_admin@t.com"],
        "split_type": "PERCENTAGE",
        "participants_percentage": [
            {"user_id": uids["pct_admin@t.com"], "percentage": "60"},
            {"user_id": uids["pct_u2@t.com"], "percentage": "40"},
        ],
    }, headers=_auth(token))
    assert res.status_code == 201
    amounts = {p["user_id"]: float(p["owed_amount"]) for p in res.json()["participants"]}
    assert amounts[uids["pct_admin@t.com"]] == 600.0
    assert amounts[uids["pct_u2@t.com"]] == 400.0


@pytest.mark.asyncio
async def test_invalid_exact_split_total_returns_422(client: AsyncClient):
    token, gid, uids = await _setup_group(
        client, "bad_admin@t.com", ["bad_u2@t.com"]
    )
    res = await client.post(f"{BASE}/groups/{gid}/expenses", json={
        "title": "Bad",
        "total_amount": "1000",
        "currency": "INR",
        "paid_by_user_id": uids["bad_admin@t.com"],
        "split_type": "EXACT",
        "participants_exact": [
            {"user_id": uids["bad_admin@t.com"], "owed_amount": "600"},
            {"user_id": uids["bad_u2@t.com"], "owed_amount": "600"},  # 1200 ≠ 1000
        ],
    }, headers=_auth(token))
    assert res.status_code == 422
    assert res.json()["error"] == "INVALID_SPLIT_TOTAL"


@pytest.mark.asyncio
async def test_non_member_participant_rejected(client: AsyncClient):
    token, gid, uids = await _setup_group(client, "nm_admin@t.com")
    _, outsider_id = await _register_and_login(client, "outsider@t.com", "Out")
    res = await client.post(f"{BASE}/groups/{gid}/expenses", json={
        "title": "X",
        "total_amount": "100",
        "currency": "INR",
        "paid_by_user_id": uids["nm_admin@t.com"],
        "split_type": "EQUAL",
        "participants_equal": [
            {"user_id": uids["nm_admin@t.com"]},
            {"user_id": outsider_id},
        ],
    }, headers=_auth(token))
    assert res.status_code == 422
    assert res.json()["error"] == "USER_NOT_IN_GROUP"


# ── Get / List Expenses ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_expenses_paginated(client: AsyncClient):
    token, gid, uids = await _setup_group(client, "pg_admin@t.com", ["pg_u2@t.com"])
    for i in range(5):
        await client.post(f"{BASE}/groups/{gid}/expenses", json={
            "title": f"Expense {i}",
            "total_amount": "100",
            "currency": "INR",
            "paid_by_user_id": uids["pg_admin@t.com"],
            "split_type": "EQUAL",
            "participants_equal": [
                {"user_id": uids["pg_admin@t.com"]},
                {"user_id": uids["pg_u2@t.com"]},
            ],
        }, headers=_auth(token))

    res = await client.get(f"{BASE}/groups/{gid}/expenses?page=1&limit=3", headers=_auth(token))
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 3
    assert data["total_items"] == 5
    assert data["total_pages"] == 2


@pytest.mark.asyncio
async def test_get_expense_detail(client: AsyncClient):
    token, gid, uids = await _setup_group(client, "det_admin@t.com", ["det_u2@t.com"])
    exp = (await client.post(f"{BASE}/groups/{gid}/expenses", json={
        "title": "Detail Exp",
        "total_amount": "200",
        "currency": "INR",
        "paid_by_user_id": uids["det_admin@t.com"],
        "split_type": "EQUAL",
        "participants_equal": [
            {"user_id": uids["det_admin@t.com"]},
            {"user_id": uids["det_u2@t.com"]},
        ],
    }, headers=_auth(token))).json()

    res = await client.get(f"{BASE}/expenses/{exp['id']}", headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["title"] == "Detail Exp"


# ── Reverse Expense ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reverse_expense(client: AsyncClient):
    token, gid, uids = await _setup_group(client, "rev_admin@t.com", ["rev_u2@t.com"])
    exp = (await client.post(f"{BASE}/groups/{gid}/expenses", json={
        "title": "To Reverse",
        "total_amount": "500",
        "currency": "INR",
        "paid_by_user_id": uids["rev_admin@t.com"],
        "split_type": "EQUAL",
        "participants_equal": [
            {"user_id": uids["rev_admin@t.com"]},
            {"user_id": uids["rev_u2@t.com"]},
        ],
    }, headers=_auth(token))).json()

    res = await client.patch(f"{BASE}/expenses/{exp['id']}/reverse", headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["status"] == "REVERSED"


@pytest.mark.asyncio
async def test_reverse_already_reversed_returns_404(client: AsyncClient):
    token, gid, uids = await _setup_group(client, "rev2_admin@t.com", ["rev2_u2@t.com"])
    exp = (await client.post(f"{BASE}/groups/{gid}/expenses", json={
        "title": "Rev2",
        "total_amount": "100",
        "currency": "INR",
        "paid_by_user_id": uids["rev2_admin@t.com"],
        "split_type": "EQUAL",
        "participants_equal": [
            {"user_id": uids["rev2_admin@t.com"]},
            {"user_id": uids["rev2_u2@t.com"]},
        ],
    }, headers=_auth(token))).json()
    await client.patch(f"{BASE}/expenses/{exp['id']}/reverse", headers=_auth(token))
    # Reverse again
    res = await client.patch(f"{BASE}/expenses/{exp['id']}/reverse", headers=_auth(token))
    assert res.status_code == 404


# ── Update Expense ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_expense_title(client: AsyncClient):
    token, gid, uids = await _setup_group(client, "upd_admin@t.com")
    exp = (await client.post(f"{BASE}/groups/{gid}/expenses", json={
        "title": "Old Title",
        "total_amount": "100",
        "currency": "INR",
        "paid_by_user_id": uids["upd_admin@t.com"],
        "split_type": "EQUAL",
        "participants_equal": [{"user_id": uids["upd_admin@t.com"]}],
    }, headers=_auth(token))).json()

    res = await client.patch(f"{BASE}/expenses/{exp['id']}",
                             json={"title": "New Title"}, headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["title"] == "New Title"
