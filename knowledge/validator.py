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
    polity_id = polity_name.lower().replace(" ", "_")
    polity = _POLITIES_BY_ID.get(polity_id)
    if polity:
        if polity["active_from"] <= year <= polity["active_to"]:
            return {"found": True, "polity": polity, "issue": None}
        return {
            "found": False,
            "polity": polity,
            "issue": (
                f"'{polity_name}' existed but not in year {year} "
                f"(active {polity['active_from']}–{polity['active_to']})"
            ),
        }

    # Name / alias match
    for p in _POLITIES:  # type: ignore[union-attr]
        names = [p["name"]] + p.get("also_known_as", [])
        if any(polity_name.lower() in n.lower() or n.lower() in polity_name.lower() for n in names):
            if p["active_from"] <= year <= p["active_to"]:
                return {"found": True, "polity": p, "issue": None}
            return {
                "found": False,
                "polity": p,
                "issue": (
                    f"'{polity_name}' existed but not in year {year} "
                    f"(active {p['active_from']}–{p['active_to']})"
                ),
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
