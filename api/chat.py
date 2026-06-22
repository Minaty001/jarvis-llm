"""
Chat API Endpoints

Handles sending messages to the Brain service and managing
conversations. The Brain does all reasoning — this layer just
validates, routes, and returns responses.
"""

import structlog
from fastapi import APIRouter, Path, Query, Request
from uuid import UUID

from database.client import supabase_client
from schemas.chat import (
    ChatRequest,
    ChatResponse,
    Conversation,
    ConversationCreate,
    ConversationDetail,
    MessageResponse,
)
from schemas.common import ErrorResponse, PaginatedResponse, SuccessResponse
from services.brain_client import brain_client

logger = structlog.get_logger()
router = APIRouter()


# ── Chat ──

@router.post("/chat", response_model=SuccessResponse[ChatResponse])
async def send_chat_message(request: ChatRequest, http_request: Request):
    """
    Send a message to the Brain for processing.

    The Brain handles reasoning, LLM calls, and skill orchestration.
    This endpoint is a transparent relay.

    Args:
        request: Validated chat request with message and optional context.
        http_request: Incoming HTTP request (for user_id extraction).

    Returns:
        ChatResponse: The Brain's response with conversation_id and message_id.
    """
    user_id = getattr(http_request.state, "user_id", None)
    if not user_id:
        return ErrorResponse(
            code="UNAUTHENTICATED",
            message="Authentication required.",
            status_code=401,
        )

    # Create conversation if new
    if not request.conversation_id:
        try:
            conv_result = await supabase_client.table("conversations").insert({
                "user_id": user_id,
                "title": request.message[:50],
            }).execute()
            request.conversation_id = UUID(conv_result.data[0]["id"])
            logger.info("conversation_created", conversation_id=str(request.conversation_id))
        except Exception as e:
            logger.exception("conversation_create_failed", error=str(e))
            return ErrorResponse(
                code="CONVERSATION_CREATE_FAILED",
                message="Failed to create conversation.",
                status_code=500,
            )

    # Store the user message in the database
    try:
        await supabase_client.table("messages").insert({
            "conversation_id": str(request.conversation_id),
            "user_id": user_id,
            "role": "user",
            "content": request.message,
            "metadata": request.context or {},
        }).execute()
    except Exception as e:
        logger.warning("message_store_failed", error=str(e))
        # Non-fatal: Brain can still respond

    # Send to Brain service
    try:
        brain_response = await brain_client.process_chat(request, user_id)
    except Exception as e:
        logger.exception("brain_processing_failed", user_id=user_id, error=str(e))
        return ErrorResponse(
            code="BRAIN_PROCESSING_FAILED",
            message="Brain service is unavailable. Please try again.",
            status_code=502,
        )

    # Store the assistant response
    try:
        await supabase_client.table("messages").insert({
            "conversation_id": str(brain_response.conversation_id),
            "user_id": user_id,
            "role": "assistant",
            "content": brain_response.response,
            "tokens_used": brain_response.tokens_used,
        }).execute()
    except Exception as e:
        logger.warning("assistant_message_store_failed", error=str(e))

    # Update conversation timestamp
    try:
        await supabase_client.table("conversations").update({
            "updated_at": "now()"
        }).eq("id", str(brain_response.conversation_id)).execute()
    except Exception:
        pass

    return SuccessResponse(data=brain_response)


# ── Conversations ──

