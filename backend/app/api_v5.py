"""Experimental FastAPI endpoints for the V5 orchestrator.

This module is kept for experimentation and is not the default integration path.
Default runtime entrypoint is `app.main` with `/v1/triage/turn`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.orchestrator_v5 import load_config, orchestrate
from app.rate_limit import check_rate_limit, build_rl_key, MAX_REQ
from app.db import insert_feedback
from app.admin_v5 import router as admin_router

app = FastAPI(title="Pre-Triage API V5 (Experimental)")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Expo dev iÃƒÂ§in; prod'da kÃ„Â±sÃ„Â±tla
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load config once at startup
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
config = load_config(str(CONFIG_DIR))


# ---------- Request models ----------

class Profile(BaseModel):
    age: Optional[int] = Field(default=None, ge=0, le=120)
    pregnant: Optional[bool] = None


class TriageRequest(BaseModel):
    session_id: str = Field(..., min_length=6)
    text: str = Field(..., min_length=1, max_length=4000)
    locale: Optional[str] = "tr-TR"
    device_id: Optional[str] = None
    profile: Optional[Profile] = None


class FeedbackRequest(BaseModel):
    session_id: str
    rating: Literal[-1, 1]
    reason_code: Optional[str] = None
    free_text: Optional[str] = Field(default=None, max_length=1000)
    user_selected_specialty_id: Optional[int] = None


# ---------- Response models ----------

class EnvelopeResponse(BaseModel):
    envelope_type: Literal["QUESTION", "RESULT", "EMERGENCY", "SAME_DAY"]
    payload: Dict[str, Any]
    stop_reason: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


# ---------- Rate limit middleware ----------

@app.middleware("http")
async def rate_limit_mw(request: Request, call_next):
    # Sadece triage/feedback'e uygula
    if request.url.path in ("/v5/triage", "/v5/feedback"):
        ip = request.client.host if request.client else None
        device_id = request.headers.get("x-device-id")

        key = build_rl_key(ip, device_id)
        allowed, remaining, reset_in = check_rate_limit(key)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "reset_in_sec": reset_in},
                headers={
                    "X-RateLimit-Limit": str(MAX_REQ),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_in),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(MAX_REQ)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_in)
        return response

    return await call_next(request)


# ---------- Endpoints ----------

@app.post("/v5/triage", response_model=EnvelopeResponse)
def triage(req: TriageRequest, request: Request):
    """Single unified triage endpoint - returns envelope."""
    ip = request.client.host if request.client else None
    device_id = req.device_id or request.headers.get("x-device-id")

    env = orchestrate(
        req.text,
        req.session_id,
        config,
        ip=ip,
        device_id=device_id,
        profile=req.profile.model_dump() if req.profile else None,
    )
    
    return {
        "envelope_type": env.envelope_type.value,
        "payload": env.payload,
        "stop_reason": env.stop_reason,
        "meta": env.meta or {},
    }


@app.post("/v5/feedback")
def feedback(req: FeedbackRequest):
    """Submit user feedback for a session."""
    insert_feedback({
        "session_id": req.session_id,
        "rating": req.rating,
        "reason_code": req.reason_code,
        "free_text": req.free_text,
        "user_selected_specialty_id": req.user_selected_specialty_id,
    })
    return {"ok": True}


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "v5"}


app.include_router(admin_router)
