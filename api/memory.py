"""
Memory API Endpoints

Handles storing, searching, listing, and deleting memories.
Memories are user-scoped and support semantic search via embeddings.
"""

import structlog
from fastapi import APIRouter, Query, Request
from uuid import UUID

from schemas.common import ErrorResponse, PaginatedResponse, SuccessResponse
from schemas.memory import MemoryResponse, MemoryStoreRequest
from services.memory_service import memory_service

logger = structlog.get_logger()
router = APIRouter()


@router.post("/store", response_model=SuccessResponse[MemoryResponse])
async def store_memory(request_body: MemoryStoreRequest, http_request: Request):
    """
    Store a new memory for the authenticated user.

    Memory types: fact, preference, context, history.

    Args:
        request_body: Memory content, type, importance, and optional TTL.

    Returns:
        The created memory record.
    """
    user_id = getattr(http_request.state, "user_id", None)
    if not user_id:
        return ErrorResponse(code="UNAUTHENTICATED", message="Not authenticated.", status_code=401)

    try:
        memory = await memory_service.store(user_id, request_body)
        return SuccessResponse(data=memory)
    except Exception as e:
        logger.exception("memory_store_failed", user_id=user_id, error=str(e))
        return ErrorResponse(
            code="MEMORY_STORE_FAILED",
            message="Failed to store memory.",
            status_code=500,
        )


@router.get("/search", response_model=SuccessResponse[list[MemoryResponse]])
async def search_memories(
    request: Request,
    query: str = Query(..., min_length=1, description="Natural language search query"),
    type: str | None = Query(None, pattern="^(fact|preference|context|history)$"),
    limit: int = Query(10, ge=1, le=100),
    min_importance: float = Query(0.0, ge=0.0, le=1.0),
):
    """
    Search memories using semantic search.

    Results are sorted by relevance score, then by importance.

    Args:
        query: Natural language search phrase.
        type: Optional filter by memory type.
        limit: Maximum number of results.
        min_importance: Minimum importance threshold (0.0 to 1.0).

    Returns:
        List of matching memories with similarity scores.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return ErrorResponse(code="UNAUTHENTICATED", message="Not authenticated.", status_code=401)

    try:
        results = await memory_service.search(
            user_id=user_id,
            query=query,
            search_type=type,
            limit=limit,
            min_importance=min_importance,
        )
        return SuccessResponse(data=results)
    except Exception as e:
        logger.exception("memory_search_failed", user_id=user_id, error=str(e))
        return ErrorResponse(
            code="MEMORY_SEARCH_FAILED",
            message="Failed to search memories.",
            status_code=500,
        )


@router.get("/list", response_model=PaginatedResponse[MemoryResponse])
async def list_memories(
    request: Request,
    type: str | None = Query(None, pattern="^(fact|preference|context|history)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    List all memories for the authenticated user.

    Results are sorted by creation date (newest first).

    Args:
        type: Optional filter by memory type.
        page: Page number (1-indexed).
        limit: Items per page (max 100).

    Returns:
        Paginated list of memories.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return ErrorResponse(code="UNAUTHENTICATED", message="Not authenticated.", status_code=401)

    try:
        memories, total = await memory_service.list_memories(
            user_id=user_id,
            memory_type=type,
            page=page,
            limit=limit,
        )

        return PaginatedResponse(
            items=memories,
            total=total,
            page=page,
            limit=limit,
            pages=max(1, (total + limit - 1) // limit),
        )
    except Exception as e:
        logger.exception("list_memories_failed", user_id=user_id, error=str(e))
        return ErrorResponse(
            code="LIST_FAILED",
            message="Failed to list memories.",
            status_code=500,
        )


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: UUID,
    request: Request,
):
    """
    Delete a specific memory by ID.

    Args:
        memory_id: UUID of the memory to delete.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return ErrorResponse(code="UNAUTHENTICATED", message="Not authenticated.", status_code=401)

    try:
        deleted = await memory_service.delete(memory_id, user_id)
        if not deleted:
            return ErrorResponse(
                code="NOT_FOUND",
                message="Memory not found.",
                status_code=404,
            )
        return {"success": True, "message": "Memory deleted."}
    except Exception as e:
        logger.exception("delete_memory_failed", memory_id=str(memory_id), error=str(e))
        return ErrorResponse(
            code="DELETE_FAILED",
            message="Failed to delete memory.",
            status_code=500,
        )
