"""
Application-wide exception types and their FastAPI handlers.

Raising one of these anywhere in the app produces a consistent JSON error
shape: {"error": {"code": ..., "message": ..., "details": ...}}
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class JarvisError(Exception):
    """Base class for all Jarvis application errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(JarvisError):
    status_code = 404
    code = "not_found"


class ValidationError(JarvisError):
    status_code = 422
    code = "validation_error"


class AuthenticationError(JarvisError):
    status_code = 401
    code = "authentication_error"


class AuthorizationError(JarvisError):
    status_code = 403
    code = "authorization_error"


class ConflictError(JarvisError):
    status_code = 409
    code = "conflict"


class PluginError(JarvisError):
    status_code = 502
    code = "plugin_error"


class IntegrationError(JarvisError):
    status_code = 502
    code = "integration_error"


class AIProviderError(JarvisError):
    status_code = 502
    code = "ai_provider_error"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(JarvisError)
    async def jarvis_error_handler(request: Request, exc: JarvisError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                    "details": {},
                }
            },
        )
