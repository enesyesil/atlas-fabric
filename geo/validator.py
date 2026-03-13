from shapely import from_wkt
from shapely.geometry import MultiPolygon, Polygon


def check_validity(geometry_wkt: str) -> list[str]:
    """Return list of error strings. Empty list means valid."""
    errors: list[str] = []
    try:
        geom = from_wkt(geometry_wkt)
    except Exception as e:
        return [f"WKT parse error: {e}"]

    if geom is None or geom.is_empty:
        errors.append("Geometry is empty")
        return errors

    if not geom.is_valid:
        errors.append(f"Invalid geometry (shapely validity check failed)")

    if not isinstance(geom, (Polygon, MultiPolygon)):
        errors.append(f"Expected Polygon or MultiPolygon, got {type(geom).__name__}")

    bounds = geom.bounds  # (minx, miny, maxx, maxy)
    if not (-180 <= bounds[0] <= 180 and -180 <= bounds[2] <= 180):
        errors.append("Longitude out of EPSG:4326 range [-180, 180]")
    if not (-90 <= bounds[1] <= 90 and -90 <= bounds[3] <= 90):
        errors.append("Latitude out of EPSG:4326 range [-90, 90]")

    return errors


def check_overlaps(polity_geometries: dict[str, object]) -> list[str]:
    """
    Check that no two polities share overlapping area.
    Returns list of error strings describing overlapping pairs.
    """
    errors: list[str] = []
    names = list(polity_geometries.keys())
    geoms = list(polity_geometries.values())

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = geoms[i], geoms[j]
            if a is None or b is None:
                continue
            if a.intersects(b):  # type: ignore[union-attr]
                overlap = a.intersection(b)  # type: ignore[union-attr]
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
    errors: list[str] = []
    for admin_id, polity in classifications.items():
        if admin_id in seen and seen[admin_id] != polity:
            errors.append(
                f"admin_id '{admin_id}' assigned to both "
                f"'{seen[admin_id]}' and '{polity}'"
            )
        else:
            seen[admin_id] = polity
    return errors
