"""
Task Manager

Implements the task state machine for long-running skill executions.
Tasks flow through: PENDING → RUNNING → COMPLETED | FAILED | CANCELLED

This service manages task lifecycle — creation, status updates,
progress tracking, and cancellation.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

import structlog

from database.client import supabase_client
from schemas.task import TaskResponse, TaskStatus

logger = structlog.get_logger()


class TaskManager:
    """
    Manages the lifecycle of background tasks.

    Each task represents a skill execution that may take seconds
    or minutes. The state machine ensures tasks transition through
    valid states only.
    """

    # Valid state transitions
    VALID_TRANSITIONS = {
        TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
        TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
        TaskStatus.COMPLETED: set(),  # Terminal
        TaskStatus.FAILED: set(),     # Terminal
        TaskStatus.CANCELLED: set(),  # Terminal
    }

    async def create_task(
        self,
        user_id: UUID,
        skill_name: str,
        input_data: dict,
        timeout_seconds: int = 300,
    ) -> TaskResponse:
        """
        Create a new task in PENDING status.

        Args:
            user_id: The owning user's UUID.
            skill_name: Name of the skill to execute.
            input_data: Input parameters as a dict.
            timeout_seconds: Max execution time in seconds.

        Returns:
            TaskResponse: The newly created task.
        """
        task_id = uuid4()
        now = datetime.now(timezone.utc)

        payload = {
            "id": str(task_id),
            "user_id": str(user_id),
            "skill_name": skill_name,
            "status": TaskStatus.PENDING.value,
            "input": input_data,
            "progress_percent": 0,
            "created_at": now.isoformat(),
            "timeout_seconds": timeout_seconds,
        }

        result = await supabase_client.table("tasks").insert(payload).execute()
        record = result.data[0]

        logger.info(
            "task_created",
            task_id=str(task_id),
            user_id=str(user_id),
            skill_name=skill_name,
        )
        return TaskResponse(**record)

    async def update_status(
        self,
        task_id: UUID,
        new_status: TaskStatus,
        user_id: Optional[UUID] = None,
    ) -> Optional[TaskResponse]:
        """
        Transition a task to a new status.

        Validates the transition against the state machine before
        applying it. Terminal states cannot be changed.

        Args:
            task_id: The task to update.
            new_status: Target status.
            user_id: Optional — if provided, scopes the update to the owner.

        Returns:
            TaskResponse: Updated task, or None if not found.

        Raises:
            ValueError: If the requested transition is invalid.
        """
        # Fetch current task
        query = supabase_client.table("tasks").select("*").eq("id", str(task_id))
        if user_id:
            query = query.eq("user_id", str(user_id))

        result = await query.execute()
        if not result.data:
            logger.warning("task_not_found", task_id=str(task_id))
            return None

        current = TaskResponse(**result.data[0])

        # Validate transition
        allowed = self.VALID_TRANSITIONS.get(current.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition task {task_id} from {current.status.value} "
                f"to {new_status.value}. Allowed: {[s.value for s in allowed]}"
            )

        # Build update payload
        now = datetime.now(timezone.utc)
        update = {
            "status": new_status.value,
            "progress_percent": 100 if new_status == TaskStatus.COMPLETED else current.progress_percent,
        }

        if new_status == TaskStatus.RUNNING:
            update["started_at"] = now.isoformat()
        elif new_status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            update["completed_at"] = now.isoformat()

        updated = (
            await supabase_client.table("tasks")
            .update(update)
            .eq("id", str(task_id))
            .execute()
        )
        record = updated.data[0]

        logger.info(
            "task_status_changed",
            task_id=str(task_id),
            from_status=current.status.value,
            to_status=new_status.value,
        )
        return TaskResponse(**record)

    async def update_progress(self, task_id: UUID, progress: int, user_id: Optional[UUID] = None) -> Optional[TaskResponse]:
        """
        Update a running task's progress percentage.

        Args:
            task_id: The task to update.
            progress: Progress percentage (0-100).
            user_id: Optional owner scope.

        Returns:
            TaskResponse: Updated task, or None if not found.
        """
        progress = max(0, min(100, progress))

        query = supabase_client.table("tasks").select("*").eq("id", str(task_id))
        if user_id:
            query = query.eq("user_id", str(user_id))

        result = await query.execute()
        if not result.data:
            return None

        updated = (
            await supabase_client.table("tasks")
            .update({"progress_percent": progress})
            .eq("id", str(task_id))
            .execute()
        )
        return TaskResponse(**updated.data[0]) if updated.data else None

    async def set_error(self, task_id: UUID, error_message: str, user_id: Optional[UUID] = None) -> Optional[TaskResponse]:
        """
        Mark a task as FAILED with an error message.

        This is a convenience method equivalent to
        update_status(FAILED) + setting the error message.

        Args:
            task_id: The task to fail.
            error_message: Description of what went wrong.
            user_id: Optional owner scope.

        Returns:
            TaskResponse: Failed task, or None if not found.
        """
        query = supabase_client.table("tasks").select("*").eq("id", str(task_id))
        if user_id:
            query = query.eq("user_id", str(user_id))

        result = await query.execute()
        if not result.data:
            return None

        now = datetime.now(timezone.utc)
        updated = (
            await supabase_client.table("tasks")
            .update({
                "status": TaskStatus.FAILED.value,
                "error_message": error_message[:1000],
                "completed_at": now.isoformat(),
            })
            .eq("id", str(task_id))
            .execute()
        )
        return TaskResponse(**updated.data[0]) if updated.data else None

    async def get_task(self, task_id: UUID, user_id: Optional[UUID] = None) -> Optional[TaskResponse]:
        """
        Retrieve a single task by ID.

        Args:
            task_id: Task UUID.
            user_id: Optional owner scope filter.

        Returns:
            TaskResponse or None.
        """
        query = supabase_client.table("tasks").select("*").eq("id", str(task_id))
        if user_id:
            query = query.eq("user_id", str(user_id))

        result = await query.execute()
        if not result.data:
            return None
        return TaskResponse(**result.data[0])

    async def list_tasks(
        self,
        user_id: UUID,
        status: Optional[TaskStatus] = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[TaskResponse], int]:
        """
        List tasks for a user with optional status filter.

        Args:
            user_id: Owner UUID.
            status: Optional status filter.
            page: Page number (1-indexed).
            limit: Items per page.

        Returns:
            tuple: (list of TaskResponse, total count).
        """
        query = (
            supabase_client.table("tasks")
            .select("*", count="exact")
            .eq("user_id", str(user_id))
            .order("created_at", desc=True)
        )
        if status:
            query = query.eq("status", status.value)

        query = query.range((page - 1) * limit, page * limit - 1)
        result = await query.execute()

        tasks = [TaskResponse(**r) for r in result.data]
        total = result.count or 0
        return tasks, total

    async def cancel_task(self, task_id: UUID, user_id: Optional[UUID] = None) -> Optional[TaskResponse]:
        """
        Cancel a task that is PENDING or RUNNING.

        Args:
            task_id: Task UUID to cancel.
            user_id: Optional owner scope.

        Returns:
            TaskResponse: Cancelled task, or None if not found.
        """
        return await self.update_status(task_id, TaskStatus.CANCELLED, user_id=user_id)


# ── Singleton ──
task_manager = TaskManager()
