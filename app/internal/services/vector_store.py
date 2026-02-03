import hashlib
import os
import re
import uuid

from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct
)

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


def normalize(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text


def point_id(patch_version: str, source: str, chunk_index: int, chunk_text: str) -> str:
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
