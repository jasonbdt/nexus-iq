"""Qdrant via LangChain ``QdrantVectorStore`` — indexing and similarity retrieval."""

import asyncio
import os
import re
import uuid
from functools import lru_cache

from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FloatIndexParams,
    FloatIndexType,
    MatchText,
    Range,
    VectorParams,
)

from app.internal.services.llm import DeterminedPatchVersions

NAMESPACE = uuid.UUID(os.getenv("APP_KEY"))


def normalize(text: str) -> str:
    """Collapse whitespace in text and strip leading/trailing spaces."""
    return re.sub(r"\s+", " ", text).strip()


def point_id(patch_version: float, source: str, chunk_index: int, content: str) -> str:
    """Generate a deterministic UUID for a chunk based on its content and position."""
    raw = f"{patch_version}|{source}|{chunk_index}|{normalize(content)}"
    return str(uuid.uuid5(NAMESPACE, raw))


@lru_cache(maxsize=1)
def _sync_client() -> QdrantClient:
    return QdrantClient(
        host=os.getenv("QDRANT_HOST"),
        port=int(os.getenv("QDRANT_PORT")),
    )


@lru_cache(maxsize=1)
def _embeddings() -> OpenAIEmbeddings:
    model = os.getenv("EMBEDDING_MODEL") or "text-embedding-3-small"
    return OpenAIEmbeddings(model=model)


@lru_cache(maxsize=1)
def patch_vector_store() -> QdrantVectorStore:
    """Shared dense vector store for patch-note Documents (LangChain payload layout)."""
    name = os.getenv("QDRANT_COLLECTION_NAME")
    if not name:
        msg = "QDRANT_COLLECTION_NAME must be set"
        raise RuntimeError(msg)
    return QdrantVectorStore(
        client=_sync_client(),
        collection_name=name,
        embedding=_embeddings(),
    )


def _to_float(value: float | str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def patch_notes_query_filter(
    patch_versions: DeterminedPatchVersions,
    keywords: list[str] | None,
) -> Filter:
    """Qdrant filter for LangChain payloads (``page_content`` + nested ``metadata``)."""
    version_condition = FieldCondition(
        key="metadata.patch_version",
        range=Range(
            gte=_to_float(patch_versions.gte, 0.0),
            lte=_to_float(patch_versions.lte, 99.99),
        ),
    )
    if keywords:
        keyword_conditions = [
            FieldCondition(key="page_content", match=MatchText(text=kw))
            for kw in keywords
        ]
        return Filter(must=[version_condition], should=keyword_conditions)
    return Filter(must=[version_condition])


def _ensure_collection_sync() -> None:
    client = _sync_client()
    name = os.getenv("QDRANT_COLLECTION_NAME")
    dim = int(os.getenv("EMBEDDING_DIMENSION", "1536"))

    collections = client.get_collections().collections
    names = [c.name for c in collections]

    if name not in names:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        client.create_payload_index(
            collection_name=name,
            field_name="metadata.patch_version",
            field_schema=FloatIndexParams(type=FloatIndexType.FLOAT, is_principal=True),
        )


async def ensure_collection() -> None:
    """Create Qdrant collection and payload index if missing."""
    await asyncio.to_thread(_ensure_collection_sync)
