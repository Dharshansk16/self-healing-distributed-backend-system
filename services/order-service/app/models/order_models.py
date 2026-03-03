from pydantic import BaseModel

class OrderRequest(BaseModel):
    product_id: int
    quantity: int
    amount: float

class OrderResponse(BaseModel):
    order_id: str
    status: str
    message: str

