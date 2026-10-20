"""Application ports implemented with the existing AI and vector SDKs."""
import asyncio

from . import llm
from .. import patch_notes


class AIGateway:
    """Share one explicitly owned SDK client across language and embedding operations."""

    def __init__(self, client, embedding_model):
        self.client = client
        self.embedding_model = embedding_model

    def versions(self, question):
        """Return primitive version bounds rather than SDK schema objects."""
        result = llm.determine_patch_versions(question, client=self.client)
        return result.gte, result.lte

    def keywords(self, question):
        """Extract entities with the original prompt."""
        return llm.extract_keywords(question, client=self.client)

    async def embed(self, text):
        """Avoid blocking the event loop with the existing synchronous SDK."""
        return (await asyncio.to_thread(self.embed_many, [text]))[0]

    def embed_many(self, texts):
        """Embed a batch with the configured original model."""
        response = self.client.embeddings.create(model=self.embedding_model, input=texts)
        return [item.embedding for item in response.data]

    def answer(self, question, context):
        """Generate a complete response with the existing prompt and model."""
        return llm.generate_response(question, context, client=self.client)

    def stream(self, question, context, history):
        """Yield SDK deltas, closing the SDK stream when the iterator closes."""
        yield from llm.stream_response(question, context, history, client=self.client)


class VectorGateway:
    """Keep Pydantic Qdrant filters inside the adapter."""

    def __init__(self, store):
        self.store = store

    async def search(self, embedding, versions, keywords, top_k):
        """Delegate search with the original version and keyword filters."""
        bounds = llm.DeterminedPatchVersions(gte=versions[0], lte=versions[1])
        return await self.store.search_similar(embedding, bounds, top_k, keywords or None)

    async def upsert(self, texts, vectors, metadata):
        """Delegate deterministic vector upserts."""
        await self.store.upsert_vectors(texts, vectors, metadata)


class PatchGateway:
    """Patch scraping with an explicitly owned HTTP session."""

    def __init__(self, session):
        self.session = session

    async def list(self):
        """List patch articles."""
        return await patch_notes.list_available_patches(self.session)

    async def chunks(self, version):
        """Extract article chunks."""
        return await patch_notes.parse_patch_notes(version, self.session)
