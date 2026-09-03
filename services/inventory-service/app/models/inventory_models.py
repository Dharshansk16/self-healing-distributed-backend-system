from pydantic import BaseModel, Field


class ReservationRequest(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class ReservationResponse(BaseModel):
    reservation_id: str
    product_id: int
    quantity: int
    status: str


class ProductResponse(BaseModel):
    product_id: int
    available_quantity: int
