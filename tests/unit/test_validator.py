from shapely.geometry import Polygon

from geo.validator import check_overlaps, check_validity, validate_classifications

VALID_WKT = "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"
# self-intersecting bowtie — invalid
BOWTIE_WKT = "POLYGON ((0 0, 2 2, 2 0, 0 2, 0 0))"


def test_valid_geometry_passes():
    errors = check_validity(VALID_WKT)
    assert errors == []


def test_invalid_geometry_caught():
    errors = check_validity(BOWTIE_WKT)
    assert len(errors) > 0


def test_empty_wkt_caught():
    errors = check_validity("POLYGON EMPTY")
    assert len(errors) > 0


def test_bad_wkt_caught():
    errors = check_validity("NOT A WKT STRING")
    assert len(errors) > 0


def test_out_of_bounds_longitude():
    wkt = "POLYGON ((200 0, 201 0, 201 1, 200 1, 200 0))"
    errors = check_validity(wkt)
    assert any("Longitude" in e for e in errors)


def test_out_of_bounds_latitude():
    wkt = "POLYGON ((0 91, 1 91, 1 92, 0 92, 0 91))"
    errors = check_validity(wkt)
    assert any("Latitude" in e for e in errors)


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


def test_single_polity_no_overlap():
    p = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    errors = check_overlaps({"only": p})
    assert errors == []


def test_empty_polities_no_overlap():
    errors = check_overlaps({})
    assert errors == []


def test_valid_classifications():
    classifications = {
        "admin_001": "frankish_empire",
        "admin_002": "byzantine_empire",
    }
    errors = validate_classifications(classifications)
    assert errors == []


def test_empty_classifications():
    assert validate_classifications({}) == []


def test_duplicate_admin_same_polity_ok():
    # Same admin_id → same polity is fine (idempotent)
    classifications = {"admin_001": "frankish_empire", "admin_002": "frankish_empire"}
    errors = validate_classifications(classifications)
    assert errors == []
