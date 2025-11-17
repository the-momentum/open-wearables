from fastapi import APIRouter
from sqlalchemy import text

from app.database import DbSession, engine

healthcheck_router = APIRouter()


def get_pool_status() -> dict[str, str]:
    """Get connection pool status for monitoring."""
    pool = engine.pool
    return {
        "max_pool_size": str(pool.size()),
        "connections_ready_for_reuse": str(pool.checkedin()),
        "active_connections": str(pool.checkedout()),
        "overflow": str(pool.overflow()),
    }


@healthcheck_router.get("/db")
async def database_health(db: DbSession) -> dict[str, str | dict[str, str]]:
    """Database health check endpoint."""
    try:
        # Test connection
        db.execute(text("SELECT 1"))

        pool_status = get_pool_status()
        return {
            "status": "healthy",
            "pool": pool_status,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }
