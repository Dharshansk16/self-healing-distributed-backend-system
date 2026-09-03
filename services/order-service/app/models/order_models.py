from pydantic import BaseModel, Field


class OrderRequest(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    amount: float = Field(gt=0)
    payment_token: str = Field(min_length=1, default="approved")


class OrderResponse(BaseModel):
    order_id: str
    status: str
    message: str
    reservation_id: str
    payment_id: str
