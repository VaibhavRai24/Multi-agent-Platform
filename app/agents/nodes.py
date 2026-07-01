import time
import random
import json
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import GraphState, TraceStep
from app.utils.logger import get_logger
from app.utils.pinecone_client import get_pinecone_index, embed_text
from app.utils.llm_client import get_llm

logger = get_logger(__name__)


# ── Timing helper ──────────────────────────────────────────────────────────────
class _Timer:
    def __init__(self):
        self._start = time.perf_counter()

    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self._start) * 1000)


# ── Router ─────────────────────────────────────────────────────────────────────

_ROUTER_SYSTEM_PROMPT = """You are an intent classification engine for an enterprise AI assistant.
Classify the user's message into EXACTLY ONE of these intents:

- general       : greetings, small-talk, or factual/knowledge questions the LLM can answer
                  from its own training data WITHOUT needing any external tool.
- web_search    : user explicitly wants CURRENT / LIVE / LATEST information from the internet,
                  OR asks about recent events, news, trends, prices, or anything time-sensitive.
- rag_query     : user wants information FROM their own uploaded documents/files.
- summarize     : user wants a summary of their own uploaded documents (NOT a general topic).

CRITICAL RULES:
1. If the user says "search", "web search", "look up", "find online", "latest", "current",
   "news", "today", or "browse" → ALWAYS return "web_search".
2. If the question is about something that changes over time → "web_search".
3. Only return "general" if purely educational/conceptual AND user did NOT ask to search.
4. Reply with ONLY the intent word. Nothing else."""


def router_agent(state: GraphState) -> GraphState:
    t = _Timer()
    logger.info("Executing Router Agent")
    query  = state.get("user_query", "").strip()
    forced = state.get("forced_intent")

    # Working-memory enrichment: remember topics seen across turns
    memory: dict = dict(state.get("working_memory") or {})

    if forced:
        intent = forced
        decision_reason = f"Frontend forced intent: '{forced}' — LLM routing skipped."
        logger.info(decision_reason)
    else:
        intent = _llm_classify_intent(query)
        decision_reason = f"LLM classified query as intent='{intent}'."
        logger.info(f"Router → '{intent}' for query: '{query[:80]}'")

    # Accumulate topic keywords into working memory
    topic_keywords = [w for w in query.lower().split() if len(w) > 4][:5]
    memory.setdefault("topic_history", [])
    memory["topic_history"] = (memory["topic_history"] + topic_keywords)[-20:]
    memory["last_intent"] = intent

    step: TraceStep = {
        "agent": "Router Agent",
        "action": "Intent Classification",
        "output": decision_reason,
        "duration_ms": t.elapsed_ms(),
        "metadata": {"intent": intent, "forced": bool(forced)},
    }

    return {
        "intent": intent,
        "working_memory": memory,
        "agent_trace": [step],
        "intermediate_steps": ["router_agent"],
    }


def _llm_classify_intent(query: str) -> str:
    llm = get_llm()
    if llm is not None:
        try:
            response = llm.invoke([
                SystemMessage(content=_ROUTER_SYSTEM_PROMPT),
                HumanMessage(content=query),
            ])
            raw = response.content.strip().lower().split()[0]
            if raw in {"general", "rag_query", "web_search", "summarize"}:
                return raw
            logger.warning(f"LLM router returned unexpected intent '{raw}', using keyword fallback.")
        except Exception as exc:
            logger.error(f"LLM router failed: {exc}. Keyword fallback.")

    q = query.lower()
    words = set(q.split())
    greetings = {"hi", "hii", "hello", "hey", "yo", "sup", "thanks", "ok", "okay"}
    if len(words) <= 3 and (words & greetings):
        return "general"
    if any(k in q for k in ["search", "internet", "latest", "news", "today", "browse", "look up", "web search"]):
        return "web_search"
    if any(k in q for k in ["summarize", "summary"]):
        return "summarize"
    if any(k in q for k in ["document", "file", "uploaded", "pdf", "according to", "in my"]):
        return "rag_query"
    return "general"


# ── Web Search Agent ───────────────────────────────────────────────────────────

