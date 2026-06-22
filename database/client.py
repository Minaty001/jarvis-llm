"""
Supabase Database Client

Provides a configured Supabase client for database operations.
Uses the service key (elevated privileges) for admin operations
and the anon key for user-scoped queries.
"""

from typing import Optional

import structlog
from supabase import Client, create_client

from utils.config import settings

logger = structlog.get_logger()


class SupabaseClient:
    """
    Wrapper around the Supabase Python client.

    Provides two access modes:
        - service_client: Uses service_role key for admin operations.
        - anon_client: Uses anon key for user-scoped operations.

    Usage:
        from database.client import supabase_client

        # Public query
        result = await supabase_client.table("conversations").select("*").execute()

        # Admin operation
        result = await supabase_client.service_table("users").delete().execute()
    """

    def __init__(self):
        self._service_client: Optional[Client] = None
        self._anon_client: Optional[Client] = None

    async def initialize(self):
        """
        Create Supabase client connections.

        Called during application startup.
        """
        if not settings.supabase_url or not settings.supabase_api_key:
            logger.warning("supabase_not_configured")
            return

        self._anon_client = create_client(
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_api_key,
        )

        if settings.supabase_service_key:
            self._service_client = create_client(
                supabase_url=settings.supabase_url,
                supabase_key=settings.supabase_service_key,
            )

        logger.info("supabase_client_initialized")

    @property
    def table(self):
        """
        Get a table reference using the anon client (user-scoped).

        Use for CRUD operations scoped to the authenticated user.
        """
        if not self._anon_client:
            raise RuntimeError("Supabase client not initialized. Call initialize() first.")
        return self._anon_client.table

    @property
    def service_table(self):
        """
        Get a table reference using the service client (admin).

        Use for administrative operations: user management,
        schema migrations, system-wide queries.
        """
        if not self._service_client:
            raise RuntimeError(
                "Service client not configured. Set SUPABASE_SERVICE_KEY."
            )
        return self._service_client.table

    async def health_check(self) -> dict:
        """
        Verify database connectivity with a simple query.

        Returns:
            dict: {"status": "healthy"} or {"status": "unhealthy", "error": ...}
        """
        try:
            result = await self.table("users").select("count", count="exact").limit(1).execute()
            return {"status": "healthy", "count": result.count}
        except Exception as e:
            logger.error("database_health_check_failed", error=str(e))
            return {"status": "unhealthy", "error": str(e)}

    async def close(self):
        """Cleanup client sessions."""
        self._service_client = None
        self._anon_client = None
        logger.info("supabase_client_closed")


# ── Singleton ──
supabase_client = SupabaseClient()
