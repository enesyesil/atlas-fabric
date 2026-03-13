from pathlib import Path

import geopandas as gpd

from geo.regions import get_bounds


def load_polygons(geojson_path: str, region: str) -> list[dict]:
    """
    Load Natural Earth admin-1 polygons for a given region.

    Returns a list of dicts, each with:
        admin_id    : str   — unique identifier (adm1_code)
        name        : str   — province/state name
        country     : str   — sovereign country name
        geometry_wkt: str   — WKT representation (EPSG:4326)
        centroid_lon: float
        centroid_lat: float
    """
    path = Path(geojson_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Natural Earth data not found at {geojson_path}. "
            "Download ne_10m_admin_1_states_provinces.geojson from naturalearthdata.com "
            "and place it at the path specified by NATURAL_EARTH_DATA_PATH."
        )

    gdf = gpd.read_file(path)
    gdf = gdf.to_crs("EPSG:4326")

    min_lon, min_lat, max_lon, max_lat = get_bounds(region)
    cx = gdf.geometry.centroid.x
    cy = gdf.geometry.centroid.y
    mask = (cx >= min_lon) & (cx <= max_lon) & (cy >= min_lat) & (cy <= max_lat)
    gdf = gdf[mask].copy()

    results: list[dict] = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        results.append({
            "admin_id":    str(row.get("adm1_code", row.get("ADM1_COD", ""))),
            "name":        str(row.get("name",       row.get("NAME", ""))),
            "country":     str(row.get("admin",      row.get("ADMIN", ""))),
            "geometry_wkt": geom.wkt,
            "centroid_lon": float(geom.centroid.x),
            "centroid_lat": float(geom.centroid.y),
        })

    return results