def _ddg_search_with_retry(query: str, max_results: int = 5, retries: int = 3) -> list:
    from ddgs import DDGS
    from ddgs.exceptions import RatelimitException, DDGSException

    base_delay = 2.0
    for attempt in range(1, retries + 1):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            logger.info(f"DDGS search succeeded on attempt {attempt} — {len(results)} results.")
            return results
        except RatelimitException:
            if attempt == retries:
                raise
            delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0.5, 1.5)
            logger.warning(f"DDGS rate-limited (attempt {attempt}/{retries}). Retry in {delay:.1f}s…")
            time.sleep(delay)
        except DDGSException as exc:
            if attempt == retries:
                raise
            delay = base_delay + random.uniform(0.5, 1.0)
            logger.warning(f"DDGS error (attempt {attempt}/{retries}): {exc}. Retry in {delay:.1f}s…")
            time.sleep(delay)
    return []


def web_search_agent(state: GraphState) -> GraphState:
    t = _Timer()
    logger.info("Executing Web Search Agent")
    query  = state.get("user_query", "")
    memory = dict(state.get("working_memory") or {})

    # Use memory to refine the search query if we have recent topic context
    topic_history = memory.get("topic_history", [])
    enriched_query = query  # could optionally prepend topic terms

    try:
        results = _ddg_search_with_retry(enriched_query, max_results=5, retries=3)
        context_docs = []
        sources_summary = []
        for r in results:
            title = r.get("title", "No title")
            body  = r.get("body", "").strip()
            href  = r.get("href", "")
            if body:
                context_docs.append(f"[{title}] ({href})\n{body}")
                sources_summary.append(title)

        memory["last_search_query"] = enriched_query
        memory["last_search_sources"] = sources_summary

        step: TraceStep = {
            "agent": "Web Search Agent",
            "action": "DuckDuckGo Search",
            "output": f"Retrieved {len(context_docs)} results for: \"{query[:70]}\"",
            "duration_ms": t.elapsed_ms(),
            "metadata": {"result_count": len(context_docs), "sources": sources_summary[:5]},
        }
        return {
            "context_docs": context_docs,
            "working_memory": memory,
            "agent_trace": [step],
            "intermediate_steps": ["web_search_agent"],
        }

    except ImportError:
        logger.error("ddgs is not installed.")
        step: TraceStep = {
            "agent": "Web Search Agent",
            "action": "DuckDuckGo Search",
            "output": "Error: ddgs package not installed.",
            "duration_ms": t.elapsed_ms(),
            "metadata": {"error": "ImportError"},
        }
        return {"context_docs": [], "working_memory": memory, "agent_trace": [step], "intermediate_steps": ["web_search_agent"]}
    except Exception as exc:
        logger.error(f"Web search failed: {exc}")
        step: TraceStep = {
            "agent": "Web Search Agent",
            "action": "DuckDuckGo Search",
            "output": f"Search failed after retries: {str(exc)[:120]}",
            "duration_ms": t.elapsed_ms(),
            "metadata": {"error": str(exc)[:200]},
        }
        return {"context_docs": [], "working_memory": memory, "agent_trace": [step], "intermediate_steps": ["web_search_agent"]}


# ── RAG Agent ──────────────────────────────────────────────────────────────────

