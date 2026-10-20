"""
Order Service (Port 8002)
Mid-tier microservice that coordinates order creation across downstream dependencies:
- Branch A: Payment Service (charges payment)
- Branch B: Inventory Service (reserves stock)
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

SERVICE_NAME = "order-service"
PORT = int(os.getenv("PORT", "8002"))
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8003").rstrip("/")
INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8004").rstrip("/")
DOWNSTREAM_TIMEOUT_SEC = float(os.getenv("DOWNSTREAM_TIMEOUT_SEC", "5.0"))

app = FastAPI(
    title=SERVICE_NAME,
    description="Coordinates order fulfillment and downstream payment & inventory operations",
    version="1.1.0",
)

logger = logging.getLogger(SERVICE_NAME)
chaos_mgr = setup_telemetry_and_chaos(app, service_name=SERVICE_NAME)


class OrderRequest(BaseModel):
    product_id: str = Field(default="prod_1", description="Identifier for item to purchase")
    quantity: int = Field(default=1, gt=0, description="Number of units")
    amount: float = Field(..., gt=0, description="Total order amount")
    user_id: Optional[str] = Field(default="user_123", description="Buyer account identifier")
    payment_token: str = Field(default="approved", description="Card or account payment token")


class OrderResponse(BaseModel):
    order_id: str
    status: str
    user_id: str
    product_id: str
    quantity: int
    amount: float
    payment_id: str
    reservation_id: Optional[str] = None
    message: str


@app.post("/orders", response_model=OrderResponse, status_code=201, tags=["Orders"])
@app.post("/api/v1/orders", response_model=OrderResponse, status_code=201, tags=["Orders"])
async def create_order(req: OrderRequest, request: Request) -> OrderResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    order_id = f"ord-{uuid4().hex[:12]}"
    user_id = req.user_id or "user_default"
    headers = {"X-Request-ID": request_id}

    logger.info(
        f"Processing order {order_id} for user {user_id}: {req.quantity}x {req.product_id} = ${req.amount:.2f}",
        extra={"request_id": request_id},
    )

    # 1. Branch B: Reserve stock in Inventory Service
    reserve_payload = {
        "product_id": req.product_id,
        "quantity": req.quantity,
        "order_id": order_id,
    }
    try:
        async with httpx.AsyncClient(timeout=DOWNSTREAM_TIMEOUT_SEC) as client:
            reserve_resp = await client.post(
                f"{INVENTORY_SERVICE_URL}/reserve",
                json=reserve_payload,
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        logger.error(f"Inventory service timed out for order {order_id}: {exc}", extra={"request_id": request_id})
        raise HTTPException(
            status_code=504,
            detail={"status": "gateway_timeout", "service": "inventory-service", "message": "Inventory service timed out"},
        )
    except httpx.RequestError as exc:
        logger.error(f"Inventory service connection failed for order {order_id}: {exc}", extra={"request_id": request_id})
        raise HTTPException(
            status_code=503,
            detail={"status": "unavailable", "service": "inventory-service", "message": "Inventory service is unreachable"},
        )

    if reserve_resp.status_code == 409:
        logger.warning(f"Stock reservation failed for order {order_id}: out of stock", extra={"request_id": request_id})
        raise HTTPException(
            status_code=409,
            detail={"status": "out_of_stock", "message": f"Product '{req.product_id}' is currently out of stock"},
        )

    if reserve_resp.is_error:
        logger.error(
            f"Inventory service error {reserve_resp.status_code} for order {order_id}",
            extra={"request_id": request_id},
        )
        raise HTTPException(
            status_code=502,
            detail={
                "status": "bad_gateway",
                "service": "inventory-service",
                "message": f"Inventory service returned error code {reserve_resp.status_code}",
            },
        )

    reserve_data = reserve_resp.json()
    reservation_id = reserve_data.get("reservation_id", f"res-{uuid4().hex[:10]}")

    # 2. Branch A: Process charge with Payment Service
    charge_payload = {
        "order_id": order_id,
        "amount": req.amount,
        "payment_token": req.payment_token,
    }

    try:
        async with httpx.AsyncClient(timeout=DOWNSTREAM_TIMEOUT_SEC) as client:
            charge_resp = await client.post(
                f"{PAYMENT_SERVICE_URL}/charge",
                json=charge_payload,
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        logger.error(f"Payment service timed out for order {order_id}: {exc}", extra={"request_id": request_id})
        raise HTTPException(
            status_code=504,
            detail={"status": "gateway_timeout", "service": "payment-service", "message": "Payment service timed out"},
        )
    except httpx.RequestError as exc:
        logger.error(f"Payment service connection failed for order {order_id}: {exc}", extra={"request_id": request_id})
        raise HTTPException(
            status_code=503,
            detail={"status": "unavailable", "service": "payment-service", "message": "Payment service is unreachable"},
        )

    if charge_resp.status_code == 402:
        logger.warning(f"Payment declined for order {order_id}", extra={"request_id": request_id})
        raise HTTPException(
            status_code=402,
            detail={"status": "declined", "message": "Payment method was declined by payment gateway"},
        )

    if charge_resp.is_error:
        logger.error(
            f"Payment service error {charge_resp.status_code} for order {order_id}",
            extra={"request_id": request_id},
        )
        raise HTTPException(
            status_code=502,
            detail={
                "status": "bad_gateway",
                "service": "payment-service",
                "message": f"Payment service returned error code {charge_resp.status_code}",
            },
        )

    payment_data = charge_resp.json()
    payment_id = payment_data.get("payment_id", f"pay-{uuid4().hex[:10]}")

    logger.info(
        f"Order {order_id} confirmed successfully (Payment: {payment_id}, Reservation: {reservation_id})",
        extra={"request_id": request_id},
    )

    return OrderResponse(
        order_id=order_id,
        status="confirmed",
        user_id=user_id,
        product_id=req.product_id,
        quantity=req.quantity,
        amount=req.amount,
        payment_id=payment_id,
        reservation_id=reservation_id,
        message="Order created, inventory reserved, and payment captured successfully",
    )


@app.get("/")
def root():
    return {
        "service": SERVICE_NAME,
        "status": "operational",
        "port": PORT,
        "downstream_payment_url": PAYMENT_SERVICE_URL,
        "downstream_inventory_url": INVENTORY_SERVICE_URL,
        "endpoints": ["/orders", "/api/v1/orders", "/health", "/metrics", "/telemetry/snapshot"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
