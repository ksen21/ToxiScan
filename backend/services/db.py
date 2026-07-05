"""
MongoDB connection using Motor (async driver).
Provides a single shared client with connection pooling.
"""

import logging
from typing import Optional

import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from services.config import settings

logger = logging.getLogger(__name__)

class Database:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

db_instance = Database()


async def connect_db():
    """Called on app startup — creates Motor client and verifies connection."""
    logger.info("Connecting to MongoDB...")
    db_instance.client = AsyncIOMotorClient(
        settings.MONGODB_URI,
        maxPoolSize=10,
        minPoolSize=1,
        serverSelectionTimeoutMS=5000,
        tlsCAFile=certifi.where(),
    )
    db_instance.db = db_instance.client["toxiscan"]

    # Ping to verify connection
    await db_instance.client.admin.command("ping")
    logger.info("✅ MongoDB connected successfully.")


async def close_db():
    """Called on app shutdown — closes Motor client."""
    if db_instance.client:
        db_instance.client.close()
        logger.info("MongoDB connection closed.")


def get_db() -> AsyncIOMotorDatabase:
    """Dependency injector — returns the active database instance."""
    assert db_instance.db is not None, "get_db() called before connect_db() ran on startup"
    return db_instance.db