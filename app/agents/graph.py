from langgraph.graph import StateGraph, END
from app.agents.state import GraphState
from app.agents.nodes import (
    router_agent,
    web_search_agent,
    rag_agent,
    summary_agent,
    report_writer_agent
)

def get_routing_logic(state: GraphState) -> str:
    intent = state.get("intent")
    if intent == "web_search":
        return "web_search_agent"
    elif intent == "summarize":
        return "summary_agent"
    elif intent == "rag_query":
        return "rag_agent"
    else:
        return "report_writer_agent"

def build_multi_agent_graph() -> StateGraph:
    workflow = StateGraph(GraphState)

    workflow.add_node("router_agent", router_agent)
    workflow.add_node("web_search_agent", web_search_agent)
    workflow.add_node("rag_agent", rag_agent)
    workflow.add_node("summary_agent", summary_agent)
    workflow.add_node("report_writer_agent", report_writer_agent)

    workflow.set_entry_point("router_agent")

    workflow.add_conditional_edges(
        "router_agent",
        get_routing_logic,
        {
            "web_search_agent": "web_search_agent",
            "rag_agent": "rag_agent",
            "summary_agent": "summary_agent",
            "report_writer_agent": "report_writer_agent",
        }
    )

    workflow.add_edge("web_search_agent", "report_writer_agent")
    workflow.add_edge("rag_agent", "report_writer_agent")
    workflow.add_edge("summary_agent", "report_writer_agent")
    workflow.add_edge("report_writer_agent", END)

    return workflow.compile()

app_graph = build_multi_agent_graph()
