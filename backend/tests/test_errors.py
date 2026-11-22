"""Every failure path returns {"error": {"code", "message", "details"}}."""

from fastapi import Query

from app.core.errors import Conflict, PermissionDenied


def _assert_envelope(body: dict, code: str) -> None:
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert body["error"]["message"]


async def test_unknown_route_uses_envelope(client):
    res = await client.get("/api/v1/does-not-exist")
    assert res.status_code == 404
    _assert_envelope(res.json(), "not_found")


async def test_method_not_allowed_uses_envelope(client):
    res = await client.delete("/api/v1/health")
    assert res.status_code == 405
    _assert_envelope(res.json(), "method_not_allowed")


async def test_app_errors_and_validation(app, client):
    @app.get("/_t/forbidden")
    async def forbidden():
        raise PermissionDenied()

    @app.get("/_t/conflict")
    async def conflict():
        raise Conflict("Already taken.", details={"field": "email"})

    @app.get("/_t/validate")
    async def validate(qty: int = Query(ge=1)):
        return {"qty": qty}

    @app.get("/_t/boom")
    async def boom():
        raise RuntimeError("secret internals")

    res = await client.get("/_t/forbidden")
    assert res.status_code == 403
    _assert_envelope(res.json(), "permission_denied")

    res = await client.get("/_t/conflict")
    assert res.status_code == 409
    assert res.json()["error"]["details"] == {"field": "email"}

    res = await client.get("/_t/validate", params={"qty": 0})
    assert res.status_code == 422
    body = res.json()
    _assert_envelope(body, "validation_error")
    assert body["error"]["details"][0]["field"] == "qty"

    res = await client.get("/_t/boom")
    assert res.status_code == 500
    _assert_envelope(res.json(), "internal_error")
    assert "secret" not in res.text
