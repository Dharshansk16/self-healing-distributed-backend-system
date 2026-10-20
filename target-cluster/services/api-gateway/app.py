"""
API Gateway (Port 8000)
Entry point microservice for all incoming client traffic.
Coordinates user authentication via Auth Service and order execution via Order Service.
Part of the Autonomous Self-Healing Microservices Mesh.
"""

import logging
import os
import sys
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
import httpx
from pydantic import BaseModel, Field

# Support imports when running as standalone module or within target-cluster
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from common.telemetry_and_chaos import setup_telemetry_and_chaos

SERVICE_NAME = "api-gateway"
PORT = int(os.getenv("PORT", "8000"))
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001").rstrip("/")
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://localhost:8002").rstrip("/")
DOWNSTREAM_TIMEOUT_SEC = float(os.getenv("DOWNSTREAM_TIMEOUT_SEC", "5.0"))

app = FastAPI(
    title=SERVICE_NAME,
    description="Primary API Gateway routing client requests to downstream microservices",
    version="1.0.0",
)

logger = logging.getLogger(SERVICE_NAME)
chaos_mgr = setup_telemetry_and_chaos(app, service_name=SERVICE_NAME)


class CheckoutRequest(BaseModel):
    user_id: str = Field(default="user_123", description="User identifier")
    auth_token: str = Field(default="valid_token", description="Session / Auth token")
    product_id: str = Field(default="prod_1", description="Item identifier")
    quantity: int = Field(default=1, gt=0, description="Quantity")
    amount: float = Field(default=49.99, gt=0, description="Total amount in USD")
    payment_token: str = Field(default="approved", description="Payment authorization token")


class CheckoutResponse(BaseModel):
    checkout_id: str
    status: str
    user_id: str
    order_id: str
    payment_id: str
    reservation_id: Optional[str] = None
    amount: float
    message: str


@app.post("/api/v1/checkout", response_model=CheckoutResponse, status_code=200, tags=["Checkout"])
@app.post("/checkout", response_model=CheckoutResponse, status_code=200, tags=["Checkout"])
async def checkout(req: CheckoutRequest, request: Request) -> CheckoutResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    checkout_id = f"chk-{uuid4().hex[:12]}"
    headers = {"X-Request-ID": request_id}

    logger.info(
        f"Incoming checkout request {checkout_id} for user {req.user_id} (${req.amount:.2f})",
        extra={"request_id": request_id},
    )

    # 1. Authenticate with Auth Service
    auth_payload = {"auth_token": req.auth_token, "user_id": req.user_id}
    try:
        async with httpx.AsyncClient(timeout=DOWNSTREAM_TIMEOUT_SEC) as client:
            auth_resp = await client.post(
                f"{AUTH_SERVICE_URL}/verify",
                json=auth_payload,
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        logger.error(f"Auth service timed out during checkout {checkout_id}: {exc}", extra={"request_id": request_id})
        raise HTTPException(
            status_code=504,
            detail={"status": "gateway_timeout", "service": "auth-service", "message": "Auth service timed out"},
        )
    except httpx.RequestError as exc:
        logger.error(f"Auth service unreachable during checkout {checkout_id}: {exc}", extra={"request_id": request_id})
        raise HTTPException(
            status_code=503,
            detail={"status": "unavailable", "service": "auth-service", "message": "Auth service is unreachable"},
        )

    if auth_resp.status_code == 401 or auth_resp.is_error:
        logger.warning(f"Checkout {checkout_id} unauthorized by Auth Service", extra={"request_id": request_id})
        raise HTTPException(
            status_code=401,
            detail={"status": "unauthorized", "message": "Invalid authentication credentials"},
        )

    # 2. Forward Order to Order Service
    order_payload = {
        "product_id": req.product_id,
        "quantity": req.quantity,
        "amount": req.amount,
        "user_id": req.user_id,
        "payment_token": req.payment_token,
    }
    try:
        async with httpx.AsyncClient(timeout=DOWNSTREAM_TIMEOUT_SEC) as client:
            order_resp = await client.post(
                f"{ORDER_SERVICE_URL}/orders",
                json=order_payload,
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        logger.error(f"Order service timed out during checkout {checkout_id}: {exc}", extra={"request_id": request_id})
        raise HTTPException(
            status_code=504,
            detail={"status": "gateway_timeout", "service": "order-service", "message": "Order service timed out"},
        )
    except httpx.RequestError as exc:
        logger.error(f"Order service unreachable during checkout {checkout_id}: {exc}", extra={"request_id": request_id})
        raise HTTPException(
            status_code=503,
            detail={"status": "unavailable", "service": "order-service", "message": "Order service is unreachable"},
        )

    if order_resp.status_code == 402:
        logger.warning(f"Payment declined during checkout {checkout_id}", extra={"request_id": request_id})
        raise HTTPException(
            status_code=402,
            detail={"status": "payment_declined", "message": "Payment was declined by payment gateway"},
        )

    if order_resp.is_error:
        logger.error(
            f"Order service returned error {order_resp.status_code} for checkout {checkout_id}",
            extra={"request_id": request_id},
        )
        raise HTTPException(
            status_code=502,
            detail={
                "status": "bad_gateway",
                "service": "order-service",
                "message": f"Order service failed with status {order_resp.status_code}",
            },
        )

    order_data = order_resp.json()
    order_id = order_data.get("order_id", "unknown")
    payment_id = order_data.get("payment_id", "unknown")
    reservation_id = order_data.get("reservation_id")

    logger.info(
        f"Checkout {checkout_id} completed successfully (Order: {order_id}, Payment: {payment_id}, Reservation: {reservation_id})",
        extra={"request_id": request_id},
    )

    return CheckoutResponse(
        checkout_id=checkout_id,
        status="confirmed",
        user_id=req.user_id,
        order_id=order_id,
        payment_id=payment_id,
        reservation_id=reservation_id,
        amount=req.amount,
        message="Checkout succeeded and order confirmed",
    )


@app.get("/")
def root():
    return {
        "service": SERVICE_NAME,
        "status": "operational",
        "port": PORT,
        "auth_service_url": AUTH_SERVICE_URL,
        "order_service_url": ORDER_SERVICE_URL,
        "endpoints": ["/api/v1/checkout", "/checkout", "/health", "/metrics", "/telemetry/snapshot"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
