"""
Command API Endpoints

Handles skill execution requests. Commands are routed through the
Skill Engine — the backend does NOT execute anything directly.
"""

import structlog
from fastapi import APIRouter, Request

from schemas.command import (
    AvailableCommand,
    AvailableCommandsResponse,
    CommandRequest,
    CommandResponse,
)
from schemas.common import ErrorResponse, SuccessResponse
from services.skill_executor import skill_executor
from services.task_manager import task_manager

logger = structlog.get_logger()
router = APIRouter()


@router.post("", response_model=SuccessResponse[CommandResponse])
async def execute_command(request_body: CommandRequest, http_request: Request):
    """
    Execute a skill command.

    Creates a task in PENDING status, then sends it to the Skill Engine
    for execution. Returns immediately with a task_id for tracking.

    Args:
        request_body: Skill name and parameters.
        http_request: Incoming request (for user_id extraction).

    Returns:
        Task tracking information with task_id and initial status.
    """
    user_id = getattr(http_request.state, "user_id", None)
    if not user_id:
        return ErrorResponse(
            code="UNAUTHENTICATED",
            message="Authentication required.",
            status_code=401,
        )

    try:
        # Create a tracked task
        task = await task_manager.create_task(
            user_id=user_id,
            skill_name=request_body.skill_name,
            input_data=request_body.parameters,
            timeout_seconds=request_body.timeout_seconds or 300,
        )

        # Update status to RUNNING and dispatch to Skill Engine
        await task_manager.update_status(task.id, task_manager.VALID_TRANSITIONS[task.status].pop())
        # Note: In production, dispatch to a background worker here
        # For now, we just create the task and return

        logger.info(
            "command_dispatched",
            user_id=user_id,
            skill_name=request_body.skill_name,
            task_id=str(task.id),
        )

        return SuccessResponse(data=CommandResponse(
            task_id=task.id,
            skill_name=request_body.skill_name,
            status=task.status.value,
            created_at=task.created_at,
        ))

    except Exception as e:
        logger.exception("command_execution_failed", skill_name=request_body.skill_name, error=str(e))
        return ErrorResponse(
            code="COMMAND_FAILED",
            message=f"Failed to execute command: {str(e)}",
            status_code=500,
        )


@router.get("/available", response_model=SuccessResponse[AvailableCommandsResponse])
async def list_available_commands():
    """
    List all available skills/commands from the Skill Engine.

    Returns:
        Available commands grouped by category.
    """
    try:
        skills = await skill_executor.list_skills()
        commands = [
            AvailableCommand(
                name=s.get("name", "unknown"),
                category=s.get("category", "general"),
                description=s.get("description"),
                version=s.get("version", "1.0.0"),
                enabled=s.get("enabled", True),
            )
            for s in skills
        ]

        return SuccessResponse(data=AvailableCommandsResponse(commands=commands))

    except Exception as e:
        logger.exception("list_commands_failed", error=str(e))
        return ErrorResponse(
            code="SKILL_ENGINE_UNAVAILABLE",
            message="Unable to fetch available commands from Skill Engine.",
            status_code=503,
        )
