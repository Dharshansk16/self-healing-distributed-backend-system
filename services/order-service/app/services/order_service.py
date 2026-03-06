from uuid import uuid4
from app.models.order_models import OrderRequest , OrderResponse
import logging

logger = logging.getLogger(__name__)

"""
Order Service
    -Core business logic for handling order creation and processing.
    -This service interacts with the order models to validate and process 
     incoming order requests,returning appropriate responses.
"""
def create_order(order_request: OrderRequest) -> OrderResponse:
    logger.info(f"Creatng order for product_id: {order_request.product_id}")
    order_id = str(uuid4())
    return OrderResponse(
        order_id=order_id,
        status="success",
        message="Order created successfully"
    )