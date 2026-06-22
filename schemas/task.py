"""
Task State Machine & Pydantic Models

Defines the task lifecycle enums and request/response schemas
for task management endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """
    Task statuses following the lifecycle:

        PENDING → RUNNING → COMPLETED
                           → FAILED
                           → CANCELLED
    """
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# ── Task Create ──

class TaskCreateRequest(BaseModel):
    """
    Request body for POST /tasks.

    Attributes:
        skill_name: Which skill to execute.
        input: Input parameters as JSON.
        timeout_seconds: Optional timeout override.
    """
    skill_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Skill to execute for this task.",
    )
    input: Dict[str, Any] = Field(
        default_factory=dict,
        description="Input parameters for the skill.",
    )
    timeout_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Max execution time in seconds.",
    )


# ── Task Response ──

class TaskResponse(BaseModel):
    """
    Full task object returned by GET endpoints.

    Attributes:
        id: Unique task identifier.
        user_id: Owner of the task.
        skill_name: Skill being executed.
        status: Current lifecycle status.
        input: Original input parameters.
        output: Execution result (set on completion).
        error_message: Error details if failed.
        progress_percent: 0-100 progress indicator.
        created_at: When the task was created.
        started_at: When execution began.
        completed_at: When execution finished.
        timeout_seconds: Max allowed execution time.
    """
    id: UUID
    user_id: UUID
    skill_name: str
    status: TaskStatus
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    progress_percent: int = Field(default=0, ge=0, le=100)
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    timeout_seconds: int = 300


class TaskCreateResponse(BaseModel):
    """
    Response body for POST /tasks.

    Attributes:
        task_id: Newly created task ID.
        status: Initial status (always PENDING).
        created_at: Creation timestamp.
    """
    task_id: UUID
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime
