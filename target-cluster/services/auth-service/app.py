"""
Auth Service (Port 8001)
Validates caller credentials and session tokens.
Part of the Autonomous Self-Healing Microservices Mesh.
"""

import logging
import os
import sys
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

# Support imports when running as standalone module or within target-cluster
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from common.telemetry_and_chaos import setup_telemetry_and_chaos

SERVICE_NAME = "auth-service"
PORT = int(os.getenv("PORT", "8001"))

app = FastAPI(
    title=SERVICE_NAME,
    description="Authenticates incoming requests from API Gateway",
    version="1.0.0",
)

logger = logging.getLogger(SERVICE_NAME)
chaos_mgr = setup_telemetry_and_chaos(app, service_name=SERVICE_NAME)


class VerifyRequest(BaseModel):
    auth_token: str = Field(..., description="Bearer/session authentication token")
    user_id: Optional[str] = Field(default=None, description="Optional user ID")


class VerifyResponse(BaseModel):
    valid: bool
    user_id: str
    status: str
    scope: str = "customer:checkout"


@app.post("/verify", response_model=VerifyResponse, tags=["Authentication"])
@app.post("/api/v1/verify", response_model=VerifyResponse, tags=["Authentication"])
def verify_token(req: VerifyRequest, request: Request) -> VerifyResponse:
    request_id = getattr(request.state, "request_id", "unknown")

    # Rejection rule for negative testing
    if not req.auth_token or req.auth_token.lower() in ("invalid", "expired", "revoked", "deny"):
        logger.warning(f"Authentication rejected for token '{req.auth_token}'", extra={"request_id": request_id})
        raise HTTPException(
            status_code=401,
            detail={"status": "unauthorized", "message": "Provided authentication token is invalid or expired"},
        )

    user_id = req.user_id or "user_default"
    logger.info(f"Authentication verified for user {user_id}", extra={"request_id": request_id})
    return VerifyResponse(
        valid=True,
        user_id=user_id,
        status="authorized",
        scope="customer:checkout",
    )


@app.get("/")
def root():
    return {
        "service": SERVICE_NAME,
        "status": "operational",
        "port": PORT,
        "endpoints": ["/verify", "/api/v1/verify", "/health", "/metrics", "/telemetry/snapshot"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