@router.get("/conversations", response_model=PaginatedResponse[Conversation])
async def list_conversations(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    List all conversations for the authenticated user.

    Returns conversations sorted by most recent activity, with
    message counts and last message timestamps.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return ErrorResponse(code="UNAUTHENTICATED", message="Not authenticated.", status_code=401)

    try:
        result = await supabase_client.table("conversations").select(
            "id, title, created_at"
        ).eq("user_id", user_id).order("updated_at", desc=True).range(
            (page - 1) * limit, page * limit - 1
        ).execute()

        # Get count
        count_result = await supabase_client.table("conversations").select(
            "id", count="exact"
        ).eq("user_id", user_id).execute()
        total = count_result.count or 0

        conversations = []
        for conv in result.data:
            # Get message count and last message timestamp
            msg_result = await supabase_client.table("messages").select(
                "created_at", count="exact"
            ).eq("conversation_id", conv["id"]).order("created_at", desc=True).limit(1).execute()

            msg_count = msg_result.count or 0
            last_msg_at = msg_result.data[0]["created_at"] if msg_result.data else None

            conversations.append(Conversation(
                id=conv["id"],
                title=conv.get("title"),
                message_count=msg_count,
                last_message_at=last_msg_at,
                created_at=conv["created_at"],
            ))

        return PaginatedResponse(
            items=conversations,
            total=total,
            page=page,
            limit=limit,
            pages=max(1, (total + limit - 1) // limit),
        )

    except Exception as e:
        logger.exception("list_conversations_failed", user_id=user_id, error=str(e))
        return ErrorResponse(
            code="LIST_FAILED",
            message="Failed to retrieve conversations.",
            status_code=500,
        )


@router.get("/conversations/{conversation_id}", response_model=SuccessResponse[ConversationDetail])
async def get_conversation(
    request: Request,
    conversation_id: UUID = Path(...),
):
    """
    Get a conversation with all its messages.

    Args:
        conversation_id: UUID of the conversation to retrieve.

    Returns:
        Full conversation detail including all messages.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return ErrorResponse(code="UNAUTHENTICATED", message="Not authenticated.", status_code=401)

    try:
        conv_result = await supabase_client.table("conversations").select("*").eq(
            "id", str(conversation_id)
        ).eq("user_id", user_id).execute()

        if not conv_result.data:
            return ErrorResponse(
                code="NOT_FOUND",
                message="Conversation not found.",
                status_code=404,
            )

        conv = conv_result.data[0]

        # Get messages
        msg_result = await supabase_client.table("messages").select(
            "id, role, content, tokens_used, created_at, metadata"
        ).eq("conversation_id", str(conversation_id)).order("created_at", asc=True).execute()

        messages = [MessageResponse(**m) for m in msg_result.data]

        return SuccessResponse(data=ConversationDetail(
            id=conv["id"],
            title=conv.get("title"),
            message_count=len(messages),
            last_message_at=messages[-1].created_at if messages else None,
            created_at=conv["created_at"],
            messages=messages,
        ))

    except Exception as e:
        logger.exception("get_conversation_failed", conversation_id=str(conversation_id), error=str(e))
        return ErrorResponse(
            code="GET_FAILED",
            message="Failed to retrieve conversation.",
            status_code=500,
        )


@router.post("/conversations", response_model=SuccessResponse[Conversation])
async def create_conversation(
    request_body: ConversationCreate,
    http_request: Request,
):
    """
    Create a new empty conversation.

    Args:
        request_body: Optional title for the conversation.

    Returns:
        The newly created conversation.
    """
    user_id = getattr(http_request.state, "user_id", None)
    if not user_id:
        return ErrorResponse(code="UNAUTHENTICATED", message="Not authenticated.", status_code=401)

    try:
        result = await supabase_client.table("conversations").insert({
            "user_id": user_id,
            "title": request_body.title or "New Conversation",
        }).execute()

        conv = result.data[0]
        return SuccessResponse(data=Conversation(
            id=conv["id"],
            title=conv.get("title"),
            created_at=conv["created_at"],
        ))
    except Exception as e:
        logger.exception("create_conversation_failed", error=str(e))
        return ErrorResponse(
            code="CREATE_FAILED",
            message="Failed to create conversation.",
            status_code=500,
        )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    request: Request,
    conversation_id: UUID = Path(...),
):
    """
    Delete a conversation and all its messages.

    Args:
        conversation_id: UUID of the conversation to delete.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return ErrorResponse(code="UNAUTHENTICATED", message="Not authenticated.", status_code=401)

    try:
        # Messages are cascade-deleted by the database foreign key
        result = await supabase_client.table("conversations").delete().eq(
            "id", str(conversation_id)
        ).eq("user_id", user_id).execute()

        if not result.data:
            return ErrorResponse(
                code="NOT_FOUND",
                message="Conversation not found.",
                status_code=404,
            )

        logger.info("conversation_deleted", conversation_id=str(conversation_id), user_id=user_id)
        return {"success": True, "message": "Conversation deleted."}

    except Exception as e:
        logger.exception("delete_conversation_failed", conversation_id=str(conversation_id), error=str(e))
        return ErrorResponse(
            code="DELETE_FAILED",
            message="Failed to delete conversation.",
            status_code=500,
        )
