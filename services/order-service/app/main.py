import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.failure_routes import router as failure_router
from app.api.v1.routes import router as api_router
from app.core.config import settings
from app.core.logging_config import setup_logging

"""
Main Application
    -Initializes the FastAPI application and configures it with the necessary routers 
    and logging settings for order services app.
"""
setup_logging()

app = FastAPI(title=settings.service_name, version=settings.service_version)

app.include_router(api_router, prefix="/api/v1")
app.include_router(failure_router, prefix="/api/v1")

logger = logging.getLogger(__name__)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled error", extra={"request_id": getattr(request.state, "request_id", None)})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
