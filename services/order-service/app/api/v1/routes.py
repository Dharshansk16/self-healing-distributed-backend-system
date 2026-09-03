from fastapi import APIRouter, Request

from app.models.order_models import OrderRequest, OrderResponse
from app.services.order_service import create_order

router = APIRouter()

@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "order-service"}

@router.post("/orders", response_model=OrderResponse, status_code=201)
def create_new_order(order_request: OrderRequest, request: Request) -> OrderResponse:
    return create_order(order_request, request.state.request_id)
