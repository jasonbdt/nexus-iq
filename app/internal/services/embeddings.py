"""LangChain OpenAI embedding helpers for single and batch text embedding."""

import os
from functools import lru_cache

from langchain_openai import OpenAIEmbeddings


@lru_cache(maxsize=1)
def _embeddings_client() -> OpenAIEmbeddings:
    model = os.getenv("EMBEDDING_MODEL") or "text-embedding-3-small"
    return OpenAIEmbeddings(model=model)


async def embed_text(text: str) -> list[float]:
    """Embed a single text using text-embedding-3-small (or ``EMBEDDING_MODEL`` when set)."""
    return await _embeddings_client().aembed_query(text)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts in a batch."""
    return _embeddings_client().embed_documents(texts)
