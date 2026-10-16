"""
Tests for Shared Telemetry & Chaos Middleware (target-cluster/common/telemetry_and_chaos.py)
Validates:
1. Naive /health liveness probe (remains HTTP 200 under latency and memory faults)
2. Prometheus /metrics scrape format
3. Fast JSON /telemetry/snapshot format
4. Deterministic Chaos injection (latency, memory leak, CPU burn, error spike)
5. Anti-flapping and remediation reset (/debug/fault/reset)
"""

import time
from fastapi import FastAPI
import pytest
from starlette.testclient import TestClient

from common.telemetry_and_chaos import setup_telemetry_and_chaos


@pytest.fixture
def test_app():
    app = FastAPI(title="test-service")
    chaos_mgr = setup_telemetry_and_chaos(app, service_name="test-service")

    @app.get("/business/work")
    def do_work():
        return {"status": "success", "result": 42}

    return app, chaos_mgr


def test_naive_health_probe(test_app):
    app, _ = test_app
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "test-service"
    assert "pid" in data


def test_prometheus_metrics_endpoint(test_app):
    app, _ = test_app
    client = TestClient(app)
    # Trigger a request to record metrics
    client.get("/business/work")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text
    assert "http_requests_total" in text
    assert "http_request_duration_seconds" in text


def test_telemetry_snapshot_endpoint(test_app):
    app, _ = test_app
    client = TestClient(app)
    # Trigger a request
    client.get("/business/work")
    resp = client.get("/telemetry/snapshot")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "test-service"
    assert "cpu_pct" in data
    assert "mem_mb" in data
    assert "rps" in data
    assert "error_rate" in data
    assert "latency_p50_ms" in data
    assert "latency_p99_ms" in data
    assert "active_faults" in data
    assert "recent_logs" in data
    assert isinstance(data["recent_logs"], list)


def test_gray_failure_latency_and_naive_health(test_app):
    """
    CRITICAL GRAY FAILURE TEST:
    Inject 200ms latency into business routes.
    Verify business route is delayed, but /health remains FAST and returns 200 OK!
    """
    app, chaos_mgr = test_app
    client = TestClient(app)

    # 1. Inject latency
    resp = client.post(
        "/debug/fault/latency",
        json={"delay_ms": 200.0, "jitter_ms": 10.0, "enabled": True},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "applied"

    # 2. Test business route is delayed
    start = time.perf_counter()
    b_resp = client.get("/business/work")
    duration = time.perf_counter() - start
    assert b_resp.status_code == 200
    assert duration >= 0.18, f"Expected business delay, got {duration}s"

    # 3. Test /health remains fast (< 50ms) and returns 200 OK!
    start_health = time.perf_counter()
    h_resp = client.get("/health")
    h_duration = time.perf_counter() - start_health
    assert h_resp.status_code == 200
    assert h_duration < 0.05, f"/health must not be affected by latency fault, got {h_duration}s"

    # 4. Reset
    reset_resp = client.post("/debug/fault/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "reset_complete"


def test_error_spike_fault_and_reset(test_app):
    app, chaos_mgr = test_app
    client = TestClient(app)

    # 1. Inject 100% error rate
    resp = client.post(
        "/debug/fault/error-spike",
        json={
            "failure_rate": 1.0,
            "http_code": 500,
            "exception_type": "DatabaseConnectionPoolExhaustedError",
            "enabled": True,
        },
    )
    assert resp.status_code == 200

    # 2. Business route should return 500
    err_resp = client.get("/business/work")
    assert err_resp.status_code == 500
    assert err_resp.json()["error"] == "DatabaseConnectionPoolExhaustedError"

    # 3. /health probe must STILL return 200 OK
    h_resp = client.get("/health")
    assert h_resp.status_code == 200

    # 4. Reset restores normal operation
    client.post("/debug/fault/reset")
    ok_resp = client.get("/business/work")
    assert ok_resp.status_code == 200
    assert ok_resp.json()["status"] == "success"


def test_memory_leak_and_cpu_burn_reset(test_app):
    app, chaos_mgr = test_app
    client = TestClient(app)

    # Test CPU burn activation and deactivation
    resp = client.post(
        "/debug/fault/cpu-burn",
        json={"utilization_target": 0.5, "enabled": True},
    )
    assert resp.status_code == 200

    # Test Memory leak configuration
    resp = client.post(
        "/debug/fault/memory-leak",
        json={"rate_mb_per_sec": 2.0, "enabled": True},
    )
    assert resp.status_code == 200

    # Check status endpoint
    status_resp = client.get("/debug/fault/status")
    status = status_resp.json()
    assert status["cpu_burn"]["enabled"] is True
    assert status["memory_leak"]["enabled"] is True

    # Reset all
    reset_resp = client.post("/debug/fault/reset")
    assert reset_resp.status_code == 200

    # Verify all disabled
    status_after = client.get("/debug/fault/status").json()
    assert status_after["cpu_burn"]["enabled"] is False
    assert status_after["memory_leak"]["enabled"] is False
    assert status_after["latency"]["enabled"] is False
    assert status_after["error_spike"]["enabled"] is False
