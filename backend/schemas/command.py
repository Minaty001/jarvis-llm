"""
Command Pydantic Models

Defines schemas for executing skills via the /command endpoint and
listing available commands.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    """
    Request body for POST /command.

    Fields:
        skill_name: Name of the skill to execute.
        parameters: Key-value parameters for the skill.
        timeout_seconds: Override default timeout for this command.
    """
    skill_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of the skill to execute (e.g. 'chrome_control').",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value parameters for the skill.",
    )
    timeout_seconds: Optional[int] = Field(
        default=None,
        ge=1,
        le=600,
        description="Override default timeout (1-600 seconds).",
    )


class CommandResponse(BaseModel):
    """
    Response body for POST /command.

    Attributes:
        task_id: ID of the created task (for tracking progress).
        skill_name: Which skill was invoked.
        status: Initial task status (always "PENDING").
        created_at: When the command was submitted.
    """
    task_id: UUID
    skill_name: str
    status: str = "PENDING"
    created_at: datetime


class AvailableCommand(BaseModel):
    """
    Describes a single available skill/command.

    Attributes:
        name: Skill name identifier.
        category: Skill category (android, browser, file, media, messaging).
        description: Human-readable description of what the skill does.
        version: Skill version string.
        enabled: Whether the skill is currently enabled.
    """
    name: str
    category: str
    description: Optional[str] = None
    version: str = "1.0.0"
    enabled: bool = True


class AvailableCommandsResponse(BaseModel):
    """
    Response body for GET /commands/available.

    Attributes:
        commands: List of available skills grouped by category.
    """
    commands: List[AvailableCommand]
