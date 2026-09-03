import logging
from uuid import uuid4

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.models.order_models import OrderRequest, OrderResponse

logger = logging.getLogger(__name__)


def create_order(order_request: OrderRequest, request_id: str) -> OrderResponse:
    """Create an order after reserving inventory and charging payment."""
    order_id = str(uuid4())
    headers = {"X-Request-ID": request_id}
    try:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            reservation = client.post(
                f"{settings.inventory_service_url}/api/v1/inventory/reservations",
                json=order_request.model_dump(include={"product_id", "quantity"}),
                headers=headers,
            )
    except httpx.HTTPError as exc:
        logger.error("inventory request failed: %s", exc, extra={"request_id": request_id})
        raise HTTPException(status_code=503, detail="Inventory service is unavailable") from exc

    if reservation.status_code == 409:
        raise HTTPException(status_code=409, detail="Insufficient inventory")
    if reservation.is_error:
        logger.error(
            "inventory reservation failed with status %s",
            reservation.status_code,
            extra={"request_id": request_id},
        )
        raise HTTPException(status_code=502, detail="Inventory service rejected the request")

    reservation_id = reservation.json()["reservation_id"]
    try:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            payment = client.post(
                f"{settings.payment_service_url}/api/v1/payments",
                json={
                    "order_id": order_id,
                    "amount": order_request.amount,
                    "payment_token": order_request.payment_token,
                },
                headers=headers,
            )
    except httpx.HTTPError as exc:
        _release_reservation(reservation_id, headers)
        logger.error("payment request failed: %s", exc, extra={"request_id": request_id})
        raise HTTPException(status_code=503, detail="Payment service is unavailable") from exc

    if payment.is_error:
        _release_reservation(reservation_id, headers)
        logger.warning("payment declined", extra={"request_id": request_id})
        raise HTTPException(status_code=402, detail="Payment was declined")

    payment_id = payment.json()["payment_id"]
    logger.info("order created", extra={"request_id": request_id})
    return OrderResponse(
        order_id=order_id,
        status="confirmed",
        message="Order created successfully",
        reservation_id=reservation_id,
        payment_id=payment_id,
    )


def _release_reservation(reservation_id: str, headers: dict[str, str]) -> None:
    try:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            response = client.delete(
                f"{settings.inventory_service_url}/api/v1/inventory/reservations/{reservation_id}",
                headers=headers,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error(
            "reservation compensation failed: %s",
            exc,
            extra={"request_id": headers["X-Request-ID"]},
        )