def rag_agent(state: GraphState) -> GraphState:
    t = _Timer()
    logger.info("Executing RAG Agent")
    query   = state.get("user_query", "")
    user_id = state.get("user_id")
    memory  = dict(state.get("working_memory") or {})

    index = get_pinecone_index()
    if index is None:
        logger.warning("Pinecone unavailable.")
        step: TraceStep = {
            "agent": "RAG Agent",
            "action": "Vector Search (Pinecone)",
            "output": "Pinecone index unavailable — no document context retrieved.",
            "duration_ms": t.elapsed_ms(),
            "metadata": {"error": "pinecone_unavailable"},
        }
        return {"context_docs": [], "working_memory": memory, "agent_trace": [step], "intermediate_steps": ["rag_agent"]}

    try:
        query_vector = embed_text(query)
        filter_dict  = {"user_id": user_id} if user_id is not None else None
        results      = index.query(vector=query_vector, top_k=5, include_metadata=True, filter=filter_dict)
        matches      = results.get("matches", []) if isinstance(results, dict) else getattr(results, "matches", [])

        context_docs = []
        sources_seen = []
        for match in matches:
            metadata = match.get("metadata", {}) if isinstance(match, dict) else getattr(match, "metadata", {}) or {}
            text     = metadata.get("text", "")
            source   = metadata.get("source", "unknown")
            score    = match.get("score") if isinstance(match, dict) else getattr(match, "score", None)
            if text:
                score_str = f"{score:.3f}" if isinstance(score, (int, float)) else "n/a"
                context_docs.append(f"[{source}] (score={score_str}) {text}")
                if source not in sources_seen:
                    sources_seen.append(source)

        # Store retrieved sources in working memory so the report writer knows what was used
        memory["last_rag_sources"] = sources_seen
        memory["last_rag_chunks"]  = len(context_docs)

        step: TraceStep = {
            "agent": "RAG Agent",
            "action": "Vector Search (Pinecone)",
            "output": f"Retrieved {len(context_docs)} chunks from {len(sources_seen)} document(s): {', '.join(sources_seen) or 'none'}",
            "duration_ms": t.elapsed_ms(),
            "metadata": {"chunk_count": len(context_docs), "sources": sources_seen},
        }
        return {
            "context_docs": context_docs,
            "working_memory": memory,
            "agent_trace": [step],
            "intermediate_steps": ["rag_agent"],
        }
    except Exception as exc:
        logger.error(f"RAG retrieval failed: {exc}")
        step: TraceStep = {
            "agent": "RAG Agent",
            "action": "Vector Search (Pinecone)",
            "output": f"Retrieval error: {str(exc)[:120]}",
            "duration_ms": t.elapsed_ms(),
            "metadata": {"error": str(exc)[:200]},
        }
        return {"context_docs": [], "working_memory": memory, "agent_trace": [step], "intermediate_steps": ["rag_agent"]}


# ── Summary Agent ──────────────────────────────────────────────────────────────

def summary_agent(state: GraphState) -> GraphState:
    t = _Timer()
    logger.info("Executing Summary Agent")

    # Delegate to RAG for retrieval, then tag the trace correctly
    rag_result = rag_agent(state)

    # Replace the RAG trace step with a Summary-branded one
    rag_trace = rag_result.get("agent_trace", [])
    rag_output = rag_trace[0]["output"] if rag_trace else "No context retrieved."

    step: TraceStep = {
        "agent": "Summary Agent",
        "action": "Document Retrieval for Summarization",
        "output": rag_output,
        "duration_ms": t.elapsed_ms(),
        "metadata": rag_trace[0].get("metadata", {}) if rag_trace else {},
    }
    return {
        "context_docs": rag_result.get("context_docs", []),
        "working_memory": rag_result.get("working_memory", state.get("working_memory") or {}),
        "agent_trace": [step],
        "intermediate_steps": ["summary_agent"],
    }


# ── Report Writer (Final Synthesis) ───────────────────────────────────────────

_REPORT_WORTHY_SYSTEM_PROMPT = """You decide whether an AI assistant's answer is substantial
enough to be worth saving as a standalone report document.

Reply with STRICT JSON only, no markdown fences, no explanation:
{"report_worthy": true or false, "title": "a short descriptive title (max 8 words) or empty string if not worthy"}

report_worthy = true for: analysis, comparisons, research write-ups, structured multi-paragraph answers.
report_worthy = false for: greetings, one-liners, error messages, conversational chit-chat."""


def _llm_judge_report_worthy(query: str, answer: str) -> dict:
    llm = get_llm()
    if llm is not None:
        try:
            response = llm.invoke([
                SystemMessage(content=_REPORT_WORTHY_SYSTEM_PROMPT),
                HumanMessage(content=f"User question:\n{query}\n\nAssistant answer:\n{answer}"),
            ])
            raw = response.content.strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.lower().startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
            return {"report_worthy": bool(parsed.get("report_worthy", False)), "title": str(parsed.get("title", "")).strip()}
        except Exception as exc:
            logger.warning(f"Report-worthiness LLM judgement failed: {exc}. Heuristic fallback.")

    word_count = len(answer.split())
    worthy = word_count >= 120 or answer.count("\n") >= 4
    return {"report_worthy": worthy, "title": query.strip()[:60] if worthy else ""}


