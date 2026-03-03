from uuid import uuid4
from app.models.order_models import OrderRequest , OrderResponse
import logging

logger = logging.getLogger(__name__)

def create_order(order_request: OrderRequest) -> OrderResponse:
    logger.info(f"Creatng order for product_id: {order_request.product_id}")
    order_id = str(uuid4())
    return OrderResponse(
        order_id=order_id,
        status="success",
        message="Order created successfully"
    )