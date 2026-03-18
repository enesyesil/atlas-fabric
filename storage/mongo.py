import os
from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorClient

from storage.schema import MapConfigDocument

_client: AsyncIOMotorClient | None = None
_indexes_initialized = False


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
        _client = AsyncIOMotorClient(uri)
    return _client


def get_collection():
    return get_client()["atlas_fabric"]["map_configs"]


async def ensure_indexes() -> None:
    global _indexes_initialized
    if _indexes_initialized:
        return

    col = get_collection()
    await col.create_index([("year", 1), ("region", 1)], unique=True)
    await col.create_index([("region", 1), ("year", 1)])
    _indexes_initialized = True


async def save_config(doc: MapConfigDocument) -> None:
    await ensure_indexes()
    col = get_collection()
    payload = doc.model_dump()
    created_at = payload.pop("created_at")
    payload["updated_at"] = datetime.now(UTC)
    await col.update_one(
        {"year": doc.year, "region": doc.region},
        {"$set": payload, "$setOnInsert": {"created_at": created_at}},
        upsert=True,
    )


async def get_config(year: int, region: str) -> dict | None:
    await ensure_indexes()
    col = get_collection()
    doc = await col.find_one({"year": year, "region": region}, {"_id": 0})
    return doc or None


def get_config_sync(year: int, region: str) -> dict | None:
    """Sync wrapper for get_config — safe to call from outside an async context."""
    import asyncio

    try:
        asyncio.get_running_loop()
        return None
    except RuntimeError:
        return asyncio.run(get_config(year, region))
    except Exception:
        return None


async def list_configs(region: str, page: int = 1, limit: int = 20) -> list[dict]:
    await ensure_indexes()
    col = get_collection()
    skip = (page - 1) * limit
    cursor = (
        col.find({"region": region}, {"_id": 0})
        .sort("year", 1)
        .skip(skip)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


async def list_configs_range(
    start_year: int,
    end_year: int,
    region: str,
    limit: int = 100,
) -> list[dict]:
    await ensure_indexes()
    col = get_collection()
    cursor = (
        col.find(
            {"year": {"$gte": start_year, "$lte": end_year}, "region": region},
            {"_id": 0},
        )
        .sort("year", 1)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)
