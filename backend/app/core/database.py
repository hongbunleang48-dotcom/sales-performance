from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings


class Database:
    client: Optional[AsyncIOMotorClient] = None


db_instance = Database()


async def connect_to_mongo() -> None:
    """Initializes the MongoDB Motor client during application startup."""
    try:
        db_instance.client = AsyncIOMotorClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=5000
        )
        print(f"Connected to MongoDB at {settings.MONGO_URI}")
    except Exception as e:
        print(f"Warning: Could not establish immediate connection to MongoDB: {e}")


async def close_mongo_connection() -> None:
    """Closes the MongoDB connection during application shutdown."""
    if db_instance.client is not None:
        db_instance.client.close()
        print("Closed MongoDB connection")


def get_database() -> AsyncIOMotorDatabase:
    """
    Dependency provider for FastAPI route handlers.
    Lazily creates client if not initialized.
    """
    if db_instance.client is None:
        db_instance.client = AsyncIOMotorClient(settings.MONGO_URI)
    return db_instance.client[settings.MONGO_DB]
