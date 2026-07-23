"""RFC 9457 (problem+json) error contract.

Every error response the API emits shares this shape so the OpenAPI contract has
a single, governed error schema (closes the gap flagged in Architecture §6).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_CONTENT_TYPE = "application/problem+json"


class AppError(Exception):
    """Base application error rendered as an RFC 9457 problem document."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "app_error"
    title: str = "Application error"

    def __init__(self, detail: str | None = None, *, code: str | None = None,
                 status_code: int | None = None, title: str | None = None,
                 extra: dict[str, Any] | None = None) -> None:
        self.detail = detail or self.title
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        if title:
            self.title = title
        self.extra = extra or {}
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    title = "Resource not found"


class AuthError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"
    title = "Authentication required or invalid"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    title = "Insufficient permissions"


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    title = "Too many requests"


class OtpInvalidError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "otp_invalid"
    title = "Invalid verification code"


class OtpExpiredError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "otp_expired"
    title = "Verification code expired"


class OtpAttemptsExceededError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "otp_attempts_exceeded"
    title = "Too many verification attempts"


def _problem(*, status_code: int, title: str, code: str, detail: str,
             instance: str, extra: dict[str, Any] | None = None) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"https://bluntly.ph/problems/{code}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
        "code": code,
    }
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status_code, content=body,
                        media_type=PROBLEM_CONTENT_TYPE)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return _problem(status_code=exc.status_code, title=exc.title, code=exc.code,
                        detail=exc.detail, instance=str(request.url), extra=exc.extra)

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _problem(status_code=exc.status_code, title="HTTP error",
                        code=f"http_{exc.status_code}", detail=str(exc.detail),
                        instance=str(request.url))

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # jsonable_encoder is required, not cosmetic: pydantic puts the constraint
        # value in each error's `ctx` (e.g. Decimal('0') for a `gt=0` Decimal
        # field), which json.dumps cannot serialize — emitting the raw errors
        # turns a 422 into a 500. Also drops the non-serializable `url` key.
        return _problem(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        title="Request validation failed", code="validation_error",
                        detail="One or more fields are invalid.",
                        instance=str(request.url),
                        extra={"errors": jsonable_encoder(exc.errors())})
