from fastapi import APIRouter, Depends
from app.schemas.schemas import ChatQuery, AgentResponse
from app.agents.graph import app_graph
from app.utils.logger import get_logger
from langchain_core.messages import HumanMessage

logger = get_logger(__name__)
router = APIRouter()

# Map frontend agent selector values → graph intent names
AGENT_MODE_MAP = {
    "web":     "web_search",
    "rag":     "rag_query",
    "summary": "summarize",
    "data":    "data_analysis",
    "report":  "general",
    "auto":    None,  # let the router LLM decide
}


@router.post("/query", response_model=AgentResponse)
def ask_question(query: ChatQuery):
    logger.info(f"Received query: {query.query} | agent_mode: {query.agent}")

    forced_intent = AGENT_MODE_MAP.get(query.agent or "auto")

    inputs = {
        "user_query": query.query,
        "messages": [HumanMessage(content=query.query)],
        "intent": forced_intent if forced_intent else "unknown",
        "forced_intent": forced_intent,
        "context_docs": [],
        "final_report": "",
        "intermediate_steps": [],
        "user_id": 1,
    }

    result_state = app_graph.invoke(inputs)

    final_response = result_state.get("final_report", "No answer generated.")
    sources = result_state.get("context_docs", [])
    report_suggested = result_state.get("report_suggested", False)
    suggested_title = result_state.get("suggested_title", "")

    return {
        "response": final_response,
        "sources": sources,
        "report_suggested": report_suggested,
        "suggested_title": suggested_title,
    }


@router.get("/history")
def get_chat_history():
    return []
