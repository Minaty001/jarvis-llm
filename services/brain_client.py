"""
Brain Service Client

Handles all HTTP communication with the Brain service.
The Brain is responsible for reasoning, planning, and orchestration.
The backend simply relays requests and responses — no thinking here.
"""

import structlog
from httpx import AsyncClient, Timeout, TimeoutException

from schemas.chat import ChatRequest, ChatResponse
from utils.config import settings

logger = structlog.get_logger()


class BrainClient:
    """
    Async HTTP client for the Brain service.

    The Brain receives a chat message, performs reasoning, may invoke
    the LLM or Skills, and returns a response. This client just ships
    the request and returns the result.
    """

    def __init__(self):
        self.base_url = settings.brain_url.rstrip("/")
        self.timeout = Timeout(settings.brain_timeout)
        self._client: AsyncClient | None = None

    async def _get_client(self) -> AsyncClient:
        """Lazy-initialize the shared HTTP client session."""
        if self._client is None:
            self._client = AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def process_chat(self, request: ChatRequest, user_id: str) -> ChatResponse:
        """
        Send a chat message to the Brain for processing.

        The Brain handles reasoning, LLM calls, and skill orchestration.
        This method is purely a relay.

        Args:
            request: Validated ChatRequest from the API layer.
            user_id: Authenticated user's UUID string.

        Returns:
            ChatResponse: The Brain's response.

        Raises:
            TimeoutException: If Brain does not respond in time.
            Exception: For any connection or protocol errors.
        """
        client = await self._get_client()
        logger.debug(
            "brain_request_sent",
            user_id=user_id,
            message_length=len(request.message),
            conversation_id=str(request.conversation_id) if request.conversation_id else "new",
        )

        try:
            response = await client.post(
                "/process",
                json={
                    "conversation_id": str(request.conversation_id) if request.conversation_id else None,
                    "message": request.message,
                    "context": request.context,
                    "user_id": user_id,
                },
            )
            response.raise_for_status()
            result = ChatResponse(**response.json())

            logger.info(
                "brain_response_received",
                user_id=user_id,
                conversation_id=str(result.conversation_id),
                response_length=len(result.response),
                tokens_used=result.tokens_used,
            )
            return result

        except TimeoutException:
            logger.error("brain_timeout", timeout=settings.brain_timeout, user_id=user_id)
            raise
        except Exception as e:
            logger.exception("brain_request_failed", user_id=user_id, error=str(e))
            raise

    async def health_check(self) -> dict:
        """
        Check if the Brain service is reachable and healthy.

        Returns:
            dict: {"status": "healthy"} or {"status": "unhealthy", "error": ...}
        """
        try:
            client = await self._get_client()
            resp = await client.get("/health", timeout=5.0)
            if resp.status_code == 200:
                return {"status": "healthy"}
            return {"status": "unhealthy", "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}

    async def close(self):
        """Close the underlying HTTP client session."""
        if self._client:
            await self._client.aclose()
            self._client = None


# ── Singleton ──
brain_client = BrainClient()
