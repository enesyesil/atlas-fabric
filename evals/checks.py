from agents.state import AtlasState
from evals.fixtures import EvalCase
from knowledge.validator import detect_anachronism


def get_polity_names(state: AtlasState) -> list[str]:
    polities = state.get("map_config", {}).get("polities", [])
    names = [polity.get("name", "") for polity in polities if polity.get("name")]
    return sorted(set(names))


def get_coverage_pct(state: AtlasState) -> float:
    polygons = state.get("polygons", [])
    classifications = state.get("classifications", {})
    if not polygons:
        return 0.0
    return round(len(classifications) / len(polygons) * 100, 1)


def run_deterministic_checks(case: EvalCase, state: AtlasState) -> dict:
    polity_names = get_polity_names(state)
    missing_required = [name for name in case.required_polities if name not in polity_names]
    found_forbidden = [name for name in case.forbidden_polities if name in polity_names]
    anachronisms = [
        {"polity": polity_name, "reason": result["reason"]}
        for polity_name in polity_names
        for result in [detect_anachronism(polity_name, case.year)]
        if result["is_anachronism"]
    ]
    coverage_pct = get_coverage_pct(state)

    return {
        "polity_names": polity_names,
        "coverage_pct": coverage_pct,
        "missing_required": missing_required,
        "found_forbidden": found_forbidden,
        "anachronisms": anachronisms,
        "passed": (
            not missing_required
            and not found_forbidden
            and not anachronisms
            and coverage_pct >= 90.0
        ),
    }
