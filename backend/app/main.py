"""
RetailIQ GIS – FastAPI application entry point.
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.db.connection import init_pool, close_pool
from app.api.datasets import router as datasets_router
from app.api.analyses import router as analyses_router, suitability_router
from app.api.audit import router as audit_router
from app.api.reports import router as reports_router
from app.api.auth import router as auth_router
from app.api.validation import router as validation_router

import os
try:
    from azure.monitor.opentelemetry import configure_azure_monitor
    azure_configured = True
except ImportError:
    azure_configured = False

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Production Telemetry & Monitoring (Azure App Insights) ────────────────────
if azure_configured and os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    configure_azure_monitor(
        connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"),
        logger_name=__name__,
    )
    logger.info("Azure Monitor OpenTelemetry configured.")

# ── Rate limiter ───────────────────────────────────────────────────────────────

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],      # 200 req/min in dev (configurable via env)
    enabled=settings.app_env != "test",
)


# ── Application lifecycle ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    logger.info("RetailIQ backend starting (env=%s).", settings.app_env)
    init_pool()
    yield
    close_pool()
    logger.info("RetailIQ backend shut down.")


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="RetailIQ GIS API",
    description=(
        "Production geospatial intelligence platform for U.S. retail site selection. "
        "Provides dataset management, GIS analysis, suitability scoring, geocoding, "
        "report generation, and full audit logging."
    ),
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ─────────────────────────────────────────────────────────────────

# CORS — restrict in production via env
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# ── Request ID middleware ──────────────────────────────────────────────────────

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach a unique X-Request-ID to every request/response for traceability."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = str(duration_ms)
    return response


# ── Global error handlers ──────────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "detail": "The requested resource does not exist.",
            "path": str(request.url.path),
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error("Unhandled error [%s]: %s", request_id, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": "An unexpected error occurred.",
            "request_id": request_id,
        },
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(datasets_router)
app.include_router(analyses_router)
app.include_router(suitability_router)
app.include_router(audit_router)
app.include_router(reports_router)
app.include_router(validation_router)


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"], summary="Health check")
def health_check():
    return {
        "status": "ok",
        "env": settings.app_env,
        "version": "0.2.0",
        "city": f"{settings.city_name}, {settings.city_state}",
    }
