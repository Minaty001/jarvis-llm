"""
Chat & Conversation Pydantic Models

Defines request/response schemas for the chat endpoint and
conversation management.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Chat Request / Response ──

class ChatRequest(BaseModel):
    """
    Request body for POST /chat.

    Attributes:
        conversation_id: Optional — creates new conversation if omitted.
        message: The user's message text.
        context: Optional additional context (e.g. current screen, location).
        stream: Whether to stream the response via WebSocket.
    """
    conversation_id: Optional[UUID] = Field(
        default=None,
        description="Conversation ID. Omit to start a new conversation.",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The user's message text.",
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional context: current screen, location, etc.",
    )
    stream: bool = Field(
        default=False,
        description="If True, response is delivered via WebSocket.",
    )


class ChatResponse(BaseModel):
    """
    Response body for POST /chat.

    Attributes:
        conversation_id: The conversation this response belongs to.
        message_id: ID of the assistant's response message.
        response: The assistant's reply text.
        tokens_used: Total tokens consumed (prompt + completion).
        thinking: Optional chain-of-thought from Brain (if available).
    """
    conversation_id: UUID
    message_id: UUID
    response: str
    tokens_used: Optional[int] = None
    thinking: Optional[str] = Field(
        default=None,
        description="Brain's chain-of-thought (if available).",
    )


# ── Conversation Models ──

class ConversationCreate(BaseModel):
    """
    Request body for POST /conversations.

    Attributes:
        title: Optional display title for the conversation.
    """
    title: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional conversation title.",
    )


class ConversationUpdate(BaseModel):
    """
    Request body for PATCH /conversations/{id}.

    Attributes:
        title: New title for the conversation.
    """
    title: Optional[str] = Field(default=None, max_length=255)


class Conversation(BaseModel):
    """
    Conversation summary (used in list responses).

    Attributes:
        id: Unique conversation identifier.
        title: Conversation title.
        message_count: Number of messages in this conversation.
        last_message_at: Timestamp of the most recent message.
        created_at: When the conversation was created.
    """
    id: UUID
    title: Optional[str] = None
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    created_at: datetime


# ── Message Models ──

class MessageResponse(BaseModel):
    """
    A single message within a conversation.

    Attributes:
        id: Unique message identifier.
        role: "user" or "assistant".
        content: Message body text.
        tokens_used: Token count (completion only for assistant messages).
        created_at: When the message was created.
        metadata: Additional message metadata.
    """
    id: UUID
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str
    tokens_used: Optional[int] = None
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None


class ConversationDetail(Conversation):
    """
    Full conversation details including messages.

    Attributes:
        messages: All messages in the conversation, ordered by creation time.
    """
    messages: List["MessageResponse"] = []
