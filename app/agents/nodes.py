import time
import random
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import GraphState
from app.utils.logger import get_logger
from app.utils.pinecone_client import get_pinecone_index, embed_text
from app.utils.llm_client import get_llm

logger = get_logger(__name__)


_ROUTER_SYSTEM_PROMPT = """You are an intent classification engine for an enterprise AI assistant.
Classify the user's message into EXACTLY ONE of these intents:

- general       : greetings, small-talk, or factual/knowledge questions the LLM can answer
                  from its own training data WITHOUT needing any external tool.
                  (e.g. "hi", "what is Python?", "explain recursion", "how does TCP work")

- web_search    : user explicitly wants CURRENT / LIVE / LATEST information from the internet,
                  OR asks about recent events, news, trends, prices, or anything time-sensitive.
                  Also use when user says "search the web", "look it up", "browse", "find online".
                  (e.g. "latest AI news", "current Bitcoin price", "search for transformer architecture",
                   "can you do a web search for...", "what happened today in...", "look up...")

- rag_query     : user wants information FROM their own uploaded documents/files.
                  (e.g. "according to my file…", "what does my contract say", "check my uploaded PDF")

- summarize     : user wants a summary of their own uploaded documents (NOT a general topic).
                  (e.g. "summarize my uploaded report", "give me a tldr of the file I sent")

CRITICAL RULES:
1. If the user says "search", "web search", "look up", "find online", "latest", "current", "news",
   "today", or "browse" → ALWAYS return "web_search", even if you know the answer yourself.
2. If the question is about something that changes over time (prices, news, recent events) → "web_search".
3. Only return "general" if the question is purely educational/conceptual AND the user did NOT ask you to search.
4. Reply with ONLY the intent word. No explanation, no punctuation, nothing else."""


def router_agent(state: GraphState) -> GraphState:
    """Classify user intent using the LLM for intelligent routing."""
    logger.info("Executing Router Agent")
    query = state.get("user_query", "").strip()

    # If the frontend forced a specific agent mode, honour it — skip LLM classification
    forced = state.get("forced_intent")
    if forced:
        logger.info(f"Router bypassed — forced intent: '{forced}'")
        return {"intent": forced, "intermediate_steps": ["router_agent"]}

    intent = _llm_classify_intent(query)
    logger.info(f"Router classified intent as: '{intent}' for query: '{query[:80]}'")
    return {"intent": intent, "intermediate_steps": ["router_agent"]}


def _llm_classify_intent(query: str) -> str:
    """Ask the LLM to classify intent; fall back to keyword heuristics on failure."""
    llm = get_llm()

    if llm is not None:
        try:
            response = llm.invoke([
                SystemMessage(content=_ROUTER_SYSTEM_PROMPT),
                HumanMessage(content=query),
            ])
            raw = response.content.strip().lower().split()[0]
            valid = {"general", "rag_query", "web_search", "summarize"}
            if raw in valid:
                return raw
            logger.warning(f"LLM router returned unexpected intent '{raw}', falling back to keywords.")
        except Exception as exc:
            logger.error(f"LLM router failed: {exc}. Falling back to keyword heuristics.")

  
    q = query.lower()
    words = set(q.split())
    greeting_words = {"hi", "hii", "hello", "hey", "yo", "sup", "thanks", "ok", "okay"}
    if len(words) <= 3 and (words & greeting_words or q in {"thank you", "thanks a lot"}):
        return "general"
    if any(k in q for k in ["search", "internet", "latest", "news", "today", "browse", "look up", "find online", "web search"]):
        return "web_search"
    if any(k in q for k in ["summarize", "summary"]):
        return "summarize"
    if any(k in q for k in ["document", "file", "uploaded", "pdf", "according to", "in my"]):
        return "rag_query"
    return "general"



