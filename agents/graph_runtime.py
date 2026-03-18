import json
from collections.abc import Callable, Sequence
from typing import Any, cast

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool

from agents.state import AtlasState

ToolArgs = dict[str, Any]
ToolResult = dict[str, Any]
StateUpdateFn = Callable[[AtlasState, str, ToolArgs, ToolResult], dict[str, Any]]


def aggregate_confidence_by_polity(
    classifications: dict[str, str],
    confidence_scores: dict[str, float],
) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}

    for admin_id, polity_name in classifications.items():
        score = confidence_scores.get(admin_id)
        if score is None:
            continue
        grouped.setdefault(polity_name, []).append(score)

    return {
        polity_name: round(sum(scores) / len(scores), 3)
        for polity_name, scores in grouped.items()
        if scores
    }


def invoke_tool_calls(
    state: AtlasState,
    tools: Sequence[BaseTool],
    update_state: StateUpdateFn,
) -> dict[str, Any]:
    messages = list(state.get("messages", []))
    if not messages:
        return {"messages": messages}

    last_message = messages[-1]
    tool_calls = getattr(last_message, "tool_calls", [])
    if not tool_calls:
        return {"messages": messages}

    tool_map = {tool.name: tool for tool in tools}
    merged_updates: dict[str, Any] = {}
    next_messages = messages[:]

    for tool_call in tool_calls:
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("args") or {}
        if not isinstance(tool_args, dict):
            tool_args = {}

        tool = tool_map.get(tool_name)
        if tool is None:
            tool_result: ToolResult = {"error": f"Unknown tool '{tool_name}'"}
        else:
            try:
                raw_result = tool.invoke(tool_args)
            except Exception as exc:  # pragma: no cover - safety net
                raw_result = {"error": str(exc)}

            if isinstance(raw_result, dict):
                tool_result = raw_result
            else:
                tool_result = {"result": raw_result}

        current_state = cast(AtlasState, {**state, **merged_updates})
        merged_updates.update(update_state(current_state, tool_name, tool_args, tool_result))
        next_messages.append(
            ToolMessage(
                content=json.dumps(tool_result, default=str),
                name=tool_name or "unknown",
                tool_call_id=tool_call.get("id", ""),
            )
        )

    merged_updates["messages"] = next_messages
    return merged_updates


def generator_state_update(
    state: AtlasState,
    tool_name: str,
    tool_args: ToolArgs,
    tool_result: ToolResult,
) -> dict[str, Any]:
    updates: dict[str, Any] = {}

    if tool_name == "get_existing_config" and tool_result.get("found"):
        config_doc = tool_result.get("config")
        if isinstance(config_doc, dict):
            updates["existing_config"] = config_doc
            map_config = config_doc.get("config", config_doc)
            if isinstance(map_config, dict):
                updates["map_config"] = map_config
            metadata = config_doc.get("metadata")
            if isinstance(metadata, dict):
                updates["metadata"] = metadata

    if tool_name == "load_polygons":
        polygons = tool_result.get("polygons")
        if isinstance(polygons, list):
            updates["polygons"] = polygons

    if tool_name == "union_geometries":
        classifications = tool_args.get("classifications")
        if isinstance(classifications, dict):
            updates["classifications"] = {
                str(admin_id): str(polity_name)
                for admin_id, polity_name in classifications.items()
            }

        polity_geometries = tool_result.get("polity_geometries")
        if isinstance(polity_geometries, dict):
            updates["polity_geometries"] = polity_geometries

    if tool_name == "validate_geometry":
        polity_geometries = tool_args.get("polity_geometries")
        if isinstance(polity_geometries, dict):
            updates["polity_geometries"] = polity_geometries

        errors = tool_result.get("errors")
        if isinstance(errors, list):
            updates["validation_errors"] = [str(error) for error in errors]

    if tool_name == "build_maplibre_config":
        classifications = tool_args.get("classifications")
        if isinstance(classifications, dict):
            updates["classifications"] = {
                str(admin_id): str(polity_name)
                for admin_id, polity_name in classifications.items()
            }

        confidence_scores = tool_args.get("confidence_scores")
        if isinstance(confidence_scores, dict):
            updates["confidence_scores"] = {
                str(admin_id): float(score)
                for admin_id, score in confidence_scores.items()
            }

        metadata = tool_args.get("metadata")
        if isinstance(metadata, dict):
            updates["metadata"] = metadata

        polity_geometries = tool_args.get("polity_geometries")
        if isinstance(polity_geometries, dict):
            updates["polity_geometries"] = polity_geometries

        map_config = tool_result.get("map_config")
        if isinstance(map_config, dict):
            updates["map_config"] = map_config

    return updates


def reviewer_state_update(
    _state: AtlasState,
    tool_name: str,
    _tool_args: ToolArgs,
    tool_result: ToolResult,
) -> dict[str, Any]:
    if tool_name != "submit_review_decision":
        return {}

    decision = tool_result.get("decision")
    if decision not in {"approved", "partial", "rejected"}:
        return {}

    return {
        "review_decision": decision,
        "review_feedback": str(tool_result.get("feedback", "")),
    }
