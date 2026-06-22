"""
Tasks API Endpoints

Manages long-running task lifecycle: creation, listing, status
tracking, and cancellation.
"""

import structlog
from fastapi import APIRouter, Path, Query, Request
from uuid import UUID

from schemas.common import ErrorResponse, PaginatedResponse, SuccessResponse
from schemas.task import TaskCreateRequest, TaskCreateResponse, TaskResponse, TaskStatus
from services.task_manager import task_manager

logger = structlog.get_logger()
router = APIRouter()


@router.post("", response_model=SuccessResponse[TaskCreateResponse])
async def create_task(request_body: TaskCreateRequest, http_request: Request):
    """
    Create a new background task.

    Tasks represent long-running skill executions. They start in
    PENDING status and are picked up by a background worker.

    Args:
        request_body: Skill name, input parameters, and timeout.
        http_request: Incoming request (for user_id extraction).

    Returns:
        TaskCreateResponse with the new task's ID and status.
    """
    user_id = getattr(http_request.state, "user_id", None)
    if not user_id:
        return ErrorResponse(code="UNAUTHENTICATED", message="Not authenticated.", status_code=401)

    try:
        task = await task_manager.create_task(
            user_id=user_id,
            skill_name=request_body.skill_name,
            input_data=request_body.input,
            timeout_seconds=request_body.timeout_seconds,
        )

        logger.info("task_created_via_api", task_id=str(task.id), skill_name=request_body.skill_name)
        return SuccessResponse(data=TaskCreateResponse(
            task_id=task.id,
            status=task.status,
            created_at=task.created_at,
        ))

    except Exception as e:
        logger.exception("task_creation_failed", error=str(e))
        return ErrorResponse(
            code="TASK_CREATE_FAILED",
            message="Failed to create task.",
            status_code=500,
        )


@router.get("", response_model=PaginatedResponse[TaskResponse])
async def list_tasks(
    request: Request,
    status: TaskStatus | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    List tasks for the authenticated user.

    Args:
        status: Optional filter by task status.
        page: Page number (1-indexed).
        limit: Items per page (max 100).

    Returns:
        Paginated list of tasks.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return ErrorResponse(code="UNAUTHENTICATED", message="Not authenticated.", status_code=401)

    try:
        tasks, total = await task_manager.list_tasks(
            user_id=user_id,
            status=status,
            page=page,
            limit=limit,
        )

        return PaginatedResponse(
            items=tasks,
            total=total,
            page=page,
            limit=limit,
            pages=max(1, (total + limit - 1) // limit),
        )

    except Exception as e:
        logger.exception("list_tasks_failed", user_id=user_id, error=str(e))
        return ErrorResponse(
            code="LIST_FAILED",
            message="Failed to retrieve tasks.",
            status_code=500,
        )


@router.get("/{task_id}", response_model=SuccessResponse[TaskResponse])
async def get_task(
    task_id: UUID = Path(...),
    request: Request = None,
):
    """
    Get detailed information about a specific task.

    Args:
        task_id: UUID of the task to retrieve.

    Returns:
        Full task details including status, progress, and output.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return ErrorResponse(code="UNAUTHENTICATED", message="Not authenticated.", status_code=401)

    try:
        task = await task_manager.get_task(task_id, user_id=user_id)
        if not task:
            return ErrorResponse(
                code="NOT_FOUND",
                message="Task not found.",
                status_code=404,
            )

        return SuccessResponse(data=task)

    except Exception as e:
        logger.exception("get_task_failed", task_id=str(task_id), error=str(e))
        return ErrorResponse(
            code="GET_FAILED",
            message="Failed to retrieve task.",
            status_code=500,
        )


@router.delete("/{task_id}")
async def cancel_task(
    task_id: UUID = Path(...),
    request: Request = None,
):
    """
    Cancel a pending or running task.

    Terminal tasks (COMPLETED, FAILED, CANCELLED) cannot be cancelled.

    Args:
        task_id: UUID of the task to cancel.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return ErrorResponse(code="UNAUTHENTICATED", message="Not authenticated.", status_code=401)

    try:
        task = await task_manager.get_task(task_id, user_id=user_id)
        if not task:
            return ErrorResponse(
                code="NOT_FOUND",
                message="Task not found.",
                status_code=404,
            )

        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            return ErrorResponse(
                code="TASK_TERMINAL",
                message=f"Cannot cancel a task in {task.status.value} state.",
                status_code=400,
            )

        cancelled = await task_manager.cancel_task(task_id, user_id=user_id)
        if cancelled:
            logger.info("task_cancelled", task_id=str(task_id), user_id=user_id)
            return {"success": True, "message": "Task cancelled."}

        return ErrorResponse(
            code="CANCEL_FAILED",
            message="Failed to cancel task.",
            status_code=500,
        )

    except Exception as e:
        logger.exception("cancel_task_failed", task_id=str(task_id), error=str(e))
        return ErrorResponse(
            code="CANCEL_FAILED",
            message="Failed to cancel task.",
            status_code=500,
        )
