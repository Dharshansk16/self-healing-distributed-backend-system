from fastapi import FastAPI, Request
from app.api.v1.routes import router as api_router
from app.api.v1.failure_routes import router as failure_router
from app.core.config import settings
from app.core.logging_config import setup_logging
from fastapi.responses import JSONResponse
import logging

"""
Main Application
    -Initializes the FastAPI application and configures it with the necessary routers 
    and logging settings for order services app.
"""
setup_logging()

app = FastAPI(title=settings.SERVICE_NAME, version = settings.SERVICE_VERSION)

app.include_router(api_router, prefix="/api/v1")
app.include_router(failure_router, prefix="/api/v1")

logger = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "ERROR",
            "message": "Internal server error"
        },
    )
