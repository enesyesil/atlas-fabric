import os

from motor.motor_asyncio import AsyncIOMotorClient

from storage.schema import MapConfigDocument

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
        _client = AsyncIOMotorClient(uri)
    return _client


def get_collection():
    return get_client()["atlas_fabric"]["map_configs"]


async def save_config(doc: MapConfigDocument) -> None:
    col = get_collection()
    await col.replace_one({"id": doc.id}, doc.model_dump(), upsert=True)


async def get_config(year: int, region: str) -> dict | None:
    col = get_collection()
    doc = await col.find_one({"year": year, "region": region}, {"_id": 0})
    return doc or None


def get_config_sync(year: int, region: str) -> dict | None:
    """Sync wrapper for get_config — safe to call from outside an async context."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already inside an event loop (e.g. FastAPI) — skip the cache check
            return None
        return loop.run_until_complete(get_config(year, region))
    except Exception:
        return None


async def list_configs(region: str, page: int = 1, limit: int = 20) -> list[dict]:
    col = get_collection()
    skip = (page - 1) * limit
    cursor = col.find({"region": region}, {"_id": 0}).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)


async def list_configs_range(
    start_year: int,
    end_year: int,
    region: str,
) -> list[dict]:
    col = get_collection()
    cursor = col.find(
        {"year": {"$gte": start_year, "$lte": end_year}, "region": region},
        {"_id": 0},
    )
    return await cursor.to_list(length=None)
