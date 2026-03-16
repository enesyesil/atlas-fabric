import json

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

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


def build_reviewer_graph() -> StateGraph:
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

    def extract_decision(state: AtlasState) -> dict:
        """Parse the final submit_review_decision result from message history."""
        for msg in reversed(state.get("messages", [])):
            content = getattr(msg, "content", "")
            if not isinstance(content, str):
                continue
            try:
                data = json.loads(content)
                if "decision" in data and data["decision"] in ("approved", "partial", "rejected"):
                    return {
                        "review_decision": data["decision"],
                        "review_feedback": data.get("feedback", ""),
                    }
            except (json.JSONDecodeError, TypeError):
                continue
        return {
            "review_decision": "rejected",
            "review_feedback": "Could not parse review decision from agent output.",
        }

    graph = StateGraph(AtlasState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_node("extract_decision", extract_decision)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    # After the agent stops calling tools, extract the decision
    graph.add_edge("agent", "extract_decision")
    graph.add_edge("extract_decision", END)

    return graph.compile()


reviewer_graph = build_reviewer_graph()
