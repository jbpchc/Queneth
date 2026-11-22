"""Brevo adapter, email queue/retry, verification and password reset, admin views."""

import json
import uuid
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import REFRESH_COOKIE, utcnow
from app.integrations.base import IntegrationName, registry
from app.integrations.brevo_email import BrevoAdapter
from app.models import EmailLog, EmailToken, Notification, User
from app.services import email_service
from tests.conftest import TEST_PASSWORD


@pytest.fixture(autouse=True)
def _fresh_registry():
    registry.reset()
    yield
    registry.reset()


def _verify_url(inbox: list[dict]) -> str:
    return next(n for n in inbox if n["type"] == "email.verify_email")["payload"]["action_url"]


def _token_from(url: str) -> str:
    return parse_qs(urlparse(url).query)["token"][0]


async def _register(client, email="isabela@queneth.test"):
    res = await client.post(
        "/api/v1/auth/register",
        json={"name": "Isabela Reyes", "email": email, "password": "silk2026x"},
    )
    assert res.status_code == 201, res.text
    return res.json()["user"]


async def test_register_sends_verification_email_and_inbox_copy(client, db):
    user = await _register(client)
    assert user["email_verified"] is False
    log = await db.scalar(select(EmailLog).where(EmailLog.to_email == "isabela@queneth.test"))
    assert log.template == "verify_email" and log.status == "mocked" and log.attempts == 1
    assert "Confirm email" in log.html and "/verify-email?token=" in log.text

    inbox = (await client.get("/api/v1/notifications")).json()["items"]
    verify = next(n for n in inbox if n["type"] == "email.verify_email")
    assert verify["payload"]["action_url"].startswith(get_settings().frontend_url)
    # Inbox: the verification email plus the welcome-credits notice.
    assert {n["type"] for n in inbox} == {"email.verify_email", "wallet.credited"}
    assert (await client.get("/api/v1/notifications/unread-count")).json() == {"unread": 2}


async def test_verify_email_flow(client, db):
    await _register(client)
    inbox = (await client.get("/api/v1/notifications")).json()["items"]
    token = _token_from(_verify_url(inbox))

    res = await client.post("/api/v1/auth/verify-email", json={"token": f"  {token} "})
    assert res.status_code == 200
    assert (await client.get("/api/v1/me")).json()["email_verified"] is True

    again = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert again.status_code == 422 and again.json()["error"]["code"] == "invalid_token"
    resend = await client.post("/api/v1/auth/verify-email/resend")
    assert resend.status_code == 409


async def test_resend_retires_the_previous_link(client, db):
    await _register(client)
    first = _token_from(_verify_url((await client.get("/api/v1/notifications")).json()["items"]))
    assert (await client.post("/api/v1/auth/verify-email/resend")).status_code == 200
    res = await client.post("/api/v1/auth/verify-email", json={"token": first})
    assert res.status_code == 422


async def test_expired_verification_link(client, db):
    await _register(client)
    token = _token_from(_verify_url((await client.get("/api/v1/notifications")).json()["items"]))
    row = await db.scalar(select(EmailToken))
    row.expires_at = utcnow() - timedelta(minutes=1)
    await db.commit()
    res = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert res.status_code == 422 and res.json()["error"]["code"] == "token_expired"


async def test_forgot_password_does_not_reveal_accounts(client, accounts, db):
    unknown = await client.post(
        "/api/v1/auth/password/forgot", json={"email": "ghost@queneth.test"}
    )
    known = await client.post(
        "/api/v1/auth/password/forgot", json={"email": " BUYER@queneth.test "}
    )
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    logs = (await db.scalars(select(EmailLog))).all()
    assert [log.to_email for log in logs] == ["buyer@queneth.test"]