def _ddg_search_with_retry(query: str, max_results: int = 5, retries: int = 3) -> list:
    """
    Run a DuckDuckGo text search using the new `ddgs` package with exponential
    backoff on rate-limit errors.
    """
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
                logger.error(f"DDGS rate-limited on all {retries} attempts. Giving up.")
                raise
            delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0.5, 1.5)
            logger.warning(f"DDGS rate-limited (attempt {attempt}/{retries}). Retrying in {delay:.1f}s…")
            time.sleep(delay)

        except DDGSException as exc:
            if attempt == retries:
                logger.error(f"DDGS search error on all attempts: {exc}")
                raise
            delay = base_delay + random.uniform(0.5, 1.0)
            logger.warning(f"DDGS search error (attempt {attempt}/{retries}): {exc}. Retrying in {delay:.1f}s…")
            time.sleep(delay)

    return []


def web_search_agent(state: GraphState) -> GraphState:
    """Tool node: search the web using DDGS and return results as context."""
    logger.info("Executing Web Search Agent")

    query = state.get("user_query", "")

    try:
        results = _ddg_search_with_retry(query, max_results=5, retries=3)

        if not results:
            logger.warning("DDGS returned no results after retries.")
            return {"context_docs": [], "intermediate_steps": ["web_search_agent"]}

        context_docs = []
        for r in results:
            title = r.get("title", "No title")
            body  = r.get("body", "").strip()
            href  = r.get("href", "")
            if body:
                context_docs.append(f"[{title}] ({href})\n{body}")

        logger.info(f"Web search returned {len(context_docs)} usable results for: '{query[:60]}'")
        return {"context_docs": context_docs, "intermediate_steps": ["web_search_agent"]}

    except ImportError:
        logger.error("ddgs is not installed. Run: pip install ddgs")
        return {"context_docs": [], "intermediate_steps": ["web_search_agent"]}

    except Exception as exc:
        logger.error(f"Web search failed after all retries: {exc}")
        return {"context_docs": [], "intermediate_steps": ["web_search_agent"]}


def rag_agent(state: GraphState) -> GraphState:
    """Tool node: retrieve document chunks from Pinecone for the Report Writer."""
    logger.info("Executing RAG Agent")

    query = state.get("user_query", "")
    user_id = state.get("user_id")

    index = get_pinecone_index()
    if index is None:
        logger.warning("Pinecone index unavailable — returning empty context.")
        return {"context_docs": [], "intermediate_steps": ["rag_agent"]}

    try:
        query_vector = embed_text(query)

        filter_dict = {"user_id": user_id} if user_id is not None else None
        results = index.query(
            vector=query_vector,
            top_k=5,
            include_metadata=True,
            filter=filter_dict,
        )

        matches = results.get("matches", []) if isinstance(results, dict) else getattr(results, "matches", [])
        context_docs = []
        for match in matches:
            metadata = match.get("metadata", {}) if isinstance(match, dict) else getattr(match, "metadata", {}) or {}
            text = metadata.get("text", "")
            source = metadata.get("source", "unknown")
            score = match.get("score") if isinstance(match, dict) else getattr(match, "score", None)
            if text:
                score_str = f"{score:.3f}" if isinstance(score, (int, float)) else "n/a"
                context_docs.append(f"[{source}] (score={score_str}) {text}")

        return {"context_docs": context_docs, "intermediate_steps": ["rag_agent"]}

    except Exception as exc:
        logger.error(f"RAG agent retrieval failed: {exc}")
        return {"context_docs": [], "intermediate_steps": ["rag_agent"]}


def summary_agent(state: GraphState) -> GraphState:
    """Tool node: gather material to summarize (delegates to RAG for now)."""
    logger.info("Executing Summary Agent")
    result = rag_agent(state)
    result["intermediate_steps"] = ["summary_agent"]
    return result




_REPORT_WORTHY_SYSTEM_PROMPT = """You decide whether an AI assistant's answer is substantial
enough to be worth saving as a standalone report document (something a user would want to
download, re-read later, or share — e.g. an analysis, comparison, summary, research write-up,
plan, or any multi-paragraph structured answer).

Reply with STRICT JSON only, no markdown fences, no explanation:
{"report_worthy": true or false, "title": "a short descriptive title (max 8 words) for the report, or empty string if not worthy"}

Guidelines:
- report_worthy = true for: explanations of a topic with real depth, comparisons, summaries,
  research, analysis, structured multi-section answers, anything the user would plausibly want
  as a saved document.
- report_worthy = false for: greetings, short factual one-liners, clarifying questions,
  error messages, very short answers (a sentence or two), conversational chit-chat.
- The title should be specific to the content (e.g. "Comparison of REST and GraphQL APIs"),
  not generic (e.g. "Report" or "Answer")."""


