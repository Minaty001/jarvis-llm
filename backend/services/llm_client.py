"""
LLM API Client

Handles HTTP communication with the LLM API service.
The LLM service is a thin proxy to upstream providers (OpenAI, Anthropic, etc.).
The backend only routes requests — it does NOT perform inference.
"""

import structlog
from httpx import AsyncClient, Timeout, TimeoutException

from utils.config import settings

logger = structlog.get_logger()


class LLMClient:
    """
    Async HTTP client for the LLM API service.

    Provides methods for text generation, embedding creation, and
    health checks. All calls are transparent relays.
    """

    def __init__(self):
        self.base_url = settings.llm_url.rstrip("/")
        self.timeout = Timeout(settings.llm_timeout)
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

    async def generate(self, prompt: str, system_prompt: str | None = None, **kwargs) -> dict:
        """
        Send a text generation request to the LLM API.

        Args:
            prompt: The user-facing prompt text.
            system_prompt: Optional system instruction override.
            **kwargs: Additional parameters (temperature, max_tokens, etc.).

        Returns:
            dict: The LLM response with keys: content, tokens_used, model.

        Raises:
            TimeoutException: If LLM API does not respond in time.
            Exception: For connection or protocol errors.
        """
        client = await self._get_client()
        payload = {"prompt": prompt, **kwargs}
        if system_prompt:
            payload["system_prompt"] = system_prompt

        try:
            response = await client.post("/generate", json=payload)
            response.raise_for_status()
            return response.json()
        except TimeoutException:
            logger.error("llm_timeout", timeout=settings.llm_timeout)
            raise
        except Exception as e:
            logger.exception("llm_request_failed", error=str(e))
            raise

    async def embed(self, text: str) -> list[float]:
        """
        Generate an embedding vector for the given text.

        Args:
            text: Input text to embed.

        Returns:
            list[float]: Dense embedding vector.

        Raises:
            TimeoutException: If LLM API does not respond in time.
        """
        client = await self._get_client()
        try:
            response = await client.post("/embed", json={"text": text})
            response.raise_for_status()
            data = response.json()
            return data["embedding"]
        except TimeoutException:
            logger.error("llm_embed_timeout")
            raise
        except Exception as e:
            logger.exception("llm_embed_failed", error=str(e))
            raise

    async def health_check(self) -> dict:
        """Check LLM API reachability."""
        try:
            client = await self._get_client()
            resp = await client.get("/health", timeout=5.0)
            return {"status": "healthy"} if resp.status_code == 200 else {"status": "unhealthy"}
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}

    async def close(self):
        """Close the HTTP client session."""
        if self._client:
            await self._client.aclose()
            self._client = None


# ── Singleton ──
llm_client = LLMClient()
