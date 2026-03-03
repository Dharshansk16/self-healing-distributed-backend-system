from uuid import uuid4
from app.models.order_models import OrderRequest , OrderResponse


def create_order(order_request: OrderRequest) -> OrderResponse:
    order_id = str(uuid4())
    return OrderResponse(
        order_id=order_id,
        status="success",
        message="Order created successfully"
    )