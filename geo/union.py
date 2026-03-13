from shapely import from_wkt
from shapely.ops import unary_union


def union_by_polity(
    polygons: list[dict],
    classifications: dict[str, str],
) -> dict[str, object]:
    """
    Union polygon geometries grouped by polity assignment.

    Args:
        polygons        : list of polygon dicts (must have admin_id, geometry_wkt)
        classifications : {admin_id → polity_name}

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
