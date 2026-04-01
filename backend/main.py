"""FastAPI application entry point."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from core.deps import get_settings
from core.exceptions import AppError, app_error_handler
from core.logging import setup_logging
from db.engine import create_tables, init_engine
from routers import eval, execute, generate, history, skills, upload

logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize DB engine and create tables on startup."""
    setup_logging(settings.log_level, settings.log_format)
    logger.info("Application starting", extra={"database_url": settings.database_url})
    init_engine(settings.database_url)
    await create_tables()
    # Seed prompts into Langfuse if enabled
    if settings.langfuse_enabled:
        try:
            from infra.prompt_manager import seed_prompts
            seed_prompts(settings)
        except Exception:
            logger.warning("Failed to seed prompts into Langfuse, continuing without it", exc_info=True)
    yield
    logger.info("Application shutdown")


app = FastAPI(
    title="Excel x NL Tool Builder API",
    version="1.0.0",
    description="Generate Python code for Excel processing from natural language.",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        request_id = uuid.uuid4().hex[:8]
        start = time.monotonic()
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
            },
        )
        try:
            response = await call_next(request)
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            return response
        except Exception:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise


app.add_middleware(LoggingMiddleware)

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(generate.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(execute.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(skills.router, prefix="/api")
app.include_router(eval.router, prefix="/api")
