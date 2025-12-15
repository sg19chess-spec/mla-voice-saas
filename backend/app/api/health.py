"""
Health Check Endpoints
======================
These endpoints help you check if the system is working.

WHAT ARE HEALTH CHECKS?
- Simple endpoints that return "OK" if everything is working
- Used by monitoring tools to detect problems
- Good for debugging connection issues
"""

from fastapi import APIRouter
from app.core.config import get_settings
from app.core.database import test_connection

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Basic health check - just confirms API is responding.

    Returns:
        {"status": "healthy"}
    """
    return {"status": "healthy"}


@router.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check - tests all connections.

    Checks:
    - Database connection (Supabase)
    - Configuration loaded

    Returns status for each component.
    """
    settings = get_settings()

    # Check database
    db_status = "connected" if test_connection() else "disconnected"

    # Check if essential configs are set
    config_status = "configured" if (
        settings.supabase_url and
        settings.supabase_service_key
    ) else "missing"

    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "components": {
            "database": db_status,
            "configuration": config_status,
        },
        "environment": settings.app_env
    }