async def test_password_reset_flow(client, accounts, login, db):
    await login("buyer@queneth.test")
    old_refresh = client.cookies.get(REFRESH_COOKIE)
    client.cookies.clear()

    await client.post("/api/v1/auth/password/forgot", json={"email": "buyer@queneth.test"})
    log = await db.scalar(select(EmailLog).where(EmailLog.template == "password_reset"))
    token = _token_from(log.text.split("one use):\n")[1].split("\n")[0])

    # The reset link is never copied into the inbox.
    notes = (
        await db.scalars(select(Notification).where(Notification.user_id == accounts.buyer.id))
    ).all()
    assert all(n.payload.get("action_url") is None for n in notes)

    weak = await client.post(
        "/api/v1/auth/password/reset", json={"token": token, "password": "short"}
    )
    assert weak.status_code == 422
    res = await client.post(
        "/api/v1/auth/password/reset", json={"token": token, "password": "newsilk2027"}
    )
    assert res.status_code == 200, res.text

    old = await client.post(
        "/api/v1/auth/login", json={"email": "buyer@queneth.test", "password": TEST_PASSWORD}
    )
    assert old.status_code == 401
    new = await client.post(
        "/api/v1/auth/login", json={"email": "buyer@queneth.test", "password": "newsilk2027"}
    )
    assert new.status_code == 200

    # Every pre-reset session was revoked.
    client.cookies.set(REFRESH_COOKIE, old_refresh, path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
    assert await db.scalar(select(EmailLog.id).where(EmailLog.template == "password_changed"))
    replay = await client.post(
        "/api/v1/auth/password/reset", json={"token": token, "password": "another2028"}
    )
    assert replay.status_code == 422


# ─── Brevo adapter, delivery and retries ───────────────────────────────────


def _brevo(status: int, seen: list[httpx.Request]) -> BrevoAdapter:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if status == 201:
            return httpx.Response(201, json={"messageId": "<abc@smtp-relay.brevo.com>"})
        return httpx.Response(status, json={"message": "nope"})

    settings = get_settings().model_copy(
        update={
            "integrations_mode": "live",
            "brevo_api_key": "xkeysib-test",
            "integration_retries": 0,
        }
    )
    return BrevoAdapter(settings, transport=httpx.MockTransport(handler))


async def _queued(db, accounts) -> EmailLog:
    from app.services.email_templates import verify_email

    entry = email_service.queue(
        db,
        user=accounts.buyer,
        to_email="buyer@queneth.test",
        email=verify_email(name="Isabela", url="https://x.test/v?token=t"),
    )
    await db.commit()
    return entry


async def test_brevo_send_success(session_factory, db, accounts):
    entry = await _queued(db, accounts)
    seen: list[httpx.Request] = []
    adapter = _brevo(201, seen)
    status = await email_service.deliver(session_factory, entry.id, adapter.settings, adapter)
    assert status == "sent"
    sent = seen[0]
    assert sent.url.path == "/v3/smtp/email" and sent.headers["api-key"] == "xkeysib-test"
    body = json.loads(sent.read())
    assert body["subject"] == "Confirm your email for Queneth"
    assert body["sender"]["email"] == get_settings().brevo_sender_email
    assert body["to"] == [{"email": "buyer@queneth.test", "name": "Isabela Reyes"}]
    await db.refresh(entry)
    assert entry.provider_message_id == "<abc@smtp-relay.brevo.com>"
    # Delivering twice never sends twice.
    assert (
        await email_service.deliver(session_factory, entry.id, adapter.settings, adapter) == "sent"
    )
    assert len(seen) == 1


async def test_brevo_failure_queues_retry_then_fails(session_factory, db, accounts):
    entry = await _queued(db, accounts)
    adapter = _brevo(503, [])
    settings = adapter.settings.model_copy(update={"email_max_attempts": 2})
    assert await email_service.deliver(session_factory, entry.id, settings, adapter) == "queued"
    await db.refresh(entry)
    assert entry.attempts == 1 and entry.next_attempt_at is not None and "503" in entry.last_error
    assert registry.get(IntegrationName.BREVO).fallbacks == 1
    # The user still got the in-app copy.
    assert await db.scalar(select(Notification.id).where(Notification.user_id == accounts.buyer.id))

    assert await email_service.deliver(session_factory, entry.id, settings, adapter) == "failed"


async def test_retry_job_only_picks_due_emails(session_factory, db, accounts):
    due = await _queued(db, accounts)
    later = await _queued(db, accounts)
    later.next_attempt_at = utcnow() + timedelta(hours=1)
    await db.commit()
    count = await email_service.retry_due(session_factory, get_settings())
    assert count == 1
    await db.refresh(due)
    await db.refresh(later)
    assert due.status == "mocked" and later.status == "queued"


async def test_unconfigured_brevo_in_live_mode_fails_gracefully(session_factory, db, accounts):
    entry = await _queued(db, accounts)
    settings = get_settings().model_copy(
        update={"integrations_mode": "live", "brevo_api_key": None}
    )
    assert await email_service.deliver(session_factory, entry.id, settings) == "queued"


# ─── Admin views ───────────────────────────────────────────────────────────


async def test_admin_integrations_page_data(client, accounts, login):
    await login("buyer@queneth.test")
    assert (await client.get("/api/v1/admin/integrations")).status_code == 403
    assert (await client.get("/api/v1/admin/emails")).status_code == 403

    await login("admin@queneth.test")
    rows = (await client.get("/api/v1/admin/integrations")).json()
    assert [r["name"] for r in rows] == ["psgc", "cloudinary", "brevo"]
    assert all(r["mode"] == "mock" and r["health"] == "mock" for r in rows)
    assert rows[0]["details"]["snapshot_date"]
    probe = await client.post("/api/v1/admin/integrations/psgc/check")
    assert probe.status_code == 409 and probe.json()["error"]["code"] == "mock_mode"


async def test_admin_email_log_and_mock_preview(client, accounts, login, db):
    await _register(client)
    await login("admin@queneth.test")
    page = (await client.get("/api/v1/admin/emails", params={"to": "ISABELA@queneth.test"})).json()
    assert len(page["items"]) == 1
    item = page["items"][0]
    assert "html" not in item and item["status"] == "mocked"
    preview = (await client.get(f"/api/v1/admin/emails/{item['id']}/preview")).json()
    assert "Confirm email" in preview["html"]

    entry = await db.get(EmailLog, uuid.UUID(item["id"]))
    entry.status = "sent"
    await db.commit()
    assert (await client.get(f"/api/v1/admin/emails/{item['id']}/preview")).status_code == 409


async def test_admin_retry_failed_email(client, accounts, login, db):
    entry = await _queued(db, accounts)
    entry.status = "failed"
    await db.commit()
    await login("admin@queneth.test")
    res = await client.post(f"/api/v1/admin/emails/{entry.id}/retry")
    assert res.status_code == 200
    await db.refresh(entry)
    assert entry.status == "mocked"  # re-queued, then delivered in mock mode


async def test_notifications_are_owner_scoped(client, accounts, login, db):
    db.add(Notification(user_id=accounts.seller.id, type="x", payload={"title": "secret"}))
    await db.commit()
    note = await db.scalar(select(Notification))
    await login("buyer@queneth.test")
    assert (await client.get("/api/v1/notifications")).json()["items"] == []
    assert (await client.post(f"/api/v1/notifications/{note.id}/read")).status_code == 404
    await login("seller@queneth.test")
    assert (await client.post(f"/api/v1/notifications/{note.id}/read")).status_code == 200
    assert (await client.get("/api/v1/notifications/unread-count")).json() == {"unread": 0}


async def test_seeded_users_are_verified(db, accounts):
    user = await db.scalar(select(User).where(User.email == "buyer@queneth.test"))
    assert user is not None
