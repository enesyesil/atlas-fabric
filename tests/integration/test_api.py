"""
Integration tests for the FastAPI layer.

Requirements:
  - API server running: make run-api
  - MongoDB running and reachable at MONGODB_URI
  - API_SECRET_KEY set (or defaults to 'changeme')

Run with:
  make test-integration
"""

import os

import pytest
import httpx

BASE_URL = f"http://localhost:{os.environ.get('PORT', '8080')}"
HEADERS = {"X-API-Key": os.environ.get("API_SECRET_KEY", "changeme")}


@pytest.mark.asyncio
async def test_health():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/health", timeout=5)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_auth_required_on_configs():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/api/v1/configs/800", timeout=5)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_missing_config_returns_404():
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/api/v1/configs/1",
            params={"region": "europe"},
            headers=HEADERS,
            timeout=5,
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_configs_returns_pagination_shape():
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/api/v1/configs",
            params={"region": "europe", "page": 1, "limit": 5},
            headers=HEADERS,
            timeout=5,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert data["page"] == 1
    assert data["limit"] == 5
    assert data["region"] == "europe"


@pytest.mark.asyncio
async def test_range_start_greater_than_end_returns_400():
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/api/v1/configs/range",
            params={"start": 1000, "end": 800, "region": "europe"},
            headers=HEADERS,
            timeout=5,
        )
    assert resp.status_code == 400
