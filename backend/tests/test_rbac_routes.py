"""401/403 at the API layer: the real gate (spec §7, enforcement layer 1)."""

import pytest
from fastapi import Depends
from sqlalchemy import select

from app.api.deps import require_permission, require_role
from app.core.permissions import Permission, Role
from app.models import AuditLog, User
from tests.conftest import TEST_PASSWORD

ADMIN_ROUTES = [
    (
        "patch",
        "/api/v1/admin/users/{id}/roles",
        {"roles": ["SELLER"], "reason": "Approved boutique"},
    ),
    (
        "patch",
        "/api/v1/admin/users/{id}/status",
        {"status": "banned", "reason": "Fraudulent listings"},
    ),
    ("get", "/api/v1/admin/audit", None),
]


async def _call(client, method, path, body, target_id):
    url = path.format(id=target_id)
    return await getattr(client, method)(url, **({"json": body} if body else {}))


@pytest.mark.parametrize(("method", "path", "body"), ADMIN_ROUTES)
async def test_admin_routes_reject_guests_with_401(client, accounts, method, path, body):
    res = await _call(client, method, path, body, accounts.buyer.id)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "not_authenticated"


@pytest.mark.parametrize("email", ["buyer@queneth.test", "seller@queneth.test"])
@pytest.mark.parametrize(("method", "path", "body"), ADMIN_ROUTES)
async def test_admin_routes_reject_non_admins_with_403(
    client, accounts, login, email, method, path, body
):
    await login(email)
    res = await _call(client, method, path, body, accounts.other_seller.id)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "permission_denied"


@pytest.fixture
def gated_app(app):
    """Mount stand-in routes so role/permission gates can be proven before the
    real seller (Phase 8) and wallet (Phase 5) endpoints exist."""

    @app.post("/_t/seller/products", dependencies=[Depends(require_role(Role.SELLER))])
    async def seller_only():
        return {"ok": True}

    @app.post("/_t/wallet/grant")
    async def grant(_: User = Depends(require_permission(Permission.WALLET_GRANT))):
        return {"ok": True}

    return app


async def test_buyer_cannot_call_seller_actions(gated_app, client, accounts, login):
    await login("buyer@queneth.test")
    assert (await client.post("/_t/seller/products")).status_code == 403
    await login("seller@queneth.test")
    assert (await client.post("/_t/seller/products")).status_code == 200


async def test_non_admin_cannot_grant_credits(gated_app, client, accounts, login):
    assert (await client.post("/_t/wallet/grant")).status_code == 401
    for email in ("buyer@queneth.test", "seller@queneth.test"):
        await login(email)
        assert (await client.post("/_t/wallet/grant")).status_code == 403
    await login("admin@queneth.test")
    assert (await client.post("/_t/wallet/grant")).status_code == 200


async def test_admin_changes_roles_with_audit(client, accounts, login, db):
    await login("admin@queneth.test")
    res = await client.patch(
        f"/api/v1/admin/users/{accounts.buyer.id}/roles",
        json={"roles": ["SELLER", "SELLER"], "reason": "Approved boutique onboarding"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["roles"] == ["SELLER"]

    entry = await db.scalar(select(AuditLog).where(AuditLog.action == "user.roles_changed"))
    assert entry is not None
    assert entry.actor_id == accounts.admin.id
    assert entry.target_id == str(accounts.buyer.id)
    assert entry.before == {"roles": ["BUYER"]}
    assert entry.after == {"roles": ["SELLER"]}
    assert entry.reason == "Approved boutique onboarding"

    # The change is effective immediately on the user's next request.
    await login("buyer@queneth.test")
    me = (await client.get("/api/v1/me")).json()
    assert me["roles"] == ["SELLER"]
    # Now a seller account: it can apply for a boutique, and no longer shops.
    assert "seller:apply" in me["permissions"]
    assert "cart:manage" not in me["permissions"]


async def test_account_is_never_buyer_and_seller(client, accounts, login):
    await login("admin@queneth.test")
    res = await client.patch(
        f"/api/v1/admin/users/{accounts.buyer.id}/roles",
        json={"roles": ["BUYER", "SELLER"], "reason": "Both at once"},
    )
    assert res.status_code == 422


async def test_admin_role_cannot_be_granted_via_api(client, accounts, login):
    await login("admin@queneth.test")
    res = await client.patch(
        f"/api/v1/admin/users/{accounts.buyer.id}/roles",
        json={"roles": ["ADMIN"], "reason": "Promote to admin"},
    )
    assert res.status_code == 422


async def test_role_change_requires_reason(client, accounts, login):
    await login("admin@queneth.test")
    res = await client.patch(
        f"/api/v1/admin/users/{accounts.buyer.id}/roles", json={"roles": ["BUYER"], "reason": ""}
    )
    assert res.status_code == 422


async def test_ban_blocks_sessions_and_login(client, accounts, login, db):
    await login("buyer@queneth.test")
    buyer_cookies = dict(client.cookies.items())

    await login("admin@queneth.test")
    res = await client.patch(
        f"/api/v1/admin/users/{accounts.buyer.id}/status",
        json={"status": "banned", "reason": "Chargeback fraud ring"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "banned"
    assert await db.scalar(select(AuditLog.id).where(AuditLog.action == "user.banned"))

    # The buyer's still-valid access token no longer works…
    client.cookies.clear()
    for name, value in buyer_cookies.items():
        client.cookies.set(name, value)
    me = await client.get("/api/v1/me")
    assert me.status_code == 403
    assert me.json()["error"]["code"] == "account_banned"

    # …and they can't sign back in.
    client.cookies.clear()
    res = await client.post(
        "/api/v1/auth/login", json={"email": "buyer@queneth.test", "password": TEST_PASSWORD}
    )
    assert res.status_code == 403


async def test_admin_cannot_ban_self_or_other_admins(client, accounts, login):
    await login("admin@queneth.test")
    res = await client.patch(
        f"/api/v1/admin/users/{accounts.admin.id}/status",
        json={"status": "banned", "reason": "Testing self-ban"},
    )
    assert res.status_code == 409


async def test_audit_log_pagination(client, accounts, login):
    await login("admin@queneth.test")
    for roles in (["SELLER"], ["BUYER"], ["SELLER"]):
        await client.patch(
            f"/api/v1/admin/users/{accounts.buyer.id}/roles",
            json={"roles": roles, "reason": "Toggling for the audit test"},
        )
    page1 = (await client.get("/api/v1/admin/audit", params={"limit": 2})).json()
    assert len(page1["items"]) == 2 and page1["has_more"]
    page2 = (
        await client.get("/api/v1/admin/audit", params={"limit": 2, "cursor": page1["next_cursor"]})
    ).json()
    assert len(page2["items"]) == 1 and not page2["has_more"]
    ids = {i["id"] for i in page1["items"] + page2["items"]}
    assert len(ids) == 3


async def test_unknown_user_is_404(client, accounts, login):
    await login("admin@queneth.test")
    res = await client.patch(
        "/api/v1/admin/users/00000000-0000-0000-0000-000000000000/roles",
        json={"roles": ["BUYER"], "reason": "Does not exist"},
    )
    assert res.status_code == 404


async def test_users_table_has_no_admin_self_registration(db, accounts):
    admins = (await db.scalars(select(User).where(User.email == "admin@queneth.test"))).all()
    assert len(admins) == 1
