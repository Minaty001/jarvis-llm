"""
Memory Pydantic Models

Defines schemas for storing, searching, and listing memories.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MemoryStoreRequest(BaseModel):
    """
    Request body for POST /memory/store.

    Attributes:
        type: Memory type classification.
        content: The memory content text.
        importance: Importance score (0.0 to 1.0).
        expires_at: Optional TTL — omit for permanent memories.
        metadata: Optional key-value metadata.
    """
    type: str = Field(
        ...,
        pattern="^(fact|preference|context|history)$",
        description="Memory type: fact, preference, context, or history.",
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The memory content text.",
    )
    importance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Importance score (0.0 to 1.0).",
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Optional TTL. Omit for permanent memories.",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional key-value metadata.",
    )


class MemorySearchRequest(BaseModel):
    """
    Request body for GET /memory/search (query params).

    Attributes:
        query: Natural language search query.
        type: Optional filter by memory type.
        limit: Max results to return.
        min_importance: Minimum importance threshold.
    """
    query: str = Field(..., min_length=1, description="Natural language search query.")
    type: Optional[str] = Field(
        default=None,
        pattern="^(fact|preference|context|history)$",
    )
    limit: int = Field(default=10, ge=1, le=100)
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)


class MemoryResponse(BaseModel):
    """
    A single memory object returned by list/search endpoints.

    Attributes:
        id: Unique memory identifier.
        type: Memory type.
        content: Memory content text.
        importance: Importance score.
        score: Semantic search similarity score (only in search results).
        created_at: When the memory was stored.
        expires_at: TTL, if set.
        metadata: Additional metadata.
    """
    id: UUID
    type: str
    content: str
    importance: float
    score: Optional[float] = Field(
        default=None,
        description="Semantic similarity score (search only).",
    )
    created_at: datetime
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
