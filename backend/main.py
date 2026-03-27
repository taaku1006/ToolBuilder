"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.deps import get_settings
from core.exceptions import AppError, app_error_handler
from db.engine import create_tables, init_engine
from routers import execute, generate, history, skills, upload

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize DB engine and create tables on startup."""
    init_engine(settings.database_url)
    await create_tables()
    yield


app = FastAPI(
    title="Excel x NL Tool Builder API",
    version="1.0.0",
    description="Generate Python code for Excel processing from natural language.",
    lifespan=lifespan,
)

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
