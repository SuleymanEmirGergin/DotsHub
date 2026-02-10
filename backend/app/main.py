"""FastAPI application entry point — V4 with unified /v1/triage/turn."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.models.database import init_db
from app.api.routes.session import router as session_router
from app.api.routes.message import router as message_router
from app.api.routes.triage import router as triage_router
from app.api.routes.feedback import router as feedback_router
from app.admin_api import router as admin_router
from app.admin_v5 import router as admin_v5_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: create tables
    try:
        await init_db()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Warning: Database init failed ({e}). The API will still start.")
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="Dotshub - Ön-Triyaj Asistanı API",
    description="Agentic AI tabanlı akıllı ön-triyaj sistemi (V4 — unified triage turn)",
    version="4.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes — /v1/ prefix
app.include_router(triage_router, prefix="/v1", tags=["Triage"])
app.include_router(feedback_router, prefix="/v1", tags=["Feedback"])
app.include_router(session_router, prefix="/v1", tags=["Session (legacy)"])
app.include_router(message_router, prefix="/v1", tags=["Message (legacy)"])
app.include_router(admin_router, prefix="/v1", tags=["Admin"])
app.include_router(admin_v5_router, tags=["Admin V5"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "dotshub-api", "version": "4.0.0"}
