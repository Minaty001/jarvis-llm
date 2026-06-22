"""
Shared Pydantic Models

Common types used across multiple schemas: pagination parameters,
standard error responses, and generic API response wrappers.
"""

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field


# ── Generic Type Variable ──
T = TypeVar("T")


# ── Pagination ──
class PaginationParams(BaseModel):
    """
    Query parameters for paginated list endpoints.

    Attributes:
        page: 1-indexed page number (default: 1).
        limit: Number of items per page (default: 20, max: 100).
    """
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Wrapper for paginated list responses.

    Attributes:
        items: The list of items for the current page.
        total: Total number of items across all pages.
        page: Current page number.
        limit: Items per page.
        pages: Total number of pages.
    """
    items: List[T]
    total: int
    page: int
    limit: int
    pages: int


# ── Standard Error Response ──
class ErrorResponse(BaseModel):
    """
    Standard error response returned for all API errors.

    Attributes:
        code: Machine-readable error code (e.g. "BRAIN_TIMEOUT").
        message: Human-readable error description.
        status_code: HTTP status code.
        details: Optional additional error context.
    """
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    status_code: int = Field(..., ge=400, lt=600, description="HTTP status code")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error context")


# ── Success Response Wrapper ──
class SuccessResponse(BaseModel, Generic[T]):
    """
    Standard success response wrapper.

    Attributes:
        success: Always True for success responses.
        data: The response payload.
    """
    success: bool = True
    data: T


# ── Health Check ──
class HealthCheck(BaseModel):
    """
    Health check response body.

    Attributes:
        status: Overall service status ("healthy" or "unhealthy").
        version: Application version string.
        uptime_seconds: Seconds since application started.
        dependencies: Per-dependency health status.
    """
    status: str = Field(..., pattern="^(healthy|unhealthy)$")
    version: str
    uptime_seconds: float
    dependencies: Dict[str, str]


class ServiceStatus(BaseModel):
    """
    Individual external service status.

    Attributes:
        name: Service name (Brain, LLM, Skill).
        url: Service base URL.
        status: "healthy", "unhealthy", or "unreachable".
        response_time_ms: Last response time in milliseconds.
    """
    name: str
    url: str
    status: str = Field(..., pattern="^(healthy|unhealthy|unreachable)$")
    response_time_ms: Optional[float] = None
