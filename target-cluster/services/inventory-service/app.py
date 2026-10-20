"""
Inventory Service (Port 8004)
Leaf microservice that manages product stock levels and reservations.
Part of the Autonomous Self-Healing Microservices Mesh (Branch B of Order Service).
"""

import logging
import os
import sys
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

# Support imports when running as standalone module or within target-cluster
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from common.telemetry_and_chaos import setup_telemetry_and_chaos

SERVICE_NAME = "inventory-service"
PORT = int(os.getenv("PORT", "8004"))

app = FastAPI(
    title=SERVICE_NAME,
    description="Downstream leaf service managing product stock reservation and inventory levels",
    version="1.0.0",
)

logger = logging.getLogger(SERVICE_NAME)
chaos_mgr = setup_telemetry_and_chaos(app, service_name=SERVICE_NAME)


class ReserveRequest(BaseModel):
    product_id: str = Field(..., description="Identifier for item to reserve")
    quantity: int = Field(default=1, gt=0, description="Quantity of items to reserve")
    order_id: Optional[str] = Field(default=None, description="Associated order identifier")


class ReserveResponse(BaseModel):
    reservation_id: str
    product_id: str
    quantity: int
    order_id: Optional[str] = None
    status: str
    message: str


@app.post("/reserve", response_model=ReserveResponse, status_code=200, tags=["Inventory"])
@app.post("/api/v1/reserve", response_model=ReserveResponse, status_code=200, tags=["Inventory"])
@app.post("/api/v1/inventory/reserve", response_model=ReserveResponse, status_code=200, tags=["Inventory"])
def reserve_inventory(req: ReserveRequest, request: Request) -> ReserveResponse:
    request_id = getattr(request.state, "request_id", "unknown")

    # Out of stock / inventory rejection test rule
    if req.product_id.lower() in ("out_of_stock", "unavailable", "zero_stock", "backorder"):
        logger.warning(
            f"Stock reservation rejected for product {req.product_id} (requested {req.quantity} units)",
            extra={"request_id": request_id},
        )
        raise HTTPException(
            status_code=409,
            detail={"status": "out_of_stock", "message": f"Product '{req.product_id}' is currently out of stock"},
        )

    reservation_id = f"res-{uuid4().hex[:12]}"
    logger.info(
        f"Reserved {req.quantity} unit(s) of product {req.product_id} (Reservation: {reservation_id}, Order: {req.order_id})",
        extra={"request_id": request_id},
    )

    return ReserveResponse(
        reservation_id=reservation_id,
        product_id=req.product_id,
        quantity=req.quantity,
        order_id=req.order_id,
        status="reserved",
        message="Inventory reserved successfully",
    )


@app.get("/")
def root():
    return {
        "service": SERVICE_NAME,
        "status": "operational",
        "port": PORT,
        "endpoints": ["/reserve", "/api/v1/reserve", "/api/v1/inventory/reserve", "/health", "/metrics", "/telemetry/snapshot"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
