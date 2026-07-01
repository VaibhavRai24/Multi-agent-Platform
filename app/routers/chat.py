from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from app.schemas.schemas import ChatQuery, AgentResponse
from app.agents.graph import app_graph
from app.utils.logger import get_logger
from app.database.database import get_db
from app.models.domain import Chat, Message, AgentMemory
from langchain_core.messages import HumanMessage

logger = get_logger(__name__)
router = APIRouter()

MOCK_USER_ID = 1
MAX_SAVED_CHATS = 5

AGENT_MODE_MAP = {
    "web":     "web_search",
    "rag":     "rag_query",
    "summary": "summarize",
    "data":    "data_analysis",
    "report":  "general",
    "auto":    None,
}


def _derive_title(text: str) -> str:
    words = text.strip().replace("\n", " ").split()
    title = " ".join(words[:8])
    if len(words) > 8:
        title += "…"
    return title[:80] if title else "New Chat"


def _enforce_chat_limit(db: DBSession, user_id: int):
    chats = (
        db.query(Chat)
        .filter(Chat.user_id == user_id)
        .order_by(Chat.created_at.desc())
        .all()
    )
    if len(chats) > MAX_SAVED_CHATS:
        for stale in chats[MAX_SAVED_CHATS:]:
            db.delete(stale)
        db.commit()


def _load_memory(db: DBSession, chat_id: int, user_id: int) -> dict:
    """Load persisted working memory for a chat session, or return empty dict."""
    if not chat_id:
        return {}
    record = db.query(AgentMemory).filter(
        AgentMemory.chat_id == chat_id,
        AgentMemory.user_id == user_id,
    ).first()
    return dict(record.memory) if record and record.memory else {}


def _save_memory(db: DBSession, chat_id: int, user_id: int, memory: dict):
    """Upsert the working memory for a chat session."""
    record = db.query(AgentMemory).filter(
        AgentMemory.chat_id == chat_id,
        AgentMemory.user_id == user_id,
    ).first()
    if record:
        record.memory = memory
    else:
        record = AgentMemory(chat_id=chat_id, user_id=user_id, memory=memory)
        db.add(record)
    db.commit()


@router.post("/query", response_model=AgentResponse)
def ask_question(query: ChatQuery, db: DBSession = Depends(get_db)):
    logger.info(f"Received query: {query.query} | agent_mode: {query.agent}")

    forced_intent = AGENT_MODE_MAP.get(query.agent or "auto")

    # ── Resolve / create the chat session first so we can load memory ────────
    chat_id = query.chat_id
    chat = None
    if chat_id:
        chat = db.query(Chat).filter(
            Chat.id == chat_id, Chat.user_id == MOCK_USER_ID
        ).first()

    if not chat:
        chat = Chat(title=_derive_title(query.query), user_id=MOCK_USER_ID)
        db.add(chat)
        db.commit()
        db.refresh(chat)

    # ── Load persisted working memory for this session ────────────────────────
    working_memory = _load_memory(db, chat.id, MOCK_USER_ID)
    logger.info(f"Loaded working memory for chat {chat.id}: {list(working_memory.keys())}")

    inputs = {
        "user_query": query.query,
        "messages": [HumanMessage(content=query.query)],
        "intent": forced_intent if forced_intent else "unknown",
        "forced_intent": forced_intent,
        "context_docs": [],
        "final_report": "",
        "intermediate_steps": [],
        "user_id": MOCK_USER_ID,
        "working_memory": working_memory,   # ← inject persisted memory
        "agent_trace": [],                  # ← starts empty; nodes append to it
    }

    result_state = app_graph.invoke(inputs)

    final_response  = result_state.get("final_report", "No answer generated.")
    sources         = result_state.get("context_docs", [])
    report_suggested = result_state.get("report_suggested", False)
    suggested_title  = result_state.get("suggested_title", "")
    agent_trace      = result_state.get("agent_trace", [])
    updated_memory   = result_state.get("working_memory", {})

    # ── DEBUG: confirm what the graph actually produced for trace/memory ─────
    logger.info(f"[TRACE DEBUG] agent_trace has {len(agent_trace)} steps: "
                f"{[s.get('agent') for s in agent_trace]}")
    logger.info(f"[TRACE DEBUG] updated_memory keys: {list(updated_memory.keys())}")
    logger.info(f"[TRACE DEBUG] result_state top-level keys: {list(result_state.keys())}")

    # ── Determine where `sources` actually came from, from the real trace ────
    # (not from forced_intent / query.agent, since the router can override it).
    agents_run = {step.get("agent") for step in agent_trace}
    if "RAG Agent" in agents_run or "Summary Agent" in agents_run:
        source_type = "document"
    elif "Web Search Agent" in agents_run:
        source_type = "web"
    else:
        source_type = "none"

    # ── Persist messages ──────────────────────────────────────────────────────
    db.add(Message(chat_id=chat.id, role="user",      content=query.query))
    db.add(Message(chat_id=chat.id, role="assistant", content=final_response))
    db.commit()

    # ── Persist updated working memory ────────────────────────────────────────
    _save_memory(db, chat.id, MOCK_USER_ID, updated_memory)
    logger.info(f"Saved working memory for chat {chat.id}: {list(updated_memory.keys())}")

    # ── Enforce 5-chat limit ──────────────────────────────────────────────────
    _enforce_chat_limit(db, MOCK_USER_ID)

    return {
        "response":        final_response,
        "sources":         sources,
        "source_type":     source_type,
        "report_suggested": report_suggested,
        "suggested_title": suggested_title,
        "chat_id":         chat.id,
        "agent_trace":     agent_trace,
        "working_memory":  updated_memory,
    }


@router.get("/sessions")
def list_chat_sessions(db: DBSession = Depends(get_db)):
    chats = (
        db.query(Chat)
        .filter(Chat.user_id == MOCK_USER_ID)
        .order_by(Chat.created_at.desc())
        .limit(MAX_SAVED_CHATS)
        .all()
    )
    results = []
    for c in chats:
        last_msg = (
            db.query(Message)
            .filter(Message.chat_id == c.id)
            .order_by(Message.created_at.desc())
            .first()
        )
        preview = (last_msg.content[:80] + "…") if last_msg and len(last_msg.content) > 80 else (last_msg.content if last_msg else "")
        results.append({
            "id":      c.id,
            "title":   c.title,
            "preview": preview,
            "date":    c.created_at.strftime("%d %b, %H:%M") if c.created_at else "",
        })
    return results


@router.get("/sessions/{chat_id}")
def get_chat_session(chat_id: int, db: DBSession = Depends(get_db)):
    chat = db.query(Chat).filter(
        Chat.id == chat_id, Chat.user_id == MOCK_USER_ID
    ).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found.")

    messages = (
        db.query(Message)
        .filter(Message.chat_id == chat.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return {
        "id":       chat.id,
        "title":    chat.title,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
    }


@router.get("/sessions/{chat_id}/memory")
def get_chat_memory(chat_id: int, db: DBSession = Depends(get_db)):
    """Return the current working memory snapshot for a chat session."""
    memory = _load_memory(db, chat_id, MOCK_USER_ID)
    return {"chat_id": chat_id, "working_memory": memory}


@router.delete("/sessions/{chat_id}")
def delete_chat_session(chat_id: int, db: DBSession = Depends(get_db)):
    chat = db.query(Chat).filter(
        Chat.id == chat_id, Chat.user_id == MOCK_USER_ID
    ).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    db.delete(chat)
    db.commit()
    return {"status": "deleted", "id": chat_id}


@router.get("/history")
def get_chat_history():
    return []
