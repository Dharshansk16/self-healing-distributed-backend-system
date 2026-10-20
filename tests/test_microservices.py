"""
Tests for Target Microservices:
- api-gateway (Port 8000)
- auth-service (Port 8001)
- order-service (Port 8002)
- payment-service (Port 8003)
- inventory-service (Port 8004)
"""

import pytest
from starlette.testclient import TestClient

from tests.conftest import load_service_app

auth_app = load_service_app("auth-service")
payment_app = load_service_app("payment-service")
inventory_app = load_service_app("inventory-service")
order_app = load_service_app("order-service")
gateway_app = load_service_app("api-gateway")


# -----------------------------------------------------------------------------
# Auth Service Tests
# -----------------------------------------------------------------------------

def test_auth_service_health():
    client = TestClient(auth_app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "auth-service"
    assert "pid" in data


def test_auth_service_verify_valid():
    client = TestClient(auth_app)
    resp = client.post("/verify", json={"auth_token": "valid_token_xyz", "user_id": "alice"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["user_id"] == "alice"
    assert data["status"] == "authorized"


def test_auth_service_verify_invalid():
    client = TestClient(auth_app)
    resp = client.post("/verify", json={"auth_token": "invalid", "user_id": "malicious"})
    assert resp.status_code == 401


# -----------------------------------------------------------------------------
# Payment Service Tests
# -----------------------------------------------------------------------------

def test_payment_service_health():
    client = TestClient(payment_app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "payment-service"


def test_payment_service_charge_success():
    client = TestClient(payment_app)
    resp = client.post("/charge", json={"order_id": "ord-123", "amount": 59.99, "payment_token": "approved"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["order_id"] == "ord-123"
    assert data["amount"] == 59.99
    assert data["payment_id"].startswith("pay-")


def test_payment_service_charge_decline():
    client = TestClient(payment_app)
    resp = client.post("/charge", json={"order_id": "ord-123", "amount": 59.99, "payment_token": "decline"})
    assert resp.status_code == 402


# -----------------------------------------------------------------------------
# Inventory Service Tests
# -----------------------------------------------------------------------------

def test_inventory_service_health():
    client = TestClient(inventory_app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "inventory-service"


def test_inventory_service_reserve_success():
    client = TestClient(inventory_app)
    resp = client.post("/reserve", json={"product_id": "prod-100", "quantity": 5, "order_id": "ord-test-1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "reserved"
    assert data["product_id"] == "prod-100"
    assert data["quantity"] == 5
    assert data["reservation_id"].startswith("res-")


def test_inventory_service_reserve_out_of_stock():
    client = TestClient(inventory_app)
    resp = client.post("/reserve", json={"product_id": "out_of_stock", "quantity": 1})
    assert resp.status_code == 409
    data = resp.json()
    assert data["detail"]["status"] == "out_of_stock"


# -----------------------------------------------------------------------------
# Order Service Tests (with mocked downstream branches: inventory & payment)
# -----------------------------------------------------------------------------

def test_order_service_health():
    client = TestClient(order_app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "order-service"


@pytest.mark.asyncio
async def test_order_service_create_order_mocked(monkeypatch):
    import httpx

    async def mock_post(self, url, json=None, headers=None):
        class MockResponse:
            def __init__(self, code, data):
                self.status_code = code
                self.is_error = code >= 400
                self._data = data

            def json(self):
                return self._data

        if "/reserve" in str(url):
            return MockResponse(
                200,
                {
                    "reservation_id": "res-mock-123",
                    "status": "reserved",
                    "product_id": json["product_id"],
                    "quantity": json["quantity"],
                    "message": "Inventory reserved",
                },
            )
        elif "/charge" in str(url):
            return MockResponse(
                200,
                {
                    "payment_id": "pay-mocked-123",
                    "status": "success",
                    "amount": json["amount"],
                },
            )
        return MockResponse(404, {})

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    client = TestClient(order_app)
    resp = client.post(
        "/orders",
        json={"product_id": "prod_1", "quantity": 2, "amount": 80.0, "user_id": "user_42"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "confirmed"
    assert data["payment_id"] == "pay-mocked-123"
    assert data["reservation_id"] == "res-mock-123"
    assert data["amount"] == 80.0


@pytest.mark.asyncio
async def test_order_service_reserve_out_of_stock_returns_409(monkeypatch):
    import httpx

    async def mock_post(self, url, json=None, headers=None):
        class MockResponse:
            def __init__(self, code, data):
                self.status_code = code
                self.is_error = code >= 400
                self._data = data

            def json(self):
                return self._data

        if "/reserve" in str(url):
            return MockResponse(409, {"detail": {"status": "out_of_stock"}})
        return MockResponse(200, {"payment_id": "pay-123", "status": "success"})

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    client = TestClient(order_app)
    resp = client.post(
        "/orders",
        json={"product_id": "out_of_stock", "quantity": 1, "amount": 50.0, "user_id": "u1"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["status"] == "out_of_stock"


@pytest.mark.asyncio
async def test_order_service_reserve_error_returns_502(monkeypatch):
    import httpx

    async def mock_post(self, url, json=None, headers=None):
        class MockResponse:
            def __init__(self, code, data):
                self.status_code = code
                self.is_error = code >= 400
                self._data = data

            def json(self):
                return self._data

        if "/reserve" in str(url):
            return MockResponse(500, {"detail": "Internal server error"})
        return MockResponse(200, {"payment_id": "pay-123", "status": "success"})

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    client = TestClient(order_app)
    resp = client.post(
        "/orders",
        json={"product_id": "prod_1", "quantity": 1, "amount": 50.0, "user_id": "u1"},
    )
    assert resp.status_code == 502
    assert resp.json()["detail"]["service"] == "inventory-service"


# -----------------------------------------------------------------------------
# API Gateway Tests
# -----------------------------------------------------------------------------

def test_gateway_health():
    client = TestClient(gateway_app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "api-gateway"


@pytest.mark.asyncio
async def test_gateway_checkout_flow_mocked(monkeypatch):
    import httpx

    async def mock_post(self, url, json=None, headers=None):
        class MockResponse:
            def __init__(self, code, data):
                self.status_code = code
                self.is_error = code >= 400
                self._data = data

            def json(self):
                return self._data

        if "/verify" in str(url):
            return MockResponse(200, {"valid": True, "user_id": json.get("user_id", "u1"), "status": "authorized"})
        elif "/orders" in str(url):
            return MockResponse(
                201,
                {
                    "order_id": "ord-gw-123",
                    "status": "confirmed",
                    "payment_id": "pay-gw-456",
                    "reservation_id": "res-gw-789",
                    "amount": json["amount"],
                    "product_id": json["product_id"],
                    "quantity": json["quantity"],
                    "user_id": json["user_id"],
                    "message": "Order created",
                },
            )
        return MockResponse(404, {})

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    client = TestClient(gateway_app)
    resp = client.post(
        "/api/v1/checkout",
        json={
            "user_id": "alice",
            "auth_token": "valid_token",
            "product_id": "prod_99",
            "quantity": 3,
            "amount": 149.99,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "confirmed"
    assert data["order_id"] == "ord-gw-123"
    assert data["payment_id"] == "pay-gw-456"
    assert data["reservation_id"] == "res-gw-789"
    assert data["checkout_id"].startswith("chk-")
    assert "X-Request-ID" in resp.headers


@pytest.mark.asyncio
async def test_gateway_unauthorized_token(monkeypatch):
    import httpx

    async def mock_post(self, url, json=None, headers=None):
        class MockResponse:
            status_code = 401
            is_error = True

            def json(self):
                return {"detail": "unauthorized"}

        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    client = TestClient(gateway_app)
    resp = client.post(
        "/api/v1/checkout",
        json={"user_id": "alice", "auth_token": "invalid"},
    )
    assert resp.status_code == 401
