# AtlasFabric — Build Plan

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Phase Summary](#2-phase-summary)
3. [Phase 0 — Environment Setup](#3-phase-0--environment-setup)
4. [Phase 1 — Core Data Models + Geo Module](#4-phase-1--core-data-models--geo-module)
5. [Phase 2 — model_factory.py](#5-phase-2--model_factorypy)
6. [Phase 3 — Generator Agent](#6-phase-3--generator-agent)
7. [Phase 4 — Reviewer Agent](#7-phase-4--reviewer-agent)
8. [Phase 5 — Orchestrator](#8-phase-5--orchestrator)
9. [Phase 6 — Storage + API](#9-phase-6--storage--api)
10. [Phase 7 — CLI](#10-phase-7--cli)
11. [Phase 8 — Integration Tests](#11-phase-8--integration-tests)
12. [Data Formats](#12-data-formats)
13. [Code Specs](#13-code-specs)

---

## 1. Architecture Overview

```
CLI input (year, region, dry_run)
        │
        ▼
   Orchestrator  ←──────────────────────────────┐
        │                                        │
        ▼                                        │ rejected (max 3 retries)
  Generator Agent (LangGraph)                    │ with specific feedback
    10 tools, sequential tool-calling loop        │
        │                                        │
        ▼                                        │
  Reviewer Agent (LangGraph)  ──────────────────►┘
    6 tools, adversarial review
        │
        ├── approved / partial
        ▼
  store_config() → MongoDB
        │
        ▼
  FastAPI serves stored configs
```

### Data flow

```
Natural Earth GeoJSON (~4,600 polygons)
        │  load_polygons
        ▼
  [polygon features with admin_id, name, geometry]
        │  classify_batch (×N batches)
        ▼
  {admin_id → polity_name}  +  confidence_scores
        │  query_knowledge_base (validation gate)
        ▼
  validated classifications
        │  union_geometries  ← only after validate_geometry passes
        ▼
  {polity_name → unified Shapely geometry}
        │  build_maplibre_config
        ▼
  MapLibre GL JS config dict
        │  reviewer gates
        ▼
  stored MapConfigDocument
```

---

## 2. Phase Summary

| Phase | What | Gate Condition |
|-------|------|----------------|
| 0 | Environment setup | `make setup` clean; all imports succeed |
| 1 | Core data models + geo module | Unit tests pass with no external deps |
| 2 | model_factory.py | All model_factory tests pass |
| 3 | Generator agent | Generator runs dry_run on year=800, region=europe |
| 4 | Reviewer agent | Reviewer runs on sample generator output |
| 5 | Orchestrator | Full pipeline: year=800, region=europe, dry_run=True |
| 6 | Storage + API | All endpoints return correct responses |
| 7 | CLI | `make generate ARGS="--year 800 --region europe --dry-run"` works |
| 8 | Integration tests | Full test suite passes |

Do not start a phase until its predecessor's gate condition is verified.

---

## 3. Phase 0 — Environment Setup

### Deliverables

- `pyproject.toml`
- `Makefile`
- `.env.example`
- `data/` directory placeholder (`data/.gitkeep`)
- Full directory skeleton (empty `__init__.py` files)

### pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "atlas-fabric"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "langgraph>=0.2",
    "langchain>=0.3",
    "langchain-anthropic",
    "langchain-openai",
    "langchain-google-genai",
    "langchain-ollama",
    "langchain-groq",
    "langchain-mistralai",
    "shapely>=2.0",
    "geopandas",
    "motor>=3.6",
    "fastapi>=0.115",
    "uvicorn[standard]",
    "typer>=0.13",
    "pydantic>=2.0",
    "slowapi",
    "python-dotenv",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-asyncio",
    "ruff",
    "mypy",
    "httpx",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.mypy]
python_version = "3.12"
strict = false
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### Makefile

```makefile
.PHONY: setup generate run-api test test-unit test-integration lint

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

setup:
	python3.12 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	mkdir -p data
	@echo "Setup complete. Copy .env.example to .env and fill in values."

generate:
	$(PYTHON) -m cli.main generate $(ARGS)

run-api:
	$(PYTHON) -m uvicorn api.app:create_app --factory --host 0.0.0.0 --port $${PORT:-8080} --reload

test:
	$(VENV)/bin/pytest tests/ -v

test-unit:
	$(VENV)/bin/pytest tests/unit/ -v

test-integration:
	$(VENV)/bin/pytest tests/integration/ -v

lint:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/mypy .
```

### .env.example

```dotenv
# Model selection — change provider/model without touching code
GENERATOR_MODEL=anthropic/claude-opus-4-5
REVIEWER_MODEL=anthropic/claude-opus-4-5

# Provider API keys — only set the ones you use
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=

# Temperatures
GENERATOR_TEMPERATURE=0.2
REVIEWER_TEMPERATURE=0.0

# Infrastructure
MONGODB_URI=mongodb://localhost:27017
API_SECRET_KEY=changeme

# Server
PORT=8080

# Data
NATURAL_EARTH_DATA_PATH=./data/ne_10m_admin_1_states_provinces.geojson
```

### Directory skeleton

Create `__init__.py` in every package directory:

```
agents/
agents/generator/
agents/reviewer/
cli/
geo/
knowledge/
storage/
api/
api/routes/
api/middleware/
tests/
tests/unit/
tests/integration/
```

### Gate condition

```bash
make setup
source .venv/bin/activate
python -c "
import langchain, langgraph, shapely, geopandas, motor, fastapi, typer, pydantic, slowapi
print('All imports OK')
"
```

Must print `All imports OK` with no errors.

---

## 4. Phase 1 — Core Data Models + Geo Module

### Deliverables

- `agents/state.py`
- `storage/schema.py`
- `geo/regions.py`
- `geo/loader.py`
- `geo/validator.py`
- `geo/union.py`
- `knowledge/polities.json`
- `knowledge/validator.py`
- `tests/unit/test_validator.py`
- `tests/unit/test_union.py`

### agents/state.py

```python
from typing import Any
from typing_extensions import TypedDict


class AtlasState(TypedDict):
    # Input
    year: int
    region: str
    dry_run: bool

    # Working data
    polygons: list[dict]                    # GeoJSON Feature dicts from Natural Earth
    classifications: dict[str, str]         # admin_id → polity_name
    confidence_scores: dict[str, float]     # polity_name → 0.0–1.0
    polity_geometries: dict[str, Any]       # polity_name → Shapely geometry (post-union)

    # Validation
    validation_errors: list[str]

    # Output
    map_config: dict                        # MapLibre GL JS config dict

    # Review
    review_decision: str                    # "approved" | "partial" | "rejected"
    review_feedback: str

    # Orchestration
    retry_count: int
    existing_config: dict | None
    metadata: dict

    # LangGraph message passing
    messages: list[Any]
```

### storage/schema.py

```python
from datetime import datetime
from pydantic import BaseModel, Field


class MapConfigMetadata(BaseModel):
    generator_model: str
    reviewer_model: str
    confidence_scores: dict[str, float]
    polygon_count: int
    polity_count: int
    retry_count: int
    review_decision: str
    known_limitations: list[str] = [
        "Natural Earth uses modern boundaries; historical polities did not follow modern province lines.",
        "polities.json accuracy depends on seeded knowledge base.",
    ]


class MapConfigDocument(BaseModel):
    id: str = Field(..., description="Composite key: {year}_{region}")
    year: int
    region: str
    config: dict
    metadata: MapConfigMetadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### geo/regions.py

```python
# Bounding boxes in EPSG:4326: (min_lon, min_lat, max_lon, max_lat)
REGION_BOUNDS: dict[str, tuple[float, float, float, float]] = {
    "world":          (-180.0, -90.0,  180.0,  90.0),
    "europe":         (-25.0,   34.0,   45.0,  72.0),
    "middle_east":    ( 25.0,   12.0,   65.0,  42.0),
    "north_africa":   (-18.0,   15.0,   42.0,  38.0),
    "sub_saharan":    (-20.0,  -35.0,   52.0,  15.0),
    "south_asia":     ( 60.0,    5.0,   90.0,  38.0),
    "east_asia":      ( 95.0,   18.0,  145.0,  55.0),
    "central_asia":   ( 45.0,   35.0,   90.0,  55.0),
    "north_america":  (-170.0,  15.0,  -50.0,  72.0),
    "south_america":  ( -82.0, -56.0,  -34.0,  13.0),
    "southeast_asia": (  92.0,  -10.0, 145.0,  28.0),
}


def get_bounds(region: str) -> tuple[float, float, float, float]:
    if region not in REGION_BOUNDS:
        raise ValueError(f"Unknown region '{region}'. Valid: {list(REGION_BOUNDS)}")
    return REGION_BOUNDS[region]


def list_regions() -> list[str]:
    return list(REGION_BOUNDS.keys())
```

### geo/loader.py

```python
import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import shape

from geo.regions import get_bounds


def load_polygons(geojson_path: str, region: str) -> list[dict]:
    """
    Load Natural Earth admin-1 polygons for a given region.

    Returns a list of dicts, each with:
        admin_id: str       unique identifier (adm1_code)
        name: str           province/state name
        country: str        sovereign country name
        geometry_wkt: str   WKT representation of the polygon (EPSG:4326)
        centroid_lon: float
        centroid_lat: float
    """
    path = Path(geojson_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Natural Earth data not found at {geojson_path}. "
            "Download ne_10m_admin_1_states_provinces.geojson from naturalearthdata.com."
        )

    gdf = gpd.read_file(path)
    gdf = gdf.to_crs("EPSG:4326")

    min_lon, min_lat, max_lon, max_lat = get_bounds(region)
    mask = (
        (gdf.geometry.centroid.x >= min_lon) &
        (gdf.geometry.centroid.x <= max_lon) &
        (gdf.geometry.centroid.y >= min_lat) &
        (gdf.geometry.centroid.y <= max_lat)
    )
    gdf = gdf[mask].copy()

    results = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        results.append({
            "admin_id": str(row.get("adm1_code", row.get("ADM1_COD", ""))),
            "name": str(row.get("name", row.get("NAME", ""))),
            "country": str(row.get("admin", row.get("ADMIN", ""))),
            "geometry_wkt": geom.wkt,
            "centroid_lon": float(geom.centroid.x),
            "centroid_lat": float(geom.centroid.y),
        })

    return results
```

### geo/validator.py

```python
from shapely import from_wkt
from shapely.geometry import MultiPolygon, Polygon


def check_validity(geometry_wkt: str) -> list[str]:
    """Return list of error strings. Empty list means valid."""
    errors = []
    try:
        geom = from_wkt(geometry_wkt)
    except Exception as e:
        return [f"WKT parse error: {e}"]

    if geom is None or geom.is_empty:
        errors.append("Geometry is empty")
        return errors

    if not geom.is_valid:
        errors.append(f"Invalid geometry: {geom.is_valid}")

    if not isinstance(geom, (Polygon, MultiPolygon)):
        errors.append(f"Expected Polygon or MultiPolygon, got {type(geom).__name__}")

    bounds = geom.bounds  # (minx, miny, maxx, maxy)
    if not (-180 <= bounds[0] <= 180 and -180 <= bounds[2] <= 180):
        errors.append("Longitude out of EPSG:4326 range")
    if not (-90 <= bounds[1] <= 90 and -90 <= bounds[3] <= 90):
        errors.append("Latitude out of EPSG:4326 range")

    return errors


def check_overlaps(polity_geometries: dict[str, object]) -> list[str]:
    """
    Check that no two polities share overlapping area.
    Returns list of error strings describing overlapping pairs.
    """
    errors = []
    names = list(polity_geometries.keys())
    geoms = list(polity_geometries.values())

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if geoms[i] is None or geoms[j] is None:
                continue
            if geoms[i].intersects(geoms[j]):
                overlap = geoms[i].intersection(geoms[j])
                if not overlap.is_empty and overlap.area > 1e-10:
                    errors.append(
                        f"Overlap between '{names[i]}' and '{names[j]}' "
                        f"(area={overlap.area:.6f} sq degrees)"
                    )
    return errors


def validate_classifications(classifications: dict[str, str]) -> list[str]:
    """
    Validate that no admin_id is assigned to more than one polity.
    classifications: {admin_id → polity_name}
    Returns list of error strings.
    """
    seen: dict[str, str] = {}
    errors = []
    for admin_id, polity in classifications.items():
        if admin_id in seen and seen[admin_id] != polity:
            errors.append(
                f"admin_id '{admin_id}' assigned to both "
                f"'{seen[admin_id]}' and '{polity}'"
            )
        seen[admin_id] = polity
    return errors
```

### geo/union.py

```python
from shapely import from_wkt
from shapely.ops import unary_union


def union_by_polity(
    polygons: list[dict],
    classifications: dict[str, str],
) -> dict[str, object]:
    """
    Union polygon geometries grouped by polity assignment.

    Args:
        polygons: list of polygon dicts (must have admin_id, geometry_wkt)
        classifications: {admin_id → polity_name}

    Returns:
        {polity_name → unified Shapely geometry}

    Note: Call this ONLY after validate_classifications and check_overlaps pass.
    """
    polity_groups: dict[str, list] = {}
    for poly in polygons:
        admin_id = poly["admin_id"]
        polity = classifications.get(admin_id)
        if polity is None:
            continue
        geom = from_wkt(poly["geometry_wkt"])
        if geom is None or geom.is_empty:
            continue
        polity_groups.setdefault(polity, []).append(geom)

    return {
        polity: unary_union(geoms)
        for polity, geoms in polity_groups.items()
    }
```

### knowledge/polities.json

Seed with well-documented polities. Each entry covers a historical entity with known active date ranges.

```json
{
  "polities": [
    {
      "id": "frankish_empire",
      "name": "Frankish Empire",
      "also_known_as": ["Francia", "Carolingian Empire"],
      "active_from": 481,
      "active_to": 987,
      "peak_years": [800, 814],
      "region_hint": "europe",
      "notes": "Charlemagne crowned Holy Roman Emperor 800 CE. Split by Treaty of Verdun 843."
    },
    {
      "id": "byzantine_empire",
      "name": "Byzantine Empire",
      "also_known_as": ["Eastern Roman Empire", "Byzantium"],
      "active_from": 330,
      "active_to": 1453,
      "peak_years": [565, 1025],
      "region_hint": "europe",
      "notes": "Survived until fall of Constantinople 1453."
    },
    {
      "id": "abbasid_caliphate",
      "name": "Abbasid Caliphate",
      "also_known_as": ["Abbasid Empire"],
      "active_from": 750,
      "active_to": 1258,
      "peak_years": [800, 850],
      "region_hint": "middle_east",
      "notes": "Replaced Umayyad Caliphate. Ended with Mongol sack of Baghdad 1258."
    },
    {
      "id": "umayyad_caliphate",
      "name": "Umayyad Caliphate",
      "also_known_as": ["Umayyad Empire"],
      "active_from": 661,
      "active_to": 750,
      "peak_years": [720],
      "region_hint": "middle_east",
      "notes": "Overthrown by Abbasid Revolution 750. Umayyad emirate survived in Al-Andalus."
    },
    {
      "id": "umayyad_emirate_andalus",
      "name": "Umayyad Emirate of Córdoba",
      "also_known_as": ["Al-Andalus", "Emirate of Córdoba"],
      "active_from": 756,
      "active_to": 929,
      "peak_years": [800, 850],
      "region_hint": "europe",
      "notes": "Became Caliphate of Córdoba in 929."
    },
    {
      "id": "caliphate_cordoba",
      "name": "Caliphate of Córdoba",
      "also_known_as": ["Cordoban Caliphate"],
      "active_from": 929,
      "active_to": 1031,
      "peak_years": [1000],
      "region_hint": "europe",
      "notes": "Fragmented into taifa kingdoms 1031."
    },
    {
      "id": "holy_roman_empire",
      "name": "Holy Roman Empire",
      "also_known_as": ["HRE", "German Kingdom"],
      "active_from": 962,
      "active_to": 1806,
      "peak_years": [1050, 1200],
      "region_hint": "europe",
      "notes": "Founded by Otto I. Complex feudal structure, not a centralized state."
    },
    {
      "id": "kingdom_england",
      "name": "Kingdom of England",
      "also_known_as": ["England"],
      "active_from": 927,
      "active_to": 1707,
      "peak_years": [1200, 1400],
      "region_hint": "europe",
      "notes": "Unified by Æthelstan 927. Became Kingdom of Great Britain 1707."
    },
    {
      "id": "kingdom_france",
      "name": "Kingdom of France",
      "also_known_as": ["France"],
      "active_from": 987,
      "active_to": 1792,
      "peak_years": [1300, 1600],
      "region_hint": "europe",
      "notes": "Capetian dynasty from 987. Became Republic 1792."
    },
    {
      "id": "mongol_empire",
      "name": "Mongol Empire",
      "also_known_as": ["Great Mongol Nation"],
      "active_from": 1206,
      "active_to": 1368,
      "peak_years": [1260, 1279],
      "region_hint": "central_asia",
      "notes": "Largest contiguous land empire. Fragmented into Khanates."
    },
    {
      "id": "tang_dynasty",
      "name": "Tang Dynasty",
      "also_known_as": ["Tang China"],
      "active_from": 618,
      "active_to": 907,
      "peak_years": [700, 750],
      "region_hint": "east_asia",
      "notes": "Golden age of Chinese civilization."
    },
    {
      "id": "song_dynasty",
      "name": "Song Dynasty",
      "also_known_as": ["Song China"],
      "active_from": 960,
      "active_to": 1279,
      "peak_years": [1000, 1100],
      "region_hint": "east_asia",
      "notes": "Northern Song fell to Jin dynasty 1127; Southern Song ended 1279."
    },
    {
      "id": "roman_empire",
      "name": "Roman Empire",
      "also_known_as": ["Rome", "Imperium Romanum"],
      "active_from": -27,
      "active_to": 476,
      "peak_years": [100, 200],
      "region_hint": "europe",
      "notes": "Western Roman Empire fell 476 CE. Eastern continued as Byzantine Empire."
    },
    {
      "id": "ottoman_empire",
      "name": "Ottoman Empire",
      "also_known_as": ["Ottoman State", "Sublime Porte"],
      "active_from": 1299,
      "active_to": 1922,
      "peak_years": [1550, 1683],
      "region_hint": "middle_east",
      "notes": "Founded by Osman I. Succeeded by Republic of Turkey 1923."
    },
    {
      "id": "kievan_rus",
      "name": "Kievan Rus",
      "also_known_as": ["Rus Khaganate", "Rus"],
      "active_from": 882,
      "active_to": 1240,
      "peak_years": [980, 1054],
      "region_hint": "europe",
      "notes": "Fragmented into principalities; destroyed by Mongol invasion 1237-1242."
    },
    {
      "id": "kingdom_poland",
      "name": "Kingdom of Poland",
      "also_known_as": ["Poland"],
      "active_from": 1025,
      "active_to": 1795,
      "peak_years": [1400, 1600],
      "region_hint": "europe",
      "notes": "Crowned kingdom 1025. Merged with Lithuania 1569 (Polish-Lithuanian Commonwealth)."
    },
    {
      "id": "kingdom_hungary",
      "name": "Kingdom of Hungary",
      "also_known_as": ["Hungary"],
      "active_from": 1000,
      "active_to": 1918,
      "peak_years": [1200, 1400],
      "region_hint": "europe",
      "notes": "Founded by Stephen I 1000. Part of Habsburg Empire from 1526."
    },
    {
      "id": "kingdom_denmark",
      "name": "Kingdom of Denmark",
      "also_known_as": ["Denmark"],
      "active_from": 936,
      "active_to": 1814,
      "peak_years": [1100, 1400],
      "region_hint": "europe",
      "notes": "One of the oldest monarchies."
    },
    {
      "id": "kingdom_norway",
      "name": "Kingdom of Norway",
      "also_known_as": ["Norway"],
      "active_from": 872,
      "active_to": 1814,
      "peak_years": [1000, 1200],
      "region_hint": "europe",
      "notes": "United under Harald Fairhair ~872."
    },
    {
      "id": "kingdom_sweden",
      "name": "Kingdom of Sweden",
      "also_known_as": ["Sweden"],
      "active_from": 970,
      "active_to": 1809,
      "peak_years": [1600, 1700],
      "region_hint": "europe",
      "notes": "Great Power in 17th century (Swedish Empire)."
    }
  ]
}
```

### knowledge/validator.py

```python
import json
from pathlib import Path


_POLITIES: list[dict] | None = None
_POLITIES_BY_ID: dict[str, dict] | None = None


def _load() -> list[dict]:
    global _POLITIES, _POLITIES_BY_ID
    if _POLITIES is None:
        path = Path(__file__).parent / "polities.json"
        data = json.loads(path.read_text())
        _POLITIES = data["polities"]
        _POLITIES_BY_ID = {p["id"]: p for p in _POLITIES}
    return _POLITIES


def get_polities_for_year(year: int, region: str | None = None) -> list[dict]:
    """Return polities active in the given year, optionally filtered by region_hint."""
    polities = _load()
    result = []
    for p in polities:
        if p["active_from"] <= year <= p["active_to"]:
            if region is None or p.get("region_hint") == region:
                result.append(p)
    return result


def verify_polity_exists(polity_name: str, year: int) -> dict:
    """
    Check if a polity name matches a known entity active in the given year.

    Returns:
        {"found": bool, "polity": dict | None, "issue": str | None}
    """
    _load()
    assert _POLITIES_BY_ID is not None

    # Exact ID match
    polity = _POLITIES_BY_ID.get(polity_name.lower().replace(" ", "_"))
    if polity:
        if polity["active_from"] <= year <= polity["active_to"]:
            return {"found": True, "polity": polity, "issue": None}
        return {
            "found": False,
            "polity": polity,
            "issue": f"'{polity_name}' existed but not in year {year} "
                     f"(active {polity['active_from']}–{polity['active_to']})",
        }

    # Name / alias fuzzy match
    for p in _POLITIES:
        names = [p["name"]] + p.get("also_known_as", [])
        if any(polity_name.lower() in n.lower() for n in names):
            if p["active_from"] <= year <= p["active_to"]:
                return {"found": True, "polity": p, "issue": None}
            return {
                "found": False,
                "polity": p,
                "issue": f"'{polity_name}' existed but not in year {year}",
            }

    return {
        "found": False,
        "polity": None,
        "issue": f"'{polity_name}' not found in knowledge base",
    }


def detect_anachronism(polity_name: str, year: int) -> dict:
    """
    Return anachronism details if the polity is used outside its known date range.

    Returns:
        {"is_anachronism": bool, "reason": str | None}
    """
    result = verify_polity_exists(polity_name, year)
    if result["found"]:
        return {"is_anachronism": False, "reason": None}
    return {"is_anachronism": True, "reason": result["issue"]}
```

### tests/unit/test_validator.py

Tests must not require MongoDB, API keys, or network access.

```python
import pytest
from geo.validator import check_validity, check_overlaps, validate_classifications
from shapely.geometry import Polygon


VALID_WKT = "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"
INVALID_WKT = "POLYGON ((0 0, 1 1, 1 0, 0 1, 0 0))"  # self-intersecting bowtie


def test_valid_geometry_passes():
    errors = check_validity(VALID_WKT)
    assert errors == []


def test_invalid_geometry_caught():
    errors = check_validity(INVALID_WKT)
    assert len(errors) > 0


def test_out_of_bounds_longitude():
    wkt = "POLYGON ((200 0, 201 0, 201 1, 200 1, 200 0))"
    errors = check_validity(wkt)
    assert any("Longitude" in e for e in errors)


def test_no_overlap():
    p1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    p2 = Polygon([(2, 0), (3, 0), (3, 1), (2, 1)])
    errors = check_overlaps({"A": p1, "B": p2})
    assert errors == []


def test_overlap_detected():
    p1 = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    p2 = Polygon([(1, 0), (3, 0), (3, 2), (1, 2)])
    errors = check_overlaps({"A": p1, "B": p2})
    assert len(errors) > 0
    assert "A" in errors[0] and "B" in errors[0]


def test_duplicate_assignment_detected():
    classifications = {
        "admin_001": "frankish_empire",
        "admin_002": "byzantine_empire",
    }
    errors = validate_classifications(classifications)
    assert errors == []


def test_no_duplicate_in_valid_classifications():
    classifications = {
        "admin_001": "polity_a",
        "admin_002": "polity_b",
    }
    assert validate_classifications(classifications) == []
```

### tests/unit/test_union.py

```python
import pytest
from geo.union import union_by_polity
from shapely.geometry import Polygon


def _make_polygon_dict(admin_id: str, minx: float, miny: float, maxx: float, maxy: float) -> dict:
    p = Polygon([(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)])
    return {
        "admin_id": admin_id,
        "name": admin_id,
        "country": "test",
        "geometry_wkt": p.wkt,
        "centroid_lon": (minx + maxx) / 2,
        "centroid_lat": (miny + maxy) / 2,
    }


def test_union_two_adjacent_polygons():
    polygons = [
        _make_polygon_dict("a1", 0, 0, 1, 1),
        _make_polygon_dict("a2", 1, 0, 2, 1),
    ]
    classifications = {"a1": "polity_x", "a2": "polity_x"}
    result = union_by_polity(polygons, classifications)
    assert "polity_x" in result
    assert abs(result["polity_x"].area - 2.0) < 1e-9


def test_union_separate_polities():
    polygons = [
        _make_polygon_dict("a1", 0, 0, 1, 1),
        _make_polygon_dict("a2", 5, 5, 6, 6),
    ]
    classifications = {"a1": "polity_x", "a2": "polity_y"}
    result = union_by_polity(polygons, classifications)
    assert "polity_x" in result
    assert "polity_y" in result
    assert abs(result["polity_x"].area - 1.0) < 1e-9


def test_unclassified_polygons_skipped():
    polygons = [_make_polygon_dict("a1", 0, 0, 1, 1)]
    result = union_by_polity(polygons, {})
    assert result == {}
```

### Gate condition

```bash
make test-unit
```

All tests in `tests/unit/test_validator.py` and `tests/unit/test_union.py` must pass. No external deps required.

---

## 5. Phase 2 — model_factory.py

### Deliverables

- `agents/model_factory.py`
- `tests/unit/test_model_factory.py`

### agents/model_factory.py

```python
"""
model_factory.py — THE ONLY FILE THAT IMPORTS LLM PROVIDER CLASSES.

Agent code NEVER imports ChatAnthropic, ChatOpenAI, etc. directly.
Always call get_model(role="generator") or get_model(role="reviewer").
"""

import os
from functools import lru_cache
from typing import Literal

from langchain_core.language_models import BaseChatModel


Role = Literal["generator", "reviewer"]


_PROVIDER_MAP = {
    "anthropic": "_load_anthropic",
    "openai":    "_load_openai",
    "google":    "_load_google",
    "ollama":    "_load_ollama",
    "groq":      "_load_groq",
    "mistral":   "_load_mistral",
}


def get_model(role: Role) -> BaseChatModel:
    """
    Return a configured LLM for the given role.

    Reads from environment:
        GENERATOR_MODEL=anthropic/claude-opus-4-5
        REVIEWER_MODEL=openai/gpt-4o

    Format: {provider}/{model_name}
    """
    env_key = f"{role.upper()}_MODEL"
    model_string = os.environ.get(env_key)
    if not model_string:
        raise ValueError(
            f"Environment variable {env_key} is not set. "
            f"Example: {env_key}=anthropic/claude-opus-4-5"
        )

    temperature_key = f"{role.upper()}_TEMPERATURE"
    temperature = float(os.environ.get(temperature_key, "0.0"))

    return _build_model(model_string, temperature)


def _build_model(model_string: str, temperature: float) -> BaseChatModel:
    if "/" not in model_string:
        raise ValueError(
            f"Invalid model string '{model_string}'. "
            f"Expected format: provider/model_name (e.g. anthropic/claude-opus-4-5)"
        )

    provider, model_name = model_string.split("/", 1)

    if provider not in _PROVIDER_MAP:
        raise ValueError(
            f"Unsupported provider '{provider}'. "
            f"Supported: {list(_PROVIDER_MAP.keys())}"
        )

    loader_name = _PROVIDER_MAP[provider]
    loader = globals()[loader_name]
    return loader(model_name, temperature)


def _load_anthropic(model_name: str, temperature: float) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=model_name, temperature=temperature)


def _load_openai(model_name: str, temperature: float) -> BaseChatModel:
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model_name, temperature=temperature)


def _load_google(model_name: str, temperature: float) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=model_name, temperature=temperature)


def _load_ollama(model_name: str, temperature: float) -> BaseChatModel:
    from langchain_ollama import ChatOllama
    return ChatOllama(model=model_name, temperature=temperature)


def _load_groq(model_name: str, temperature: float) -> BaseChatModel:
    from langchain_groq import ChatGroq
    return ChatGroq(model=model_name, temperature=temperature)


def _load_mistral(model_name: str, temperature: float) -> BaseChatModel:
    from langchain_mistralai import ChatMistralAI
    return ChatMistralAI(model=model_name, temperature=temperature)
```

### tests/unit/test_model_factory.py

```python
import os
import pytest
from unittest.mock import patch, MagicMock


def test_missing_env_var_raises():
    from agents.model_factory import get_model
    with patch.dict(os.environ, {}, clear=True):
        # Remove any existing GENERATOR_MODEL
        env = {k: v for k, v in os.environ.items() if k != "GENERATOR_MODEL"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="GENERATOR_MODEL"):
                get_model("generator")


def test_invalid_format_raises():
    from agents.model_factory import _build_model
    with pytest.raises(ValueError, match="provider/model_name"):
        _build_model("claude-opus-4-5", 0.0)  # missing provider prefix


def test_unsupported_provider_raises():
    from agents.model_factory import _build_model
    with pytest.raises(ValueError, match="Unsupported provider"):
        _build_model("cohere/command-r", 0.0)


def test_correct_provider_selected_anthropic():
    from agents.model_factory import _build_model
    mock_model = MagicMock()
    with patch("agents.model_factory._load_anthropic", return_value=mock_model) as mock_loader:
        result = _build_model("anthropic/claude-opus-4-5", 0.2)
        mock_loader.assert_called_once_with("claude-opus-4-5", 0.2)
        assert result is mock_model


def test_correct_provider_selected_openai():
    from agents.model_factory import _build_model
    mock_model = MagicMock()
    with patch("agents.model_factory._load_openai", return_value=mock_model) as mock_loader:
        result = _build_model("openai/gpt-4o", 0.0)
        mock_loader.assert_called_once_with("gpt-4o", 0.0)
        assert result is mock_model


def test_temperature_passed_correctly():
    from agents.model_factory import _build_model
    mock_model = MagicMock()
    with patch("agents.model_factory._load_anthropic", return_value=mock_model) as mock_loader:
        _build_model("anthropic/claude-haiku-4-5", 0.7)
        _, kwargs = mock_loader.call_args
        # temperature is a positional arg
        assert mock_loader.call_args[0][1] == 0.7


def test_get_model_reads_env():
    from agents.model_factory import get_model
    mock_model = MagicMock()
    env = {
        "GENERATOR_MODEL": "anthropic/claude-opus-4-5",
        "GENERATOR_TEMPERATURE": "0.2",
    }
    with patch.dict(os.environ, env):
        with patch("agents.model_factory._load_anthropic", return_value=mock_model):
            result = get_model("generator")
            assert result is mock_model


def test_reviewer_role_reads_reviewer_env():
    from agents.model_factory import get_model
    mock_model = MagicMock()
    env = {
        "REVIEWER_MODEL": "openai/gpt-4o",
        "REVIEWER_TEMPERATURE": "0.0",
    }
    with patch.dict(os.environ, env):
        with patch("agents.model_factory._load_openai", return_value=mock_model):
            result = get_model("reviewer")
            assert result is mock_model


def test_all_providers_have_loaders():
    from agents.model_factory import _PROVIDER_MAP
    expected = {"anthropic", "openai", "google", "ollama", "groq", "mistral"}
    assert set(_PROVIDER_MAP.keys()) == expected
```

### Gate condition

```bash
make test-unit
```

All 8 tests in `test_model_factory.py` must pass. No API keys needed — tests use mocks only.

---

## 6. Phase 3 — Generator Agent

### Deliverables

- `agents/generator/prompts.py`
- `agents/generator/tools.py` (10 `@tool` definitions)
- `agents/generator/graph.py`

### agents/generator/prompts.py

```python
SYSTEM_PROMPT = """You are a historical cartographer AI.
Your job is to assign modern administrative polygons to the historical polities that controlled them
for a specific year and region.

You will be given a year and a region. Follow this exact sequence of tool calls:

1. Call get_existing_config FIRST. If a config already exists and is recent, return it directly.
2. Call estimate_cost to check if the request is within budget.
3. Call get_region_bounds to get the geographic bounding box.
4. Call query_knowledge_base to get known polities active in this year and region.
5. Call load_polygons to fetch the administrative polygons for this region.
6. Call research_historical_context to gather historical facts about this year and region.
7. Call classify_batch repeatedly until ALL polygons are classified.
   - Use batches of 50 polygons maximum.
   - Assign UNCONTROLLED to polygons in stateless regions (oceans, deserts, ungoverned territory).
8. Call union_geometries ONLY after all polygons are classified.
9. Call validate_geometry to check for overlaps and validity errors.
   - If errors exist, re-classify the conflicting polygons and re-validate.
10. Call build_maplibre_config to produce the final output.

Rules:
- Every polygon must be assigned to exactly one polity (or UNCONTROLLED).
- Do not assign a polygon to a polity that did not exist in the given year.
- Use the knowledge base — do not invent polity names.
- Confidence scores reflect certainty: use 0.9+ only for well-documented assignments.
"""

RETRY_PROMPT_TEMPLATE = """The reviewer rejected the previous attempt with this feedback:

{feedback}

Retry number {retry_count} of 3.

Address the specific issues raised. Do not repeat the same mistakes.
Re-classify the flagged polygons. Explain your corrections.
"""
```

### agents/generator/tools.py

All 10 tools. Docstrings are behavioral instructions for the LLM — never rewrite them for style.

```python
import json
import os
from typing import Any

from langchain_core.tools import tool

from geo.loader import load_polygons as _load_polygons
from geo.union import union_by_polity
from geo.validator import check_overlaps, check_validity, validate_classifications
from geo.regions import get_bounds, list_regions
from knowledge.validator import get_polities_for_year


@tool
def get_existing_config(year: int, region: str) -> dict:
    """Call this FIRST before any other tool.
    Returns an existing map config if one was already generated for this year and region.
    If found, you MUST return it immediately without re-generating.
    Returns {"found": False} if no existing config exists."""
    # Import here to avoid circular at module level; storage may not be initialized yet
    try:
        from storage.mongo import get_config_sync
        config = get_config_sync(year, region)
        if config:
            return {"found": True, "config": config}
    except Exception:
        pass
    return {"found": False}


@tool
def estimate_cost(year: int, region: str, polygon_count: int) -> dict:
    """Call this SECOND, after get_existing_config returns {"found": False}.
    Estimates the approximate token cost for classifying polygon_count polygons.
    Returns {"estimated_tokens": int, "within_budget": bool, "warning": str | None}.
    Do NOT proceed if within_budget is False."""
    tokens_per_polygon = 150
    estimated = polygon_count * tokens_per_polygon
    within_budget = estimated < 500_000
    warning = None
    if estimated > 300_000:
        warning = f"Large request: ~{estimated:,} tokens. Consider narrowing region."
    return {
        "estimated_tokens": estimated,
        "within_budget": within_budget,
        "warning": warning,
    }


@tool
def get_region_bounds(region: str) -> dict:
    """Returns the geographic bounding box for the given region name.
    Call this to understand the spatial extent before loading polygons.
    Returns {"min_lon": float, "min_lat": float, "max_lon": float, "max_lat": float}
    or {"error": str} if the region is not recognised."""
    try:
        min_lon, min_lat, max_lon, max_lat = get_bounds(region)
        return {
            "min_lon": min_lon,
            "min_lat": min_lat,
            "max_lon": max_lon,
            "max_lat": max_lat,
        }
    except ValueError as e:
        return {"error": str(e), "valid_regions": list_regions()}


@tool
def query_knowledge_base(year: int, region: str) -> dict:
    """Call this BEFORE classify_batch.
    Returns all polities known to be active in the given year and region.
    Use this list as the authoritative set of polity names when classifying polygons.
    Do not invent polity names not present in this list.
    Returns {"polities": list[dict], "count": int}."""
    polities = get_polities_for_year(year, region)
    return {"polities": polities, "count": len(polities)}


@tool
def load_polygons(region: str) -> dict:
    """Loads Natural Earth admin-1 polygons for the given region.
    Returns {"polygons": list[dict], "count": int} where each polygon has:
      admin_id, name, country, geometry_wkt, centroid_lon, centroid_lat.
    Returns {"error": str} if the data file is not found."""
    geojson_path = os.environ.get(
        "NATURAL_EARTH_DATA_PATH",
        "./data/ne_10m_admin_1_states_provinces.geojson",
    )
    try:
        polygons = _load_polygons(geojson_path, region)
        return {"polygons": polygons, "count": len(polygons)}
    except FileNotFoundError as e:
        return {"error": str(e)}


@tool
def research_historical_context(year: int, region: str) -> dict:
    """Call this to retrieve relevant historical context for the year and region.
    Use this information to guide polygon classification decisions.
    Returns {"context": str} with a narrative summary of the political situation."""
    # This is a pass-through tool — the LLM itself synthesises the context
    # from its training knowledge. The tool call forces it to reason explicitly.
    return {
        "context": (
            f"Synthesise your knowledge of the political situation in {region} "
            f"around the year {year}. List the major polities, their approximate "
            "territories, and any relevant border changes in this period."
        ),
        "instruction": (
            "Use this context to guide classification. "
            "Cross-reference with the knowledge base polities."
        ),
    }


@tool
def classify_batch(
    polygons: list[dict],
    year: int,
    known_polities: list[str],
) -> dict:
    """Classify a batch of polygons (max 50) into polities for the given year.
    ONLY call after query_knowledge_base and research_historical_context.
    known_polities must come from query_knowledge_base — do not invent names.
    Each polygon in the batch must be assigned to exactly one polity name,
    or to the special value UNCONTROLLED for stateless regions.
    Returns {
      "classifications": {admin_id: polity_name},
      "confidence_scores": {admin_id: float},
      "reasoning": {admin_id: str}
    }."""
    # This tool is intentionally thin — classification logic lives in the LLM's
    # reasoning. The tool validates inputs and enforces the batch size limit.
    if len(polygons) > 50:
        return {
            "error": f"Batch too large: {len(polygons)} polygons. Maximum is 50. Split into smaller batches."
        }

    valid_polity_set = set(known_polities) | {"UNCONTROLLED"}

    # Return the structure; LLM fills it in via its reasoning
    return {
        "instruction": (
            "For each polygon, assign a polity_name from the known_polities list "
            "or use UNCONTROLLED. Return a JSON object matching this schema: "
            '{"classifications": {admin_id: polity_name}, '
            '"confidence_scores": {admin_id: 0.0-1.0}, '
            '"reasoning": {admin_id: "brief explanation"}}'
        ),
        "polygons_to_classify": [
            {"admin_id": p["admin_id"], "name": p["name"], "country": p["country"],
             "centroid_lon": p["centroid_lon"], "centroid_lat": p["centroid_lat"]}
            for p in polygons
        ],
        "valid_polities": list(valid_polity_set),
        "year": year,
    }


@tool
def union_geometries(
    polygons: list[dict],
    classifications: dict[str, str],
) -> dict:
    """Union polygon geometries by polity assignment.
    ONLY call this AFTER validate_classifications returns no errors.
    Polygon union happens AFTER validation — never before.
    Returns {"polity_geometries": {polity_name: geometry_wkt}, "polity_count": int}
    or {"error": str} if union fails."""
    errors = validate_classifications(classifications)
    if errors:
        return {"error": f"Classification errors must be fixed first: {errors}"}

    try:
        geoms = union_by_polity(polygons, classifications)
        return {
            "polity_geometries": {name: geom.wkt for name, geom in geoms.items()},
            "polity_count": len(geoms),
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def validate_geometry(polity_geometries: dict[str, str]) -> dict:
    """Validate all polity geometries for correctness.
    Check each geometry for validity, bounds, and type.
    Check all pairs for overlaps.
    Returns {"valid": bool, "errors": list[str]}.
    If valid is False, re-classify the conflicting polygons and re-call union_geometries."""
    from shapely import from_wkt

    all_errors: list[str] = []
    shapely_geoms: dict[str, Any] = {}

    for polity, wkt in polity_geometries.items():
        errors = check_validity(wkt)
        if errors:
            all_errors.extend([f"[{polity}] {e}" for e in errors])
        else:
            shapely_geoms[polity] = from_wkt(wkt)

    overlap_errors = check_overlaps(shapely_geoms)
    all_errors.extend(overlap_errors)

    return {"valid": len(all_errors) == 0, "errors": all_errors}


@tool
def build_maplibre_config(
    year: int,
    region: str,
    polity_geometries: dict[str, str],
    confidence_scores: dict[str, float],
    metadata: dict,
) -> dict:
    """Build the final MapLibre GL JS configuration.
    ONLY call after validate_geometry returns {"valid": True}.
    Returns the complete map_config dict ready for storage and API serving."""
    import hashlib
    import json

    # Assign deterministic colours per polity
    def polity_colour(name: str) -> str:
        h = int(hashlib.md5(name.encode()).hexdigest()[:6], 16)
        r = (h >> 16) & 0xFF
        g = (h >> 8) & 0xFF
        b = h & 0xFF
        # Shift toward mid-tones for map legibility
        r = 80 + (r % 120)
        g = 80 + (g % 120)
        b = 80 + (b % 120)
        return f"#{r:02x}{g:02x}{b:02x}"

    from shapely import from_wkt
    import shapely

    polity_features = []
    for polity_name, wkt in polity_geometries.items():
        geom = from_wkt(wkt)
        geojson_geom = shapely.geometry.mapping(geom)
        polity_features.append({
            "type": "Feature",
            "properties": {
                "polity_id": polity_name.lower().replace(" ", "_"),
                "polity_name": polity_name,
                "color": polity_colour(polity_name),
                "confidence": confidence_scores.get(polity_name, 0.5),
                "year": year,
            },
            "geometry": geojson_geom,
        })

    geojson_source = {
        "type": "FeatureCollection",
        "features": polity_features,
    }

    config = {
        "year": year,
        "region": region,
        "style": {
            "version": 8,
            "glyphs": "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
            "sources": {
                "polities": {
                    "type": "geojson",
                    "data": geojson_source,
                }
            },
            "layers": [
                {
                    "id": "polities-fill",
                    "type": "fill",
                    "source": "polities",
                    "paint": {
                        "fill-color": ["get", "color"],
                        "fill-opacity": 0.6,
                    },
                },
                {
                    "id": "polities-line",
                    "type": "line",
                    "source": "polities",
                    "paint": {
                        "line-color": "#000000",
                        "line-width": 0.5,
                        "line-opacity": 0.4,
                    },
                },
            ],
        },
        "polities": [
            {
                "id": f["properties"]["polity_id"],
                "name": f["properties"]["polity_name"],
                "color": f["properties"]["color"],
                "confidence": f["properties"]["confidence"],
            }
            for f in polity_features
            if f["properties"]["polity_name"] != "UNCONTROLLED"
        ],
        "metadata": metadata,
    }

    return {"map_config": config}
```

### agents/generator/graph.py

```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition

from agents.state import AtlasState
from agents.model_factory import get_model
from agents.generator.tools import (
    get_existing_config,
    estimate_cost,
    get_region_bounds,
    query_knowledge_base,
    load_polygons,
    research_historical_context,
    classify_batch,
    union_geometries,
    validate_geometry,
    build_maplibre_config,
)
from agents.generator.prompts import SYSTEM_PROMPT, RETRY_PROMPT_TEMPLATE
from langchain_core.messages import SystemMessage, HumanMessage


TOOLS = [
    get_existing_config,
    estimate_cost,
    get_region_bounds,
    query_knowledge_base,
    load_polygons,
    research_historical_context,
    classify_batch,
    union_geometries,
    validate_geometry,
    build_maplibre_config,
]


def build_generator_graph() -> StateGraph:
    llm = get_model("generator")
    llm_with_tools = llm.bind_tools(TOOLS)

    def agent_node(state: AtlasState) -> dict:
        messages = state.get("messages", [])
        if not messages:
            retry_count = state.get("retry_count", 0)
            review_feedback = state.get("review_feedback", "")
            if retry_count > 0 and review_feedback:
                user_content = RETRY_PROMPT_TEMPLATE.format(
                    feedback=review_feedback,
                    retry_count=retry_count,
                )
            else:
                user_content = (
                    f"Generate a historical map configuration for:\n"
                    f"  Year: {state['year']}\n"
                    f"  Region: {state['region']}\n"
                    f"  Dry run: {state.get('dry_run', False)}"
                )
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_content),
            ]

        response = llm_with_tools.invoke(messages)
        return {"messages": messages + [response]}

    graph = StateGraph(AtlasState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph.compile()


generator_graph = build_generator_graph()
```

### Gate condition

```bash
GENERATOR_MODEL=anthropic/claude-opus-4-5 \
ANTHROPIC_API_KEY=<your_key> \
NATURAL_EARTH_DATA_PATH=./data/ne_10m_admin_1_states_provinces.geojson \
python -m cli.main generate --year 800 --region europe --dry-run
```

Must complete without exceptions. `review_decision` must be populated.

---

## 7. Phase 4 — Reviewer Agent

### Deliverables

- `agents/reviewer/prompts.py`
- `agents/reviewer/tools.py` (6 `@tool` definitions)
- `agents/reviewer/graph.py`

### agents/reviewer/prompts.py

```python
SYSTEM_PROMPT = """You are an adversarial historical review agent.
Your job is to reject, partially approve, or approve a generated map configuration.
You are a different model from the generator. You have no memory of generating this config.

Follow this exact sequence:

1. Call detect_anachronism for EVERY polity in the config.
   Reject immediately if any polity did not exist in the given year.
2. Call verify_polity_exists for any polity you are uncertain about.
3. Call audit_confidence to flag low-confidence assignments.
4. Call check_coverage to ensure all polygons have been assigned.
5. Call cross_check_plausibility to assess geographic coherence.
6. Call submit_review_decision with your final verdict.

Decision criteria:
- approved: No anachronisms, coverage > 90%, no major plausibility issues.
- partial: Minor issues (low confidence zones, small coverage gaps). Include specific feedback.
- rejected: Anachronisms found, coverage < 70%, or major implausible assignments.

When rejecting, provide specific actionable feedback — list exactly which polities
or polygons are wrong and why. The generator will retry with your feedback.
"""
```

### agents/reviewer/tools.py

```python
from langchain_core.tools import tool

from knowledge.validator import detect_anachronism as _detect_anachronism
from knowledge.validator import verify_polity_exists as _verify_polity_exists


@tool
def detect_anachronism(polity_name: str, year: int) -> dict:
    """Call this for EVERY polity in the configuration — no exceptions.
    Returns {"is_anachronism": bool, "reason": str | None}.
    If is_anachronism is True, you MUST reject the configuration."""
    return _detect_anachronism(polity_name, year)


@tool
def verify_polity_exists(polity_name: str, year: int) -> dict:
    """Call this when detect_anachronism is inconclusive or for unknown polities.
    Returns {"found": bool, "polity": dict | None, "issue": str | None}.
    Use to cross-reference names, aliases, and date ranges."""
    return _verify_polity_exists(polity_name, year)


@tool
def audit_confidence(confidence_scores: dict[str, float], threshold: float = 0.5) -> dict:
    """Audit confidence scores across all polity assignments.
    Flag all polities with confidence below threshold.
    Returns {"flagged": list[str], "mean_confidence": float, "min_confidence": float}."""
    if not confidence_scores:
        return {"flagged": [], "mean_confidence": 0.0, "min_confidence": 0.0}

    flagged = [p for p, score in confidence_scores.items() if score < threshold]
    values = list(confidence_scores.values())
    return {
        "flagged": flagged,
        "mean_confidence": sum(values) / len(values),
        "min_confidence": min(values),
    }


@tool
def check_coverage(
    total_polygon_count: int,
    classified_polygon_count: int,
) -> dict:
    """Check what percentage of polygons have been classified.
    Returns {"coverage_pct": float, "missing_count": int, "acceptable": bool}.
    Coverage below 90% is flagged; below 70% warrants rejection."""
    if total_polygon_count == 0:
        return {"coverage_pct": 0.0, "missing_count": 0, "acceptable": False}

    pct = classified_polygon_count / total_polygon_count * 100
    missing = total_polygon_count - classified_polygon_count
    return {
        "coverage_pct": round(pct, 1),
        "missing_count": missing,
        "acceptable": pct >= 90.0,
    }


@tool
def cross_check_plausibility(
    polity_assignments: dict[str, list[str]],
    year: int,
    region: str,
) -> dict:
    """Assess geographic and historical plausibility of assignments.
    polity_assignments: {polity_name: [admin_id, ...]}
    Returns {"issues": list[str], "plausible": bool}.
    Flag implausible cases: e.g. a landlocked polity assigned coastal provinces
    on the wrong continent, or assignments that defy known geography."""
    # The LLM uses its world knowledge to assess plausibility.
    return {
        "instruction": (
            f"Review these polity assignments for year {year} in region {region}. "
            "For each polity, assess whether the assigned provinces are geographically "
            "and historically consistent. List specific issues as strings. "
            "Return {\"issues\": [...], \"plausible\": bool}."
        ),
        "assignments": polity_assignments,
        "year": year,
        "region": region,
    }


@tool
def submit_review_decision(
    decision: str,
    feedback: str,
    confidence_summary: str,
) -> dict:
    """ONLY call this as the final tool call — after all other checks are complete.
    decision must be exactly one of: "approved", "partial", "rejected".
    feedback must be specific and actionable if decision is not "approved".
    Returns {"decision": str, "feedback": str, "confidence_summary": str}."""
    valid_decisions = {"approved", "partial", "rejected"}
    if decision not in valid_decisions:
        return {
            "error": f"Invalid decision '{decision}'. Must be one of: {valid_decisions}"
        }
    return {
        "decision": decision,
        "feedback": feedback,
        "confidence_summary": confidence_summary,
    }
```

### agents/reviewer/graph.py

```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition

from agents.state import AtlasState
from agents.model_factory import get_model
from agents.reviewer.tools import (
    detect_anachronism,
    verify_polity_exists,
    audit_confidence,
    check_coverage,
    cross_check_plausibility,
    submit_review_decision,
)
from agents.reviewer.prompts import SYSTEM_PROMPT
from langchain_core.messages import SystemMessage, HumanMessage
import json


TOOLS = [
    detect_anachronism,
    verify_polity_exists,
    audit_confidence,
    check_coverage,
    cross_check_plausibility,
    submit_review_decision,
]


def build_reviewer_graph() -> StateGraph:
    llm = get_model("reviewer")
    llm_with_tools = llm.bind_tools(TOOLS)

    def agent_node(state: AtlasState) -> dict:
        messages = state.get("messages", [])
        if not messages:
            review_input = {
                "year": state["year"],
                "region": state["region"],
                "map_config": state.get("map_config", {}),
                "confidence_scores": state.get("confidence_scores", {}),
                "classifications": state.get("classifications", {}),
                "total_polygon_count": len(state.get("polygons", [])),
                "classified_polygon_count": len(state.get("classifications", {})),
            }
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=f"Review this map configuration:\n\n{json.dumps(review_input, indent=2)}"
                ),
            ]

        response = llm_with_tools.invoke(messages)
        return {"messages": messages + [response]}

    def extract_decision(state: AtlasState) -> dict:
        """Parse the reviewer's final submit_review_decision tool call result."""
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, "content") and isinstance(msg.content, str):
                try:
                    data = json.loads(msg.content)
                    if "decision" in data:
                        return {
                            "review_decision": data["decision"],
                            "review_feedback": data.get("feedback", ""),
                        }
                except (json.JSONDecodeError, TypeError):
                    continue
        return {"review_decision": "rejected", "review_feedback": "Could not parse review decision."}

    graph = StateGraph(AtlasState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_node("extract_decision", extract_decision)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    graph.add_edge("agent", "extract_decision")
    graph.add_edge("extract_decision", END)

    return graph.compile()


reviewer_graph = build_reviewer_graph()
```

### Gate condition

Run reviewer on a hardcoded sample state containing a plausible year=800 output. Must parse `review_decision` without exceptions.

---

## 8. Phase 5 — Orchestrator

### Deliverables

- `agents/orchestrator.py`

### agents/orchestrator.py

```python
import logging
from agents.state import AtlasState
from agents.generator.graph import generator_graph
from agents.reviewer.graph import reviewer_graph

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def run_pipeline(year: int, region: str, dry_run: bool = False) -> AtlasState:
    """
    Run the full generation + review pipeline.

    Retry loop (max MAX_RETRIES):
        generator → reviewer
            approved/partial → store (unless dry_run) → return state
            rejected → increment retry_count → re-run generator with feedback

    store_config is called ONLY after reviewer approves. Never from the generator.
    """
    state: AtlasState = {
        "year": year,
        "region": region,
        "dry_run": dry_run,
        "polygons": [],
        "classifications": {},
        "confidence_scores": {},
        "polity_geometries": {},
        "validation_errors": [],
        "map_config": {},
        "review_decision": "",
        "review_feedback": "",
        "retry_count": 0,
        "existing_config": None,
        "metadata": {},
        "messages": [],
    }

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info(f"Generator attempt {attempt}/{MAX_RETRIES} — year={year} region={region}")

        state["messages"] = []  # reset messages for each attempt
        state = generator_graph.invoke(state)

        logger.info("Reviewer starting...")
        state["messages"] = []
        state = reviewer_graph.invoke(state)

        decision = state.get("review_decision", "rejected")
        logger.info(f"Reviewer decision: {decision}")

        if decision in ("approved", "partial"):
            if not dry_run:
                _store_config(state)
            return state

        # rejected — set up next retry
        state["retry_count"] = attempt
        logger.warning(
            f"Rejected (attempt {attempt}). Feedback: {state.get('review_feedback', '')}"
        )

    logger.error(f"All {MAX_RETRIES} attempts failed for year={year} region={region}")
    return state


def _store_config(state: AtlasState) -> None:
    """Store the approved config to MongoDB. Called ONLY after reviewer approval."""
    from storage.mongo import save_config
    from storage.schema import MapConfigDocument, MapConfigMetadata
    import asyncio
    from datetime import datetime

    metadata = MapConfigMetadata(
        generator_model=state.get("metadata", {}).get("generator_model", "unknown"),
        reviewer_model=state.get("metadata", {}).get("reviewer_model", "unknown"),
        confidence_scores=state.get("confidence_scores", {}),
        polygon_count=len(state.get("polygons", [])),
        polity_count=len(state.get("polity_geometries", {})),
        retry_count=state.get("retry_count", 0),
        review_decision=state.get("review_decision", "unknown"),
    )

    doc = MapConfigDocument(
        id=f"{state['year']}_{state['region']}",
        year=state["year"],
        region=state["region"],
        config=state.get("map_config", {}),
        metadata=metadata,
    )

    asyncio.run(save_config(doc))
```

### Gate condition

```bash
GENERATOR_MODEL=anthropic/claude-opus-4-5 \
REVIEWER_MODEL=anthropic/claude-opus-4-5 \
ANTHROPIC_API_KEY=<your_key> \
python -c "
from agents.orchestrator import run_pipeline
state = run_pipeline(year=800, region='europe', dry_run=True)
print('Decision:', state['review_decision'])
assert state['review_decision'] in ('approved', 'partial', 'rejected')
print('Pipeline OK')
"
```

---

## 9. Phase 6 — Storage + API

### Deliverables

- `storage/mongo.py`
- `api/app.py`
- `api/routes/configs.py`
- `api/middleware/auth.py`
- `api/middleware/rate_limit.py`

### storage/mongo.py

```python
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
    await col.replace_one(
        {"id": doc.id},
        doc.model_dump(),
        upsert=True,
    )


async def get_config(year: int, region: str) -> dict | None:
    col = get_collection()
    doc = await col.find_one({"year": year, "region": region})
    if doc:
        doc.pop("_id", None)
    return doc


def get_config_sync(year: int, region: str) -> dict | None:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return None  # Can't run sync in async context; skip cache check
        return loop.run_until_complete(get_config(year, region))
    except Exception:
        return None


async def list_configs(region: str, page: int = 1, limit: int = 20) -> list[dict]:
    col = get_collection()
    skip = (page - 1) * limit
    cursor = col.find({"region": region}, {"_id": 0}).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)


async def list_configs_range(
    start_year: int, end_year: int, region: str
) -> list[dict]:
    col = get_collection()
    cursor = col.find(
        {"year": {"$gte": start_year, "$lte": end_year}, "region": region},
        {"_id": 0},
    )
    return await cursor.to_list(length=None)
```

### api/middleware/auth.py

```python
import os
from fastapi import Request, HTTPException, status


async def api_key_middleware(request: Request, call_next):
    # Skip auth for health check
    if request.url.path == "/health":
        return await call_next(request)

    api_key = request.headers.get("X-API-Key")
    secret = os.environ.get("API_SECRET_KEY", "changeme")

    if not api_key or api_key != secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
        )

    return await call_next(request)
```

### api/middleware/rate_limit.py

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
```

### api/routes/configs.py

```python
from fastapi import APIRouter, HTTPException, Query
from storage.mongo import get_config, list_configs, list_configs_range

router = APIRouter(prefix="/api/v1/configs", tags=["configs"])


@router.get("/{year}")
async def get_config_by_year(
    year: int,
    region: str = Query(default="world"),
):
    doc = await get_config(year, region)
    if not doc:
        raise HTTPException(status_code=404, detail=f"No config for year={year} region={region}")
    return doc


@router.get("")
async def list_configs_paginated(
    region: str = Query(default="world"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    configs = await list_configs(region, page, limit)
    return {"region": region, "page": page, "limit": limit, "results": configs}


@router.get("/range")
async def get_configs_range(
    start: int = Query(...),
    end: int = Query(...),
    region: str = Query(default="world"),
):
    if start > end:
        raise HTTPException(status_code=400, detail="start must be <= end")
    configs = await list_configs_range(start, end, region)
    return {"start": start, "end": end, "region": region, "results": configs}
```

### api/app.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.middleware.auth import api_key_middleware
from api.middleware.rate_limit import limiter
from api.routes.configs import router as configs_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="AtlasFabric API",
        description="Historical boundary configurations served via REST API.",
        version="0.1.0",
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.middleware("http")(api_key_middleware)

    app.include_router(configs_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
```

### Gate condition

```bash
make run-api
# In another terminal:
curl http://localhost:8080/health
# Expected: {"status":"ok"}

curl -H "X-API-Key: changeme" "http://localhost:8080/api/v1/configs/800?region=europe"
# Expected: 404 with detail message (no data yet) or config if pipeline was run
```

---

## 10. Phase 7 — CLI

### Deliverables

- `cli/main.py`

### cli/main.py

```python
import os
import json
import typer
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

app = typer.Typer(help="AtlasFabric — Historical boundary generation engine.")


@app.command()
def generate(
    year: int = typer.Option(..., "--year", "-y", help="Historical year to generate"),
    region: str = typer.Option(..., "--region", "-r", help="Region name (see geo/regions.py)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run without storing to MongoDB"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write config JSON to file"),
):
    """Run the historical boundary generation pipeline."""
    from geo.regions import list_regions
    valid_regions = list_regions()

    if region not in valid_regions:
        typer.echo(f"Error: Unknown region '{region}'. Valid: {valid_regions}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Generating year={year} region={region} dry_run={dry_run}")

    from agents.orchestrator import run_pipeline
    state = run_pipeline(year=year, region=region, dry_run=dry_run)

    decision = state.get("review_decision", "unknown")
    typer.echo(f"Review decision: {decision}")

    if decision in ("approved", "partial"):
        typer.echo("Generation successful.")
        if output:
            config = state.get("map_config", {})
            output.write_text(json.dumps(config, indent=2))
            typer.echo(f"Config written to {output}")
    else:
        typer.echo("Generation failed after all retries.", err=True)
        typer.echo(f"Last feedback: {state.get('review_feedback', '')}", err=True)
        raise typer.Exit(1)


@app.command()
def regions():
    """List all supported region names."""
    from geo.regions import list_regions
    for r in list_regions():
        typer.echo(r)


if __name__ == "__main__":
    app()
```

### Gate condition

```bash
make generate ARGS="--year 800 --region europe --dry-run"
```

Must print `Generation successful.` or exit with informative error. No unhandled exceptions.

---

## 11. Phase 8 — Integration Tests

### Deliverables

- `tests/integration/test_pipeline.py`
- `tests/integration/test_api.py`

### tests/integration/test_pipeline.py

Requires: MongoDB running, `GENERATOR_MODEL` + `REVIEWER_MODEL` env vars set, Natural Earth data downloaded.

```python
import pytest
import os


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
    reason="No API key set",
)
def test_full_pipeline_dry_run():
    from agents.orchestrator import run_pipeline
    state = run_pipeline(year=800, region="europe", dry_run=True)
    assert state["review_decision"] in ("approved", "partial", "rejected")
    assert isinstance(state.get("map_config"), dict)


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
    reason="No API key set",
)
def test_pipeline_produces_maplibre_config():
    from agents.orchestrator import run_pipeline
    state = run_pipeline(year=800, region="europe", dry_run=True)
    if state["review_decision"] in ("approved", "partial"):
        config = state["map_config"]
        assert "style" in config
        assert "year" in config
        assert config["year"] == 800
        assert "polities" in config
```

### tests/integration/test_api.py

Requires: MongoDB running, API server running.

```python
import pytest
import httpx
import os


BASE_URL = f"http://localhost:{os.environ.get('PORT', 8080)}"
HEADERS = {"X-API-Key": os.environ.get("API_SECRET_KEY", "changeme")}


@pytest.mark.asyncio
async def test_health():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_auth_required():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/api/v1/configs/800")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_missing_config_returns_404():
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/api/v1/configs/1",
            params={"region": "europe"},
            headers=HEADERS,
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_configs_pagination():
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/api/v1/configs",
            params={"region": "europe", "page": 1, "limit": 5},
            headers=HEADERS,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert data["page"] == 1
```

### Gate condition

```bash
make test-integration
```

All tests that are not skipped must pass.

---

## 12. Data Formats

### AtlasState (full field reference)

| Field | Type | Set by |
|-------|------|--------|
| `year` | `int` | CLI input |
| `region` | `str` | CLI input |
| `dry_run` | `bool` | CLI input |
| `polygons` | `list[dict]` | `load_polygons` tool |
| `classifications` | `dict[str, str]` | `classify_batch` tool |
| `confidence_scores` | `dict[str, float]` | `classify_batch` tool |
| `polity_geometries` | `dict[str, Any]` | `union_geometries` tool |
| `validation_errors` | `list[str]` | `validate_geometry` tool |
| `map_config` | `dict` | `build_maplibre_config` tool |
| `review_decision` | `str` | reviewer graph |
| `review_feedback` | `str` | reviewer graph |
| `retry_count` | `int` | orchestrator |
| `existing_config` | `dict\|None` | `get_existing_config` tool |
| `metadata` | `dict` | orchestrator |
| `messages` | `list` | LangGraph internal |

### Polygon dict (from load_polygons)

```json
{
  "admin_id": "USA-3150",
  "name": "Bavaria",
  "country": "Germany",
  "geometry_wkt": "POLYGON ((...))",
  "centroid_lon": 11.5,
  "centroid_lat": 48.1
}
```

### MapLibre config (stored + served)

```json
{
  "year": 800,
  "region": "europe",
  "style": {
    "version": 8,
    "glyphs": "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
    "sources": {
      "polities": {
        "type": "geojson",
        "data": { "type": "FeatureCollection", "features": [...] }
      }
    },
    "layers": [
      { "id": "polities-fill", "type": "fill", ... },
      { "id": "polities-line", "type": "line", ... }
    ]
  },
  "polities": [
    {
      "id": "frankish_empire",
      "name": "Frankish Empire",
      "color": "#7a5c3d",
      "confidence": 0.85
    }
  ],
  "metadata": {
    "generator_model": "anthropic/claude-opus-4-5",
    "reviewer_model": "anthropic/claude-opus-4-5",
    "confidence_scores": { "Frankish Empire": 0.85 },
    "polygon_count": 124,
    "polity_count": 8,
    "retry_count": 0,
    "review_decision": "approved",
    "known_limitations": [...]
  }
}
```

---

## 13. Code Specs

### Import rules (enforced)

| File | May import | May NOT import |
|------|-----------|----------------|
| `agents/model_factory.py` | Any LLM provider class | — |
| `agents/generator/graph.py` | `model_factory.get_model` | Any provider class directly |
| `agents/reviewer/graph.py` | `model_factory.get_model` | Any provider class directly |
| `agents/orchestrator.py` | `generator_graph`, `reviewer_graph` | `model_factory` directly |
| `geo/union.py` | `shapely`, stdlib | `geo/validator` |
| `geo/validator.py` | `shapely`, stdlib | `geo/union` |
| `storage/mongo.py` | `motor`, `storage/schema` | `agents/*` |
| `api/*` | `storage/*`, `fastapi`, stdlib | `agents/*` |

### Pipeline invariants

1. `union_geometries` is never called before `validate_classifications` passes.
2. `store_config` / `save_config` is never called from the generator graph.
3. `store_config` is called from the orchestrator only after `review_decision` is `"approved"` or `"partial"`.
4. No admin polygon may appear in more than one polity's classification for a given year+region.
5. All geometries use EPSG:4326 throughout.
6. Every `MapConfigDocument` must have `year`, `region`, `config`, and `metadata`.

### Tool docstring policy

Tool docstrings are behavioral instructions for the LLM. The phrasing "Call this FIRST", "ONLY call after", "MUST" is intentional and must not be rewritten for style. Do not add standard documentation headings (Args, Returns, Raises) to tool docstrings — the instructional text is the entire docstring.

### Confidence score semantics

| Score | Meaning |
|-------|---------|
| 0.9–1.0 | Well-documented, primary historical source confirms |
| 0.7–0.9 | Highly likely based on multiple corroborating sources |
| 0.5–0.7 | Probable but with uncertainty (contested territory, border zone) |
| 0.3–0.5 | Uncertain — review recommended |
| 0.0–0.3 | Speculative — flag for manual correction |

### Error handling policy

- Geo functions raise `ValueError` for invalid inputs and `FileNotFoundError` for missing data files.
- Tools return `{"error": str}` dicts rather than raising — the LLM handles error recovery.
- The orchestrator catches all exceptions per attempt and logs them; it does not let a single agent failure crash the process.
- The API returns standard HTTP error codes; never exposes internal stack traces.
