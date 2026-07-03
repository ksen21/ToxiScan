"""
One-off script to list all chemical names + aliases currently in MongoDB.
Run from backend/ folder: python list_chemicals.py
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from services.config import settings


async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client["toxiscan"]

    count = await db.chemicals.count_documents({})
    print(f"\nTotal chemicals in DB: {count}\n")
    print(f"{'Name':<35} {'Aliases':<40} {'Severity'}")
    print("-" * 90)

    async for doc in db.chemicals.find({}).sort("name", 1):
        name = doc.get("name", "")
        aliases = ", ".join(doc.get("aliases", []))
        severity = doc.get("severity", "")
        print(f"{name:<35} {aliases:<40} {severity}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
