import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "AppError handled",
        extra={"status_code": exc.status_code, "error_message": exc.message, "path": _request.url.path},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )
