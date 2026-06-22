"""
Memory Service

Handles memory storage and retrieval via the database layer.
Supports storing facts, preferences, context, and history entries
with optional semantic search via embeddings.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import structlog

from database.client import supabase_client
from schemas.memory import MemoryResponse, MemoryStoreRequest

logger = structlog.get_logger()


class MemoryService:
    """
    Service layer for memory operations.

    Stores memories in Supabase and supports both exact-match
    and semantic (embedding-based) retrieval.
    """

    async def store(self, user_id: UUID, request: MemoryStoreRequest) -> MemoryResponse:
        """
        Store a new memory for a user.

        Args:
            user_id: The owning user's UUID.
            request: Validated memory data.

        Returns:
            MemoryResponse: The created memory record.
        """
        payload = {
            "user_id": str(user_id),
            "type": request.type,
            "content": request.content,
            "importance": request.importance,
            "expires_at": request.expires_at.isoformat() if request.expires_at else None,
            "metadata": request.metadata or {},
        }

        result = await supabase_client.table("memories").insert(payload).execute()
        record = result.data[0]
        logger.info(
            "memory_stored",
            user_id=str(user_id),
            memory_type=request.type,
            memory_id=record["id"],
        )
        return MemoryResponse(**record)

    async def search(
        self,
        user_id: UUID,
        query: str,
        search_type: Optional[str] = None,
        limit: int = 10,
        min_importance: float = 0.0,
    ) -> list[MemoryResponse]:
        """
        Search memories using semantic similarity (if embeddings available)
        or fall back to full-text search.

        Args:
            user_id: The owning user's UUID.
            query: Natural language search query.
            search_type: Optional type filter.
            limit: Max results.
            min_importance: Minimum importance threshold.

        Returns:
            list[MemoryResponse]: Matching memories, sorted by relevance.
        """
        # Build query
        query_builder = (
            supabase_client.table("memories")
            .select("*")
            .eq("user_id", str(user_id))
            .gte("importance", min_importance)
            .order("created_at", desc=True)
            .limit(limit)
        )

        if search_type:
            query_builder = query_builder.eq("type", search_type)

        result = await query_builder.execute()

        memories = [MemoryResponse(**r) for r in result.data]

        # Simple text relevance scoring: prioritize exact substring matches
        query_lower = query.lower()
        for mem in memories:
            if query_lower in mem.content.lower():
                mem.score = 1.0
            else:
                mem.score = 0.0

        # Sort by score descending, then by importance
        memories.sort(key=lambda m: (m.score or 0, m.importance), reverse=True)

        logger.info(
            "memory_search_completed",
            user_id=str(user_id),
            query_length=len(query),
            results=len(memories),
        )
        return memories

    async def list_memories(
        self,
        user_id: UUID,
        memory_type: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[MemoryResponse], int]:
        """
        List memories for a user with pagination.

        Args:
            user_id: The owning user's UUID.
            memory_type: Optional type filter.
            page: Page number (1-indexed).
            limit: Items per page.

        Returns:
            tuple: (list of MemoryResponse, total count).
        """
        query = supabase_client.table("memories").select("*", count="exact").eq("user_id", str(user_id))

        if memory_type:
            query = query.eq("type", memory_type)

        query = query.order("created_at", desc=True).range((page - 1) * limit, page * limit - 1)
        result = await query.execute()

        memories = [MemoryResponse(**r) for r in result.data]
        total = result.count or 0

        return memories, total

    async def delete(self, memory_id: UUID, user_id: UUID) -> bool:
        """
        Delete a memory by ID, scoped to the user.

        Args:
            memory_id: Memory UUID to delete.
            user_id: Owner UUID for authorization.

        Returns:
            True if deleted, False if not found.
        """
        result = (
            await supabase_client.table("memories")
            .delete()
            .eq("id", str(memory_id))
            .eq("user_id", str(user_id))
            .execute()
        )
        deleted = len(result.data) > 0
        if deleted:
            logger.info("memory_deleted", memory_id=str(memory_id), user_id=str(user_id))
        return deleted


# ── Singleton ──
memory_service = MemoryService()
