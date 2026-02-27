"""Qdrant vector store client for upserting and searching patch-note embeddings."""

import os
import re
import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Range,
    Filter,
    MatchText,
    PointStruct,
    FloatIndexParams,
    FloatIndexType,
    VectorParams
)

from app.internal.services.llm import DeterminedPatchVersions

NAMESPACE = uuid.UUID(os.getenv("APP_KEY"))
client = AsyncQdrantClient(
    host=os.getenv("QDRANT_HOST"),
    port=int(os.getenv("QDRANT_PORT"))
)


async def ensure_collection() -> None:
    """Create collection if it doesn't exist."""
    collections = (await client.get_collections()).collections
    collection_names = [c.name for c in collections]

    if os.getenv("QDRANT_COLLECTION_NAME") not in collection_names:
        await client.create_collection(
            collection_name=os.getenv("QDRANT_COLLECTION_NAME"),
            vectors_config=VectorParams(
                size=int(os.getenv("EMBEDDING_DIMENSION")),
                distance=Distance.COSINE
            )
        )

        await client.create_payload_index(
            collection_name=os.getenv("QDRANT_COLLECTION_NAME"),
            field_name="patch_version",
            field_schema=FloatIndexParams(
                type=FloatIndexType.FLOAT,
                is_principal=True
            )
        )


def normalize(text: str) -> str:
    """Collapse whitespace in text and strip leading/trailing spaces."""
    text = re.sub(r"\s+", " ", text).strip()
    return text


def point_id(patch_version: str, source: str, chunk_index: int, chunk_text: str) -> str:
    """Generate a deterministic UUID for a chunk based on its content and position."""
    raw = f"{patch_version}|{source}|{chunk_index}|{normalize(chunk_text)}"
    return str(uuid.uuid5(NAMESPACE, raw))


async def upsert_vectors(
    texts: list[str],
    embeddings: list[list[float]],
    metadata: list[dict]
) -> None:
    """Insert vectors with metadata into QDrant."""
    points = [PointStruct(
        id=point_id(**meta, chunk_text=text),
        vector=embedding,
        payload={"text": text, **meta}
    ) for text, embedding, meta in zip(texts, embeddings, metadata)]

    await client.upsert(
        collection_name=os.getenv("QDRANT_COLLECTION_NAME"),
        points=points
    )


async def search_similar(
    query_embedding: list[float],
    patch_versions: DeterminedPatchVersions,
    top_k: int = None,
    keywords: list[str] | None = None,
) -> list[dict]:
    """Search for similar vectors and return results with text and metadata.

    Parameters
    ----------
    query_embedding:
        Dense vector produced by the embedding model.
    patch_versions:
        Version range filter (gte / lte).
    top_k:
        Maximum number of results to return.
    keywords:
        Optional list of words that *must* appear in the chunk text.
        When provided, Qdrant's full-text ``MatchText`` filter is applied so
        that only chunks containing at least one keyword are considered.
        This is the primary fix for champion-specific queries: passing
        ``["Malphite"]`` guarantees every returned chunk mentions Malphite,
        regardless of cosine similarity.
    """
    if top_k is None:
        top_k = int(os.getenv("TOP_K"))

    def _to_float(value: float | str, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    version_condition = FieldCondition(
        key="patch_version",
        range=Range(
            gte=_to_float(patch_versions.gte, 0.0),
            lte=_to_float(patch_versions.lte, 99.99),
        ),
    )

    if keywords:
        # should conditions act as OR — any keyword match is sufficient
        keyword_conditions = [
            FieldCondition(key="text", match=MatchText(text=kw))
            for kw in keywords
        ]
        query_filter = Filter(
            must=[version_condition],
            should=keyword_conditions,
        )
    else:
        query_filter = Filter(must=[version_condition])

    results = await client.query_points(
        collection_name=os.getenv("QDRANT_COLLECTION_NAME"),
        query=query_embedding,
        limit=top_k,
        query_filter=query_filter,
    )

    return [
        {
            "text": hit.payload.get("text", ""),
            "score": hit.score,
            "source": hit.payload.get("source", ""),
            "patch_version": hit.payload.get("patch_version", ""),
        }
        for hit in results.points
    ]
