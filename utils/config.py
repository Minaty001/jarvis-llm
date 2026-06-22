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
    jwt_secret: Optional[str] = None
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
    supabase_url: Optional[str] = None
    supabase_api_key: Optional[str] = None
    supabase_service_key: Optional[str] = None

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

    def validate(self) -> List[str]:
        """
        Validate critical configuration at startup.

        Returns a list of warning/error messages instead of raising,
        so the app can start for health checks even if some config
        is missing. Callers can decide whether to block startup.

        Returns:
            List[str]: List of validation messages (empty if all good).
        """
        messages = []

        # JWT secret must be long enough to prevent brute-force
        if self.jwt_secret is None:
            messages.append("JWT_SECRET is not set — authentication will be disabled")
        elif len(self.jwt_secret) < 32:
            messages.append("JWT_SECRET must be at least 32 characters long")

        # Supabase URL must use HTTPS in production
        if self.supabase_url is None:
            messages.append("SUPABASE_URL is not set — database features will be unavailable")
        elif self.environment == "production":
            if not self.supabase_url.startswith("https://"):
                messages.append("SUPABASE_URL must use HTTPS in production")

        # Validate URLs are well-formed (skip if None)
        for name, url in [
            ("BRAIN_URL", self.brain_url),
            ("LLM_URL", self.llm_url),
            ("SKILL_URL", self.skill_url),
        ]:
            if url and not url.startswith(("http://", "https://")):
                messages.append(f"{name} must start with http:// or https://")

        if self.supabase_api_key is None:
            messages.append("SUPABASE_API_KEY is not set — database features will be unavailable")
        if self.supabase_service_key is None:
            messages.append("SUPABASE_SERVICE_KEY is not set — admin database features will be unavailable")

        return messages


# ── Singleton ──
settings = Settings()
# NOTE: .validate() is called at app startup in main.py's startup event,
# so the app can serve health checks even if some optional config is missing.
