from shapely.geometry import Polygon

from geo.union import union_by_polity


def _poly(admin_id: str, minx: float, miny: float, maxx: float, maxy: float) -> dict:
    p = Polygon([(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)])
    return {
        "admin_id":    admin_id,
        "name":        admin_id,
        "country":     "test",
        "geometry_wkt": p.wkt,
        "centroid_lon": (minx + maxx) / 2,
        "centroid_lat": (miny + maxy) / 2,
    }


def test_two_adjacent_polygons_unioned():
    polygons = [_poly("a1", 0, 0, 1, 1), _poly("a2", 1, 0, 2, 1)]
    classifications = {"a1": "polity_x", "a2": "polity_x"}
    result = union_by_polity(polygons, classifications)

    assert "polity_x" in result
    assert abs(result["polity_x"].area - 2.0) < 1e-9


def test_separate_polities_stay_separate():
    polygons = [_poly("a1", 0, 0, 1, 1), _poly("a2", 5, 5, 6, 6)]
    classifications = {"a1": "polity_x", "a2": "polity_y"}
    result = union_by_polity(polygons, classifications)

    assert "polity_x" in result
    assert "polity_y" in result
    assert abs(result["polity_x"].area - 1.0) < 1e-9
    assert abs(result["polity_y"].area - 1.0) < 1e-9


def test_unclassified_polygons_skipped():
    polygons = [_poly("a1", 0, 0, 1, 1)]
    result = union_by_polity(polygons, {})
    assert result == {}


def test_empty_inputs():
    result = union_by_polity([], {})
    assert result == {}


def test_three_polygons_two_polities():
    polygons = [
        _poly("a1", 0, 0, 1, 1),
        _poly("a2", 1, 0, 2, 1),
        _poly("a3", 10, 10, 11, 11),
    ]
    classifications = {"a1": "west", "a2": "west", "a3": "east"}
    result = union_by_polity(polygons, classifications)

    assert abs(result["west"].area - 2.0) < 1e-9
    assert abs(result["east"].area - 1.0) < 1e-9


def test_uncontrolled_polygons_grouped():
    polygons = [_poly("a1", 0, 0, 1, 1), _poly("a2", 2, 0, 3, 1)]
    classifications = {"a1": "UNCONTROLLED", "a2": "UNCONTROLLED"}
    result = union_by_polity(polygons, classifications)
    assert "UNCONTROLLED" in result
    assert abs(result["UNCONTROLLED"].area - 2.0) < 1e-9
