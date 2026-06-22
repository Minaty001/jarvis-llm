"""
Skill Executor Client

Handles HTTP communication with the Skill Engine service.
The Skill Engine executes Android intents, browser actions, file
operations, and other device-level capabilities.
"""

import structlog
from httpx import AsyncClient, Timeout, TimeoutException

from utils.config import settings

logger = structlog.get_logger()


class SkillExecutorClient:
    """
    Async HTTP client for the Skill Engine service.

    Takes a skill name and parameters, sends them to the executor,
    and returns the result. The backend does NOT execute skills directly.
    """

    def __init__(self):
        self.base_url = settings.skill_url.rstrip("/")
        self.timeout = Timeout(settings.skill_timeout)
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

    async def execute(self, skill_name: str, parameters: dict, timeout_override: int | None = None) -> dict:
        """
        Send a skill execution request to the Skill Engine.

        Args:
            skill_name: Name of the skill to execute (e.g. "chrome_control").
            parameters: Key-value parameters for the skill.
            timeout_override: Optional per-call timeout override.

        Returns:
            dict: Execution result with keys: status, output (optional), error (optional).

        Raises:
            TimeoutException: If skill execution does not complete in time.
        """
        client = await self._get_client()
        payload = {
            "skill_name": skill_name,
            "parameters": parameters,
            "timeout": timeout_override or settings.skill_timeout,
        }

        logger.info(
            "skill_execution_started",
            skill_name=skill_name,
            parameter_count=len(parameters),
        )

        try:
            response = await client.post("/execute", json=payload)
            response.raise_for_status()
            result = response.json()

            logger.info(
                "skill_execution_completed",
                skill_name=skill_name,
                status=result.get("status"),
            )
            return result

        except TimeoutException:
            logger.error("skill_timeout", skill_name=skill_name, timeout=settings.skill_timeout)
            raise
        except Exception as e:
            logger.exception("skill_execution_failed", skill_name=skill_name, error=str(e))
            raise

    async def list_skills(self) -> list[dict]:
        """
        Fetch all available skills from the Skill Engine.

        Returns:
            list[dict]: List of skill descriptors with name, category,
                        description, version, and enabled status.
        """
        client = await self._get_client()
        try:
            response = await client.get("/skills", timeout=10.0)
            response.raise_for_status()
            return response.json().get("skills", [])
        except Exception as e:
            logger.exception("list_skills_failed", error=str(e))
            return []

    async def health_check(self) -> dict:
        """Check Skill Engine reachability."""
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
skill_executor = SkillExecutorClient()
