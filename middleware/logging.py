"""
Request/Response Logging Middleware

Logs every request and response as structured JSON lines using structlog.
Includes timing, status, method, path, and a truncated response body.
"""

import time
import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all incoming requests and outgoing responses.

    Assigns a unique X-Request-ID to each request if not already present.
    Logs are emitted as structured JSON for ingestion by log aggregators.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Assign or preserve request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        # Capture request start time
        start_time = time.time()

        # Log request
        logger.info(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query_string=str(request.url.query),
            client_host=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("User-Agent", "unknown"),
        )

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            # Log unhandled exceptions and re-raise
            elapsed = time.time() - start_time
            logger.exception(
                "request_unhandled_error",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                elapsed_ms=round(elapsed * 1000, 2),
                error=str(exc),
            )
            raise

        # Calculate elapsed time
        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        # Set response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(elapsed_ms)

        # Log response
        log_level = logger.warning if response.status_code >= 400 else logger.info
        log_level(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
            content_length=response.headers.get("content-length", "unknown"),
        )

        return response
