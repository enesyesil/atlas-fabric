import os

from langchain_core.tools import tool

from geo.loader import load_polygons as _load_polygons
from geo.regions import get_bounds, list_regions
from geo.union import union_by_polity
from geo.validator import check_validity, check_overlaps, validate_classifications
from knowledge.validator import get_polities_for_year


@tool
def get_existing_config(year: int, region: str) -> dict:
    """Call this FIRST before any other tool.
    Returns an existing map config if one was already generated for this year and region.
    If found, you MUST return it immediately without re-generating.
    Returns {"found": False} if no existing config exists."""
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
        return {"min_lon": min_lon, "min_lat": min_lat, "max_lon": max_lon, "max_lat": max_lat}
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
    Returns a prompt instructing you to synthesise your historical knowledge."""
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
    Each polygon must be assigned to exactly one polity name from known_polities,
    or to the special value UNCONTROLLED for stateless regions.
    Returns {"classifications": {admin_id: polity_name},
             "confidence_scores": {admin_id: float},
             "reasoning": {admin_id: str}}."""
    if len(polygons) > 50:
        return {
            "error": (
                f"Batch too large: {len(polygons)} polygons. "
                "Maximum is 50. Split into smaller batches."
            )
        }
    valid_polity_set = set(known_polities) | {"UNCONTROLLED"}
    return {
        "instruction": (
            "For each polygon, assign a polity_name from the known_polities list "
            "or use UNCONTROLLED. Return a JSON object matching: "
            '{"classifications": {admin_id: polity_name}, '
            '"confidence_scores": {admin_id: 0.0-1.0}, '
            '"reasoning": {admin_id: "brief explanation"}}'
        ),
        "polygons_to_classify": [
            {
                "admin_id": p["admin_id"],
                "name": p["name"],
                "country": p["country"],
                "centroid_lon": p["centroid_lon"],
                "centroid_lat": p["centroid_lat"],
            }
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
    """Validate all polity geometries for correctness and overlaps.
    Returns {"valid": bool, "errors": list[str]}.
    If valid is False, re-classify the conflicting polygons and re-call union_geometries."""
    from shapely import from_wkt

    all_errors: list[str] = []
    shapely_geoms: dict[str, object] = {}

    for polity, wkt in polity_geometries.items():
        errs = check_validity(wkt)
        if errs:
            all_errors.extend([f"[{polity}] {e}" for e in errs])
        else:
            shapely_geoms[polity] = from_wkt(wkt)

    all_errors.extend(check_overlaps(shapely_geoms))
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
    import shapely
    from shapely import from_wkt

    def _colour(name: str) -> str:
        h = int(hashlib.md5(name.encode()).hexdigest()[:6], 16)
        r = 80 + ((h >> 16) & 0xFF) % 120
        g = 80 + ((h >> 8) & 0xFF) % 120
        b = 80 + (h & 0xFF) % 120
        return f"#{r:02x}{g:02x}{b:02x}"

    features = []
    for polity_name, wkt in polity_geometries.items():
        geom = from_wkt(wkt)
        features.append({
            "type": "Feature",
            "properties": {
                "polity_id": polity_name.lower().replace(" ", "_"),
                "polity_name": polity_name,
                "color": _colour(polity_name),
                "confidence": confidence_scores.get(polity_name, 0.5),
                "year": year,
            },
            "geometry": shapely.geometry.mapping(geom),
        })

    config = {
        "year": year,
        "region": region,
        "style": {
            "version": 8,
            "glyphs": "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
            "sources": {
                "polities": {
                    "type": "geojson",
                    "data": {"type": "FeatureCollection", "features": features},
                }
            },
            "layers": [
                {
                    "id": "polities-fill",
                    "type": "fill",
                    "source": "polities",
                    "paint": {"fill-color": ["get", "color"], "fill-opacity": 0.6},
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
            for f in features
            if f["properties"]["polity_name"] != "UNCONTROLLED"
        ],
        "metadata": metadata,
    }

    return {"map_config": config}