def report_writer_agent(state: GraphState) -> GraphState:
    t = _Timer()
    logger.info("Executing Report Writer Agent")

    query        = state.get("user_query", "")
    context_docs = state.get("context_docs", [])
    intent       = state.get("intent", "general")
    memory       = dict(state.get("working_memory") or {})
    llm          = get_llm()

    if llm is None:
        step: TraceStep = {
            "agent": "Report Writer Agent",
            "action": "Final Synthesis",
            "output": "No LLM configured — cannot generate response.",
            "duration_ms": t.elapsed_ms(),
            "metadata": {"error": "no_llm"},
        }
        return {
            "final_report": "I can't generate a response right now — no LLM API key is configured.",
            "report_suggested": False,
            "suggested_title": "",
            "working_memory": memory,
            "agent_trace": [step],
            "intermediate_steps": ["report_writer_agent"],
        }

    # Build system prompt from context + intent
    if context_docs:
        context_block = "\n\n---\n\n".join(context_docs)
        if intent == "web_search":
            system_prompt = (
                "You are a helpful enterprise AI assistant with access to live web search results.\n"
                "The snippets below are short and incomplete — do not just restate them. Synthesize "
                "them into a thorough, well-organized answer: pull out every distinct fact, name, "
                "number, or event mentioned across the snippets, group related points together, and "
                "add relevant context/background from your own knowledge to fill gaps the snippets "
                "don't cover. If the user asked for a list (e.g. 'top 10'), build the best list you "
                "can from what's available, explicitly note if fewer than the requested number of "
                "distinct items were found, and never respond with just one or two lines saying "
                "information wasn't available — always give the fullest answer the snippets support "
                "plus your own knowledge. Mention source titles where relevant.\n\n"
                f"Web Search Results:\n{context_block}"
            )
        else:
            system_prompt = (
                "You are an enterprise AI assistant. Use the provided context to answer accurately "
                "and in detail — cover every relevant point in the context rather than a brief summary.\n"
                "Supplement with your own knowledge where needed, making clear which parts come from context.\n\n"
                f"Context:\n{context_block}"
            )
    else:
        system_prompt = (
            "You are a helpful, friendly enterprise AI assistant. Answer the user's message "
            "thoroughly using your own knowledge."
            if intent != "web_search" else
            "You are a helpful enterprise AI assistant. A web search was attempted but returned "
            "no results. Answer thoroughly using your own knowledge and inform the user live results were unavailable."
        )

    # Inject working memory as additional context for the LLM
    if memory.get("topic_history"):
        recent_topics = ", ".join(memory["topic_history"][-10:])
        system_prompt += f"\n\n[Session context — recent topics discussed: {recent_topics}]"

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=query),
        ])
        answer = response.content
    except Exception as exc:
        logger.error(f"LLM call failed in report_writer_agent: {exc}")
        answer = f"Sorry, I ran into an error: {exc}"

    # Judge report worthiness
    report_suggested = False
    suggested_title  = ""
    judge_output     = "Report-worthiness check skipped."
    try:
        judgement        = _llm_judge_report_worthy(query, answer)
        report_suggested = judgement["report_worthy"]
        suggested_title  = judgement["title"]
        judge_output     = f"Report-worthy: {report_suggested}. Title: '{suggested_title}'"
        if report_suggested:
            logger.info(f"Report-worthy. Suggested title: '{suggested_title}'")
    except Exception as exc:
        logger.warning(f"Report-worthiness check raised: {exc}")

    # Update working memory with what was synthesised
    memory["last_answer_length"] = len(answer.split())
    memory["last_report_suggested"] = report_suggested

    step: TraceStep = {
        "agent": "Report Writer Agent",
        "action": "Final Synthesis + Report Check",
        "output": f"Generated {len(answer.split())} word answer. {judge_output}",
        "duration_ms": t.elapsed_ms(),
        "metadata": {
            "word_count": len(answer.split()),
            "report_suggested": report_suggested,
            "suggested_title": suggested_title,
            "context_chunks_used": len(context_docs),
        },
    }

    return {
        "final_report": answer,
        "report_suggested": report_suggested,
        "suggested_title": suggested_title,
        "working_memory": memory,
        "agent_trace": [step],
        "intermediate_steps": ["report_writer_agent"],
    }
