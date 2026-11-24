"""Register, login, refresh rotation, logout, CSRF and rate limiting."""

import pytest
from sqlalchemy import select

from app.core.rate_limit import limiter
from app.core.security import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    REFRESH_COOKIE,
    SESSION_HINT_COOKIE,
)
from app.models import RefreshToken, User
from tests.conftest import TEST_PASSWORD

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/me"


async def test_register_creates_buyer_and_signs_in(client, db):
    res = await client.post(
        REGISTER,
        # Postel's Law: messy input is normalised.
        json={
            "name": "  Isabela   Reyes ",
            "email": " Isabela@Example.COM ",
            "password": "silk2026x",
        },
    )
    assert res.status_code == 201, res.text
    user = res.json()["user"]
    assert user["email"] == "isabela@example.com"
    assert user["name"] == "Isabela Reyes"
    assert user["roles"] == ["BUYER"]
    assert "cart:manage" in user["permissions"]
    assert "product:create" not in user["permissions"]
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE, SESSION_HINT_COOKIE):
        assert client.cookies.get(name), name
    assert client.cookies.get(SESSION_HINT_COOKIE) == "BUYER"
    stored = await db.scalar(select(User).where(User.email == "isabela@example.com"))
    assert stored is not None and stored.password_hash.startswith("$argon2")


async def test_register_seller_account(client, db):
    res = await client.post(
        REGISTER,
        json={
            "name": "Mira Santos",
            "email": "mira@example.com",
            "password": "atelier2026",
            "account_type": "seller",
        },
    )
    assert res.status_code == 201, res.text
    user = res.json()["user"]
    assert user["roles"] == ["SELLER"]
    # A new seller can apply and upload, but can't shop or use the Studio yet.
    assert {"seller:apply", "media:upload", "wallet:view"} <= set(user["permissions"])
    assert "cart:manage" not in user["permissions"]
    assert "product:create" not in user["permissions"]
    assert client.cookies.get(SESSION_HINT_COOKIE) == "SELLER"
    wallet = (await client.get("/api/v1/wallet")).json()
    assert wallet["balance_qc"] == 0  # the welcome credit is for shoppers


async def test_register_rejects_duplicate_email(client, accounts):
    res = await client.post(
        REGISTER, json={"name": "Copy Cat", "email": "BUYER@queneth.test", "password": "abc12345"}
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"name": "Al", "email": "not-an-email", "password": "abc12345"}, "email"),
        ({"name": "Al", "email": "a@queneth.test", "password": "short1"}, "password"),
        ({"name": "Al", "email": "a@queneth.test", "password": "lettersonly"}, "password"),
        ({"name": "A", "email": "a@queneth.test", "password": "abc12345"}, "name"),
    ],
)
async def test_register_validation(client, payload, field):
    res = await client.post(REGISTER, json=payload)
    assert res.status_code == 422
    fields = [d["field"] for d in res.json()["error"]["details"]]
    assert field in fields


async def test_register_cannot_self_assign_admin(client):
    res = await client.post(
        REGISTER,
        json={
            "name": "Sneaky",
            "email": "s@queneth.test",
            "password": "abc12345",
            "roles": ["ADMIN"],
        },
    )
    assert res.status_code == 201
    assert res.json()["user"]["roles"] == ["BUYER"]


async def test_login_wrong_password_is_generic(client, accounts):
    wrong = await client.post(LOGIN, json={"email": "buyer@queneth.test", "password": "nope"})
    unknown = await client.post(LOGIN, json={"email": "ghost@queneth.test", "password": "nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()  # no account enumeration
    assert wrong.json()["error"]["code"] == "invalid_credentials"


async def test_login_and_me(client, accounts):
    assert (await client.get(ME)).status_code == 401
    res = await client.post(LOGIN, json={"email": "seller@queneth.test", "password": TEST_PASSWORD})
    assert res.status_code == 200
    me = await client.get(ME)
    assert me.status_code == 200
    body = me.json()
    assert body["roles"] == ["SELLER"]
    assert "product:create" in body["permissions"]
    assert "cart:manage" not in body["permissions"]
    assert client.cookies.get(SESSION_HINT_COOKIE) == "SELLER"


async def test_update_profile(client, accounts, login):
    await login("buyer@queneth.test")
    res = await client.patch(ME, json={"name": "  Isabela  R. "})
    assert res.status_code == 200
    assert res.json()["name"] == "Isabela R."


async def test_refresh_rotates_and_detects_reuse(client, accounts, login, db):
    await login("buyer@queneth.test")
    first_refresh = client.cookies.get(REFRESH_COOKIE)

    res = await client.post(REFRESH)
    assert res.status_code == 200
    second_refresh = client.cookies.get(REFRESH_COOKIE)
    assert second_refresh and second_refresh != first_refresh

    # Replaying the rotated token is treated as theft: the family is revoked.
    client.cookies.set(REFRESH_COOKIE, first_refresh, path="/api/v1/auth")
    replay = await client.post(REFRESH)
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "refresh_reused"

    tokens = (await db.scalars(select(RefreshToken))).all()
    assert tokens and all(t.revoked_at is not None for t in tokens)


async def test_failed_refresh_clears_cookies(client, accounts):
    client.cookies.set(REFRESH_COOKIE, "garbage", path="/api/v1/auth")
    client.cookies.set(CSRF_COOKIE, "x")
    res = await client.post(REFRESH)
    assert res.status_code == 401
    cleared = [h for h in res.headers.get_list("set-cookie") if "Max-Age=0" in h]
    assert any(h.startswith(f"{SESSION_HINT_COOKIE}=") for h in cleared)


async def test_logout_revokes_refresh_token(client, accounts, login):
    await login("buyer@queneth.test")
    refresh_token = client.cookies.get(REFRESH_COOKIE)
    res = await client.post(LOGOUT)
    assert res.status_code == 204
    assert client.cookies.get(ACCESS_COOKIE) is None
    # Even if someone kept a copy of the refresh token, it's dead now.
    client.cookies.set(REFRESH_COOKIE, refresh_token, path="/api/v1/auth")
    client.cookies.set(CSRF_COOKIE, "x")
    assert (await client.post(REFRESH)).status_code == 401


async def test_csrf_required_for_cookie_mutations(raw_client, accounts):
    res = await raw_client.post(
        LOGIN, json={"email": "buyer@queneth.test", "password": TEST_PASSWORD}
    )
    assert res.status_code == 200  # login itself is exempt
    blocked = await raw_client.patch(ME, json={"name": "Hijacked"})
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "csrf_failed"

    forged = await raw_client.patch(
        ME, json={"name": "Hijacked"}, headers={"X-CSRF-Token": "guess"}
    )
    assert forged.status_code == 403

    ok = await raw_client.patch(
        ME, json={"name": "Isabela"}, headers={"X-CSRF-Token": raw_client.cookies[CSRF_COOKIE]}
    )
    assert ok.status_code == 200


async def test_tampered_access_token_is_401(client, accounts, login):
    await login("buyer@queneth.test")
    token = client.cookies.get(ACCESS_COOKIE)
    client.cookies.set(ACCESS_COOKIE, token[:-4] + "AAAA")
    res = await client.get(ME)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "invalid_token"


async def test_login_is_rate_limited(client, accounts):
    limiter.enabled = True
    limiter.reset()
    try:
        codes = [
            (
                await client.post(LOGIN, json={"email": "buyer@queneth.test", "password": "x"})
            ).status_code
            for _ in range(11)
        ]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert codes[:10] == [401] * 10
    assert codes[10] == 429
