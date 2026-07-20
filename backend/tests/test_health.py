# =============================================================================
# test_health.py -- smoke test for the FastAPI app wiring.
#
# Deliberately does NOT use `with TestClient(app) as client`, because that
# form triggers the app's lifespan (which pre-warms CodeBERT/XGBoost/Random
# Forest -- a real, ~20-30s cost by design, see main.py). Using the client
# directly still routes real requests through the real ASGI app without
# paying that cost, which is what a fast health check needs.
# =============================================================================

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_endpoint_returns_ok():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_app_registers_expected_routers():
    # Every router in main.py should have contributed at least one route
    # under its own prefix -- this fails loudly if a router import silently
    # broke or a router was removed from main.py without removing its file.
    # Read via the OpenAPI schema rather than app.routes directly, since the
    # internal route object shape is a FastAPI/Starlette implementation
    # detail that has changed across versions.
    paths = set(app.openapi()["paths"].keys())
    expected_prefixes = [
        "/api/scan", "/api/dashboard", "/api/history", "/api/analytics",
        "/api/knowledge", "/api/report", "/api/system", "/api/project",
        "/api/research", "/api/copilot", "/api/export", "/api/watch",
        "/api/github", "/api/gamification", "/api/search",
    ]
    for prefix in expected_prefixes:
        assert any(p.startswith(prefix) for p in paths), f"no route registered under {prefix}"
