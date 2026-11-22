from app.api.v1.routers.health import get_db_pinger


async def test_health_ok(client):
    res = await client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["integrations_mode"] in {"live", "mock"}
    assert res.headers["X-Request-ID"]


async def test_health_degraded_when_db_down(app, client):
    async def down() -> bool:
        return False

    async def pinger():
        return down

    app.dependency_overrides[get_db_pinger] = pinger
    res = await client.get("/api/v1/health")
    assert res.status_code == 503
    assert res.json()["database"] == "unavailable"


async def test_request_id_is_echoed(client):
    res = await client.get("/api/v1/health", headers={"X-Request-ID": "abc123"})
    assert res.headers["X-Request-ID"] == "abc123"


async def test_openapi_and_docs_are_served(client):
    spec = await client.get("/api/v1/openapi.json")
    assert spec.status_code == 200
    assert "/api/v1/health" in spec.json()["paths"]
    assert (await client.get("/docs")).status_code == 200
