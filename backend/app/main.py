"""FastAPI application entrypoint.

Publishes the governed OpenAPI 3.x contract (versioned, RFC 9457 error schema),
mounts the health probe and the v1 API, and wires CORS + structured logging.
"""

from __future__ import annotations

import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.api.v1.routes import health, redirect
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger

configure_logging()
log = get_logger("app")

# Fail fast in production if hard requirements aren't met (JWT secret, DB, CORS).
if settings.is_production:
    _issues = settings.production_issues()
    if _issues:
        raise RuntimeError("Production configuration invalid:\n  - " + "\n  - ".join(_issues))

# Docs are served unless explicitly disabled (e.g. a locked-down production).
_docs = "/docs" if settings.enable_docs else None

app = FastAPI(
    title="Bluntly.ph API",
    version=settings.app_version,
    description=(
        "Verified product review platform. All error responses use the "
        "RFC 9457 problem+json schema. Identity is a FastAPI-issued JWT (ADR-010)."
    ),
    openapi_url="/openapi.json" if settings.enable_docs else None,
    docs_url=_docs,
    redoc_url="/redoc" if settings.enable_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# Health + public referral redirect at root (no auth, no version prefix).
app.include_router(health.router)
app.include_router(redirect.router)
# Versioned API surface.
app.include_router(api_v1_router, prefix=settings.api_v1_prefix)


@app.on_event("startup")
def _log_startup() -> None:
    # Make the AnyIO threadpool ceiling explicit + tunable (sync endpoints run here).
    anyio.to_thread.current_default_thread_limiter().total_tokens = settings.threadpool_tokens
    log.info("startup", extra={"extra_fields": {
        "env": settings.app_env, "use_supabase": settings.use_supabase,
        "ai_provider": settings.ai_provider, "docs": settings.enable_docs,
        "threadpool_tokens": settings.threadpool_tokens}})


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"service": settings.product_id, "version": settings.app_version,
            "docs": _docs or "disabled"}
