"""
Shared Pinecone client and embedding model.

Provides a single lazily-initialized Pinecone index handle and a single
SentenceTransformer model so we don't reconnect or reload the model on
every request. Embeddings use all-MiniLM-L6-v2 (384 dimensions) so the
Pinecone index must be created with dimension=384 and metric=cosine.
"""

from functools import lru_cache
from typing import Optional

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

EMBEDDING_DIM = 1024


@lru_cache(maxsize=1)
def get_embedding_model():
    """Load and cache the sentence-transformers embedding model.
    
    Model: BAAI/bge-large-en-v1.5 — 1024 dimensions, matches Pinecone index.
    Alternatives if this is too heavy: 'intfloat/e5-large-v2' (1024-dim) or
    recreate Pinecone index at 384 dims and revert to all-MiniLM-L6-v2.
    """
    from sentence_transformers import SentenceTransformer
    logger.info("Loading embedding model: BAAI/bge-large-en-v1.5 (1024-dim)")
    return SentenceTransformer("BAAI/bge-large-en-v1.5")


def embed_text(text: str) -> list[float]:
    """Embed a single piece of text into a 384-dim vector."""
    model = get_embedding_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts."""
    model = get_embedding_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


@lru_cache(maxsize=1)
def get_pinecone_index():
    """
    Return a cached Pinecone Index handle, or None if Pinecone isn't
    configured. Callers must handle a None return gracefully.
    """
    if not settings.PINECONE_API_KEY:
        logger.warning("PINECONE_API_KEY not set — Pinecone retrieval disabled.")
        return None

    from pinecone import Pinecone

    pc = Pinecone(api_key=settings.PINECONE_API_KEY)

    try:
        if settings.PINECONE_HOST:
            # Connect directly via host — avoids an extra describe_index call
            # and works even if the API key's list permissions are restricted.
            index = pc.Index(host=settings.PINECONE_HOST)
        else:
            index = pc.Index(settings.PINECONE_INDEX_NAME)
        return index
    except Exception as exc:
        logger.error(f"Failed to connect to Pinecone index: {exc}")
        return None
