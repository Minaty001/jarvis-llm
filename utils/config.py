"""
Configuration Management

Loads, validates, and provides typed access to environment variables
using pydantic-settings. All configuration is validated once at startup
and accessible via the singleton `settings` object.

Usage:
    from utils.config import settings
    print(settings.brain_url)
"""

from typing import List, Optional
from typing_extensions import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.

    All values are read from .env or the process environment at
    instantiation. Critical fields are validated by `validate()`.
    """

    # ── App Identity ──
    app_name: str = "jarvis-backend"
    app_version: str = "1.0.0"
    environment: Literal["development", "production"] = "development"
    debug: bool = False

    # ── Server ──
    port: int = 8000
    host: str = "0.0.0.0"
    workers: int = 4

    # ── CORS ──
    cors_origins: List[str] = [
        "capacitor://localhost",
        "http://localhost",
        "http://localhost:8100",
        "http://localhost:3000",
        "*",  # Android WebView needs wide open; restrict in production
    ]

    # ── Security ──
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24
    refresh_token_expiry_days: int = 7

    # ── External Services ──
    # BRAIN_URL: URL of the Brain service deployed on Render.com
    # Example: https://jarvis-brain.onrender.com
    brain_url: str  # Required — set via BRAIN_URL env var on Render
    brain_timeout: int = 30

    llm_url: str = "http://localhost:8002"
    llm_timeout: int = 60
    skill_url: str = "http://localhost:8003"
    skill_timeout: int = 120

    # ── Supabase ──
    supabase_url: str
    supabase_api_key: str
    supabase_service_key: str

    # ── Logging ──
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    # ── Optional: Redis ──
    redis_url: Optional[str] = None

    class Config:
        """Pydantic settings configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra env vars

    def validate(self) -> None:
        """
        Validate critical configuration at startup.

        Raises:
            ValueError: If required security or connectivity values
                        fail validation.
        """
        errors = []

        # JWT secret must be long enough to prevent brute-force
        if len(self.jwt_secret) < 32:
            errors.append("JWT_SECRET must be at least 32 characters long")

        # Supabase URL must use HTTPS in production
        if self.environment == "production":
            if not self.supabase_url.startswith("https://"):
                errors.append("SUPABASE_URL must use HTTPS in production")

        # Validate URLs are well-formed
        for name, url in [
            ("BRAIN_URL", self.brain_url),
            ("LLM_URL", self.llm_url),
            ("SKILL_URL", self.skill_url),
            ("SUPABASE_URL", self.supabase_url),
        ]:
            if not url.startswith(("http://", "https://")):
                errors.append(f"{name} must start with http:// or https://")

        if errors:
            raise ValueError("\n".join(errors))


# ── Singleton ──
settings = Settings()
settings.validate()
