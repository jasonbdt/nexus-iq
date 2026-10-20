"""Patch ingestion and retrieval orchestration independent of SDKs."""
from dataclasses import dataclass

from app.domain.policies import resolved_question
from .ports import AI, Vectors, PatchNotes


@dataclass
class Retrieval:
    """Shared retrieval flow for stateless questions and coaching conversations."""

    ai: AI
    vectors: Vectors
    patches: PatchNotes

    async def context(self, question: str, top_k: int = 15,
                      history: list[dict[str, str]] | None = None) -> str:
        """Preserve context formatting, keyword filtering and history resolution."""
        resolved = resolved_question(question, history or [])
        versions = self.ai.versions(resolved)
        keywords = self.ai.keywords(resolved)
        embedding = await self.ai.embed(question)
        results = await self.vectors.search(embedding, versions, keywords, top_k)
        return '\n\n---\n\n'.join(
            f"[Patch {result['patch_version']}]\n{result['text']}" for result in results
        )

    async def ingest(self, version: str) -> tuple[dict, int]:
        """Preserve ingestion response shapes, validation order and deterministic IDs."""
        chunks = await self.patches.chunks(version)
        if not chunks:
            return {'message': f'No text extracted from patch notes for {version}'}, 400
        try:
            numeric_version = float(version)
        except ValueError:
            return {'message': f'Invalid patch version: {version}'}, 422
        texts = [chunk['text'] for chunk in chunks]
        metadata = [{'source': chunk['source'], 'patch_version': numeric_version,
                     'chunk_index': chunk['chunk_index']} for chunk in chunks]
        await self.vectors.upsert(texts, self.ai.embed_many(texts), metadata)
        return {'message': f'Patch Notes for v{version} ingested successfully',
                'count': len(chunks)}, 200
