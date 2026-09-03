import logging
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request

from app.core.logging_config import setup_logging
from app.models.payment_models import PaymentRequest, PaymentResponse
from app.services.payment_service import charge

setup_logging()
logger = logging.getLogger(__name__)
app = FastAPI(title="payment-service", version="1.0.0")


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/api/v1/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "payment-service"}


@app.post("/api/v1/payments", response_model=PaymentResponse, status_code=201)
def create_payment(payload: PaymentRequest, request: Request) -> PaymentResponse:
    payment = charge(payload)
    if payment is None:
        logger.warning("payment declined", extra={"request_id": request.state.request_id})
        raise HTTPException(status_code=402, detail="Payment was declined")
    logger.info("payment captured", extra={"request_id": request.state.request_id})
    return payment
