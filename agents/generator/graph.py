from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agents.generator.prompts import RETRY_PROMPT_TEMPLATE, SYSTEM_PROMPT
from agents.generator.tools import (
    build_maplibre_config,
    classify_batch,
    estimate_cost,
    get_existing_config,
    get_region_bounds,
    load_polygons,
    query_knowledge_base,
    research_historical_context,
    union_geometries,
    validate_geometry,
)
from agents.model_factory import get_model
from agents.state import AtlasState

TOOLS = [
    get_existing_config,
    estimate_cost,
    get_region_bounds,
    query_knowledge_base,
    load_polygons,
    research_historical_context,
    classify_batch,
    union_geometries,
    validate_geometry,
    build_maplibre_config,
]


def build_generator_graph() -> StateGraph:
    llm = get_model("generator")
    llm_with_tools = llm.bind_tools(TOOLS)

    def agent_node(state: AtlasState) -> dict:
        messages = state.get("messages", [])
        if not messages:
            retry_count = state.get("retry_count", 0)
            review_feedback = state.get("review_feedback", "")
            if retry_count > 0 and review_feedback:
                user_content = RETRY_PROMPT_TEMPLATE.format(
                    feedback=review_feedback,
                    retry_count=retry_count,
                )
            else:
                user_content = (
                    f"Generate a historical map configuration for:\n"
                    f"  Year: {state['year']}\n"
                    f"  Region: {state['region']}\n"
                    f"  Dry run: {state.get('dry_run', False)}"
                )
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_content),
            ]

        response = llm_with_tools.invoke(messages)
        return {"messages": messages + [response]}

    graph = StateGraph(AtlasState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph.compile()


generator_graph = build_generator_graph()
