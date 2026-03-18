import pytest
from fastapi.testclient import TestClient

from api.middleware.rate_limit import limiter


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("API_SECRET_KEY", "test-secret")

    from api.app import create_app

    limiter._storage.reset()
    with TestClient(create_app(load_env=False), raise_server_exceptions=False) as test_client:
        yield test_client
    limiter._storage.reset()


def test_api_secret_required(monkeypatch):
    monkeypatch.delenv("API_SECRET_KEY", raising=False)

    from api.app import create_app

    with pytest.raises(RuntimeError, match="API_SECRET_KEY"):
        create_app(load_env=False)


def test_create_app_loads_api_secret_from_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("API_SECRET_KEY=from-dotenv\n")
    monkeypatch.setenv("ATLAS_FABRIC_ENV_FILE", str(env_file))
    monkeypatch.delenv("API_SECRET_KEY", raising=False)

    from api.app import create_app

    app = create_app()
    assert app.title == "AtlasFabric API"


def test_health_is_public_and_rate_limit_exempt(client):
    for _ in range(105):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_auth_required_on_configs(client):
    resp = client.get("/api/v1/configs/800", params={"region": "europe"})
    assert resp.status_code == 401


def test_wrong_api_key_returns_401(client):
    resp = client.get(
        "/api/v1/configs/800",
        params={"region": "europe"},
        headers={"X-API-Key": "wrong"},
    )
    assert resp.status_code == 401


def test_missing_config_returns_404(client, monkeypatch):
    async def fake_get_config(year: int, region: str):
        assert year == 1
        assert region == "europe"
        return None

    monkeypatch.setattr("api.routes.configs.get_config", fake_get_config)

    resp = client.get(
        "/api/v1/configs/1",
        params={"region": "europe"},
        headers={"X-API-Key": "test-secret"},
    )
    assert resp.status_code == 404


def test_list_configs_returns_pagination_shape(client, monkeypatch):
    async def fake_list_configs(region: str, page: int, limit: int):
        assert region == "europe"
        assert page == 1
        assert limit == 5
        return [{"year": 800, "region": region}]

    monkeypatch.setattr("api.routes.configs.list_configs", fake_list_configs)

    resp = client.get(
        "/api/v1/configs",
        params={"region": "europe", "page": 1, "limit": 5},
        headers={"X-API-Key": "test-secret"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"] == [{"year": 800, "region": "europe"}]
    assert data["page"] == 1
    assert data["limit"] == 5
    assert data["region"] == "europe"


def test_range_start_greater_than_end_returns_400(client):
    resp = client.get(
        "/api/v1/configs/range",
        params={"start": 1000, "end": 800, "region": "europe"},
        headers={"X-API-Key": "test-secret"},
    )
    assert resp.status_code == 400


def test_range_forwards_limit_and_returns_shape(client, monkeypatch):
    async def fake_list_configs_range(start_year: int, end_year: int, region: str, limit: int):
        assert start_year == 800
        assert end_year == 1200
        assert region == "europe"
        assert limit == 2
        return [{"year": 800}, {"year": 900}]

    monkeypatch.setattr("api.routes.configs.list_configs_range", fake_list_configs_range)

    resp = client.get(
        "/api/v1/configs/range",
        params={"start": 800, "end": 1200, "region": "europe", "limit": 2},
        headers={"X-API-Key": "test-secret"},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "start": 800,
        "end": 1200,
        "region": "europe",
        "limit": 2,
        "results": [{"year": 800}, {"year": 900}],
    }


def test_more_than_100_requests_are_rate_limited(client, monkeypatch):
    async def fake_get_config(year: int, region: str):
        return {"year": year, "region": region}

    monkeypatch.setattr("api.routes.configs.get_config", fake_get_config)

    for _ in range(100):
        resp = client.get(
            "/api/v1/configs/800",
            params={"region": "europe"},
            headers={"X-API-Key": "test-secret"},
        )
        assert resp.status_code == 200

    resp = client.get(
        "/api/v1/configs/800",
        params={"region": "europe"},
        headers={"X-API-Key": "test-secret"},
    )
    assert resp.status_code == 429
