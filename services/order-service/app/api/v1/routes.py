from fastapi import APIRouter
from app.models.order_models import OrderRequest, OrderResponse
from app.services.order_service import create_order

router= APIRouter()

"""
    API Routes
    -Defines the main API endpoints for the order service
    including health checks and order creation.
"""

@router.get("/health")
def health_check():
    return {"status": "Order Service is healthy"}

@router.post("/order")
def create_new_orer(order_request: OrderRequest) -> OrderResponse:
    return create_order(order_request)