"""
Integration tests for balance computation and settlement.
These are the most important tests — they verify financial correctness.
"""
from decimal import Decimal

import pytest
from httpx import AsyncClient

BASE = "/api/v1"


async def _register_and_login(client, email, name="User"):
    reg = await client.post(f"{BASE}/auth/register", json={
        "name": name, "email": email, "password": "Pass12345"
    })
    uid = reg.json()["id"]
    token = (await client.post(f"{BASE}/auth/login", json={
        "email": email, "password": "Pass12345"
    })).json()["access_token"]
    return token, uid


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _full_setup(client, prefix):
    """Setup: 3-person group with one 3000 EQUAL expense paid by admin."""
    token_a, uid_a = await _register_and_login(client, f"{prefix}_a@t.com", "Alice")
    token_b, uid_b = await _register_and_login(client, f"{prefix}_b@t.com", "Bob")
    token_c, uid_c = await _register_and_login(client, f"{prefix}_c@t.com", "Carol")

    grp = (await client.post(f"{BASE}/groups", json={"name": "Trip"},
                              headers=_auth(token_a))).json()
    gid = grp["id"]

    for email in [f"{prefix}_b@t.com", f"{prefix}_c@t.com"]:
        await client.post(f"{BASE}/groups/{gid}/members",
                          json={"email": email}, headers=_auth(token_a))

    # Alice pays 3000, split equally → B owes 1000, C owes 1000
    await client.post(f"{BASE}/groups/{gid}/expenses", json={
        "title": "Dinner",
        "total_amount": "3000",
        "currency": "INR",
        "paid_by_user_id": uid_a,
        "split_type": "EQUAL",
        "participants_equal": [
            {"user_id": uid_a},
            {"user_id": uid_b},
            {"user_id": uid_c},
        ],
    }, headers=_auth(token_a))

    return {
        "gid": gid,
        "token_a": token_a, "uid_a": uid_a,
        "token_b": token_b, "uid_b": uid_b,
        "token_c": token_c, "uid_c": uid_c,
    }


# ── Balance correctness ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_balances_after_equal_expense(client: AsyncClient):
    ctx = await _full_setup(client, "bal1")
    res = await client.get(f"{BASE}/groups/{ctx['gid']}/balances",
                           headers=_auth(ctx["token_a"]))
    assert res.status_code == 200
    balances = res.json()["balances"]
    # Should have B→A and C→A, each 1000
    debts = {(b["from_user_id"], b["to_user_id"]): float(b["amount"]) for b in balances}
    assert debts.get((ctx["uid_b"], ctx["uid_a"])) == 1000.0
    assert debts.get((ctx["uid_c"], ctx["uid_a"])) == 1000.0


@pytest.mark.asyncio
async def test_simplified_balances(client: AsyncClient):
    ctx = await _full_setup(client, "simp1")
    res = await client.get(f"{BASE}/groups/{ctx['gid']}/balances/simplified",
                           headers=_auth(ctx["token_a"]))
    assert res.status_code == 200
    txns = res.json()["transactions"]
    # Alice is sole creditor; Bob and Carol each owe 1000
    assert len(txns) == 2
    total = sum(float(t["amount"]) for t in txns)
    assert total == 2000.0
    # All settle to Alice
    assert all(t["to_user_id"] == ctx["uid_a"] for t in txns)


@pytest.mark.asyncio
async def test_balance_zero_after_reverse(client: AsyncClient):
    ctx = await _full_setup(client, "rev_bal")
    # List the expense
    exps = (await client.get(f"{BASE}/groups/{ctx['gid']}/expenses",
                             headers=_auth(ctx["token_a"]))).json()["items"]
    exp_id = exps[0]["id"]

    # Reverse it
    await client.patch(f"{BASE}/expenses/{exp_id}/reverse", headers=_auth(ctx["token_a"]))

    res = await client.get(f"{BASE}/groups/{ctx['gid']}/balances",
                           headers=_auth(ctx["token_a"]))
    # After reversal, balances should be empty (all zeroed out)
    assert res.json()["balances"] == []


# ── Settlement ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_settlement_reduces_balance(client: AsyncClient):
    ctx = await _full_setup(client, "setl1")
    # Bob settles 500 with Alice
    res = await client.post(f"{BASE}/groups/{ctx['gid']}/settlements", json={
        "from_user_id": ctx["uid_b"],
        "to_user_id": ctx["uid_a"],
        "amount": "500",
        "currency": "INR",
        "note": "Partial payment",
    }, headers=_auth(ctx["token_b"]))
    assert res.status_code == 201
    data = res.json()
    assert float(data["amount"]) == 500.0
    assert data["status"] == "COMPLETED"

    # Check Bob's remaining debt
    balances = (await client.get(f"{BASE}/groups/{ctx['gid']}/balances",
                                 headers=_auth(ctx["token_a"]))).json()["balances"]
    bob_debt = next(
        (b for b in balances
         if b["from_user_id"] == ctx["uid_b"] and b["to_user_id"] == ctx["uid_a"]),
        None,
    )
    assert bob_debt is not None
    assert float(bob_debt["amount"]) == 500.0  # 1000 - 500


