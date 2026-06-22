"""
Authentication API Endpoints

Handles device-based authentication using Android device IDs.
JWT tokens are issued on login and refreshed via refresh tokens.

Flow:
    1. Device registers/logs in with device_id → gets JWT pair
    2. Client uses access_token for subsequent requests
    3. When access_token expires, use refresh_token to get a new pair
    4. On logout, sessions are invalidated
"""

from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field

from database.client import supabase_client
from schemas.common import ErrorResponse, SuccessResponse
from utils.config import settings
from utils.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_id_from_token,
)
from utils.validators import is_valid_device_id

logger = structlog.get_logger()
router = APIRouter()


# ── Request/Response Schemas ──

class LoginRequest(BaseModel):
    """Request body for POST /auth/login."""
    device_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique Android device identifier.",
    )


class RefreshRequest(BaseModel):
    """Request body for POST /auth/refresh."""
    refresh_token: str = Field(..., min_length=1, description="Valid refresh token.")


class AuthTokens(BaseModel):
    """JWT token pair returned on login/refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_hours: int


class UserInfo(BaseModel):
    """Current user information."""
    id: str
    device_id: str
    created_at: datetime


# ── Endpoints ──

@router.post("/login", response_model=SuccessResponse[AuthTokens])
async def login(request: LoginRequest, http_request: Request):
    """
    Register or login a device.

    If the device_id is new, a user record is created.
    If it already exists, the existing user is looked up.

    Returns a JWT access token + refresh token pair.
    """
    device_id = request.device_id.strip()

    if not is_valid_device_id(device_id):
        return ErrorResponse(
            code="INVALID_DEVICE_ID",
            message="Device ID contains invalid characters.",
            status_code=400,
        )

    # Upsert user: create if new, return existing if known
    try:
        result = await supabase_client.table("users").upsert(
            {"device_id": device_id},
            on_conflict="device_id",
        ).execute()

        if not result.data:
            # User didn't exist, create explicitly
            result = await supabase_client.table("users").insert(
                {"device_id": device_id}
            ).execute()

        user = result.data[0]
        user_id = user["id"]
        created = user.get("created_at")

    except Exception as e:
        logger.exception("user_upsert_failed", device_id=device_id, error=str(e))
        return ErrorResponse(
            code="USER_CREATE_FAILED",
            message="Failed to register user. Please try again.",
            status_code=500,
        )

    # Generate tokens
    access_token = create_access_token(device_id, user_id)
    refresh_token = create_refresh_token(device_id, user_id)
    expires_at = datetime.now(timezone.utc).replace(
        hour=(datetime.now(timezone.utc).hour + settings.jwt_expiry_hours) % 24
    )

    # Store session
    client_host = http_request.client.host if http_request.client else "unknown"
    user_agent = http_request.headers.get("User-Agent", "unknown")

    try:
        await supabase_client.table("sessions").insert({
            "user_id": user_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at.isoformat(),
            "ip_address": client_host,
            "user_agent": user_agent,
        }).execute()
    except Exception as e:
        logger.warning("session_create_failed", user_id=user_id, error=str(e))
        # Non-critical: client can still use tokens

    logger.info(
        "user_logged_in",
        user_id=user_id,
        device_id=device_id,
        is_new=created is not None,
    )

    return SuccessResponse(data=AuthTokens(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in_hours=settings.jwt_expiry_hours,
    ))


@router.post("/refresh", response_model=SuccessResponse[AuthTokens])
async def refresh(request: RefreshRequest):
    """
    Exchange a valid refresh token for a new access token + refresh token.

    The old refresh token is invalidated after use (rotation).
    """
    try:
        payload = decode_token(request.refresh_token)
    except Exception:
        return ErrorResponse(
            code="INVALID_REFRESH_TOKEN",
            message="Refresh token is expired or invalid.",
            status_code=401,
        )

    # Verify it's actually a refresh token
    if payload.get("type") != "refresh":
        return ErrorResponse(
            code="INVALID_TOKEN_TYPE",
            message="Provided token is not a refresh token.",
            status_code=401,
        )

    user_id = payload.get("sub")
    device_id = payload.get("device_id")

    if not user_id or not device_id:
        return ErrorResponse(
            code="INVALID_TOKEN_PAYLOAD",
            message="Token payload is malformed.",
            status_code=401,
        )

    # Invalidate old session
    try:
        await supabase_client.table("sessions").update(
            {"expires_at": datetime.now(timezone.utc).isoformat()}
        ).eq("refresh_token", request.refresh_token).execute()
    except Exception:
        pass  # Non-critical

    # Issue new tokens
    new_access = create_access_token(device_id, user_id)
    new_refresh = create_refresh_token(device_id, user_id)

    # Store new session
    try:
        await supabase_client.table("sessions").insert({
            "user_id": user_id,
            "access_token": new_access,
            "refresh_token": new_refresh,
            "expires_at": datetime.now(timezone.utc).replace(
                hour=(datetime.now(timezone.utc).hour + settings.jwt_expiry_hours) % 24
            ).isoformat(),
        }).execute()
    except Exception as e:
        logger.warning("new_session_create_failed", error=str(e))

    logger.info("token_refreshed", user_id=user_id)

    return SuccessResponse(data=AuthTokens(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in_hours=settings.jwt_expiry_hours,
    ))


@router.post("/logout")
async def logout(request: Request):
    """
    Invalidate the current session.

    Requires a valid access token in the Authorization header.
    """
    user_id = getattr(request.state, "user_id", None)
    auth_header = request.headers.get("Authorization", "")

    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):].strip()
        try:
            await supabase_client.table("sessions").update(
                {"expires_at": datetime.now(timezone.utc).isoformat()}
            ).eq("access_token", token).execute()
        except Exception as e:
            logger.warning("session_invalidation_failed", error=str(e))

    logger.info("user_logged_out", user_id=user_id)
    return {"success": True, "message": "Logged out successfully."}


@router.get("/me", response_model=SuccessResponse[UserInfo])
async def get_current_user(request: Request):
    """
    Get the currently authenticated user's information.

    Requires a valid access token.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return ErrorResponse(
            code="UNAUTHENTICATED",
            message="Not authenticated.",
            status_code=401,
        )

    try:
        result = await supabase_client.table("users").select("*").eq("id", user_id).execute()
        if not result.data:
            return ErrorResponse(
                code="USER_NOT_FOUND",
                message="User not found.",
                status_code=404,
            )
        user = result.data[0]
        return SuccessResponse(data=UserInfo(
            id=user["id"],
            device_id=user["device_id"],
            created_at=user["created_at"],
        ))
    except Exception as e:
        logger.exception("get_user_failed", user_id=user_id, error=str(e))
        return ErrorResponse(
            code="INTERNAL_ERROR",
            message="Failed to retrieve user info.",
            status_code=500,
        )
