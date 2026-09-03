from threading import Lock
from uuid import uuid4

from app.models.inventory_models import ProductResponse, ReservationResponse


class InventoryService:
    def __init__(self) -> None:
        self._stock = {1: 100, 2: 50, 3: 0}
        self._reservations: dict[str, tuple[int, int]] = {}
        self._lock = Lock()

    def get_product(self, product_id: int) -> ProductResponse | None:
        with self._lock:
            quantity = self._stock.get(product_id)
            if quantity is None:
                return None
            return ProductResponse(product_id=product_id, available_quantity=quantity)

    def reserve(self, product_id: int, quantity: int) -> ReservationResponse | None:
        with self._lock:
            available = self._stock.get(product_id)
            if available is None or available < quantity:
                return None
            self._stock[product_id] -= quantity
            reservation_id = str(uuid4())
            self._reservations[reservation_id] = (product_id, quantity)
            return ReservationResponse(
                reservation_id=reservation_id,
                product_id=product_id,
                quantity=quantity,
                status="reserved",
            )

    def release(self, reservation_id: str) -> bool:
        with self._lock:
            reservation = self._reservations.pop(reservation_id, None)
            if reservation is None:
                return False
            product_id, quantity = reservation
            self._stock[product_id] += quantity
            return True


inventory_service = InventoryService()
