# Bounding boxes in EPSG:4326: (min_lon, min_lat, max_lon, max_lat)
REGION_BOUNDS: dict[str, tuple[float, float, float, float]] = {
    "world":          (-180.0, -90.0,  180.0,  90.0),
    "europe":         ( -25.0,  34.0,   45.0,  72.0),
    "middle_east":    (  25.0,  12.0,   65.0,  42.0),
    "north_africa":   ( -18.0,  15.0,   42.0,  38.0),
    "sub_saharan":    ( -20.0, -35.0,   52.0,  15.0),
    "south_asia":     (  60.0,   5.0,   90.0,  38.0),
    "east_asia":      (  95.0,  18.0,  145.0,  55.0),
    "central_asia":   (  45.0,  35.0,   90.0,  55.0),
    "north_america":  (-170.0,  15.0,  -50.0,  72.0),
    "south_america":  ( -82.0, -56.0,  -34.0,  13.0),
    "southeast_asia": (  92.0, -10.0,  145.0,  28.0),
}


def get_bounds(region: str) -> tuple[float, float, float, float]:
    if region not in REGION_BOUNDS:
        raise ValueError(
            f"Unknown region '{region}'. Valid: {list(REGION_BOUNDS)}"
        )
    return REGION_BOUNDS[region]


def list_regions() -> list[str]:
    return list(REGION_BOUNDS.keys())
