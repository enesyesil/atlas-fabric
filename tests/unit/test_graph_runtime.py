from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from agents.graph_runtime import (
    aggregate_confidence_by_polity,
    generator_state_update,
    invoke_tool_calls,
    reviewer_state_update,
)
from agents.state import AtlasState


def _state(**updates) -> AtlasState:
    base: AtlasState = {
        "year": 800,
        "region": "europe",
        "dry_run": True,
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
    base.update(updates)
    return base


def test_aggregate_confidence_by_polity():
    result = aggregate_confidence_by_polity(
        {"a1": "frankish_empire", "a2": "frankish_empire", "a3": "byzantine_empire"},
        {"a1": 0.8, "a2": 0.6, "a3": 0.9},
    )
    assert result == {"frankish_empire": 0.7, "byzantine_empire": 0.9}


def test_generator_state_update_merges_cached_config():
    updates = generator_state_update(
        _state(),
        "get_existing_config",
        {"year": 800, "region": "europe"},
        {
            "found": True,
            "config": {
                "config": {"year": 800, "region": "europe"},
                "metadata": {"review_decision": "approved"},
            },
        },
    )
    assert updates["existing_config"]["metadata"]["review_decision"] == "approved"
    assert updates["map_config"] == {"year": 800, "region": "europe"}


def test_generator_state_update_merges_build_args_and_result():
    updates = generator_state_update(
        _state(),
        "build_maplibre_config",
        {
            "classifications": {"a1": "frankish_empire"},
            "confidence_scores": {"a1": 0.8},
            "metadata": {"generator_model": "test-model"},
            "polity_geometries": {"frankish_empire": "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"},
        },
        {"map_config": {"year": 800}},
    )
    assert updates["classifications"] == {"a1": "frankish_empire"}
    assert updates["confidence_scores"] == {"a1": 0.8}
    assert updates["metadata"] == {"generator_model": "test-model"}
    assert updates["map_config"] == {"year": 800}


def test_reviewer_state_update_reads_submit_review_decision():
    updates = reviewer_state_update(
        _state(),
        "submit_review_decision",
        {},
        {"decision": "partial", "feedback": "Needs small fixes"},
    )
    assert updates == {
        "review_decision": "partial",
        "review_feedback": "Needs small fixes",
    }


def test_invoke_tool_calls_appends_tool_message_and_merges_state():
    @tool
    def echo(value: int) -> dict:
        """Return a JSON payload."""
        return {"value": value}

    def update_state(
        _state: AtlasState,
        _tool_name: str,
        _tool_args: dict,
        tool_result: dict,
    ) -> dict:
        return {"metadata": {"value": tool_result["value"]}}

    state = _state(
        messages=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "echo",
                        "args": {"value": 3},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )

    result = invoke_tool_calls(state, [echo], update_state)

    assert result["metadata"] == {"value": 3}
    assert isinstance(result["messages"][-1], ToolMessage)
    assert result["messages"][-1].tool_call_id == "call-1"
