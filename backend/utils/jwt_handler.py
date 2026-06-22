"""
JWT Token Operations

Handles creation, validation, and decoding of JWT access tokens
and refresh tokens for device-based authentication.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt

from utils.config import settings


def create_access_token(device_id: str, user_id: UUID) -> str:
    """
    Create a signed JWT access token.

    The token encodes the device identity and user ID, with an
    expiration time configured in settings.

    Args:
        device_id: Unique Android device identifier.
        user_id: The user's UUID in the database.

    Returns:
        str: Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "device_id": device_id,
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_expiry_hours),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(device_id: str, user_id: UUID) -> str:
    """
    Create a signed JWT refresh token with a longer expiry.

    Args:
        device_id: Unique Android device identifier.
        user_id: The user's UUID in the database.

    Returns:
        str: Encoded JWT refresh token string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "device_id": device_id,
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_expiry_days),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.

    Args:
        token: The JWT string to decode.

    Returns:
        dict: The decoded payload.

    Raises:
        JWTError: If the token is expired, malformed, or signature invalid.
    """
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def get_user_id_from_token(token: str) -> Optional[UUID]:
    """
    Extract the user ID from a validated token payload.

    Args:
        token: A validated JWT payload dictionary.

    Returns:
        Optional[UUID]: The user's UUID, or None if missing/invalid.
    """
    try:
        payload = decode_token(token)
        return UUID(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        return None
