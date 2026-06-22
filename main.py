"""
JARVIS Backend Gateway - FastAPI Application Entry Point

This is the traffic cop. It receives requests from the Android app,
validates them, routes them to the appropriate service (Brain, LLM,
Skill Engine), and returns responses. No thinking, reasoning, or
generation happens here.

Architecture:
    Android App (Capacitor/WebView)
        ↓
    Backend Gateway (FastAPI) ← You Are Here
        ├→ Brain Service (reasoning)
        ├→ LLM API (generation)
        ├→ Skill Engine (execution)
        └→ Supabase (persistence)
"""

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from api import auth, chat, command, tasks, memory, health
from middleware.auth import JWTAuthMiddleware
from middleware.logging import RequestLoggingMiddleware
from database.client import supabase_client
from utils.config import settings
from utils.redis_cache import cache
from services.brain_client import brain_client
from services.llm_client import llm_client
from services.skill_executor import skill_executor

# ── Structured Logger ──
logger = structlog.get_logger()


def create_app() -> FastAPI:
    """
    Application factory. Creates and configures the FastAPI instance.

    Returns:
        FastAPI: Fully configured application with middleware, routers,
                 and startup/shutdown handlers attached.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="JARVIS Backend Gateway — receives, validates, routes, responds",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── Middleware Stack (order matters: first added = innermost) ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(JWTAuthMiddleware)   # JWT validation on protected routes
    app.add_middleware(RequestLoggingMiddleware)  # Structured request/response logs

    # ── Register Routers ──
    app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
    app.include_router(chat.router, prefix="", tags=["Chat"])
    app.include_router(command.router, prefix="/command", tags=["Commands"])
    app.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
    app.include_router(memory.router, prefix="/memory", tags=["Memory"])
    app.include_router(health.router, prefix="", tags=["Health"])

    # ── Lifecycle Events ──
    @app.on_event("startup")
    async def startup():
        """Initialize connections and validate configuration on startup."""
        logger.info(
            "backend_starting",
            app=settings.app_name,
            version=settings.app_version,
            environment=settings.environment,
        )

        # Validate configuration — log warnings but don't block startup
        config_issues = settings.validate()
        for msg in config_issues:
            logger.warning("config_issue", detail=msg)

        # Initialize Supabase database client connection
        if settings.supabase_url and settings.supabase_api_key:
            await supabase_client.initialize()
        else:
            logger.warning("supabase_not_configured", detail="Supabase credentials missing — database features disabled")

        # Initialize Redis Cache connection
        await cache.initialize()

        # Verify critical external dependencies are reachable
        await _check_dependencies()

    @app.on_event("shutdown")
    async def shutdown():
        """Gracefully close connections on shutdown."""
        logger.info("backend_shutting_down")
        await supabase_client.close()
        await cache.close()
        await brain_client.close()
        await llm_client.close()
        await skill_executor.close()

    # Mount UI static files at root
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


async def _check_dependencies():
    """
    Verify that critical external services are reachable at startup.

    Logs a warning for each unreachable service but does NOT prevent
    the application from starting — individual endpoints handle timeouts.
    """
    import httpx

    services = {
        "Brain": settings.brain_url,
        "LLM": settings.llm_url,
        "Skill": settings.skill_url,
    }

    async with httpx.AsyncClient() as client:
        for name, url in services.items():
            try:
                resp = await client.get(f"{url}/health", timeout=5.0)
                if resp.status_code == 200:
                    logger.info("dependency_healthy", service=name, url=url)
                else:
                    logger.warning("dependency_unhealthy", service=name, url=url, status=resp.status_code)
            except Exception as e:
                logger.warning("dependency_unreachable", service=name, url=url, error=str(e))


# ── Entry Point ──
app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
        workers=1 if settings.environment == "development" else settings.workers,
    )
