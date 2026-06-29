"""
Shared LLM client — Google Gemini via langchain-google-genai.

Falls back gracefully if no API key is configured.
The lru_cache ensures a single instance is reused across all agent nodes.
"""

from functools import lru_cache

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_llm():
    """Return a cached ChatGoogleGenerativeAI instance, or None if no key."""
    if not settings.GOOGLE_API_KEY:
        logger.warning("GOOGLE_API_KEY not set — LLM calls will be disabled.")
        return None

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        model_name = settings.GEMINI_MODEL or "gemini-2.5-flash"
        logger.info(f"Initializing Gemini LLM with model: {model_name}")

        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.3,
            google_api_key=settings.GOOGLE_API_KEY,
           
        )
    except Exception as exc:
        logger.error(f"Failed to initialize Gemini LLM: {exc}")
        return None
