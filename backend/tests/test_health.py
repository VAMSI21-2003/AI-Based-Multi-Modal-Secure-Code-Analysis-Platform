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
    body = response.json()
    assert body["status"] == "ok"
    # codebert_available is None ONLY when get_codebert() has genuinely
    # never run in this process. This test module deliberately skips
    # lifespan (see module docstring above) so it wouldn't trigger that
    # call itself -- but system_monitor's state is process-wide, and
    # pytest runs the whole backend/tests/ directory in one process, so
    # some OTHER test file collected earlier (one that does trigger
    # lifespan, or calls ml_bridge.run_prediction()/get_codebert()
    # directly) may have already resolved it to a real True/False before
    # this test's turn. Both are valid; only asserting the type (not a
    # specific value) keeps this test correct regardless of run order or
    # whether it's run in isolation.
    assert body["codebert_available"] in (None, True, False)


def test_health_endpoint_reports_codebert_availability_once_resolved():
    # Simulates what the real app guarantees via lifespan(): by the time any
    # request is served, get_codebert() has already run once and recorded a
    # real True/False. Sets that state directly via system_monitor rather
    # than calling the real (possibly slow, real-weights-downloading)
    # ml_bridge.get_codebert() -- this test is about /api/health's wiring to
    # that state, not about re-testing model loading itself.
    import system_monitor
    system_monitor.record_codebert_available(False)
    try:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["codebert_available"] is False
    finally:
        system_monitor.record_codebert_available(None)  # restore "unknown" for other tests


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
