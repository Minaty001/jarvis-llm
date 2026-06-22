"""
Health Check & Monitoring Endpoints

Provides endpoints for service health checks, dependency status,
and Prometheus metrics.
"""

import time
import structlog
from fastapi import APIRouter
from fastapi.responses import Response

from database.client import supabase_client
from schemas.common import HealthCheck, ServiceStatus
from services.brain_client import brain_client
from services.llm_client import llm_client
from services.skill_executor import skill_executor

logger = structlog.get_logger()
router = APIRouter()

# Track application start time for uptime calculation
APP_START_TIME = time.time()


@router.get("/health", response_model=HealthCheck)
async def health_check():
    """
    Lightweight health check endpoint.

    Returns overall service health and per-dependency status.
    Used by load balancers and orchestrators for readiness probes.
    """
    # Check all dependencies concurrently
    import asyncio

    brain_status, llm_status, skill_status, db_status = await asyncio.gather(
        brain_client.health_check(),
        llm_client.health_check(),
        skill_executor.health_check(),
        supabase_client.health_check(),
    )

    dependencies = {
        "brain": brain_status.get("status", "unreachable"),
        "llm": llm_status.get("status", "unreachable"),
        "skill_engine": skill_status.get("status", "unreachable"),
        "database": db_status.get("status", "unhealthy"),
    }

    # Overall status: healthy only if ALL dependencies are healthy
    overall = "healthy" if all(v == "healthy" for v in dependencies.values()) else "unhealthy"

    return HealthCheck(
        status=overall,
        version="1.0.0",
        uptime_seconds=time.time() - APP_START_TIME,
        dependencies=dependencies,
    )


@router.get("/status", response_model=dict)
async def service_status():
    """
    Detailed status of all external service dependencies.

    Returns response time and error details for each service.
    Useful for debugging connectivity issues.
    """
    import asyncio
    from datetime import datetime, timezone

    brain_start = time.time()
    brain = await brain_client.health_check()
    brain_time = (time.time() - brain_start) * 1000

    llm_start = time.time()
    llm = await llm_client.health_check()
    llm_time = (time.time() - llm_start) * 1000

    skill_start = time.time()
    skill = await skill_executor.health_check()
    skill_time = (time.time() - skill_start) * 1000

    db_start = time.time()
    db = await supabase_client.health_check()
    db_time = (time.time() - db_start) * 1000

    return {
        "app": {
            "name": "jarvis-backend",
            "version": "1.0.0",
            "uptime_seconds": time.time() - APP_START_TIME,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
        "dependencies": [
            ServiceStatus(name="Brain", url="", status=brain.get("status"), response_time_ms=round(brain_time, 2)).model_dump(),
            ServiceStatus(name="LLM API", url="", status=llm.get("status"), response_time_ms=round(llm_time, 2)).model_dump(),
            ServiceStatus(name="Skill Engine", url="", status=skill.get("status"), response_time_ms=round(skill_time, 2)).model_dump(),
            ServiceStatus(name="Supabase", url="", status=db.get("status"), response_time_ms=round(db_time, 2)).model_dump(),
        ],
    }


@router.get("/metrics")
async def metrics():
    """
    Basic application metrics in Prometheus text format.

    Returns:
        str: Prometheus-compatible metrics.
    """
    import os, platform

    uptime = time.time() - APP_START_TIME
    pid = os.getpid()

    metrics_text = f"""# HELP jarvis_uptime_seconds Application uptime
# TYPE jarvis_uptime_seconds gauge
jarvis_uptime_seconds {uptime}

# HELP jarvis_process_id Process ID
# TYPE jarvis_process_id gauge
jarvis_process_id {pid}

# HELP jarvis_python_version Python runtime version
# TYPE jarvis_python_version gauge
jarvis_python_version 1.0

# HELP jarvis_info Static application metadata
# TYPE jarvis_info gauge
jarvis_info{{app="jarvis-backend",version="1.0.0",python="{platform.python_version()}"}} 1
"""
    return Response(
        content=metrics_text,
        media_type="text/plain",
        headers={"Content-Type": "text/plain; charset=utf-8"},
    )
