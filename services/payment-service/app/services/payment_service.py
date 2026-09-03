from uuid import uuid4

from app.models.payment_models import PaymentRequest, PaymentResponse


def charge(payload: PaymentRequest) -> PaymentResponse | None:
    """Deterministic payment stub; use token 'decline' to exercise compensation."""
    if payload.payment_token == "decline":
        return None
    return PaymentResponse(payment_id=str(uuid4()), order_id=payload.order_id, status="captured")
