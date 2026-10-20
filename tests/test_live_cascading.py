"""
End-to-end integration test verifying live network requests across all 5 microservices,
cascading gray failure latency propagation across branching DAG branches, and remediation reset.
"""

import time
import httpx
import pytest

from run_local_cluster import cmd_start, cmd_stop, check_health, SERVICES


@pytest.fixture(scope="module", autouse=True)
def live_cluster():
    """Starts local cluster before tests, stops after."""
    cmd_start(foreground=False)
    # Ensure all are healthy
    time.sleep(1.0)
    for s in SERVICES:
        assert check_health(s["port"]), f"Service {s['name']} failed to start on port {s['port']}"
    yield
    cmd_stop(silent=True)


def test_live_end_to_end_checkout_and_cascading_latency():
    with httpx.Client(timeout=10.0) as client:
        # 1. Normal Checkout
        resp = client.post(
            "http://localhost:8000/api/v1/checkout",
            json={
                "user_id": "test_e2e_user",
                "auth_token": "valid_token",
                "product_id": "item_123",
                "quantity": 2,
                "amount": 99.99,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "confirmed"
        assert "order_id" in data
        assert "payment_id" in data
        assert "reservation_id" in data and data["reservation_id"] is not None

        # 2. Inject Gray Failure (400ms latency) in downstream leaf: payment-service (port 8003)
        fault_resp = client.post(
            "http://localhost:8003/debug/fault/latency",
            json={"delay_ms": 400.0, "jitter_ms": 10.0, "enabled": True},
        )
        assert fault_resp.status_code == 200

        # 3. Observe Cascading Latency at API Gateway (port 8000)
        t_start = time.perf_counter()
        slow_resp = client.post(
            "http://localhost:8000/api/v1/checkout",
            json={
                "user_id": "test_e2e_user",
                "auth_token": "valid_token",
                "product_id": "item_123",
                "quantity": 1,
                "amount": 49.99,
            },
        )
        duration = time.perf_counter() - t_start
        assert slow_resp.status_code == 200
        assert duration >= 0.38, f"Expected cascading latency >= 0.38s, observed {duration:.3f}s"

        # 4. Critical Gray Failure verification: /health endpoints on payment and gateway remain FAST (< 50ms)
        t_h1 = time.perf_counter()
        h_pay = client.get("http://localhost:8003/health")
        dt_pay = time.perf_counter() - t_h1
        assert h_pay.status_code == 200
        assert dt_pay < 0.05, f"Payment /health took {dt_pay:.3f}s"

        t_h2 = time.perf_counter()
        h_gw = client.get("http://localhost:8000/health")
        dt_gw = time.perf_counter() - t_h2
        assert h_gw.status_code == 200
        assert dt_gw < 0.05, f"Gateway /health took {dt_gw:.3f}s"

        # 5. Reset remediation on payment-service
        reset_resp = client.post("http://localhost:8003/debug/fault/reset")
        assert reset_resp.status_code == 200
        assert reset_resp.json()["status"] == "reset_complete"

        # 6. Verify Gateway latency recovers
        t_fast = time.perf_counter()
        fast_resp = client.post(
            "http://localhost:8000/api/v1/checkout",
            json={
                "user_id": "test_e2e_user",
                "auth_token": "valid_token",
                "product_id": "item_123",
                "quantity": 1,
                "amount": 49.99,
            },
        )
        dt_fast = time.perf_counter() - t_fast
        assert fast_resp.status_code == 200
        assert dt_fast < 0.20, f"Expected latency recovery, took {dt_fast:.3f}s"


def test_live_inventory_service_cascading_latency():
    """Verify Branch B (inventory-service port 8004) latency injection cascades to API Gateway."""
    with httpx.Client(timeout=10.0) as client:
        # 1. Inject 350ms delay in inventory-service
        fault_resp = client.post(
            "http://localhost:8004/debug/fault/latency",
            json={"delay_ms": 350.0, "jitter_ms": 10.0, "enabled": True},
        )
        assert fault_resp.status_code == 200

        # 2. Observe cascading latency at API Gateway
        t_start = time.perf_counter()
        resp = client.post(
            "http://localhost:8000/api/v1/checkout",
            json={
                "user_id": "test_e2e_user",
                "auth_token": "valid_token",
                "product_id": "item_branch_b",
                "quantity": 1,
                "amount": 25.0,
            },
        )
        duration = time.perf_counter() - t_start
        assert resp.status_code == 200
        assert duration >= 0.33, f"Expected cascading latency >= 0.33s from inventory-service, observed {duration:.3f}s"
        assert resp.json()["status"] == "confirmed"
        assert resp.json()["reservation_id"] is not None

        # 3. Reset inventory fault
        reset_resp = client.post("http://localhost:8004/debug/fault/reset")
        assert reset_resp.status_code == 200
        assert reset_resp.json()["status"] == "reset_complete"

