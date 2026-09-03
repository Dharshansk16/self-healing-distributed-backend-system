from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.failure.failure_simulation import crash, cpu_spike, latency, memory_leak, random_error

router = APIRouter()

def _ensure_enabled() -> None:
    if not settings.failure_simulation_enabled:
        raise HTTPException(status_code=404, detail="Failure simulation is disabled")

@router.get("/simulate/crash")
def simulate_crash() -> None:
    _ensure_enabled()
    crash()

@router.get("/simulate/cpu-spike")
def simulate_cpu_spike() -> None:
    _ensure_enabled()
    cpu_spike()

@router.get("/simulate/memory-leak")
def simulate_memory_leak() -> None:
    _ensure_enabled()
    memory_leak()

@router.get("/simulate/latency")
def simulate_latency() -> dict[str, str]:
    _ensure_enabled()
    latency()
    return {"message": "Latency simulation complete"}  

@router.get("/simulate/random-error")
def simulate_random_error() -> dict[str, str]:
    _ensure_enabled()
    random_error()
    return {"message": "No error triggered"}
