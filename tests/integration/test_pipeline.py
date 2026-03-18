"""
Integration tests for the full generation pipeline.

Requirements:
  - GENERATOR_MODEL and REVIEWER_MODEL env vars set
  - At least one provider API key
    (AZURE_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY)
  - If using azure/ models, AZURE_API_BASE must point to the direct endpoint root
    ending in /openai/v1
  - NATURAL_EARTH_DATA_PATH pointing to the downloaded Natural Earth dataset

Run with:
  make test-integration
"""

import os

import pytest

_HAS_API_KEY = bool(
    os.environ.get("AZURE_API_KEY")
    or os.environ.get("ANTHROPIC_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
    or os.environ.get("GOOGLE_API_KEY")
)
_USES_AZURE = any(
    os.environ.get(env_var, "").startswith("azure/")
    for env_var in ("GENERATOR_MODEL", "REVIEWER_MODEL")
)
_HAS_AZURE_ENDPOINT = bool(os.environ.get("AZURE_API_BASE"))
_HAS_DATA = os.path.exists(
    os.environ.get(
        "NATURAL_EARTH_DATA_PATH",
        "./data/ne_10m_admin_1_states_provinces.geojson",
    )
)

skip_no_api = pytest.mark.skipif(not _HAS_API_KEY, reason="No provider API key set")
skip_no_azure_endpoint = pytest.mark.skipif(
    _USES_AZURE and not _HAS_AZURE_ENDPOINT,
    reason="AZURE_API_BASE must point to the direct Foundry endpoint root ending in /openai/v1",
)
skip_no_data = pytest.mark.skipif(not _HAS_DATA, reason="Natural Earth data not found")


@skip_no_api
@skip_no_azure_endpoint
@skip_no_data
def test_full_pipeline_dry_run():
    from agents.orchestrator import run_pipeline

    state = run_pipeline(year=800, region="europe", dry_run=True)

    assert state["review_decision"] in ("approved", "partial", "rejected"), (
        f"Unexpected decision: {state['review_decision']}"
    )
    assert isinstance(state.get("map_config"), dict)
    assert state["year"] == 800
    assert state["region"] == "europe"


@skip_no_api
@skip_no_azure_endpoint
@skip_no_data
def test_pipeline_produces_valid_maplibre_config():
    from agents.orchestrator import run_pipeline

    state = run_pipeline(year=800, region="europe", dry_run=True)

    if state["review_decision"] not in ("approved", "partial"):
        pytest.skip("Pipeline did not produce an approved config for this run")

    config = state["map_config"]
    assert "style" in config, "map_config missing 'style' key"
    assert "year" in config, "map_config missing 'year' key"
    assert "region" in config, "map_config missing 'region' key"
    assert "polities" in config, "map_config missing 'polities' key"
    assert config["year"] == 800
    assert config["region"] == "europe"
    assert config["style"]["version"] == 8
    assert "sources" in config["style"]
    assert "layers" in config["style"]
    assert len(config["style"]["layers"]) >= 2


@skip_no_api
@skip_no_azure_endpoint
@skip_no_data
def test_pipeline_max_retries_does_not_crash():
    """Even if all retries are rejected, the pipeline must return cleanly."""
    from agents.orchestrator import run_pipeline

    state = run_pipeline(year=800, region="europe", dry_run=True)

    assert "review_decision" in state
    assert state.get("retry_count", 0) <= 3