def _llm_judge_report_worthy(query: str, answer: str) -> dict:
    """Ask the LLM whether this Q&A pair deserves to be saved as a report.

    Falls back to a simple length heuristic if the LLM is unavailable or
    returns something unparseable, so the feature degrades gracefully
    instead of failing the whole chat request.
    """
    import json

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
            worthy = bool(parsed.get("report_worthy", False))
            title = str(parsed.get("title", "")).strip()
            return {"report_worthy": worthy, "title": title}
        except Exception as exc:
            logger.warning(f"Report-worthiness LLM judgement failed: {exc}. Falling back to heuristic.")

    # --- Heuristic fallback: longer, multi-line answers are more likely report-worthy ---
    word_count = len(answer.split())
    worthy = word_count >= 120 or answer.count("\n") >= 4
    title = (query.strip()[:60] if worthy else "")
    return {"report_worthy": worthy, "title": title}




def report_writer_agent(state: GraphState) -> GraphState:
    """Generate the final answer grounded in context when available, then
    judge whether the answer is worth offering/saving as a report."""
    logger.info("Executing Report Writer Agent")

    query        = state.get("user_query", "")
    context_docs = state.get("context_docs", [])
    intent       = state.get("intent", "general")
    llm          = get_llm()

    if llm is None:
        return {
            "final_report": "I can't generate a response right now because no LLM API key is configured on the server.",
            "report_suggested": False,
            "suggested_title": "",
            "intermediate_steps": ["report_writer_agent"],
        }

    if context_docs:
        context_block = "\n\n---\n\n".join(context_docs)
        if intent == "web_search":
            system_prompt = (
                "You are a helpful enterprise AI assistant with access to live web search results.\n"
                "The following search results were retrieved from the internet for the user's query.\n"
                "Synthesize them into a clear, accurate, and well-structured answer.\n"
                "Always mention the source titles where relevant so the user knows where the info comes from.\n"
                "If the results don't fully answer the question, say so and supplement with your own knowledge.\n\n"
                f"Web Search Results:\n{context_block}"
            )
        else:
            system_prompt = (
                "You are an enterprise AI assistant. Use the provided context to answer "
                "the user's question accurately and concisely. Supplement with your own "
                "knowledge where needed, making clear which parts come from the context.\n\n"
                f"Context:\n{context_block}"
            )
    else:
        if intent == "web_search":
            system_prompt = (
                "You are a helpful enterprise AI assistant. A web search was attempted but "
                "returned no results (possibly a temporary rate limit). Answer using your own "
                "knowledge and inform the user that live results were unavailable."
            )
        else:
            system_prompt = (
                "You are a helpful, friendly enterprise AI assistant. Answer the user's "
                "message directly and naturally using your own knowledge."
            )

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=query),
        ])
        answer = response.content
    except Exception as exc:
        logger.error(f"LLM call failed in report_writer_agent: {exc}")
        answer = f"Sorry, I ran into an error generating a response: {exc}"

    # Decide whether this answer is substantial enough to suggest/save as a report.
    report_suggested = False
    suggested_title = ""
    try:
        judgement = _llm_judge_report_worthy(query, answer)
        report_suggested = judgement["report_worthy"]
        suggested_title = judgement["title"]
        if report_suggested:
            logger.info(f"Report-worthy answer detected. Suggested title: '{suggested_title}'")
    except Exception as exc:
        logger.warning(f"Report-worthiness judgement raised unexpectedly: {exc}")

    return {
        "final_report": answer,
        "report_suggested": report_suggested,
        "suggested_title": suggested_title,
        "intermediate_steps": ["report_writer_agent"],
    }
