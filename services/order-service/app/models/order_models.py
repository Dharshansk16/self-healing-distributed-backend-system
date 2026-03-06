from pydantic import BaseModel

"""
Order Models
    -Defines the data models for order requests and responses using Pydantic.
    -These models ensure data validation and serialization for the order service.
"""
class OrderRequest(BaseModel):
    product_id: int
    quantity: int
    amount: float

class OrderResponse(BaseModel):
    order_id: str
    status: str
    message: str

