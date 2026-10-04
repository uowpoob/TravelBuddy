import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter()


@router.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Report that the API process is running."""
    return {"status": "ok", "service": "TravelBuddy"}


@router.get(
    "/health/db",
    tags=["health"],
    responses={503: {"description": "Database unavailable"}},
)
async def database_health(request: Request):
    engine = request.app.state.db_engine
    if engine is None:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "not_configured"},
        )
    try:
        async with asyncio.timeout(6):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError, TimeoutError):
        # Do not expose connection strings, credentials or driver errors.
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unavailable"},
        )
    return {"status": "ok", "database": "postgresql"}
