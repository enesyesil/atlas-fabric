from langchain_core.tools import tool

from knowledge.validator import (
    detect_anachronism as _detect_anachronism,
    verify_polity_exists as _verify_polity_exists,
)


@tool
def detect_anachronism(polity_name: str, year: int) -> dict:
    """Call this for EVERY polity in the configuration — no exceptions.
    Returns {"is_anachronism": bool, "reason": str | None}.
    If is_anachronism is True, you MUST reject the configuration."""
    return _detect_anachronism(polity_name, year)


@tool
def verify_polity_exists(polity_name: str, year: int) -> dict:
    """Call this when detect_anachronism is inconclusive or for unknown polities.
    Returns {"found": bool, "polity": dict | None, "issue": str | None}.
    Use to cross-reference names, aliases, and date ranges."""
    return _verify_polity_exists(polity_name, year)


@tool
def audit_confidence(confidence_scores: dict[str, float], threshold: float = 0.5) -> dict:
    """Audit confidence scores across all polity assignments.
    Flag all polities with confidence below threshold.
    Returns {"flagged": list[str], "mean_confidence": float, "min_confidence": float}."""
    if not confidence_scores:
        return {"flagged": [], "mean_confidence": 0.0, "min_confidence": 0.0}

    flagged = [p for p, score in confidence_scores.items() if score < threshold]
    values = list(confidence_scores.values())
    return {
        "flagged": flagged,
        "mean_confidence": round(sum(values) / len(values), 3),
        "min_confidence": round(min(values), 3),
    }


@tool
def check_coverage(total_polygon_count: int, classified_polygon_count: int) -> dict:
    """Check what percentage of polygons have been classified.
    Returns {"coverage_pct": float, "missing_count": int, "acceptable": bool}.
    Coverage below 90% is flagged; below 70% warrants rejection."""
    if total_polygon_count == 0:
        return {"coverage_pct": 0.0, "missing_count": 0, "acceptable": False}

    pct = classified_polygon_count / total_polygon_count * 100
    missing = total_polygon_count - classified_polygon_count
    return {
        "coverage_pct": round(pct, 1),
        "missing_count": missing,
        "acceptable": pct >= 90.0,
    }


@tool
def cross_check_plausibility(
    polity_assignments: dict[str, list[str]],
    year: int,
    region: str,
) -> dict:
    """Assess geographic and historical plausibility of the polity assignments.
    polity_assignments: {polity_name: [admin_id, ...]}
    Flag implausible cases such as polities assigned to the wrong continent,
    or assignments that contradict known geography for the given year.
    Returns {"issues": list[str], "plausible": bool}."""
    return {
        "instruction": (
            f"Review these polity assignments for year {year} in region {region}. "
            "For each polity, assess whether the assigned provinces are geographically "
            "and historically consistent. List specific issues as strings. "
            'Return {"issues": [...], "plausible": bool}.'
        ),
        "assignments": polity_assignments,
        "year": year,
        "region": region,
    }


@tool
def submit_review_decision(
    decision: str,
    feedback: str,
    confidence_summary: str,
) -> dict:
    """ONLY call this as the final tool call — after all other checks are complete.
    decision must be exactly one of: "approved", "partial", "rejected".
    feedback must be specific and actionable if decision is not "approved".
    Returns {"decision": str, "feedback": str, "confidence_summary": str}."""
    valid = {"approved", "partial", "rejected"}
    if decision not in valid:
        return {"error": f"Invalid decision '{decision}'. Must be one of: {valid}"}
    return {
        "decision": decision,
        "feedback": feedback,
        "confidence_summary": confidence_summary,
    }
