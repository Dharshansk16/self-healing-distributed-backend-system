from pydantic import BaseModel, Field


class PaymentRequest(BaseModel):
    order_id: str = Field(min_length=1)
    amount: float = Field(gt=0)
    payment_token: str = Field(min_length=1)


class PaymentResponse(BaseModel):
    payment_id: str
    order_id: str
    status: str
