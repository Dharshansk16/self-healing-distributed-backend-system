from fastapi import APIRouter
from app.models.order_models import OrderRequest, OrderResponse
from app.failure.failure_simulation import (
    crash,
    cpu_spike,
    memory_leak,
    latency,
    random_error
)

router = APIRouter()

"""Failure Simulation Routes
    -Endpoints for simulating various failure scenarios in the order service.
"""

@router.get("/simulate/crash")
def simulate_crash():
    crash()

@router.get("/simulate/cpu-spike")
def simulate_cpu_spike():
    cpu_spike()

@router.get("/simulate/memory-leak")
def simulate_memory_leak():
    memory_leak()

@router.get("/simulate/latency")
def simulate_latency():
    latency()
    return {"message": "Latency simulation complete"}  

@router.get("/simulate/random-error")
def simulate_random_error():
    random_error()
    return {"message": "No error triggered"}

