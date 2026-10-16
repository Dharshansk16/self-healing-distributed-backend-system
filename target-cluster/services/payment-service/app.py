"""
Payment Service (Port 8003)
Leaf microservice that processes payment charges.
Part of the Autonomous Self-Healing Microservices Mesh.
"""

import logging
import os
import sys
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

# Support imports when running as standalone module or within target-cluster
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from common.telemetry_and_chaos import setup_telemetry_and_chaos

SERVICE_NAME = "payment-service"
PORT = int(os.getenv("PORT", "8003"))

app = FastAPI(
    title=SERVICE_NAME,
    description="Downstream leaf service handling credit charges and transactions",
    version="1.0.0",
)

logger = logging.getLogger(SERVICE_NAME)
chaos_mgr = setup_telemetry_and_chaos(app, service_name=SERVICE_NAME)


class ChargeRequest(BaseModel):
    order_id: str = Field(..., description="ID of the order to charge")
    amount: float = Field(..., gt=0, description="Amount in USD to charge")
    payment_token: str = Field(default="approved", description="Token to test approve/decline flows")


class ChargeResponse(BaseModel):
    payment_id: str
    order_id: str
    amount: float
    status: str
    message: str


@app.post("/charge", response_model=ChargeResponse, status_code=200, tags=["Payment"])
@app.post("/api/v1/charge", response_model=ChargeResponse, status_code=200, tags=["Payment"])
@app.post("/api/v1/payments", response_model=ChargeResponse, status_code=200, tags=["Payment"])
def process_charge(req: ChargeRequest, request: Request) -> ChargeResponse:
    request_id = getattr(request.state, "request_id", "unknown")

    # Payment rejection rule
    if req.payment_token.lower() in ("decline", "declined", "fail", "insufficient_funds"):
        logger.warning(
            f"Payment declined for order {req.order_id} with amount ${req.amount:.2f}",
            extra={"request_id": request_id},
        )
        raise HTTPException(
            status_code=402,
            detail={"status": "declined", "message": "Payment method was declined by payment gateway"},
        )

    payment_id = f"pay-{uuid4().hex[:12]}"
    logger.info(
        f"Payment {payment_id} successfully captured for order {req.order_id} (${req.amount:.2f})",
        extra={"request_id": request_id},
    )

    return ChargeResponse(
        payment_id=payment_id,
        order_id=req.order_id,
        amount=req.amount,
        status="success",
        message="Payment processed and captured successfully",
    )


@app.get("/")
def root():
    return {
        "service": SERVICE_NAME,
        "status": "operational",
        "port": PORT,
        "endpoints": ["/charge", "/api/v1/charge", "/health", "/metrics", "/telemetry/snapshot"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
