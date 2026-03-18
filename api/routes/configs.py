from fastapi import APIRouter, HTTPException, Query

from storage.mongo import get_config, list_configs, list_configs_range

router = APIRouter(prefix="/api/v1/configs", tags=["configs"])


@router.get("/range")
async def get_configs_range(
    start: int = Query(...),
    end: int = Query(...),
    region: str = Query(default="world"),
    limit: int = Query(default=100, ge=1, le=500),
):
    if start > end:
        raise HTTPException(status_code=400, detail="start must be <= end")
    configs = await list_configs_range(start, end, region, limit=limit)
    return {"start": start, "end": end, "region": region, "limit": limit, "results": configs}


@router.get("/{year}")
async def get_config_by_year(
    year: int,
    region: str = Query(default="world"),
):
    doc = await get_config(year, region)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"No config found for year={year} region={region}",
        )
    return doc


@router.get("")
async def list_configs_paginated(
    region: str = Query(default="world"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    configs = await list_configs(region, page, limit)
    return {"region": region, "page": page, "limit": limit, "results": configs}
