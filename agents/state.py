from typing import Any
from typing_extensions import TypedDict


class AtlasState(TypedDict):
    # Input
    year: int
    region: str
    dry_run: bool

    # Working data
    polygons: list[dict]                # GeoJSON Feature dicts from Natural Earth
    classifications: dict[str, str]     # admin_id → polity_name
    confidence_scores: dict[str, float] # polity_name → 0.0–1.0
    polity_geometries: dict[str, Any]   # polity_name → Shapely geometry (post-union)

    # Validation
    validation_errors: list[str]

    # Output
    map_config: dict                    # MapLibre GL JS config dict

    # Review
    review_decision: str                # "approved" | "partial" | "rejected"
    review_feedback: str

    # Orchestration
    retry_count: int
    existing_config: dict | None
    metadata: dict

    # LangGraph message passing
    messages: list[Any]
