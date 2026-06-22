"""
Tests for Configuration Validation.
"""

import pytest
from pydantic import ValidationError


class TestConfigValidation:
    """Test suite for settings validation."""

    def test_valid_config_loads(self):
        """Valid config should load without errors."""
        from utils.config import settings
        assert settings.app_name == "jarvis-backend"
        assert settings.app_version == "1.0.0"

    def test_jwt_secret_validation(self):
        """Settings.validate() should reject short secrets."""
        from utils.config import Settings

        with pytest.raises(ValueError, match="JWT_SECRET must be at least 32 characters"):
            s = Settings(
                jwt_secret="short",
                brain_url="http://localhost:8001",
                llm_url="http://localhost:8002",
                skill_url="http://localhost:8003",
                supabase_url="https://test.supabase.co",
                supabase_api_key="test-key",
                supabase_service_key="test-service-key",
            )
            s.validate()
