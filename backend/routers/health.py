"""
Health check endpoint — used by Render, uptime monitors, and CI.
"""

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from services.db import get_db
from services.config import settings
from models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Returns API status and DB connectivity."""
    try:
        await db.command("ping")
        db_ok = True
    except Exception:
        db_ok = False

    return HealthResponse(
        status="ok",
        environment=settings.APP_ENV,
        db_connected=db_ok,
    )