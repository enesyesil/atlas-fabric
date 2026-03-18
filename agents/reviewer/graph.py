import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import tools_condition

from agents.graph_runtime import invoke_tool_calls, reviewer_state_update
from agents.model_factory import get_model
from agents.reviewer.prompts import SYSTEM_PROMPT
from agents.reviewer.tools import (
    audit_confidence,
    check_coverage,
    cross_check_plausibility,
    detect_anachronism,
    submit_review_decision,
    verify_polity_exists,
)
from agents.state import AtlasState

TOOLS = [
    detect_anachronism,
    verify_polity_exists,
    audit_confidence,
    check_coverage,
    cross_check_plausibility,
    submit_review_decision,
]


def build_reviewer_graph() -> Any:
    llm = get_model("reviewer")
    llm_with_tools = llm.bind_tools(TOOLS)

    def agent_node(state: AtlasState) -> dict:
        messages = state.get("messages", [])
        if not messages:
            review_input = {
                "year": state["year"],
                "region": state["region"],
                "map_config": state.get("map_config", {}),
                "confidence_scores": state.get("confidence_scores", {}),
                "total_polygon_count": len(state.get("polygons", [])),
                "classified_polygon_count": len(state.get("classifications", {})),
            }
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Review this map configuration:\n\n"
                        f"{json.dumps(review_input, indent=2)}"
                    )
                ),
            ]

        response = llm_with_tools.invoke(messages)
        return {"messages": messages + [response]}

    def tool_node(state: AtlasState) -> dict:
        return invoke_tool_calls(state, TOOLS, reviewer_state_update)

    def extract_decision(state: AtlasState) -> dict:
        if state.get("review_decision") in {"approved", "partial", "rejected"}:
            return {
                "review_decision": state["review_decision"],
                "review_feedback": state.get("review_feedback", ""),
            }
        return {
            "review_decision": "rejected",
            "review_feedback": "Reviewer did not submit a final decision.",
        }

    graph = StateGraph(AtlasState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("extract_decision", extract_decision)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition, {
        "tools": "tools",
        "__end__": "extract_decision",
    })
    graph.add_edge("tools", "agent")
    graph.add_edge("extract_decision", END)

    return graph.compile()


reviewer_graph: Any = build_reviewer_graph()
