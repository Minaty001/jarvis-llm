"""
Tests for JWT Handler Utilities.
"""

import pytest
from uuid import uuid4
from jose import JWTError

from utils.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_id_from_token,
)


class TestJWTHandler:
    """Test suite for JWT token operations."""

    def setup_method(self):
        self.device_id = "android-test-device-12345"
        self.user_id = uuid4()

    def test_create_access_token(self):
        """Access token should be a valid JWT string."""
        token = create_access_token(self.device_id, self.user_id)
        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # header.payload.signature

    def test_create_refresh_token(self):
        """Refresh token should be a valid JWT string."""
        token = create_refresh_token(self.device_id, self.user_id)
        assert isinstance(token, str)
        assert len(token.split(".")) == 3

    def test_decode_valid_token(self):
        """Decoding a valid token should return the payload."""
        token = create_access_token(self.device_id, self.user_id)
        payload = decode_token(token)
        assert payload["sub"] == str(self.user_id)
        assert payload["device_id"] == self.device_id
        assert payload["type"] == "access"

    def test_decode_refresh_token_type(self):
        """Refresh token should have type='refresh'."""
        token = create_refresh_token(self.device_id, self.user_id)
        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_decode_invalid_token_raises(self):
        """Invalid tokens should raise JWTError."""
        with pytest.raises(JWTError):
            decode_token("this.is.not.a.valid.token")

    def test_decode_expired_token_raises(self):
        """Expired tokens should raise JWTError."""
        from datetime import datetime, timedelta, timezone
        from jose import jwt
        from utils.config import settings

        # Manually create an already-expired token
        payload = {
            "sub": str(self.user_id),
            "device_id": self.device_id,
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "type": "access",
        }
        expired_token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

        with pytest.raises(JWTError):
            decode_token(expired_token)

    def test_get_user_id_from_token(self):
        """Should extract user ID from a valid token."""
        token = create_access_token(self.device_id, self.user_id)
        extracted = get_user_id_from_token(token)
        assert extracted == self.user_id

    def test_get_user_id_from_invalid_token(self):
        """Should return None for invalid token."""
        extracted = get_user_id_from_token("invalid.token.here")
        assert extracted is None
