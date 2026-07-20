"""
Text embeddings for the memory system.

Uses OpenAI's `text-embedding-3-small` when `OPENAI_API_KEY` is set — cheap,
well-understood, genuinely semantic (catches paraphrases, not just shared
words). Without a key, falls back to a dependency-free deterministic hashing
embedding so search still works on day one, just with lexical (keyword-ish)
recall rather than true semantic recall.

Because the two methods produce different vector spaces (and different
dimensionality), `memory_service.search_memory` only does a direct cosine
comparison between entries embedded with the *same* model as the query, and
falls back to plain token overlap for anything embedded the other way. Run
`scripts/reembed_memory.py` after adding an OpenAI key for the first time to
upgrade every existing entry to real embeddings in one pass.
"""
import hashlib
import math
import re
from collections import Counter

import httpx

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

LOCAL_MODEL_NAME = "local-hashing-v1"
OPENAI_MODEL_NAME = "text-embedding-3-small"
LOCAL_EMBEDDING_DIM = 256

_WORD_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _local_embedding(text: str) -> list[float]:
    vec = [0.0] * LOCAL_EMBEDDING_DIM
    tokens = tokenize(text)
    if not tokens:
        return vec
    counts = Counter(tokens)
    for token, count in counts.items():
        bucket = int(hashlib.sha256(token.encode()).hexdigest(), 16) % LOCAL_EMBEDDING_DIM
        vec[bucket] += count
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


async def _openai_embedding(text: str) -> list[float] | None:
    if not settings.OPENAI_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={"model": OPENAI_MODEL_NAME, "input": text[:8000]},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]
    except httpx.HTTPError as exc:
        logger.warning("openai_embedding_failed", error=str(exc))
        return None


async def embed_text(text: str) -> tuple[list[float], str]:
    """Returns (embedding, model_name_used)."""
    openai_vec = await _openai_embedding(text)
    if openai_vec is not None:
        return openai_vec, OPENAI_MODEL_NAME
    return _local_embedding(text), LOCAL_MODEL_NAME


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


def jaccard_similarity(a_tokens: set[str], b_tokens: set[str]) -> float:
    if not a_tokens or not b_tokens:
        return 0.0
    intersection = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return intersection / union if union else 0.0
