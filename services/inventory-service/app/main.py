import logging
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response

from app.core.logging_config import setup_logging
from app.models.inventory_models import ProductResponse, ReservationRequest, ReservationResponse
from app.services.inventory_service import inventory_service

setup_logging()
logger = logging.getLogger(__name__)
app = FastAPI(title="inventory-service", version="1.0.0")


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/api/v1/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "inventory-service"}


@app.get("/api/v1/inventory/{product_id}", response_model=ProductResponse)
def get_inventory(product_id: int) -> ProductResponse:
    product = inventory_service.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.post("/api/v1/inventory/reservations", response_model=ReservationResponse, status_code=201)
def create_reservation(payload: ReservationRequest, request: Request) -> ReservationResponse:
    reservation = inventory_service.reserve(payload.product_id, payload.quantity)
    if reservation is None:
        logger.warning("inventory unavailable", extra={"request_id": request.state.request_id})
        raise HTTPException(status_code=409, detail="Insufficient inventory")
    logger.info("inventory reserved", extra={"request_id": request.state.request_id})
    return reservation


@app.delete("/api/v1/inventory/reservations/{reservation_id}", status_code=204)
def release_reservation(reservation_id: str, request: Request) -> Response:
    if not inventory_service.release(reservation_id):
        raise HTTPException(status_code=404, detail="Reservation not found")
    logger.info("inventory reservation released", extra={"request_id": request.state.request_id})
    return Response(status_code=204)
