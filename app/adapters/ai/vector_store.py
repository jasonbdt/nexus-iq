"""Qdrant vector store client for upserting and searching patch-note embeddings."""

import re
import uuid

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

from .llm import DeterminedPatchVersions

class VectorStore:
    """Qdrant access with application-scoped client ownership."""

    def __init__(self, client, collection, dimension, namespace, top_k=5):
        self.client = client
        self.collection = collection
        self.dimension = dimension
        self.namespace = uuid.UUID(namespace)
        self.top_k = top_k

    async def ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        collections = (await self.client.get_collections()).collections
        collection_names = [c.name for c in collections]

        if self.collection not in collection_names:
            await self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=self.dimension,
                    distance=Distance.COSINE
                )
            )

            await self.client.create_payload_index(
                collection_name=self.collection,
                field_name="patch_version",
                field_schema=FloatIndexParams(
                    type=FloatIndexType.FLOAT,
                    is_principal=True
                )
            )


    def normalize(self, text: str) -> str:
        """Collapse whitespace in text and strip leading/trailing spaces."""
        text = re.sub(r"\s+", " ", text).strip()
        return text


    def point_id(self, patch_version: str, source: str, chunk_index: int, chunk_text: str) -> str:
        """Generate a deterministic UUID for a chunk based on its content and position."""
        raw = f"{patch_version}|{source}|{chunk_index}|{self.normalize(chunk_text)}"
        return str(uuid.uuid5(self.namespace, raw))


    async def upsert_vectors(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadata: list[dict]
    ) -> None:
        """Insert vectors with metadata into QDrant."""
        points = [PointStruct(
            id=self.point_id(**meta, chunk_text=text),
            vector=embedding,
            payload={"text": text, **meta}
        ) for text, embedding, meta in zip(texts, embeddings, metadata)]

        await self.client.upsert(
            collection_name=self.collection,
            points=points
        )


    async def search_similar(
        self,
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
            top_k = self.top_k

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

        results = await self.client.query_points(
            collection_name=self.collection,
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
