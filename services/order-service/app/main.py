from fastapi import FastAPI
from app.api.v1.routes import router as api_router
from app.api.v1.failure_routes import router as failure_router

app = FastAPI(title="Order Service")

app.include_router(api_router, prefix="/api/v1")
app.include_router(failure_router, prefix="/api/v1")