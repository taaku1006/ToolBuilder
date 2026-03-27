"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.deps import get_settings
from core.exceptions import AppError, app_error_handler
from routers import generate, upload

settings = get_settings()

app = FastAPI(
    title="Excel x NL Tool Builder API",
    version="1.0.0",
    description="Generate Python code for Excel processing from natural language.",
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
