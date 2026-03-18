import logging

from agents.graph_runtime import aggregate_confidence_by_polity
from agents.state import AtlasState

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

_EMPTY_STATE: AtlasState = {
    "year": 0,
    "region": "",
    "dry_run": False,
    "polygons": [],
    "classifications": {},
    "confidence_scores": {},
    "polity_geometries": {},
    "validation_errors": [],
    "map_config": {},
    "review_decision": "",
    "review_feedback": "",
    "retry_count": 0,
    "existing_config": None,
    "metadata": {},
    "messages": [],
}


def run_pipeline(year: int, region: str, dry_run: bool = False) -> AtlasState:
    """
    Run the full generation + review pipeline with up to MAX_RETRIES attempts.

    Flow:
        generator → reviewer
            approved/partial → store (unless dry_run) → return state
            rejected         → retry generator with feedback (max 3 times)

    store_config is called ONLY after reviewer approves. Never from the generator.
    """
    # Import graphs here to avoid circular imports at module level
    from agents.generator.graph import generator_graph
    from agents.reviewer.graph import reviewer_graph

    state: AtlasState = {
        **_EMPTY_STATE,
        "year": year,
        "region": region,
        "dry_run": dry_run,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info(
            "Generator attempt %d/%d — year=%d region=%s",
            attempt, MAX_RETRIES, year, region,
        )

        state["messages"] = []
        state = generator_graph.invoke(state)

        if state.get("existing_config"):
            existing_config = state["existing_config"] or {}
            metadata = existing_config.get("metadata", {})
            state["review_decision"] = metadata.get("review_decision", "approved")
            state["review_feedback"] = ""
            return state

        logger.info("Reviewer starting (attempt %d)…", attempt)
        state["messages"] = []
        state = reviewer_graph.invoke(state)

        decision = state.get("review_decision", "rejected")
        logger.info("Reviewer decision: %s", decision)

        if decision in ("approved", "partial"):
            if not dry_run:
                _store_config(state)
            return state

        logger.warning(
            "Rejected (attempt %d/%d). Feedback: %s",
            attempt, MAX_RETRIES, state.get("review_feedback", ""),
        )
        state["retry_count"] = attempt

    logger.error(
        "All %d attempts failed for year=%d region=%s",
        MAX_RETRIES, year, region,
    )
    return state


def _store_config(state: AtlasState) -> None:
    """Store approved config to MongoDB. Called ONLY after reviewer approval."""
    import asyncio
    import os

    from storage.mongo import save_config
    from storage.schema import MapConfigDocument, MapConfigMetadata

    meta_raw = state.get("metadata", {})
    polity_confidence_scores = aggregate_confidence_by_polity(
        state.get("classifications", {}),
        state.get("confidence_scores", {}),
    )
    metadata = MapConfigMetadata(
        generator_model=meta_raw.get(
            "generator_model",
            os.environ.get("GENERATOR_MODEL", "unknown"),
        ),
        reviewer_model=meta_raw.get(
            "reviewer_model",
            os.environ.get("REVIEWER_MODEL", "unknown"),
        ),
        confidence_scores=polity_confidence_scores,
        polygon_count=len(state.get("polygons", [])),
        polity_count=len(state.get("polity_geometries", {})),
        retry_count=state.get("retry_count", 0),
        review_decision=state.get("review_decision", "unknown"),
    )

    doc = MapConfigDocument(
        id=f"{state['year']}_{state['region']}",
        year=state["year"],
        region=state["region"],
        config=state.get("map_config", {}),
        metadata=metadata,
    )

    asyncio.run(save_config(doc))