@pytest.mark.asyncio
async def test_full_settlement_clears_balance(client: AsyncClient):
    ctx = await _full_setup(client, "setl2")
    await client.post(f"{BASE}/groups/{ctx['gid']}/settlements", json={
        "from_user_id": ctx["uid_b"],
        "to_user_id": ctx["uid_a"],
        "amount": "1000",
        "currency": "INR",
    }, headers=_auth(ctx["token_b"]))

    balances = (await client.get(f"{BASE}/groups/{ctx['gid']}/balances",
                                 headers=_auth(ctx["token_a"]))).json()["balances"]
    bob_debt = next(
        (b for b in balances
         if b["from_user_id"] == ctx["uid_b"] and b["to_user_id"] == ctx["uid_a"]),
        None,
    )
    # Bob's balance should be gone (zeroed out)
    assert bob_debt is None


@pytest.mark.asyncio
async def test_settlement_exceeds_balance_rejected(client: AsyncClient):
    ctx = await _full_setup(client, "setl3")
    res = await client.post(f"{BASE}/groups/{ctx['gid']}/settlements", json={
        "from_user_id": ctx["uid_b"],
        "to_user_id": ctx["uid_a"],
        "amount": "9999",  # Bob only owes 1000
        "currency": "INR",
    }, headers=_auth(ctx["token_b"]))
    assert res.status_code == 422
    assert res.json()["error"] == "SETTLEMENT_EXCEEDS_BALANCE"


@pytest.mark.asyncio
async def test_self_settlement_rejected(client: AsyncClient):
    ctx = await _full_setup(client, "self_setl")
    res = await client.post(f"{BASE}/groups/{ctx['gid']}/settlements", json={
        "from_user_id": ctx["uid_a"],
        "to_user_id": ctx["uid_a"],
        "amount": "100",
        "currency": "INR",
    }, headers=_auth(ctx["token_a"]))
    assert res.status_code == 422
    assert res.json()["error"] == "SELF_SETTLEMENT_INVALID"


@pytest.mark.asyncio
async def test_settlement_when_no_debt_rejected(client: AsyncClient):
    ctx = await _full_setup(client, "no_debt")
    # Alice tries to settle with Bob (Alice is the creditor, not debtor)
    res = await client.post(f"{BASE}/groups/{ctx['gid']}/settlements", json={
        "from_user_id": ctx["uid_a"],
        "to_user_id": ctx["uid_b"],
        "amount": "100",
        "currency": "INR",
    }, headers=_auth(ctx["token_a"]))
    assert res.status_code == 422
    assert res.json()["error"] == "SETTLEMENT_EXCEEDS_BALANCE"


@pytest.mark.asyncio
async def test_list_settlements(client: AsyncClient):
    ctx = await _full_setup(client, "list_setl")
    await client.post(f"{BASE}/groups/{ctx['gid']}/settlements", json={
        "from_user_id": ctx["uid_b"], "to_user_id": ctx["uid_a"],
        "amount": "300", "currency": "INR",
    }, headers=_auth(ctx["token_b"]))
    await client.post(f"{BASE}/groups/{ctx['gid']}/settlements", json={
        "from_user_id": ctx["uid_c"], "to_user_id": ctx["uid_a"],
        "amount": "500", "currency": "INR",
    }, headers=_auth(ctx["token_c"]))

    res = await client.get(f"{BASE}/groups/{ctx['gid']}/settlements",
                           headers=_auth(ctx["token_a"]))
    assert res.status_code == 200
    assert len(res.json()) == 2


# ── Cannot remove member with balance ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_cannot_remove_member_with_outstanding_balance(client: AsyncClient):
    ctx = await _full_setup(client, "rem_bal")
    # Bob still owes 1000; admin tries to remove him
    res = await client.delete(
        f"{BASE}/groups/{ctx['gid']}/members/{ctx['uid_b']}",
        headers=_auth(ctx["token_a"]),
    )
    assert res.status_code == 422
    assert res.json()["error"] == "OUTSTANDING_BALANCE_EXISTS"


# ── User overall balance ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_user_overall_balances(client: AsyncClient):
    ctx = await _full_setup(client, "overall")
    res = await client.get(f"{BASE}/users/me/balances", headers=_auth(ctx["token_b"]))
    assert res.status_code == 200
    # Bob owes Alice 1000 across all groups
    balances = res.json()
    assert len(balances) >= 1
    alice_entry = next(
        (b for b in balances if b["counterpart_user_id"] == ctx["uid_a"]), None
    )
    assert alice_entry is not None
    assert float(alice_entry["net_amount"]) == 1000.0
