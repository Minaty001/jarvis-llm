"""
JWT Authentication Middleware

Validates JWT access tokens on protected routes and injects the
authenticated user identity into request state.

Routes are classified as:
    - Public: No auth required (listed in PUBLIC_PATHS).
    - Protected: JWT validation required.
"""

from typing import Optional

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from jose import JWTError

from utils.jwt_handler import decode_token

logger = structlog.get_logger()


# Paths that do NOT require authentication
PUBLIC_PATHS = {
    "/api/auth/refresh",
    "/api/health",
    "/api/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
}

# Pattern for paths that vary (e.g., trailing slashes)
PUBLIC_PATH_PREFIXES = (
    "/api/auth/refresh/",
)


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that validates JWT tokens on protected routes.

    On success, sets `request.state.user_id` (UUID string) and
    `request.state.device_id` for downstream handlers.

    On failure, returns 401 Unauthorized.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip auth for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # Extract and validate token
        token = self._extract_token(request)
        if not token:
            return JSONResponse(
                status_code=401,
                content={
                    "code": "MISSING_TOKEN",
                    "message": "Authentication required. Provide a Bearer token.",
                    "status_code": 401,
                },
            )

        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
            device_id = payload.get("device_id")

            if not user_id or not device_id:
                return JSONResponse(
                    status_code=401,
                    content={
                        "code": "INVALID_TOKEN",
                        "message": "Token payload is missing required fields.",
                        "status_code": 401,
                    },
                )

            # Validate token type is 'access'
            if payload.get("type") != "access":
                return JSONResponse(
                    status_code=401,
                    content={
                        "code": "INVALID_TOKEN_TYPE",
                        "message": "Use an access token, not a refresh token.",
                        "status_code": 401,
                    },
                )

            # Inject identity into request state
            request.state.user_id = user_id
            request.state.device_id = device_id

        except JWTError as e:
            logger.warning("jwt_validation_failed", path=request.url.path, error=str(e))
            return JSONResponse(
                status_code=401,
                content={
                    "code": "TOKEN_EXPIRED_OR_INVALID",
                    "message": "Token is expired or invalid. Please login again.",
                    "status_code": 401,
                },
            )

        return await call_next(request)

    def _is_public_path(self, path: str) -> bool:
        """
        Check if a path is publicly accessible without authentication.

        Args:
            path: The request URL path.

        Returns:
            True if the path is public.
        """
        if path in PUBLIC_PATHS:
            return True
        if path.startswith(PUBLIC_PATH_PREFIXES):
            return True
        # Allow root and static assets publicly
        if path == "/":
            return True
        if path.endswith((".html", ".css", ".js", ".ico", ".png", ".jpg", ".jpeg", ".svg", ".map")):
            return True
        return False

    def _extract_token(self, request: Request) -> Optional[str]:
        """
        Extract Bearer token from the Authorization header.

        Args:
            request: Incoming HTTP request.

        Returns:
            The JWT string, or None if not present/invalid format.
        """
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        return auth_header[len("Bearer "):].strip()
